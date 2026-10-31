import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace

from test_certificate import DIAG

from undertaker.config import Settings
from undertaker.morgue.app import code_spans, create_app


class AsgiClient:
    """Minimal ASGI caller (no httpx)."""

    def __init__(self, app):
        self.app = app

    def _call(self, method, path, headers=None):
        hdrs = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": method,
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "root_path": "",
            "headers": hdrs,
            "client": ("127.0.0.1", 1),
            "server": ("127.0.0.1", 8666),
        }
        out = {"status": 0, "body": b""}

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(msg):
            if msg["type"] == "http.response.start":
                out["status"] = msg["status"]
            elif msg["type"] == "http.response.body":
                out["body"] += msg.get("body", b"")

        asyncio.run(self.app(scope, receive, send))
        return SimpleNamespace(status_code=out["status"], text=out["body"].decode())

    def get(self, path, headers=None):
        return self._call("GET", path, headers)

    def post(self, path, headers=None):
        return self._call("POST", path, headers)


def client(tmp_path, **kw):
    app = create_app(Settings(data_dir=tmp_path, no_model=True, **kw), start_loop=False)
    m = app.state.morgue
    m.results = list(DIAG.values())
    m.by_id = {d.workflow_id: d for d in m.results}
    m.swept_at = datetime.now(UTC)
    return AsgiClient(app), m


def test_morgue_page_lists_toe_tags(tmp_path):
    c, _ = client(tmp_path)
    r = c.get("/")
    assert r.status_code == 200
    for cause in DIAG:
        assert f'data-cause="{cause}"' in r.text
    assert "Sweep now" in r.text


def test_certificate_page_template_and_disabled_actions(tmp_path):
    c, m = client(tmp_path)
    m.by_id = {"order-1": DIAG["retry-loop"]}
    r = c.get("/w/order-1")
    assert r.status_code == 200
    assert "Certificate of undeath" in r.text
    assert "temporal workflow terminate" in r.text
    assert "disabled" in r.text and "--allow-actions" in r.text


def test_actions_refused_without_flag_or_header(tmp_path):
    c, m = client(tmp_path)
    m.by_id = {"order-1": DIAG["retry-loop"]}
    assert c.post("/api/w/order-1/terminate").status_code == 400
    r = c.post("/api/w/order-1/terminate", headers={"X-Undertaker": "1"})
    assert r.status_code == 403


def test_unknown_workflow_404(tmp_path):
    c, _ = client(tmp_path)
    assert c.get("/w/nope").status_code == 404


def test_code_spans_escape_html():
    out = str(code_spans("run `<script>x</script>` now"))
    assert "<script>" not in out
    assert "<code>&lt;script&gt;" in out
