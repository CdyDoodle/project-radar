"""`radar serve` over real HTTP on a random local port."""
import json
import threading
import urllib.error
import urllib.request

import pytest

from radar import serve as sv
from radar.store import open_store
from tests.test_report import seed


@pytest.fixture
def server(store, cfg):
    seed(store, cfg)
    httpd, app = sv.make_server(cfg, port=0, token="t0ken")
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    yield app
    httpd.shutdown()
    httpd.server_close()


def req(app, path, body=None, token="t0ken", host=None):
    url = f"http://127.0.0.1:{app.port}{path}"
    r = urllib.request.Request(url, method="POST" if body is not None else "GET",
                               data=json.dumps(body).encode() if body is not None else None)
    r.add_header("Content-Type", "application/json")
    if token:
        r.add_header("X-Radar-Token", token)
    if host:
        r.add_header("Host", host)
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")


def test_page_is_served_with_its_token(server):
    code, page = req(server, "/")
    assert code == 200 and '"t0ken"' in page and 'data-cmd="note"' in page


def test_served_page_never_touches_the_published_one(server, cfg):
    req(server, "/")
    assert (cfg.out_dir / "served.html").exists()
    published = cfg.out_dir / "index.html"
    assert not published.exists() or "t0ken" not in published.read_text(encoding="utf-8")


def test_verdict_and_note_write_to_the_database(server, cfg):
    assert req(server, "/api/verdict", {"key": "gh:b/db", "status": "saved"})[0] == 200
    assert req(server, "/api/note", {"key": "gh:b/db", "note": "try this"})[0] == 200
    row = open_store(cfg).get("gh:b/db")
    assert row["status"] == "saved" and row["note"] == "try this"
    fb = open_store(cfg).feedback()
    assert fb[-1]["via"] == "web"
    _, page = req(server, "/")
    assert "try this" in page                            # page rebuilt after the write


@pytest.mark.parametrize("kw,code", [
    ({"token": None}, 403),                              # no token
    ({"token": "wrong"}, 403),                           # wrong token
    ({"host": "evil.example:80"}, 403),                  # DNS rebinding
])
def test_writes_are_refused_without_token_and_host(server, cfg, kw, code):
    assert req(server, "/api/verdict", {"key": "gh:b/db", "status": "saved"}, **kw)[0] == code
    assert open_store(cfg).get("gh:b/db")["status"] == "new"


def test_foreign_host_cannot_even_read(server):
    assert req(server, "/", host="evil.example:80")[0] == 403


def test_bad_input(server):
    assert req(server, "/api/verdict", {"key": "gh:b/db", "status": "deleted"})[0] == 400
    assert req(server, "/api/verdict", {"key": "gh:no/such", "status": "saved"})[0] == 404
    assert req(server, "/api/dive", {"brief": "nope"})[0] == 404


def test_dive_runs_in_the_background(server, store, monkeypatch):
    from radar import dive as dv
    store.add_brief("r1-00", "r1", {"title": "b"})
    done = threading.Event()

    def fake_dive(cfg, st, brief, http=None):
        done.set()
        return {}

    monkeypatch.setattr(dv, "dive", fake_dive)
    code, body = req(server, "/api/dive", {"brief": "r1-00"})
    assert code == 202 and json.loads(body)["state"] == "running"
    assert done.wait(5)
    for _ in range(50):
        _, jobs = req(server, "/api/jobs")
        if json.loads(jobs)["r1-00"]["state"] == "done":
            break
        threading.Event().wait(0.1)
    assert json.loads(jobs)["r1-00"]["state"] == "done"
