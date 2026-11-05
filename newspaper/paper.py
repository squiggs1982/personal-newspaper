"""Compose the personal newspaper: a clean, modern multi-column HTML edition."""
import datetime
import html as html_mod
import re

PAPER_CSS = """
:root { --ink:#1a1a1a; --muted:#6b6b6b; --rule:#d8d4cc; --accent:#8a1f1f; }
* { box-sizing: border-box; }
body { margin:0; background:#f4f1ea; color:var(--ink);
  font-family: Georgia, 'Iowan Old Style', 'Times New Roman', serif; }
.page { max-width: 980px; margin: 0 auto; background:#fffdf8; padding: 48px 56px 64px;
  box-shadow: 0 2px 24px rgba(0,0,0,.08); }
.masthead { text-align:center; border-bottom: 3px double var(--ink); padding-bottom: 18px; margin-bottom: 8px; }
.masthead h1 { font-size: 56px; margin: 0; letter-spacing: .04em; font-variant: small-caps; }
.dateline { display:flex; justify-content:space-between; color:var(--muted);
  font-size: 13px; text-transform: uppercase; letter-spacing:.12em; margin: 10px 0 0; }
.section { margin-top: 36px; }
.section > h2 { font-size: 15px; text-transform: uppercase; letter-spacing: .22em;
  color: var(--accent); border-bottom: 1px solid var(--rule); padding-bottom: 6px; margin: 0 0 20px; }
.articles { column-width: 300px; column-gap: 40px; column-rule: 1px solid var(--rule); }
article { break-inside: avoid-column; margin: 0 0 28px; }
article h3 { font-size: 24px; line-height: 1.2; margin: 0 0 6px; }
article h3 a { color: inherit; text-decoration: none; }
article h3 a:hover { color: var(--accent); }
.byline { font-size: 12.5px; color: var(--muted); font-style: italic; margin: 0 0 12px; }
article p { font-size: 15.5px; line-height: 1.62; margin: 0 0 12px; text-align: justify; }
article p:first-of-type::first-letter { float:left; font-size: 52px; line-height: .85;
  padding: 4px 8px 0 0; font-weight: bold; color: var(--accent); }
article img { max-width: 100%; height: auto; margin: 8px 0; }
article blockquote { margin: 0 0 12px; padding: 4px 0 4px 16px; border-left: 3px solid var(--rule);
  font-style: italic; color:#333; }
article ul, article ol { margin: 0 0 12px; padding-left: 22px; font-size: 15.5px; line-height: 1.6; }
.src { font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: .08em; }
footer.colophon { margin-top: 40px; border-top: 1px solid var(--rule); padding-top: 12px;
  color: var(--muted); font-size: 12px; text-align: center; }
@media print { body { background:#fff; } .page { box-shadow:none; max-width:none; padding:0; } }
"""


def _esc(s):
    return html_mod.escape(s or "")


def article_block(row):
    byline_parts = []
    if row["author"]:
        byline_parts.append(f"By {_esc(row['author'])}")
    if row["published"]:
        byline_parts.append(_esc(str(row["published"])[:10]))
    source = getattr(row, "source_name", None) if hasattr(row, "keys") else None
    byline = " &middot; ".join(byline_parts)
    src = f'<div class="src">{_esc(source)}</div>' if source else ""
    title = _esc(row["title"])
    url = row["url"]
    if url:
        title = f'<a href="{_esc(url)}">{title}</a>'
    return f"""<article>
  <h3>{title}</h3>
  <p class="byline">{byline}</p>
  {src}
  {row["content_html"]}
</article>"""


def render_paper(articles, paper_title="The Personal Paper", when=None):
    """articles: list of db rows (with optional source_name). Returns full HTML page."""
    when = when or datetime.date.today()
    sections = {}
    for row in articles:
        sections.setdefault(row["section"] or "News", []).append(row)

    section_html = []
    for name in sorted(sections):
        blocks = "\n".join(article_block(r) for r in sections[name])
        section_html.append(
            f'<section class="section"><h2>{_esc(name)}</h2>\n'
            f'<div class="articles">\n{blocks}\n</div></section>'
        )

    date_str = when.strftime("%A, %B %-d, %Y") if hasattr(when, "strftime") else str(when)
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(paper_title)} — {_esc(date_str)}</title>
<style>{PAPER_CSS}</style></head>
<body><div class="page">
<header class="masthead">
  <h1>{_esc(paper_title)}</h1>
  <div class="dateline"><span>{_esc(date_str)}</span><span>Your daily edition</span></div>
</header>
{''.join(section_html)}
<footer class="colophon">Compiled automatically from your sources &middot; {len(articles)} articles</footer>
</div></body></html>"""


def sanitize_filename(name):
    return re.sub(r"[^\w\-]+", "_", name).strip("_") or "paper"
