"""Article extraction and cleanup: turn messy web pages into clean article HTML.

A small readability-style extractor built on BeautifulSoup: strip boilerplate,
pick the main content container, keep only meaningful elements, absolutize
URLs, and pull out title/author/date metadata.
"""
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

JUNK_TAGS = [
    "script", "style", "noscript", "iframe", "svg", "form", "button", "input",
    "select", "textarea", "nav", "header", "footer", "aside",
]
JUNK_CLASS_RE = re.compile(
    r"(ad|advert|banner|comment|cookie|footer|header|masthead|nav|navbar|"
    r"sidebar|social|share|subscribe|newsletter|promo|related|recommend|"
    r"popup|modal|paywall|meter|regwall)",
    re.IGNORECASE,
)
KEEP_TAGS = {
    "p", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "pre",
    "ul", "ol", "li", "img", "a", "strong", "em", "b", "i", "br", "hr",
    "table", "thead", "tbody", "tr", "th", "td", "figcaption", "cite",
    "dl", "dt", "dd", "figure",
}
STRIP_ATTRS = ("class", "style", "id", "onclick", "srcset", "sizes", "width",
               "height", "rel", "target")
MIN_PARA_TEXT = 25


def make_soup(html):
    return BeautifulSoup(html, "html.parser")


def extract_metadata(soup):
    def meta(*names):
        for name in names:
            tag = soup.find("meta", attrs={"property": name}) or soup.find(
                "meta", attrs={"name": name})
            if tag and tag.get("content"):
                return tag["content"].strip()
        return None

    title = meta("og:title", "twitter:title") or ""
    if not title and soup.title and soup.title.string:
        title = soup.title.string.strip()
    if not title:
        h1 = soup.find("h1")
        title = h1.get_text(strip=True) if h1 else "Untitled"
    title = re.sub(r"\s*[|\-–—]\s*[^|\-–—]{3,60}$", "", title).strip() or title

    author = meta("author", "article:author", "og:article:author", "twitter:creator")
    if not author:
        rel = soup.find(attrs={"rel": "author"})
        author = rel.get_text(strip=True) if rel else None

    published = meta("article:published_time", "og:published_time", "datepublished", "date")
    if not published:
        t = soup.find("time")
        if t:
            published = t.get("datetime") or t.get_text(strip=True)

    return {"title": title, "author": author, "published": published}


def _text_len(node):
    return len(node.get_text(" ", strip=True))


def _score(node):
    """Higher = more likely to be the main content."""
    text = _text_len(node)
    if text < 200:
        return 0
    paras = len(node.find_all("p"))
    link_text = sum(_text_len(a) for a in node.find_all("a"))
    link_density = link_text / max(text, 1)
    return text + paras * 80 - link_density * text


def find_main(soup):
    for selector in ("article", '[role="main"]', "main"):
        node = soup.find(selector)
        if node and _text_len(node) > 200:
            return node
    best, best_score = None, 0
    for div in soup.find_all(["div", "section"]):
        s = _score(div)
        if s > best_score:
            best, best_score = div, s
    return best or soup.body or soup


def _is_junk(el):
    if el.attrs is None:
        return True
    ident = " ".join(el.get("class", [])) + " " + (el.get("id") or "")
    return bool(JUNK_CLASS_RE.search(ident))


def _clean_attributes(el, base_url):
    for attr in STRIP_ATTRS:
        if el.has_attr(attr):
            del el[attr]
    for attr in list(el.attrs):
        if attr.startswith("data-") or attr.startswith("aria-"):
            del el[attr]
    if el.name == "img":
        src = el.get("src")
        if src and base_url:
            el["src"] = urljoin(base_url, src)
        if not el.get("src") or el["src"].startswith("data:"):
            el.decompose()
    if el.name == "a":
        href = el.get("href")
        if href and base_url:
            el["href"] = urljoin(base_url, href)
        if not el.get_text(strip=True) and not el.find("img"):
            el.decompose()


def clean_html(html, base_url=None):
    """Return (clean_content_html, metadata dict) for a raw article page."""
    soup = make_soup(html)
    for tag in soup.find_all(JUNK_TAGS):
        tag.decompose()
    for el in list(soup.find_all(True)):
        if getattr(el, "decomposed", False) or el.attrs is None:
            continue
        if el.find_parent(["article", "main"]):
            continue
        if _is_junk(el):
            el.decompose()

    main = find_main(soup)
    for p in list(main.find_all("p")):
        if getattr(p, "decomposed", False):
            continue
        if _text_len(p) < MIN_PARA_TEXT and not p.find("img"):
            p.decompose()
    for el in list(main.find_all(True)):
        if getattr(el, "decomposed", False) or el.attrs is None:
            continue
        if el.name not in KEEP_TAGS:
            el.unwrap()
        else:
            _clean_attributes(el, base_url)

    content = main.decode_contents().strip()
    content = re.sub(r"\n{3,}", "\n\n", content)
    meta = extract_metadata(soup)
    meta["content_text"] = make_soup(content).get_text("\n", strip=True)
    return content, meta


def clean_text_to_html(text):
    """Convert pasted plain text into simple article HTML (paragraph per block)."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
    if not paras and text.strip():
        paras = [l.strip() for l in text.splitlines() if l.strip()]
    escaped = [p.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;") for p in paras]
    return "\n".join(f"<p>{p}</p>" for p in escaped)


def looks_like_url(s):
    return bool(re.match(r"^https?://", s.strip(), re.IGNORECASE))


def is_probably_html(s):
    return bool(re.search(r"<\s*(p|div|article|h1|html|body)\b", s, re.IGNORECASE))


def domain_of(url):
    return urlparse(url).netloc.lower().lstrip("www.")
