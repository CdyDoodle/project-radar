"""`radar serve`: the dashboard, live, on your own machine.

The published page is static, so its save and dismiss buttons can only copy a
command. Served locally they write straight to the database, notes can be
added, and a brief can be sent for a dive with one click.

Local only, and defended as if it weren't:
- binds 127.0.0.1, never all interfaces;
- every write needs a random token that exists only inside the served page,
  so another website open in the same browser cannot post to it;
- the Host header must be this server's own address, which defeats DNS
  rebinding (a hostile domain re-pointed at 127.0.0.1).
Standard library only; one short-lived database connection per request.
"""
from __future__ import annotations

import json
import logging
import secrets
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from radar import report
from radar.config import Config
from radar.store import open_store

log = logging.getLogger("radar.serve")

STATUSES = {"saved", "dismissed", "new"}
MAX_BODY = 64 * 1024


class App:
    """State shared by all requests: config, token, the page, dive jobs."""

    def __init__(self, cfg: Config, port: int, token: str | None = None):
        self.cfg = cfg
        self.port = port
        self.token = token or secrets.token_urlsafe(24)
        self.allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
        self.lock = threading.Lock()
        self.dirty = True
        self.page: bytes = b""
        self.jobs: dict[str, dict] = {}

    def html(self) -> bytes:
        with self.lock:
            if self.dirty or not self.page:
                store = open_store(self.cfg)
                path, _ = report.build(self.cfg, store, api_token=self.token)
                self.page = Path(path).read_bytes()
                self.dirty = False
            return self.page

    def start_dive(self, brief_id: str) -> dict:
        from radar import dive as dv
        with self.lock:
            job = self.jobs.get(brief_id)
            if job and job["state"] == "running":
                return job
            job = {"state": "running", "error": ""}
            self.jobs[brief_id] = job

        def work():
            try:
                store = open_store(self.cfg)
                brief = store.brief(brief_id)
                if not brief:
                    raise ValueError(f"no brief {brief_id}")
                dv.dive(self.cfg, store, brief)
                job["state"] = "done"
            except BaseException as exc:          # SystemExit from require_login too
                job["state"], job["error"] = "failed", str(exc)[:300]
                log.warning("dive %s failed: %s", brief_id, exc)
            finally:
                self.dirty = True

        threading.Thread(target=work, name=f"dive-{brief_id}", daemon=True).start()
        return job


def make_handler(app: App):
    class Handler(BaseHTTPRequestHandler):
        server_version = "radar"

        def log_message(self, fmt, *args):       # quiet by default
            log.info("%s - " + fmt, self.address_string(), *args)

        # -- plumbing ------------------------------------------------------------
        def _send(self, code: int, body: bytes, ctype: str = "application/json") -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code: int, obj) -> None:
            self._send(code, json.dumps(obj).encode("utf-8"))

        def _host_ok(self) -> bool:
            return (self.headers.get("Host") or "") in app.allowed_hosts

        def _authorised(self) -> bool:
            sent = self.headers.get("X-Radar-Token") or ""
            return self._host_ok() and secrets.compare_digest(sent, app.token)

        def _body(self) -> dict:
            n = int(self.headers.get("Content-Length") or 0)
            if n <= 0 or n > MAX_BODY:
                raise ValueError("bad body size")
            data = json.loads(self.rfile.read(n).decode("utf-8"))
            if not isinstance(data, dict):
                raise ValueError("expected a JSON object")
            return data

        # -- routes ------------------------------------------------------------------
        def do_GET(self):
            if not self._host_ok():
                return self._send(403, b"forbidden host", "text/plain")
            path = self.path.split("?", 1)[0]
            if path in ("/", "/index.html"):
                return self._send(200, app.html(), "text/html; charset=utf-8")
            if path == "/api/jobs":
                if not self._authorised():
                    return self._send(403, b"forbidden", "text/plain")
                return self._json(200, app.jobs)
            return self._send(404, b"not found", "text/plain")

        def do_POST(self):
            if not self._authorised():
                return self._send(403, b"forbidden", "text/plain")
            try:
                body = self._body()
            except (ValueError, UnicodeDecodeError) as exc:
                return self._send(400, str(exc).encode(), "text/plain")
            path = self.path.split("?", 1)[0]
            store = open_store(app.cfg)
            if path == "/api/verdict":
                key, status = str(body.get("key") or ""), str(body.get("status") or "")
                if status not in STATUSES:
                    return self._send(400, b"bad status", "text/plain")
                if not store.set_status(key, status, via="web"):
                    return self._send(404, b"no such item", "text/plain")
                app.dirty = True
                return self._json(200, {"ok": True, "status": status})
            if path == "/api/note":
                key, note = str(body.get("key") or ""), str(body.get("note") or "")[:2000]
                if not store.set_note(key, note):
                    return self._send(404, b"no such item", "text/plain")
                app.dirty = True
                return self._json(200, {"ok": True})
            if path == "/api/dive":
                brief_id = str(body.get("brief") or "")
                if not store.brief(brief_id):
                    return self._send(404, b"no such brief", "text/plain")
                return self._json(202, app.start_dive(brief_id))
            return self._send(404, b"not found", "text/plain")

    return Handler


def make_server(cfg: Config, port: int = 8766, token: str | None = None):
    app = App(cfg, port, token)
    httpd = ThreadingHTTPServer(("127.0.0.1", port), make_handler(app))
    app.port = httpd.server_address[1]                 # port 0 -> the real one
    app.allowed_hosts = {f"127.0.0.1:{app.port}", f"localhost:{app.port}"}
    return httpd, app


def serve(cfg: Config, port: int = 8766, open_browser: bool = True) -> None:
    httpd, app = make_server(cfg, port)
    url = f"http://127.0.0.1:{app.port}/"
    print(f"radar serving {url}  (Ctrl+C to stop)")
    if open_browser:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
