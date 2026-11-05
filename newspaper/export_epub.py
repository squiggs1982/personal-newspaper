"""EPUB 3 export using only the standard library (zipfile + xml).

E-ink devices (Kindle, Kobo, reMarkable, PocketBook) read EPUB, so the
generated file can be copied over USB straight to the device.
"""
import datetime
import html as html_mod
import os
import re
import uuid
import zipfile

from .paper import sanitize_filename

CONTAINER_XML = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""

NAV_XHTML = """<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head><title>Contents</title><style>body{{font-family:serif}} li{{margin:.4em 0}}</style></head>
<body><nav epub:type="toc"><h1>Contents</h1><ol>{items}</ol></nav></body></html>
"""

ARTICLE_CSS = """
body { font-family: Georgia, serif; line-height: 1.55; margin: 0 4%; }
h1 { font-size: 1.5em; line-height: 1.25; }
.byline { color: #666; font-style: italic; font-size: .85em; }
.src { color: #888; font-size: .75em; text-transform: uppercase; letter-spacing: .08em; }
p { margin: 0 0 .9em; text-align: justify; }
img { max-width: 100%; }
blockquote { margin: 0 0 .9em; padding-left: 1em; border-left: 2px solid #ccc; font-style: italic; }
"""


def _esc(s):
    return html_mod.escape(s or "")


def _article_xhtml(row, source_name=None):
    byline = []
    if row["author"]:
        byline.append(f"By {_esc(row['author'])}")
    if row["published"]:
        byline.append(_esc(str(row["published"])[:10]))
    byline_html = f'<p class="byline">{" &middot; ".join(byline)}</p>' if byline else ""
    src_html = f'<p class="src">{_esc(source_name)}</p>' if source_name else ""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>{_esc(row['title'])}</title><style>{ARTICLE_CSS}</style></head>
<body><article>
<h1>{_esc(row['title'])}</h1>
{byline_html}{src_html}
{row['content_html']}
</article></body></html>"""


def _cover_xhtml(paper_title, when, count):
    date_str = when.strftime("%A, %B %-d, %Y")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>{_esc(paper_title)}</title>
<style>body{{font-family:Georgia,serif;text-align:center;padding-top:30%}}
h1{{font-variant:small-caps;font-size:2.2em}}p{{color:#666}}</style></head>
<body><h1>{_esc(paper_title)}</h1><p>{_esc(date_str)}</p><p>{count} articles</p></body></html>"""


def build_epub(articles, out_path, paper_title="The Personal Paper", source_names=None, when=None):
    """articles: list of db rows. Writes an EPUB 3 file to out_path."""
    when = when or datetime.date.today()
    uid = uuid.uuid4().hex
    items = []
    manifest = []
    spine = []

    files = {"OEBPS/cover.xhtml": _cover_xhtml(paper_title, when, len(articles)),
             "OEBPS/style.css": ARTICLE_CSS}
    items.append('<li><a href="cover.xhtml">Cover</a></li>')
    manifest.append('<item id="cover" href="cover.xhtml" media-type="application/xhtml+xml"/>')
    manifest.append('<item id="css" href="style.css" media-type="text/css"/>')
    manifest.append('<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>')
    spine.append('<itemref idref="cover"/>')

    for i, row in enumerate(articles):
        fname = f"article_{i+1}.xhtml"
        src = (source_names or {}).get(row["id"])
        files[f"OEBPS/{fname}"] = _article_xhtml(row, src)
        files[f"OEBPS/{fname}"] = re.sub(r'<(img[^>]*?)\s*/>', r'<\1/>', files[f"OEBPS/{fname}"])
        manifest.append(f'<item id="a{i+1}" href="{fname}" media-type="application/xhtml+xml"/>')
        spine.append(f'<itemref idref="a{i+1}"/>')
        items.append(f'<li><a href="{fname}">{_esc(row["title"])}</a></li>')

    files["OEBPS/nav.xhtml"] = NAV_XHTML.format(items="\n".join(items))

    opf = f"""<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="uid">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="uid">urn:uuid:{uid}</dc:identifier>
    <dc:title>{_esc(paper_title)}</dc:title>
    <dc:creator>Personal Newspaper</dc:creator>
    <dc:language>en</dc:language>
    <dc:date>{when.isoformat()}</dc:date>
    <meta property="dcterms:modified">{datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")}</meta>
  </metadata>
  <manifest>{''.join(manifest)}</manifest>
  <spine>{''.join(spine)}</spine>
</package>"""
    files["OEBPS/content.opf"] = opf

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with zipfile.ZipFile(out_path, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip",
                   compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml", CONTAINER_XML)
        for name, data in files.items():
            z.writestr(name, data, compress_type=zipfile.ZIP_DEFLATED)
    return out_path


def default_epub_path(paper_title, when=None):
    when = when or datetime.date.today()
    base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "exports")
    return os.path.join(base, f"{sanitize_filename(paper_title)}_{when.isoformat()}.epub")
