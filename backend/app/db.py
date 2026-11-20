"""SQLite storage with FTS5 full-text search."""
import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(os.getenv("SMR_DB", Path(__file__).resolve().parent.parent / "data" / "smr.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
    id          INTEGER PRIMARY KEY,
    slug        TEXT UNIQUE NOT NULL,
    name        TEXT NOT NULL,
    url         TEXT NOT NULL,          -- feed URL or page URL
    homepage    TEXT,
    kind        TEXT NOT NULL,          -- rss | html
    parser      TEXT NOT NULL,          -- rss | nauka | ec_smr | wna | generic
    lang        TEXT NOT NULL DEFAULT 'en',
    builtin     INTEGER NOT NULL DEFAULT 0,
    enabled     INTEGER NOT NULL DEFAULT 1,
    last_fetch  TEXT,
    last_error  TEXT
);

CREATE TABLE IF NOT EXISTS articles (
    id           INTEGER PRIMARY KEY,
    source_id    INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    kind         TEXT NOT NULL DEFAULT 'news',   -- news | report
    url          TEXT UNIQUE NOT NULL,
    title        TEXT NOT NULL,
    excerpt      TEXT,
    content      TEXT,                            -- plain text, paragraphs split by \n\n
    image        TEXT,
    lang         TEXT NOT NULL DEFAULT 'en',
    published_at TEXT NOT NULL,                   -- ISO 8601 UTC
    fetched_at   TEXT NOT NULL,
    tags         TEXT NOT NULL DEFAULT '[]',      -- JSON list of category slugs
    title_en     TEXT,
    bullets   TEXT,                            -- JSON list of strings
    ai_model     TEXT,
    cluster_id   INTEGER                          -- id of canonical article for duplicates
);
CREATE INDEX IF NOT EXISTS idx_articles_pub ON articles(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_articles_cluster ON articles(cluster_id);

CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts USING fts5(
    title, title_en, excerpt, content, bullets,
    content='articles', content_rowid='id', tokenize='unicode61 remove_diacritics 2'
);
CREATE TRIGGER IF NOT EXISTS articles_ai AFTER INSERT ON articles BEGIN
  INSERT INTO articles_fts(rowid, title, title_en, excerpt, content, bullets)
  VALUES (new.id, new.title, new.title_en, new.excerpt, new.content, new.bullets);
END;
CREATE TRIGGER IF NOT EXISTS articles_ad AFTER DELETE ON articles BEGIN
  INSERT INTO articles_fts(articles_fts, rowid, title, title_en, excerpt, content, bullets)
  VALUES ('delete', old.id, old.title, old.title_en, old.excerpt, old.content, old.bullets);
END;
CREATE TRIGGER IF NOT EXISTS articles_au AFTER UPDATE ON articles BEGIN
  INSERT INTO articles_fts(articles_fts, rowid, title, title_en, excerpt, content, bullets)
  VALUES ('delete', old.id, old.title, old.title_en, old.excerpt, old.content, old.bullets);
  INSERT INTO articles_fts(rowid, title, title_en, excerpt, content, bullets)
  VALUES (new.id, new.title, new.title_en, new.excerpt, new.content, new.bullets);
END;

CREATE TABLE IF NOT EXISTS companies (
    id          INTEGER PRIMARY KEY,
    slug        TEXT UNIQUE NOT NULL,
    name        TEXT NOT NULL,
    country     TEXT,
    founded     INTEGER,
    kind        TEXT,          -- госкорпорация | корпорация | стартап
    website     TEXT,
    description TEXT,
    keywords    TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS reactors (
    id            INTEGER PRIMARY KEY,
    slug          TEXT UNIQUE NOT NULL,
    company_id    INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    name          TEXT NOT NULL,
    reactor_type  TEXT,        -- PWR, BWR, SFR, LFR, HTGR, MSR, FHR...
    coolant       TEXT,
    power_mwe     REAL,
    power_mwt     REAL,
    stage         TEXT,        -- concept | design | licensing | construction | operation
    licensing     TEXT,        -- licensing status text
    sites         TEXT,
    description   TEXT,
    keywords      TEXT NOT NULL DEFAULT '[]',
    size          TEXT         -- large | smr | micro
);

CREATE TABLE IF NOT EXISTS devices (
    token      TEXT PRIMARY KEY,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS alerts (
    id         INTEGER PRIMARY KEY,
    token      TEXT NOT NULL REFERENCES devices(token) ON DELETE CASCADE,
    keyword    TEXT NOT NULL,
    UNIQUE(token, keyword)
);

CREATE TABLE IF NOT EXISTS sent_pushes (
    token      TEXT NOT NULL,
    article_id INTEGER NOT NULL,
    PRIMARY KEY (token, article_id)
);
"""


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


@contextmanager
def session():
    conn = connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init() -> None:
    with session() as c:
        c.executescript(SCHEMA)
        cols = {r[1] for r in c.execute("PRAGMA table_info(reactors)")}
        if "size" not in cols:  # databases created before reactor size classes existed
            c.execute("ALTER TABLE reactors ADD COLUMN size TEXT")


def row_to_dict(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    d = dict(row)
    for key in ("tags", "bullets", "keywords"):
        if key in d and isinstance(d[key], str):
            try:
                d[key] = json.loads(d[key])
            except json.JSONDecodeError:
                d[key] = []
    return d
