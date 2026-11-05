"""Flask web UI: manage sources/articles, preview the paper, export EPUB/HTML."""
import datetime
import os
import tempfile

from flask import Flask, g, redirect, render_template, request, send_file, url_for

from . import db, fetch, pipeline
from .export_epub import build_epub, default_epub_path
from .paper import render_paper, sanitize_filename

PAPER_TITLE = "The Personal Paper"


def create_app(db_path=None):
    app = Flask(__name__)

    def get_conn():
        if "conn" not in g:
            g.conn = db.connect(db_path)
        return g.conn

    @app.teardown_appcontext
    def close_conn(exc):
        conn = g.pop("conn", None)
        if conn is not None:
            conn.close()

    @app.route("/")
    def index():
        conn = get_conn()
        sources = db.list_sources(conn)
        articles = db.list_articles(conn)
        return render_template("index.html", sources=sources, articles=articles,
                               paper_title=PAPER_TITLE)

    @app.route("/sources/add", methods=["POST"])
    def add_source():
        name = request.form.get("name", "").strip()
        url = request.form.get("url", "").strip()
        if name and url:
            db.add_source(get_conn(), name, url, kind="rss")
        return redirect(url_for("index"))

    @app.route("/sources/<int:sid>/delete", methods=["POST"])
    def del_source(sid):
        db.delete_source(get_conn(), sid)
        return redirect(url_for("index"))

    @app.route("/sources/<int:sid>/sync", methods=["POST"])
    def sync(sid):
        try:
            pipeline.sync_source(get_conn(), sid)
        except fetch.FetchError:
            pass
        return redirect(url_for("index"))

    @app.route("/add", methods=["POST"])
    def add_article():
        text = request.form.get("content", "")
        title = request.form.get("title", "").strip() or None
        section = request.form.get("section", "News").strip() or "News"
        try:
            pipeline.add_by_paste(get_conn(), text, title=title, section=section)
        except ValueError:
            pass
        return redirect(url_for("index"))

    @app.route("/articles/<int:aid>/toggle", methods=["POST"])
    def toggle(aid):
        row = db.get_article(get_conn(), aid)
        db.set_in_paper(get_conn(), aid, not row["in_paper"])
        return redirect(url_for("index"))

    @app.route("/articles/<int:aid>/delete", methods=["POST"])
    def del_article(aid):
        db.delete_article(get_conn(), aid)
        return redirect(url_for("index"))

    @app.route("/articles/<int:aid>/section", methods=["POST"])
    def set_section(aid):
        db.set_section(get_conn(), aid, request.form.get("section", "News").strip() or "News")
        return redirect(url_for("index"))

    def _paper_rows():
        conn = get_conn()
        rows = db.list_articles(conn, only_paper=True)
        names = {s["id"]: s["name"] for s in db.list_sources(conn)}
        out = []
        for r in rows:
            d = dict(r)
            d["source_name"] = names.get(r["source_id"])
            out.append(d)
        return out

    @app.route("/paper")
    def paper():
        return render_paper(_paper_rows(), paper_title=PAPER_TITLE)

    @app.route("/export/html")
    def export_html():
        path = os.path.join(tempfile.gettempdir(),
                            f"{sanitize_filename(PAPER_TITLE)}_{datetime.date.today().isoformat()}.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(render_paper(_paper_rows(), paper_title=PAPER_TITLE))
        return send_file(path, as_attachment=True, download_name=os.path.basename(path))

    @app.route("/export/epub")
    def export_epub():
        rows = _paper_rows()
        path = default_epub_path(PAPER_TITLE)
        build_epub(rows, path, paper_title=PAPER_TITLE)
        return send_file(path, as_attachment=True,
                         download_name=f"{sanitize_filename(PAPER_TITLE)}_{datetime.date.today().isoformat()}.epub")

    return app


app = create_app()
