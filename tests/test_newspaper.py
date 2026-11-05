import os
import sqlite3
import sys
import tempfile
import unittest
import zipfile
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from newspaper import db, fetch
from newspaper.clean import clean_html, clean_text_to_html, looks_like_url, is_probably_html
from newspaper.export_epub import build_epub
from newspaper.paper import render_paper

FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def read_fixture(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as f:
        return f.read()


class TestClean(unittest.TestCase):
    def test_strips_boilerplate(self):
        content, meta = clean_html(read_fixture("messy_article.html"),
                                   base_url="https://www.ft.com/content/xyz")
        self.assertEqual(meta["title"], "Markets rally as tech leads the way")
        self.assertEqual(meta["author"], "Jane Doe")
        self.assertIn("2024-05-01", meta["published"])
        self.assertNotIn("BUY OUR PRODUCTS", content)
        self.assertNotIn("related-stories", content)
        self.assertNotIn("Most read", content)
        self.assertNotIn("<script", content)
        self.assertNotIn("<style", content)
        self.assertNotIn("Cookie preferences", content)
        self.assertIn("Global stock markets climbed", content)
        self.assertIn("<blockquote>", content)
        self.assertIn("Commodity markets were mixed", content)

    def test_substack_style_post(self):
        content, meta = clean_html(read_fixture("substack_post.html"),
                                   base_url="https://example.substack.com/p/slow-mornings")
        self.assertEqual(meta["title"], "Why slow mornings matter")
        self.assertIn("attention residue", content)
        self.assertNotIn("Subscribe to my newsletter", content)
        self.assertNotIn("Great post!", content)

    def test_plain_text_conversion(self):
        html = clean_text_to_html("First paragraph here.\n\nSecond paragraph here.")
        self.assertEqual(html.count("<p>"), 2)
        self.assertIn("First paragraph here.", html)

    def test_detectors(self):
        self.assertTrue(looks_like_url("https://example.com/x"))
        self.assertFalse(looks_like_url("just some text"))
        self.assertTrue(is_probably_html("<p>hello</p>"))
        self.assertFalse(is_probably_html("plain text"))


class TestFeed(unittest.TestCase):
    def test_parse_rss(self):
        entries = fetch.parse_feed(read_fixture("feed.xml"),
                                   base_url="https://example.substack.com/feed")
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["title"], "Why slow mornings matter")
        self.assertEqual(entries[0]["url"], "https://example.substack.com/p/slow-mornings")
        self.assertEqual(entries[0]["published"], "2024-05-01")


class TestDb(unittest.TestCase):
    def setUp(self):
        self.conn = db.connect(":memory:")

    def test_source_and_article_flow(self):
        sid = db.add_source(self.conn, "Dispatch", "https://example.substack.com/feed")
        self.assertEqual(len(db.list_sources(self.conn)), 1)
        aid = db.add_article(self.conn, "T", "<p>hi</p>", "hi", url="https://x/1", source_id=sid)
        self.assertTrue(db.article_exists(self.conn, "https://x/1"))
        self.assertFalse(db.article_exists(self.conn, "https://x/2"))
        db.set_in_paper(self.conn, aid, False)
        self.assertEqual(len(db.list_articles(self.conn, only_paper=True)), 0)
        db.set_in_paper(self.conn, aid, True)
        self.assertEqual(len(db.list_articles(self.conn, only_paper=True)), 1)
        db.delete_article(self.conn, aid)
        self.assertEqual(len(db.list_articles(self.conn)), 0)


class TestPaperAndEpub(unittest.TestCase):
    def setUp(self):
        self.conn = db.connect(":memory:")
        sid = db.add_source(self.conn, "Dispatch", "https://example.substack.com/feed")
        content, meta = clean_html(read_fixture("substack_post.html"),
                                   base_url="https://example.substack.com/p/slow-mornings")
        self.aid = db.add_article(self.conn, meta["title"], content, meta["content_text"],
                                  url="https://example.substack.com/p/slow-mornings",
                                  source_id=sid, author=meta["author"], section="Essays")
        content2, meta2 = clean_html(read_fixture("messy_article.html"),
                                     base_url="https://www.ft.com/content/xyz")
        self.aid2 = db.add_article(self.conn, meta2["title"], content2, meta2["content_text"],
                                   url="https://www.ft.com/content/xyz", section="News")

    def _rows(self):
        rows = db.list_articles(self.conn, only_paper=True)
        names = {s["id"]: s["name"] for s in db.list_sources(self.conn)}
        out = []
        for r in rows:
            d = dict(r)
            d["source_name"] = names.get(r["source_id"])
            out.append(d)
        return out

    def test_render_paper(self):
        html = render_paper(self._rows(), paper_title="The Personal Paper")
        self.assertIn("The Personal Paper", html)
        self.assertIn("Why slow mornings matter", html)
        self.assertIn("Markets rally as tech leads the way", html)
        self.assertIn("Essays", html)
        self.assertIn("News", html)

    def test_epub_structure(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "paper.epub")
            build_epub(self._rows(), path, paper_title="The Personal Paper")
            with zipfile.ZipFile(path) as z:
                names = z.namelist()
                self.assertEqual(names[0], "mimetype")
                info = z.getinfo("mimetype")
                self.assertEqual(info.compress_type, zipfile.ZIP_STORED)
                self.assertEqual(z.read("mimetype").decode(), "application/epub+zip")
                self.assertIn("META-INF/container.xml", names)
                self.assertIn("OEBPS/content.opf", names)
                self.assertIn("OEBPS/nav.xhtml", names)
                self.assertIn("OEBPS/article_1.xhtml", names)
                # every xml file must be well-formed
                for n in names:
                    if n.endswith((".xhtml", ".opf", ".xml")):
                        ET.fromstring(z.read(n))
                opf = z.read("OEBPS/content.opf").decode()
                self.assertIn("The Personal Paper", opf)
                art = z.read("OEBPS/article_1.xhtml").decode()
                self.assertIn("attention residue", art)


if __name__ == "__main__":
    unittest.main()
