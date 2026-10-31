"""The morgue: a FastAPI app on 127.0.0.1 with background sweeps and certificates."""

import asyncio
import re
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from markupsafe import Markup, escape

from undertaker.commands import fact_line, reader_for
from undertaker.config import Settings
from undertaker.diagnose.remedies import remedy
from undertaker.diagnose.rules import CAUSES, Diagnosis
from undertaker.explain.cache import CertCache
from undertaker.explain.certificate import template
from undertaker.explain.render import when, written_by
from undertaker.explain.source import excerpts
from undertaker.explain.writer import Written, write
from undertaker.sweep import sweep

HERE = Path(__file__).parent


def code_spans(text: str) -> Markup:
    """Escape text, then turn `code` into <code> elements."""
    safe = str(escape(text))
    return Markup(re.sub(r"`([^`]+)`", r"<code>\1</code>", safe))


class Morgue:
    """Sweep results and certificates, refreshed in the background."""

    def __init__(self, s: Settings) -> None:
        self.s = s
        self.reader = None
        self.results: list[Diagnosis] = []
        self.by_id: dict[str, Diagnosis] = {}
        self.certs: dict[str, Written] = {}
        self.swept_at: datetime | None = None
        self.error: str | None = None
        self.lock = asyncio.Lock()
        self.cache = CertCache(s.data_dir / "certificates.sqlite")
        self.writing = False
        self._writer: asyncio.Task | None = None
        self.cert_state: dict[tuple[str, str], tuple[int, str]] = {}

    async def sweep_now(self) -> None:
        """Run one sweep and remember the results."""
        async with self.lock:
            try:
                if self.reader is None:
                    self.reader = await reader_for(self.s)
                self.results = await sweep(self.reader, self.s.thresholds)
                self.by_id = {d.workflow_id: d for d in self.results}
                self.swept_at = datetime.now(UTC)
                self.error = None
            except BaseException as e:  # SystemExit from reader_for included
                self.error = f"Cannot sweep {self.s.address}: {type(e).__name__}"
                self.reader = None

    async def write_certs(self) -> None:
        """Write certificates for undead workflows whose state changed."""
        if self.writing:
            return
        self.writing = True
        try:
            for d in list(self.results):
                if not d.undead:
                    continue
                key = (d.workflow_id, d.run_id)
                state = (d.history_length, d.cause)
                if key in self.certs and self.cert_state.get(key) == state:
                    continue
                self.certs[key] = await asyncio.to_thread(write, d, self.s, self.cache)
                self.cert_state[key] = state
        finally:
            self.writing = False

    async def loop(self) -> None:
        """Sweep every --every; certificates are written alongside, one at a time."""
        while True:
            await self.sweep_now()
            if not self.writing:
                self._writer = asyncio.create_task(self.write_certs())
            await asyncio.sleep(self.s.every.total_seconds())

    def cert_for(self, d: Diagnosis) -> tuple[Written, bool]:
        """The latest certificate for a workflow; a template if none is written yet."""
        w = self.certs.get((d.workflow_id, d.run_id))
        if w:
            return w, False
        return Written(template(d), excerpts(d.frames, self.s.source)), True


def create_app(s: Settings, start_loop: bool = True) -> FastAPI:
    """Build the app.

    Args:
        s: Settings.
        start_loop: Start background sweeps on startup.

    Returns:
        The FastAPI app.
    """
    m = Morgue(s)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        task = asyncio.create_task(m.loop()) if start_loop else None
        yield
        if task:
            task.cancel()

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.state.morgue = m
    app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
    tpl = Jinja2Templates(directory=HERE / "templates")
    tpl.env.filters["code"] = code_spans
    tpl.env.filters["when"] = when
    tpl.env.globals["CAUSES"] = CAUSES

    def base_ctx(request: Request) -> dict:
        undead = sum(d.undead for d in m.results)
        return {
            "request": request,
            "s": s,
            "m": m,
            "undead": undead,
            "alive": len(m.results) - undead,
            "swept": m.swept_at.isoformat() if m.swept_at else "",
        }

    @app.get("/", response_class=HTMLResponse)
    async def morgue(request: Request):
        if m.swept_at is None:
            await m.sweep_now()
        counts = {c: sum(d.cause == c for d in m.results) for c in CAUSES}
        tags = [(d, fact_line(d)) for d in m.results]
        return tpl.TemplateResponse(
            request, "morgue.html", base_ctx(request) | {"counts": counts, "tags": tags}
        )

    @app.get("/w/{workflow_id}", response_class=HTMLResponse)
    async def certificate(request: Request, workflow_id: str):
        if m.swept_at is None:
            await m.sweep_now()
        d = m.by_id.get(workflow_id)
        if not d:
            raise HTTPException(404, "Not a running workflow. It may have been laid to rest.")
        w, pending = m.cert_for(d) if d.undead else (None, False)
        stale = bool(
            w
            and not pending
            and (w.cert.last_event_id != d.history_length or w.cert.attempt != d.pending_attempt)
        )
        ctx = base_ctx(request) | {
            "d": d,
            "w": w,
            "pending": pending,
            "stale": stale,
            "by": written_by(w) if w and not pending else "template certificate",
            "remedy": remedy(d, s.address, s.namespace) if d.undead else None,
            "fact": fact_line(d),
        }
        return tpl.TemplateResponse(request, "certificate.html", ctx)

    def _guard(request: Request) -> None:
        if request.headers.get("x-undertaker") != "1":
            raise HTTPException(400, "Missing header.")

    @app.post("/api/sweep")
    async def api_sweep(request: Request):
        _guard(request)
        await m.sweep_now()
        if not m.writing:
            m._writer = asyncio.create_task(m.write_certs())
        return {"undead": sum(d.undead for d in m.results), "error": m.error}

    @app.get("/api/state")
    async def api_state():
        return {
            "swept_at": m.swept_at.isoformat() if m.swept_at else None,
            "results": [d.to_dict() for d in m.results],
            "certificates": {k[0]: w.cert.to_dict() for k, w in m.certs.items()},
        }

    async def _act(request: Request, workflow_id: str, what: str):
        _guard(request)
        if not s.allow_actions:
            raise HTTPException(403, "Actions are off. Start serve with --allow-actions.")
        if workflow_id not in m.by_id:
            raise HTTPException(404, "Not a running workflow.")
        cause = m.by_id[workflow_id].cause
        try:
            if what == "terminate":
                await m.reader.terminate(workflow_id, f"laid to rest by undertaker ({cause})")
                out = {"ok": True, "message": f"{workflow_id} was laid to rest."}
            else:
                run = await m.reader.reset_last_task(
                    workflow_id, f"resurrected by undertaker ({cause})"
                )
                out = {"ok": True, "message": f"{workflow_id} was resurrected as run {run}."}
        except Exception as e:
            return JSONResponse({"ok": False, "message": f"{type(e).__name__}: {e}"[:300]}, 500)
        await m.sweep_now()
        return out

    @app.post("/api/w/{workflow_id}/terminate")
    async def api_terminate(request: Request, workflow_id: str):
        return await _act(request, workflow_id, "terminate")

    @app.post("/api/w/{workflow_id}/reset")
    async def api_reset(request: Request, workflow_id: str):
        return await _act(request, workflow_id, "reset")

    return app


async def serve(s: Settings, port: int) -> int:
    """Run the morgue on 127.0.0.1 until interrupted."""
    app = create_app(s)
    print(
        f"The morgue is open at http://127.0.0.1:{port}{' (actions on)' if s.allow_actions else ''}"
    )
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    await server.serve()
    return 0
