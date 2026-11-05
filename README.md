# Personal Newspaper

A small app for Linux Mint that collects articles from blogs (Substack, Medium,
any RSS feed) and from individual articles you paste in (e.g. from paywalled
newspapers you subscribe to), cleans them up, and compiles a clean, modern
personal "newspaper" that you can export as **EPUB** for e-ink devices
(Kindle, Kobo, reMarkable, PocketBook) or as a print-ready **HTML** file.

## Install (Linux Mint)

```bash
sudo apt install python3-pip python3-venv
cd personal-newspaper
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
source .venv/bin/activate
python3 run.py serve          # then open http://localhost:5000 in your browser
```

From the web UI you can:

- **Add a blog/feed** — paste the site URL (e.g. `https://yoursubstack.substack.com`);
  the feed is auto-discovered, or paste the feed URL directly (`/feed`). "Sync"
  pulls in new posts.
- **Add an article** — paste a URL, raw HTML, or plain text. For paywalled titles
  (The Economist, FT), open the article in your browser while logged in, copy the
  article text, and paste it here.
- Toggle articles in/out of the paper, move them between sections, preview the
  paper, and download **EPUB** (copy the file to your e-reader over USB) or HTML.

## Command line

```bash
python3 run.py add-source "My Blog" https://example.substack.com
python3 run.py sync                 # fetch new articles from all sources
python3 run.py add https://example.substack.com/p/some-post
python3 run.py list                 # show articles in the paper
python3 run.py paper                # write exports/<title>_<date>.html
python3 run.py epub                 # write exports/<title>_<date>.epub
```

## How it works

- `newspaper/fetch.py` — HTTP fetching, RSS/Atom parsing, feed discovery.
- `newspaper/clean.py` — readability-style cleanup: strips ads/nav/scripts,
  picks the main content, keeps paragraphs/headings/quotes/images, extracts
  title/author/date.
- `newspaper/paper.py` — newspaper-style layout (masthead, sections, multi-column
  serif typography, drop caps).
- `newspaper/export_epub.py` — EPUB 3 generation with the standard library only.
- `newspaper/db.py` — SQLite storage (`newspaper.db` in the project folder).

## Tests

```bash
python3 -m unittest discover -s tests -v
```

Note: the app only fetches pages that are publicly accessible, or content you
paste yourself from your own subscription. It does not bypass paywalls.
