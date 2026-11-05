"""High-level operations tying fetching, cleaning and storage together."""
import re

from . import db, fetch
from .clean import clean_html, clean_text_to_html, is_probably_html, looks_like_url


def sync_source(conn, source_id, limit=10):
    """Fetch new articles from a source's feed. Returns list of new article ids."""
    source = conn.execute("SELECT * FROM sources WHERE id = ?", (source_id,)).fetchone()
    if not source:
        raise fetch.FetchError("Unknown source")
    feed_url = source["url"] if source["kind"] == "rss" else fetch.discover_feed(source["url"])
    entries = fetch.fetch_feed_entries(feed_url)
    new_ids = []
    for entry in entries[:limit]:
        if not entry.get("url") or db.article_exists(conn, entry["url"]):
            continue
        try:
            art = fetch.fetch_article(entry["url"])
        except fetch.FetchError:
            continue
        aid = db.add_article(
            conn, art["title"], art["content_html"], art["content_text"],
            url=art["url"], source_id=source_id, author=art["author"],
            published=art["published"], section=source["name"],
        )
        new_ids.append(aid)
    return new_ids


def add_by_url(conn, url, section="News"):
    """Fetch a single article URL (Substack/Medium post, open-access news)."""
    if not looks_like_url(url):
        raise ValueError("Not a valid URL")
    if db.article_exists(conn, url):
        raise ValueError("Article already in your library")
    art = fetch.fetch_article(url)
    return db.add_article(
        conn, art["title"], art["content_html"], art["content_text"],
        url=url, author=art["author"], published=art["published"], section=section,
    )


def add_by_paste(conn, text, title=None, section="News"):
    """Add an article from pasted content (URL, HTML, or plain text).

    Intended for paywalled subscriptions (e.g. The Economist, FT): paste the
    article text/HTML while logged in on the publisher's site yourself.
    """
    text = text.strip()
    if not text:
        raise ValueError("Nothing pasted")
    if looks_like_url(text):
        return add_by_url(conn, text, section=section)
    if is_probably_html(text):
        content, meta = clean_html(text)
        return db.add_article(
            conn, title or meta["title"], content, meta["content_text"],
            author=meta["author"], published=meta["published"], section=section,
        )
    content = clean_text_to_html(text)
    first_line = re.split(r"\n", text)[0].strip()
    return db.add_article(
        conn, title or first_line[:120], content,
        "\n".join(re.split(r"\n\s*\n", text)), section=section,
    )
