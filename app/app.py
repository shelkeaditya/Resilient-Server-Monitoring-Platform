import logging
import os

from flask import Flask, jsonify, render_template

from monitor.collector import Sampler

CSP = ("default-src 'self'; "
       "style-src 'self' 'unsafe-inline'; "
       "img-src 'self' data:; "
       "base-uri 'self'; form-action 'self'; frame-ancestors 'none'")


def create_app():
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"),
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    app = Flask(__name__)
    sampler = Sampler(interval=float(os.environ.get("MONITOR_INTERVAL", "3")),
                      history_points=int(os.environ.get("MONITOR_HISTORY", "300")))
    sampler.start()
    app.extensions["sampler"] = sampler

    @app.get("/")
    def index():
        return render_template("dashboard.html")

    @app.get("/api/v1/snapshot")
    def snapshot():
        return jsonify(sampler.snapshot())

    @app.get("/api/v1/history")
    def history():
        return jsonify(sampler.history())

    @app.get("/healthz")
    def healthz():
        s = sampler.snapshot()
        ok = s.get("status") == "ok" and not s.get("stale")
        return jsonify({"ok": ok}), (200 if ok else 503)

    @app.after_request
    def headers(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "same-origin"
        resp.headers["Content-Security-Policy"] = CSP
        if resp.mimetype == "application/json":
            resp.headers["Cache-Control"] = "no-store"
        return resp

    return app


if __name__ == "__main__":
    create_app().run(host=os.environ.get("MONITOR_HOST", "127.0.0.1"),
                     port=int(os.environ.get("MONITOR_PORT", "5000")), debug=False)
