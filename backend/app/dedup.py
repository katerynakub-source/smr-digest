"""Feedly-style duplicate detection: the same story from several outlets collapses into one card.

Two signals:
  1. Canonical URL match (e.g. WNA cards that link straight to a WNN article).
  2. Title similarity within a +/-3 day window: token-set Jaccard on normalised, stop-word-free
     titles. For Russian items the AI-translated title (title_en) is compared against English
     titles' translations too, so cross-language duplicates are caught once AI is enabled.
"""
import re
from datetime import datetime, timedelta
from urllib.parse import urlparse

STOP = set("""a an the of for to in on at by and or with from as is are be its into new over after
plans plan says said will first nuclear power plant project и в во на по с со к для из о об от до
что как это при за а также новый новая первый первая""".split())

THRESHOLD = 0.55
WINDOW = timedelta(days=3)


def canon_url(url: str) -> str:
    p = urlparse(url.lower())
    host = p.netloc.removeprefix("www.")
    return f"{host}{p.path.rstrip('/')}"


def _stem(w: str) -> str:
    # crude stemming so "reactors"/"reactor", "реакторов"/"реактор" match
    return w[:6] if len(w) > 6 else w.rstrip("s")


def tokens(title: str) -> set[str]:
    words = re.findall(r"[\w\-]+", (title or "").lower())
    return {_stem(w) for w in words if w not in STOP and len(w) > 2}


def similarity(a: str, b: str) -> float:
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def find_cluster(conn, url: str, title: str, title_en: str | None, published_at: str,
                 exclude_id: int | None = None) -> int | None:
    """Return the canonical article id this item duplicates, or None."""
    cu = canon_url(url)
    pub = datetime.fromisoformat(published_at)
    lo, hi = (pub - WINDOW).isoformat(), (pub + WINDOW).isoformat()
    rows = conn.execute(
        "SELECT id, url, title, title_en, cluster_id FROM articles "
        "WHERE published_at BETWEEN ? AND ? AND kind='news'", (lo, hi)).fetchall()
    best_id, best = None, 0.0
    for r in rows:
        if exclude_id is not None and exclude_id in (r["id"], r["cluster_id"]):
            continue
        if canon_url(r["url"]) == cu:
            return r["cluster_id"] or r["id"]
        s = max(similarity(title, r["title"]),
                similarity(title_en or "", r["title_en"] or "") if title_en and r["title_en"] else 0,
                similarity(title, r["title_en"] or "") if r["title_en"] else 0,
                similarity(title_en or "", r["title"]) if title_en else 0)
        if s > best:
            best, best_id = s, (r["cluster_id"] or r["id"])
    return best_id if best >= THRESHOLD else None
