"""Nuclear Digest API."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from hashlib import sha1

import httpx
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl

from . import ai, annotate, catalog, db, ingest, tagger, tenders
from .documents import pdf_bytes_to_text, pdf_title
from .sources import BUILTIN_SOURCES, HTTP, discover

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
REFRESH_MIN = int(os.getenv("REFRESH_MINUTES", "30"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init()
    with db.session() as c:
        for s in BUILTIN_SOURCES:
            c.execute("INSERT OR IGNORE INTO sources(slug,name,url,homepage,kind,parser,lang,builtin) "
                      "VALUES (:slug,:name,:url,:homepage,:kind,:parser,:lang,1)", s)
        c.execute("INSERT OR IGNORE INTO sources(slug,name,url,homepage,kind,parser,lang,builtin,enabled) "
                  "VALUES ('reports','My reports','local://reports',NULL,'html','generic','en',1,0)")
        catalog.seed(c)
    task = asyncio.create_task(ingest.scheduler(REFRESH_MIN)) if REFRESH_MIN > 0 else None
    yield
    if task:
        task.cancel()


app = FastAPI(title="Nuclear Digest API", version="1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

CARD_COLS = """a.id, a.kind, a.url, a.title, a.title_en, a.excerpt, a.image, a.lang, a.published_at, a.tags,
               a.bullets, a.ai_model, a.cluster_id, a.sections, a.relevance, a.bullets_en, a.excerpt_en, s.slug AS source_slug, s.name AS source_name"""


def _card(row, conn) -> dict:
    d = db.row_to_dict(row)
    d["source"] = {"slug": d.pop("source_slug"), "name": d.pop("source_name")}
    dups = conn.execute(
        "SELECT a.id, a.url, s.name FROM articles a JOIN sources s ON s.id=a.source_id WHERE a.cluster_id=? "
        "ORDER BY a.published_at", (d["id"],)).fetchall()
    d["also_in"] = [{"id": r["id"], "url": r["url"], "source": r["name"]} for r in dups]
    return d


def fts_query(q: str) -> str:
    terms = re.findall(r"[\w\-]+", q)
    return " ".join(f'"{t}"*' for t in terms) if terms else '""'


def keyword_query(keywords: list[str]) -> str:
    return " OR ".join('"' + k.replace('"', "") + '"' for k in keywords)


# ---------- meta ----------

@app.get("/api/health")
def health():
    return {"ok": True, "ai": ai.enabled(), "model": ai.MODEL if ai.enabled() else "extractive"}


@app.get("/api/categories")
def categories():
    return tagger.CATEGORIES


# ---------- feed ----------

@app.get("/api/articles")
def articles(category: str | None = None, source: str | None = None, kind: str = "news",
             limit: int = Query(30, le=100), before: str | None = None, include_duplicates: bool = False,
             section: str | None = None, lang: str | None = None):
    where, args = ["a.kind = ?"], [kind]
    if kind == "news":
        where.append(f"COALESCE(a.relevance, 0) >= {annotate.MIN_SCORE}")
    if section:
        where.append("EXISTS (SELECT 1 FROM json_each(a.sections) WHERE value = ?)")
        args.append(section)
        where.append("(a.lang = 'en' OR a.bullets_en IS NOT NULL)")  # English tabs need English text
    if lang:
        where.append("a.lang = ?")
        args.append(lang)
    if not include_duplicates:
        where.append("a.cluster_id IS NULL")
    if category:
        where.append("EXISTS (SELECT 1 FROM json_each(a.tags) WHERE value = ?)")
        args.append(category)
    if source:
        where.append("s.slug = ?")
        args.append(source)
    if before:
        where.append("a.published_at < ?")
        args.append(before)
    with db.session() as c:
        rows = c.execute(f"SELECT {CARD_COLS} FROM articles a JOIN sources s ON s.id=a.source_id "
                         f"WHERE {' AND '.join(where)} ORDER BY a.published_at DESC LIMIT ?", (*args, limit)).fetchall()
        return [_card(r, c) for r in rows]


@app.get("/api/articles/{article_id}")
async def article(article_id: int):
    a = await ingest.ensure_content(article_id)
    if not a:
        raise HTTPException(404)
    with db.session() as c:
        row = c.execute(f"SELECT {CARD_COLS}, a.content FROM articles a JOIN sources s ON s.id=a.source_id "
                        "WHERE a.id=?", (article_id,)).fetchone()
        return _card(row, c)


@app.post("/api/articles/{article_id}/digest")
async def article_digest(article_id: int, force: bool = False):
    try:
        await ingest.summarize(article_id, force=force)
    except KeyError:
        raise HTTPException(404)
    return await article(article_id)


class Question(BaseModel):
    question: str


@app.post("/api/articles/{article_id}/ask")
async def article_ask(article_id: int, q: Question):
    a = await ingest.ensure_content(article_id)
    if not a:
        raise HTTPException(404)
    text = a["content"] or a["excerpt"] or ""
    if not text:
        raise HTTPException(422, "This item has no text to analyse")
    return await ai.ask(a["title"], text, q.question)


@app.get("/api/search")
def search(q: str, limit: int = Query(40, le=100), kind: str | None = None):
    with db.session() as c:
        sql = (f"SELECT {CARD_COLS}, snippet(articles_fts, -1, '«', '»', '…', 14) AS snippet "
               "FROM articles_fts f JOIN articles a ON a.id=f.rowid JOIN sources s ON s.id=a.source_id "
               "WHERE articles_fts MATCH ?" + (" AND a.kind=?" if kind else "") +
               " ORDER BY bm25(articles_fts, 8, 8, 3, 1, 3) LIMIT ?")
        rows = c.execute(sql, (fts_query(q), *([kind] if kind else []), limit)).fetchall()
        return [_card(r, c) for r in rows]


@app.post("/api/refresh")
async def refresh():
    return await ingest.refresh_all()


# ---------- sources ----------

class SourceIn(BaseModel):
    url: HttpUrl
    name: str | None = None


@app.get("/api/sources")
def list_sources():
    with db.session() as c:
        rows = c.execute("SELECT s.*, (SELECT COUNT(*) FROM articles a WHERE a.source_id=s.id) AS articles "
                         "FROM sources s WHERE s.slug != 'reports' ORDER BY builtin DESC, name").fetchall()
        return [dict(r) for r in rows]


@app.post("/api/sources", status_code=201)
async def add_source(body: SourceIn):
    try:
        info = await discover(str(body.url))
    except httpx.HTTPError as e:
        raise HTTPException(422, f"Could not open the URL: {e}")
    slug = "u-" + sha1(info["url"].encode()).hexdigest()[:10]
    with db.session() as c:
        if c.execute("SELECT 1 FROM sources WHERE url=?", (info["url"],)).fetchone():
            raise HTTPException(409, "Source already added")
        c.execute("INSERT INTO sources(slug,name,url,homepage,kind,parser,lang) VALUES (?,?,?,?,?,?,?)",
                  (slug, body.name or info["name"], info["url"], str(body.url), info["kind"], info["parser"],
                   info["lang"]))
        src = dict(c.execute("SELECT * FROM sources WHERE slug=?", (slug,)).fetchone())
    async with httpx.AsyncClient(**HTTP) as client:
        new = await ingest.refresh_source(client, src)
    return {**src, "articles": len(new)}


class SourcePatch(BaseModel):
    enabled: bool


@app.patch("/api/sources/{slug}")
def toggle_source(slug: str, body: SourcePatch):
    with db.session() as c:
        c.execute("UPDATE sources SET enabled=? WHERE slug=?", (int(body.enabled), slug))
    return {"slug": slug, "enabled": body.enabled}


@app.delete("/api/sources/{slug}", status_code=204)
def delete_source(slug: str):
    with db.session() as c:
        row = c.execute("SELECT builtin FROM sources WHERE slug=?", (slug,)).fetchone()
        if not row:
            raise HTTPException(404)
        if row["builtin"]:
            raise HTTPException(400, "Built-in sources can only be disabled")
        c.execute("DELETE FROM sources WHERE slug=?", (slug,))


# ---------- reports (PDF) ----------

class ReportUrl(BaseModel):
    url: HttpUrl


async def _store_report(data: bytes, url: str, fallback_title: str) -> dict:
    text = pdf_bytes_to_text(data)
    if not text:
        raise HTTPException(422, "Could not extract text from the PDF (it may be a scan)")
    title = pdf_title(data, fallback_title)
    lang = "ru" if len(re.findall(r"[а-яё]", text[:3000], re.I)) > 300 else "en"
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with db.session() as c:
        sid = c.execute("SELECT id FROM sources WHERE slug='reports'").fetchone()[0]
        existing = c.execute("SELECT id FROM articles WHERE url=?", (url,)).fetchone()
        if existing:
            return {"id": existing[0]}
        cur = c.execute(
            "INSERT INTO articles(source_id,kind,url,title,excerpt,content,lang,published_at,fetched_at,tags) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (sid, "report", url, title, text[:400], text, lang, now, now,
             json.dumps(tagger.classify(title, text[:6000]))))
        rid = cur.lastrowid
    await ingest.summarize(rid)
    return {"id": rid}


@app.post("/api/reports/upload", status_code=201)
async def upload_report(file: UploadFile = File(...)):
    data = await file.read()
    if not data.startswith(b"%PDF"):
        raise HTTPException(422, "A PDF file is expected")
    return await _store_report(data, f"upload://{sha1(data).hexdigest()}", file.filename or "Report")


@app.post("/api/reports/url", status_code=201)
async def report_from_url(body: ReportUrl):
    async with httpx.AsyncClient(**HTTP) as client:
        r = await client.get(str(body.url))
    if r.status_code >= 400 or not r.content.startswith(b"%PDF"):
        raise HTTPException(422, "The URL does not point to a PDF")
    return await _store_report(r.content, str(body.url), str(body.url).rsplit("/", 1)[-1])


# ---------- catalog ----------

def _related_news(c, keywords: list[str], limit: int = 20) -> list[dict]:
    if not keywords:
        return []
    rows = c.execute(f"SELECT {CARD_COLS} FROM articles_fts f JOIN articles a ON a.id=f.rowid "
                     "JOIN sources s ON s.id=a.source_id WHERE articles_fts MATCH ? AND a.cluster_id IS NULL "
                     "ORDER BY a.published_at DESC LIMIT ?", (keyword_query(keywords), limit)).fetchall()
    return [_card(r, c) for r in rows]


@app.get("/api/catalog/stages")
def stages():
    return catalog.STAGES


@app.get("/api/catalog/reactors")
def reactors(stage: str | None = None, reactor_type: str | None = None, q: str | None = None,
             size: str | None = None):
    sql = ("SELECT r.*, c.name AS company_name, c.slug AS company_slug, c.country FROM reactors r "
           "JOIN companies c ON c.id=r.company_id WHERE 1=1")
    args = []
    if stage:
        sql += " AND r.stage=?"
        args.append(stage)
    if size:
        sql += " AND r.size=?"
        args.append(size)
    if reactor_type:
        sql += " AND r.reactor_type=?"
        args.append(reactor_type)
    if q:
        sql += " AND (r.name LIKE ? OR c.name LIKE ? OR r.coolant LIKE ?)"
        args += [f"%{q}%"] * 3
    with db.session() as c:
        return [db.row_to_dict(r) for r in c.execute(sql + " ORDER BY r.power_mwe IS NULL, r.power_mwe DESC", args)]


@app.get("/api/catalog/reactors/{slug}")
def reactor(slug: str):
    with db.session() as c:
        r = db.row_to_dict(c.execute(
            "SELECT r.*, c.name AS company_name, c.slug AS company_slug, c.country, c.keywords AS company_keywords "
            "FROM reactors r JOIN companies c ON c.id=r.company_id WHERE r.slug=?", (slug,)).fetchone())
        if not r:
            raise HTTPException(404)
        r.pop("company_keywords", None)
        r["news"] = _related_news(c, r["keywords"])
        return r


@app.get("/api/catalog/companies")
def companies():
    with db.session() as c:
        rows = c.execute("SELECT c.*, (SELECT COUNT(*) FROM reactors r WHERE r.company_id=c.id) AS reactors "
                         "FROM companies c ORDER BY c.name").fetchall()
        return [db.row_to_dict(r) for r in rows]


@app.get("/api/catalog/companies/{slug}")
def company(slug: str):
    with db.session() as c:
        co = db.row_to_dict(c.execute("SELECT * FROM companies WHERE slug=?", (slug,)).fetchone())
        if not co:
            raise HTTPException(404)
        co["reactors"] = [db.row_to_dict(r) for r in c.execute(
            "SELECT * FROM reactors WHERE company_id=? ORDER BY power_mwe DESC", (co["id"],))]
        kw = list(co["keywords"]) + [k for r in co["reactors"] for k in r["keywords"]]
        co["news"] = _related_news(c, kw)
        return co


# ---------- push alerts ----------

class DeviceIn(BaseModel):
    token: str


class AlertIn(BaseModel):
    token: str
    keyword: str


@app.post("/api/devices", status_code=201)
def register_device(body: DeviceIn):
    with db.session() as c:
        c.execute("INSERT OR IGNORE INTO devices VALUES (?,?)",
                  (body.token, datetime.now(timezone.utc).isoformat(timespec="seconds")))
    return {"token": body.token}


@app.get("/api/alerts")
def list_alerts(token: str):
    with db.session() as c:
        return [r["keyword"] for r in c.execute("SELECT keyword FROM alerts WHERE token=? ORDER BY id", (token,))]


@app.post("/api/alerts", status_code=201)
def add_alert(body: AlertIn):
    kw = body.keyword.strip()
    if not kw:
        raise HTTPException(422, "Keyword is empty")
    register_device(DeviceIn(token=body.token))
    with db.session() as c:
        c.execute("INSERT OR IGNORE INTO alerts(token, keyword) VALUES (?,?)", (body.token, kw))
    return list_alerts(body.token)


@app.delete("/api/alerts")
def delete_alert(token: str, keyword: str):
    with db.session() as c:
        c.execute("DELETE FROM alerts WHERE token=? AND keyword=?", (token, keyword))
    return list_alerts(token)


# ---------- supply chain: tenders ----------

_tenders_cache: dict = {"at": 0.0, "data": None}


@app.get("/api/tenders")
async def list_tenders():
    import time
    if not _tenders_cache["data"] or time.time() - _tenders_cache["at"] > 3600:
        _tenders_cache.update(at=time.time(), data=await tenders.fetch_all())
    return _tenders_cache["data"]
