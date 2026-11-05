"""Fetching: grab article pages, discover and parse RSS/Atom feeds.

Substack and Medium both expose public RSS feeds (e.g. https://example.substack.com/feed),
so blogs are handled through feeds; individual articles can be fetched by URL
or pasted in manually (useful for paywalled papers you subscribe to).
"""
import re
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin

import requests

from .clean import clean_html, domain_of

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0 Safari/537.36 PersonalNewspaper/1.0")
TIMEOUT = 30


class FetchError(Exception):
    pass


def fetch_url(url):
    try:
        resp = requests.get(url, headers={"User-Agent": UA}, timeout=TIMEOUT)
        resp.raise_for_status()
        if not resp.encoding or resp.encoding.lower() == "iso-8859-1":
            resp.encoding = resp.apparent_encoding or "utf-8"
        return resp.text
    except requests.RequestException as exc:
        raise FetchError(f"Could not fetch {url}: {exc}") from exc


def fetch_article(url):
    """Fetch and clean a single article URL. Returns dict for db.add_article."""
    html = fetch_url(url)
    content, meta = clean_html(html, base_url=url)
    return {
        "url": url,
        "title": meta["title"],
        "author": meta["author"],
        "published": meta["published"],
        "content_html": content,
        "content_text": meta["content_text"],
    }


FEED_LINK_RE = re.compile(
    r'<link[^>]+rel=["\']alternate["\'][^>]+type=["\'](application/rss\+xml|application/atom\+xml)["\'][^>]*>',
    re.IGNORECASE,
)
FEED_LINK_RE2 = re.compile(
    r'<link[^>]+type=["\'](application/rss\+xml|application/atom\+xml)["\'][^>]+rel=["\']alternate["\'][^>]*>',
    re.IGNORECASE,
)


def discover_feed(site_url):
    """Find the RSS/Atom feed URL for a site homepage (Substack, Medium, blogs)."""
    candidates = []
    for suffix in ("/feed", "/rss", "/feed.xml", "/rss.xml", "/atom.xml"):
        candidates.append(urljoin(site_url.rstrip("/") + "/", suffix.lstrip("/")))
    try:
        html = fetch_url(site_url)
        for rx in (FEED_LINK_RE, FEED_LINK_RE2):
            m = rx.search(html)
            if m:
                href = re.search(r'href=["\']([^"\']+)["\']', m.group(0))
                if href:
                    return urljoin(site_url, href.group(1))
    except FetchError:
        pass
    for cand in candidates:
        try:
            text = fetch_url(cand)
            if "<rss" in text or "<feed" in text:
                return cand
        except FetchError:
            continue
    raise FetchError(f"No RSS/Atom feed found for {site_url}")


def _text(el, *paths):
    for p in paths:
        found = el.find(p)
        if found is not None and found.text:
            return found.text.strip()
    return None


def _atom_text(el, *paths):
    for p in paths:
        found = el.find(p)
        if found is not None:
            return (found.text or "").strip() or None
    return None


def parse_feed(xml_text, base_url=None):
    """Parse RSS 2.0 or Atom into a list of entry dicts."""
    root = ET.fromstring(xml_text)
    entries = []
    if root.tag == "rss" or root.tag.endswith("}rss"):
        channel = root.find("channel")
        for item in channel.findall("item"):
            link = _text(item, "link") or (item.find("guid") is not None and item.find("guid").text)
            pub = _text(item, "pubDate", "published", "date")
            if pub:
                try:
                    pub = parsedate_to_datetime(pub).date().isoformat()
                except (TypeError, ValueError):
                    pass
            entries.append({
                "title": _text(item, "title") or "Untitled",
                "url": urljoin(base_url, link) if base_url and link else link,
                "author": _text(item, "author") or _text(item, "{http://purl.org/dc/elements/1.1/}creator"),
                "published": pub,
                "summary": _text(item, "description", "summary"),
            })
    elif root.tag.endswith("}feed"):
        ns = "{http://www.w3.org/2005/Atom}"
        for entry in root.findall(f"{ns}entry"):
            link = None
            for l in entry.findall(f"{ns}link"):
                if l.get("rel") in (None, "alternate") and l.get("href"):
                    link = l.get("href")
                    break
            pub = _atom_text(entry, f"{ns}published", f"{ns}updated")
            entries.append({
                "title": _atom_text(entry, f"{ns}title") or "Untitled",
                "url": urljoin(base_url, link) if base_url and link else link,
                "author": _atom_text(entry, f"{ns}author/{ns}name"),
                "published": pub[:10] if pub else None,
                "summary": _atom_text(entry, f"{ns}summary", f"{ns}content"),
            })
    else:
        raise FetchError("Unrecognized feed format (not RSS or Atom)")
    return entries


def fetch_feed_entries(feed_url):
    return parse_feed(fetch_url(feed_url), base_url=feed_url)


def known_site_hint(url):
    d = domain_of(url)
    if d.endswith("substack.com"):
        return "substack"
    if d.endswith("medium.com") or ".medium.com" in d:
        return "medium"
    return None
