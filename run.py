#!/usr/bin/env python3
"""Personal Newspaper — entry point.

Usage:
  python3 run.py serve [--port 5000]     Start the local web UI (default)
  python3 run.py add-source NAME URL     Add a blog/feed source
  python3 run.py sync [SOURCE_ID]        Fetch new articles from sources
  python3 run.py add URL_OR_TEXT [--title T] [--section S]   Add one article
  python3 run.py list                    List articles in the paper
  python3 run.py paper                   Write the newspaper HTML to exports/
  python3 run.py epub                    Write an EPUB to exports/
"""
import argparse
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from newspaper import db, fetch, pipeline
from newspaper.export_epub import build_epub, default_epub_path
from newspaper.paper import render_paper, sanitize_filename

PAPER_TITLE = "The Personal Paper"
EXPORTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "exports")


def _paper_rows(conn):
    rows = db.list_articles(conn, only_paper=True)
    names = {s["id"]: s["name"] for s in db.list_sources(conn)}
    out = []
    for r in rows:
        d = dict(r)
        d["source_name"] = names.get(r["source_id"])
        out.append(d)
    return out


def main():
    ap = argparse.ArgumentParser(prog="personal-newspaper")
    ap.add_argument("command", choices=["serve", "add-source", "sync", "add", "list", "paper", "epub"])
    ap.add_argument("arg", nargs="?", default=None)
    ap.add_argument("--port", type=int, default=5000)
    ap.add_argument("--title", default=None)
    ap.add_argument("--section", default="News")
    args = ap.parse_args()

    conn = db.connect()

    if args.command == "serve":
        from newspaper.web import create_app
        app = create_app()
        print(f"Personal Newspaper running at http://localhost:{args.port}")
        app.run(host="127.0.0.1", port=args.port)

    elif args.command == "add-source":
        if not args.arg:
            sys.exit("Usage: run.py add-source NAME URL")
        # accept "NAME URL" as a single quoted arg or split
        parts = args.arg.split(None, 1) if " " in args.arg else (args.arg, "")
        if not parts[1]:
            sys.exit("Usage: run.py add-source \"NAME URL\"")
        sid = db.add_source(conn, parts[0], parts[1])
        print(f"Added source #{sid}: {parts[0]} ({parts[1]})")

    elif args.command == "sync":
        sources = db.list_sources(conn)
        if args.arg:
            sources = [s for s in sources if str(s["id"]) == args.arg]
        for s in sources:
            try:
                new = pipeline.sync_source(conn, s["id"])
                print(f"{s['name']}: {len(new)} new article(s)")
            except fetch.FetchError as e:
                print(f"{s['name']}: FAILED ({e})")

    elif args.command == "add":
        if not args.arg:
            sys.exit("Provide a URL or text to add")
        aid = pipeline.add_by_paste(conn, args.arg, title=args.title, section=args.section)
        print(f"Added article #{aid}")

    elif args.command == "list":
        for a in db.list_articles(conn, only_paper=True):
            print(f"[{a['id']}] ({a['section']}) {a['title']}")

    elif args.command == "paper":
        os.makedirs(EXPORTS, exist_ok=True)
        path = os.path.join(EXPORTS, f"{sanitize_filename(PAPER_TITLE)}_{datetime.date.today().isoformat()}.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(render_paper(_paper_rows(conn), paper_title=PAPER_TITLE))
        print(f"Wrote {path}")

    elif args.command == "epub":
        rows = _paper_rows(conn)
        path = default_epub_path(PAPER_TITLE)
        build_epub(rows, path, paper_title=PAPER_TITLE)
        print(f"Wrote {path} ({len(rows)} articles)")


if __name__ == "__main__":
    main()
