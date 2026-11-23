"""Serverless mode: collect news once and write static JSON for the web app.

Run on a schedule (GitHub Actions) — no always-on server needed:

    python -m app.export --previous ../site-data/articles.json --out ../site-data

1. Loads the previous articles.json (if any) so history survives between runs.
2. Fetches all sources, tags, dedupes, pulls full text and builds digests
   (AI if OPENAI_API_KEY is set, otherwise extractive "key facts").
3. Collects nuclear tenders (EU TED, UK Contracts Finder).
4. Writes articles.json, catalog.json, tenders.json and meta.json into --out.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Work in a throwaway database; the JSON files are the persistent store.
_tmp = Path(tempfile.mkdtemp()) / "export.db"
os.environ["SMR_DB"] = str(_tmp)

from . import ai, annotate, catalog, db, ingest, tagger, tenders, translate  # noqa: E402
from .main import CARD_COLS, _card, _related_news  # noqa: E402
from .sources import BUILTIN_SOURCES, discover  # noqa: E402

KEEP_DAYS = int(os.getenv("KEEP_DAYS", "1100"))
KEEP_MAX = int(os.getenv("KEEP_MAX", "800"))
# Full article text is NOT published by default: the site is public, and republishing outlets'
# articles would infringe their copyright. Cards keep headline, excerpt, digest and the link.
CONTENT_MAX = int(os.getenv("CONTENT_MAX", "0"))
EXTRA_SOURCES = Path(__file__).resolve().parent.parent / "extra_sources.json"


def setup() -> None:
    db.init()
    with db.session() as c:
        for s in BUILTIN_SOURCES:
            c.execute("INSERT OR IGNORE INTO sources(slug,name,url,homepage,kind,parser,lang,builtin) "
                      "VALUES (:slug,:name,:url,:homepage,:kind,:parser,:lang,1)", s)
        catalog.seed(c)


async def add_extra_sources() -> None:
    """User-defined feeds/sites live in extra_sources.json: [{"url": "...", "name": "optional"}]."""
    if not EXTRA_SOURCES.exists():
        return
    for i, entry in enumerate(json.loads(EXTRA_SOURCES.read_text())):
        try:
            info = await discover(entry["url"])
        except Exception as e:  # noqa: BLE001
            print(f"extra source skipped {entry['url']}: {e}", file=sys.stderr)
            continue
        with db.session() as c:
            c.execute("INSERT OR IGNORE INTO sources(slug,name,url,homepage,kind,parser,lang) VALUES (?,?,?,?,?,?,?)",
                      (f"extra-{i}", entry.get("name") or info["name"], info["url"], entry["url"],
                       info["kind"], info["parser"], info["lang"]))


def import_previous(path: Path) -> int:
    if not path.exists():
        return 0
    data = json.loads(path.read_text())
    n = 0
    with db.session() as c:
        slugs = {r["slug"]: r["id"] for r in c.execute("SELECT id, slug FROM sources")}
        for a in data.get("articles", []):
            sid = slugs.get(a["source"]["slug"])
            if sid is None:
                continue
            c.execute(
                "INSERT OR IGNORE INTO articles(id,source_id,kind,url,title,excerpt,content,image,lang,published_at,"
                "fetched_at,tags,title_en,bullets,ai_model,cluster_id,bullets_en,excerpt_en) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (a["id"], sid, a.get("kind", "news"), a["url"], a["title"], a.get("excerpt"), a.get("content"),
                 a.get("image"), a["lang"], a["published_at"], a.get("fetched_at") or a["published_at"],
                 json.dumps(sorted((set(a.get("tags", [])) - {"supply"}) | set(tagger.classify(  # re-tag history; supply recomputed
                     a["title"], a.get("title_en") or "", a.get("excerpt") or "", " ".join(a.get("bullets") or []))))),
                 a.get("title_en"),
                 json.dumps(a["bullets"], ensure_ascii=False) if a.get("bullets") else None,
                 a.get("ai_model"), a.get("cluster_id"),
                 json.dumps(a["bullets_en"], ensure_ascii=False) if a.get("bullets_en") else None, a.get("excerpt_en")))
            n += 1
        # duplicates arrive inside also_in; keep their source links working
        for a in data.get("duplicates", []):
            sid = slugs.get(a["source_slug"])
            if sid is not None:
                c.execute("INSERT OR IGNORE INTO articles(id,source_id,url,title,lang,published_at,fetched_at,cluster_id) "
                          "VALUES (?,?,?,?,?,?,?,?)", (a["id"], sid, a["url"], a["title"], a["lang"],
                                                       a["published_at"], a["published_at"], a["cluster_id"]))
    return n


def prune() -> None:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=KEEP_DAYS)).isoformat()
    with db.session() as c:
        c.execute("DELETE FROM articles WHERE published_at < ?", (cutoff,))
        c.execute("DELETE FROM articles WHERE id NOT IN (SELECT id FROM articles ORDER BY published_at DESC LIMIT ?)",
                  (KEEP_MAX,))
        # a duplicate whose canonical item was pruned becomes canonical itself
        c.execute("UPDATE articles SET cluster_id=NULL WHERE cluster_id IS NOT NULL "
                  "AND cluster_id NOT IN (SELECT id FROM articles)")


def export(out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    with db.session() as c:
        rows = c.execute(f"SELECT {CARD_COLS}, a.content, a.fetched_at FROM articles a JOIN sources s "
                         "ON s.id=a.source_id WHERE a.cluster_id IS NULL AND COALESCE(a.relevance, 0) >= ? "
                         "ORDER BY a.published_at DESC", (annotate.MIN_SCORE,)).fetchall()
        articles = []
        for r in rows:
            card = _card(r, c)
            card["content"] = (card.get("content") or "")[:CONTENT_MAX] or None
            articles.append(card)
        dups = [dict(r) for r in c.execute(
            "SELECT a.id, a.url, a.title, a.lang, a.published_at, a.cluster_id, s.slug AS source_slug "
            "FROM articles a JOIN sources s ON s.id=a.source_id WHERE a.cluster_id IS NOT NULL")]
        sources = [dict(r) for r in c.execute(
            "SELECT s.slug, s.name, s.url, s.homepage, s.kind, s.lang, s.builtin, s.enabled, s.last_fetch, s.last_error, "
            "(SELECT COUNT(*) FROM articles a WHERE a.source_id=s.id) AS articles FROM sources s ORDER BY builtin DESC, name")]

        companies = []
        for co in c.execute("SELECT * FROM companies ORDER BY name"):
            co = db.row_to_dict(co)
            reactors = [db.row_to_dict(r) for r in c.execute(
                "SELECT slug, keywords FROM reactors WHERE company_id=?", (co["id"],))]
            kw = list(co["keywords"]) + [k for r in reactors for k in r["keywords"]]
            co["reactor_slugs"] = [r["slug"] for r in reactors]
            co["news_ids"] = [a["id"] for a in _related_news(c, kw)]
            companies.append(co)
        reactors = []
        for r in c.execute("SELECT r.*, c.name AS company_name, c.slug AS company_slug, c.country FROM reactors r "
                           "JOIN companies c ON c.id=r.company_id ORDER BY r.power_mwe IS NULL, r.power_mwe DESC"):
            r = db.row_to_dict(r)
            r["news_ids"] = [a["id"] for a in _related_news(c, r["keywords"])]
            reactors.append(r)

    meta = {"generated_at": ingest.now_iso(), "ai": ai.enabled(), "model": ai.MODEL if ai.enabled() else "extractive",
            "translator": "argos ru-en (offline)" if translate.enabled() else None,
            "articles": len(articles), "categories": tagger.CATEGORIES, "sources": sources}
    (out / "articles.json").write_text(json.dumps({"articles": articles, "duplicates": dups}, ensure_ascii=False))
    (out / "catalog.json").write_text(json.dumps({"stages": catalog.STAGES, "sizes": catalog.SIZES, "companies": companies,
                                                  "reactors": reactors}, ensure_ascii=False))
    (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    return meta


async def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--previous", type=Path, help="previous articles.json to carry history over")
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()

    setup()
    await add_extra_sources()
    kept = import_previous(args.previous) if args.previous else 0
    result = await ingest.refresh_all()
    prune()
    meta = export(args.out)
    t = await tenders.fetch_all()
    if t["tenders"] or not (args.out / "tenders.json").exists():  # keep last good list if both registries failed
        (args.out / "tenders.json").write_text(json.dumps(t, ensure_ascii=False))
    print(f"previous={kept} new={result.get('new')} digested={result.get('digested')} "
          f"published={meta['articles']} ai={meta['model']} tenders={len(t['tenders'])} errors={t['errors']}")


if __name__ == "__main__":
    asyncio.run(main())
