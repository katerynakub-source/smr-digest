"""Fetch → normalise → tag → dedupe → store → AI digest → push alerts."""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone

import httpx

from . import ai, db, dedup, tagger
from .sources import HTTP, PARSERS, fetch_article_text

log = logging.getLogger("ingest")
AI_PER_RUN = int(os.getenv("AI_PER_RUN", "40"))  # cap paid API calls per refresh
EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"

_lock = asyncio.Lock()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


async def refresh_source(client: httpx.AsyncClient, src: dict) -> list[int]:
    parser = PARSERS[src["parser"]]
    new_ids = []
    try:
        items = await parser(client, src)
    except Exception as e:  # noqa: BLE001 — one broken site must not stop the others
        log.warning("source %s failed: %s", src["slug"], e)
        with db.session() as c:
            c.execute("UPDATE sources SET last_fetch=?, last_error=? WHERE id=?", (now_iso(), str(e)[:300], src["id"]))
        return []
    with db.session() as c:
        for it in items:
            if c.execute("SELECT 1 FROM articles WHERE url=?", (it.url,)).fetchone():
                continue
            pub = it.published_at.isoformat(timespec="seconds")
            tags = tagger.classify(it.title, it.excerpt, it.content[:3000])
            cluster = dedup.find_cluster(c, it.url, it.title, it.title if it.lang == "en" else None, pub)
            cur = c.execute(
                "INSERT INTO articles(source_id,url,title,excerpt,content,image,lang,published_at,fetched_at,tags,"
                "title_en,cluster_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (src["id"], it.url, it.title, it.excerpt, it.content or None, it.image, it.lang, pub, now_iso(),
                 json.dumps(tags), it.title if it.lang == "en" else None, cluster))
            new_ids.append(cur.lastrowid)
        c.execute("UPDATE sources SET last_fetch=?, last_error=NULL WHERE id=?", (now_iso(), src["id"]))
    return new_ids


async def ensure_content(article_id: int) -> dict:
    """Load full text for an article if the feed only gave a title/teaser."""
    with db.session() as c:
        a = db.row_to_dict(c.execute("SELECT * FROM articles WHERE id=?", (article_id,)).fetchone())
    if a and not a["content"] and a["kind"] == "news":
        try:
            text, image = await fetch_article_text(a["url"])
        except Exception as e:  # noqa: BLE001
            log.info("content fetch failed %s: %s", a["url"], e)
            text, image = "", None
        if text:
            tags = sorted(set(a["tags"]) | set(tagger.classify(a["title"], text[:3000])))
            with db.session() as c:
                c.execute("UPDATE articles SET content=?, image=COALESCE(image, ?), tags=? WHERE id=?",
                          (text, image, json.dumps(tags), article_id))
            a.update(content=text, image=a["image"] or image, tags=tags)
    return a


async def summarize(article_id: int, force: bool = False) -> dict:
    a = await ensure_content(article_id)
    if a is None:
        raise KeyError(article_id)
    if a["bullets"] and not force and (a["ai_model"] != "extractive" or not ai.enabled()):
        return a
    res = await ai.digest(a["title"], a["content"] or a["excerpt"] or "", a["lang"])
    with db.session() as c:
        c.execute("UPDATE articles SET title_en=COALESCE(?, title_en), bullets=?, ai_model=? WHERE id=?",
                  (res["title_en"], json.dumps(res["bullets"], ensure_ascii=False), res["ai_model"], article_id))
        # with an English title available, re-check cross-language duplicates
        if res["title_en"] and not a["cluster_id"]:
            cl = dedup.find_cluster(c, a["url"], a["title"], res["title_en"], a["published_at"],
                                    exclude_id=article_id)
            if cl:
                c.execute("UPDATE articles SET cluster_id=? WHERE id=?", (cl, article_id))
    a.update(title_en=res["title_en"] or a["title_en"], bullets=res["bullets"], ai_model=res["ai_model"])
    return a


async def send_alerts(article_ids: list[int]) -> int:
    if not article_ids:
        return 0
    with db.session() as c:
        alerts = c.execute("SELECT token, keyword FROM alerts").fetchall()
        if not alerts:
            return 0
        q = ",".join("?" * len(article_ids))
        arts = c.execute(f"SELECT id, title, title_en, excerpt, content FROM articles WHERE id IN ({q}) "
                         "AND cluster_id IS NULL", article_ids).fetchall()
        messages, sent = [], []
        for a in arts:
            blob = " ".join(filter(None, [a["title"], a["title_en"], a["excerpt"], (a["content"] or "")[:4000]])).lower()
            for al in alerts:
                if al["keyword"].lower() in blob and not c.execute(
                        "SELECT 1 FROM sent_pushes WHERE token=? AND article_id=?", (al["token"], a["id"])).fetchone():
                    messages.append({"to": al["token"], "title": f"🔔 {al['keyword']}",
                                     "body": a["title_en"] or a["title"], "data": {"articleId": a["id"]}})
                    sent.append((al["token"], a["id"]))
        c.executemany("INSERT OR IGNORE INTO sent_pushes VALUES (?,?)", sent)
    real = [m for m in messages if m["to"].startswith("ExponentPushToken")]
    if real:
        async with httpx.AsyncClient(timeout=20) as client:
            for i in range(0, len(real), 100):
                try:
                    await client.post(EXPO_PUSH_URL, json=real[i:i + 100])
                except httpx.HTTPError as e:
                    log.warning("push failed: %s", e)
    return len(messages)


async def refresh_all() -> dict:
    if _lock.locked():
        return {"status": "already running"}
    async with _lock:
        with db.session() as c:
            sources = [dict(r) for r in c.execute("SELECT * FROM sources WHERE enabled=1")]
        async with httpx.AsyncClient(**HTTP) as client:
            results = await asyncio.gather(*(refresh_source(client, s) for s in sources))
        new_ids = [i for r in results for i in r]
        # AI digests for the newest canonical items (bounded per run)
        with db.session() as c:
            todo = [r[0] for r in c.execute(
                "SELECT id FROM articles WHERE bullets IS NULL AND cluster_id IS NULL "
                "ORDER BY published_at DESC LIMIT ?", (AI_PER_RUN,))]
        sem = asyncio.Semaphore(4)

        async def run(i):
            async with sem:
                try:
                    await summarize(i)
                except Exception as e:  # noqa: BLE001
                    log.warning("digest %s failed: %s", i, e)

        await asyncio.gather(*(run(i) for i in todo))
        pushed = await send_alerts(new_ids)
        return {"status": "ok", "new": len(new_ids), "digested": len(todo), "alerts": pushed}


async def scheduler(interval_min: int) -> None:
    while True:
        try:
            log.info("refresh: %s", await refresh_all())
        except Exception:  # noqa: BLE001
            log.exception("refresh crashed")
        await asyncio.sleep(interval_min * 60)
