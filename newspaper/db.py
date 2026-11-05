"""SQLite storage for sources and articles."""
import os
import sqlite3
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    url TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'rss',
    added_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER REFERENCES sources(id) ON DELETE SET NULL,
    url TEXT,
    title TEXT NOT NULL,
    author TEXT,
    published TEXT,
    content_html TEXT NOT NULL,
    content_text TEXT NOT NULL DEFAULT '',
    fetched_at REAL NOT NULL,
    in_paper INTEGER NOT NULL DEFAULT 1,
    section TEXT NOT NULL DEFAULT 'News',
    position INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_articles_in_paper ON articles(in_paper);
"""

DEFAULT_DB = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "newspaper.db"
)


def connect(db_path=None):
    path = db_path or os.environ.get("NEWSPAPER_DB", DEFAULT_DB)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def add_source(conn, name, url, kind="rss"):
    cur = conn.execute(
        "INSERT INTO sources (name, url, kind, added_at) VALUES (?, ?, ?, ?)",
        (name, url, kind, time.time()),
    )
    conn.commit()
    return cur.lastrowid


def list_sources(conn):
    return conn.execute("SELECT * FROM sources ORDER BY name").fetchall()


def delete_source(conn, source_id):
    conn.execute("DELETE FROM sources WHERE id = ?", (source_id,))
    conn.commit()


def article_exists(conn, url):
    if not url:
        return False
    return (
        conn.execute("SELECT 1 FROM articles WHERE url = ? LIMIT 1", (url,)).fetchone()
        is not None
    )


def add_article(conn, title, content_html, content_text, url=None, source_id=None,
                author=None, published=None, section="News"):
    cur = conn.execute(
        """INSERT INTO articles
           (source_id, url, title, author, published, content_html, content_text,
            fetched_at, in_paper, section, position)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)""",
        (source_id, url, title, author, published, content_html, content_text,
         time.time(), section, 0),
    )
    conn.commit()
    return cur.lastrowid


def list_articles(conn, only_paper=False):
    q = "SELECT a.*, s.name AS source_name FROM articles a LEFT JOIN sources s ON a.source_id = s.id"
    if only_paper:
        q += " WHERE a.in_paper = 1 ORDER BY a.section, a.position, a.fetched_at DESC"
    else:
        q += " ORDER BY a.fetched_at DESC"
    return conn.execute(q).fetchall()


def get_article(conn, article_id):
    return conn.execute("SELECT * FROM articles WHERE id = ?", (article_id,)).fetchone()


def set_in_paper(conn, article_id, in_paper):
    conn.execute("UPDATE articles SET in_paper = ? WHERE id = ?", (1 if in_paper else 0, article_id))
    conn.commit()


def delete_article(conn, article_id):
    conn.execute("DELETE FROM articles WHERE id = ?", (article_id,))
    conn.commit()


def set_section(conn, article_id, section):
    conn.execute("UPDATE articles SET section = ? WHERE id = ?", (section, article_id))
    conn.commit()


def reorder_paper(conn, ordered_ids):
    for pos, aid in enumerate(ordered_ids):
        conn.execute("UPDATE articles SET position = ? WHERE id = ?", (pos, aid))
    conn.commit()
