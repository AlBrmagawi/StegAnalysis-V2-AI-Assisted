from __future__ import annotations

import asyncio
import json
import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

import httpx
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .assistant import ProviderResponseError, answer, disclosure, provider_health
from .db import Store
from .engine import REGISTRY, create_job, load_analyzers
from .jobs import TERMINAL, JobManager
from .models import AnalysisRequest, AssistantRequest, CaseInput, CaseUpdate, Review
from .reports import html_report, report_data
from .storage import CaseCapacityError, artifact_path, ingest
from .tools import doctor

MAX_UPLOAD = 32 * 1024 * 1024


class BodyLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        total = 0

        async def limited_receive():
            nonlocal total
            message = await receive()
            total += len(message.get("body", b""))
            if total > MAX_UPLOAD + 1024 * 1024:
                raise HTTPException(413, "Request body exceeds upload limit")
            return message

        await self.app(scope, limited_receive, send)


def create_app(data_dir: Path | None = None, *, start_worker: bool = True) -> FastAPI:
    store = Store(data_dir or Path(os.getenv("STEG_DATA_DIR", ".data")))
    manager = JobManager(store)
    queue_lock = threading.Lock()

    @asynccontextmanager
    async def lifespan(app):
        if start_worker:
            manager.start()
        yield
        if start_worker:
            manager.close()

    app = FastAPI(title="StegAnalysis local workbench", version=__version__, lifespan=lifespan)
    app.state.store = store
    app.state.manager = manager
    app.add_middleware(BodyLimit)

    @app.middleware("http")
    async def local_boundary(request: Request, call_next):
        if request.url.hostname not in {"localhost", "127.0.0.1", "::1", "testserver"}:
            return JSONResponse({"detail": "Only loopback hosts are allowed"}, status_code=403)
        origin = request.headers.get("origin")
        if request.headers.get("sec-fetch-site") == "cross-site":
            return JSONResponse({"detail": "Cross-site access is not accepted"}, status_code=403)
        if origin and origin != str(request.base_url).rstrip("/"):
            return JSONResponse(
                {"detail": "Cross-origin requests are not accepted; use the same-origin development proxy"},
                status_code=403,
            )
        if request.url.path.startswith("/api") and request.method not in ("GET", "HEAD", "OPTIONS"):
            if request.headers.get("x-steganalysis") != "local":
                return JSONResponse({"detail": "Missing local client header"}, status_code=403)
        length = request.headers.get("content-length")
        if length and (not length.isdigit() or int(length) > MAX_UPLOAD + 1024 * 1024):
            return JSONResponse({"detail": "Request too large"}, status_code=413)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Cache-Control"] = "no-store"
        if "text/html" in response.headers.get("content-type", "") and not request.url.path.startswith(
            "/docs"
        ):
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
            )
        return response

    @app.exception_handler(KeyError)
    async def missing(request, exc):
        return JSONResponse({"detail": "Record not found in this case"}, status_code=404)

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=400)

    @app.exception_handler(CaseCapacityError)
    async def case_full(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=409)

    @app.get("/api/health")
    def health():
        load_analyzers()
        return {
            "application": "StegAnalysis",
            "version": __version__,
            "mode": "single-user local",
            "analyzers": [a.describe() for a in REGISTRY],
            "providers": provider_health(),
            "ml": {
                "available": bool(os.getenv("STEG_ML_MODEL") and Path(os.environ["STEG_ML_MODEL"]).is_file()),
                "experimental": True,
            },
            "limits": {"upload_bytes": MAX_UPLOAD, "workers": 1, "queue": 8},
            "doctor": doctor(),
        }

    @app.get("/api/cases")
    def cases():
        artifacts, findings = store.list("artifacts"), store.list("findings")
        return [
            {
                **c,
                "evidence_count": sum(a["case_id"] == c["id"] and a["role"] == "original" for a in artifacts),
                "finding_count": sum(f["case_id"] == c["id"] for f in findings),
            }
            for c in reversed(store.list("cases"))
        ]

    @app.post("/api/cases", status_code=201)
    def new_case(data: CaseInput):
        return store.create_case(data.name.strip() or "Untitled investigation", data.description)

    @app.get("/api/cases/{case_id}")
    def get_case(case_id: str):
        return store.snapshot(case_id)

    @app.patch("/api/cases/{case_id}")
    def update_case(case_id: str, data: CaseUpdate):
        return store.patch("cases", case_id, **data.model_dump(exclude_unset=True))

    @app.post("/api/cases/{case_id}/evidence", status_code=201)
    async def upload(case_id: str, file: Annotated[UploadFile, File()]):
        store.get("cases", case_id)
        try:
            content = await file.read(MAX_UPLOAD + 1)
            if len(content) > MAX_UPLOAD:
                raise HTTPException(413, "Evidence exceeds the 32 MiB file limit")
            return ingest(store, case_id, content, file.filename or "evidence.bin", max_originals=128)
        finally:
            await file.close()

    @app.get("/api/cases/{case_id}/artifacts/{artifact_id}/content")
    def content(case_id: str, artifact_id: str, download: bool = False):
        artifact = store.get("artifacts", artifact_id, case_id)
        safe_inline = artifact["mime"] in ("image/png", "image/jpeg", "image/bmp", "audio/wav", "text/plain")
        return FileResponse(
            artifact_path(store, artifact),
            media_type=artifact["mime"] if safe_inline else "application/octet-stream",
            filename=artifact["name"],
            content_disposition_type="attachment" if download or not safe_inline else "inline",
        )

    @app.get("/api/cases/{case_id}/artifacts/{artifact_id}/preview")
    def preview(case_id: str, artifact_id: str):
        artifact = store.get("artifacts", artifact_id, case_id)
        with artifact_path(store, artifact).open("rb") as stream:
            data = stream.read(65536)
        if artifact["kind"] == "text":
            return {"text": data.decode("utf-8", "replace"), "truncated": artifact["size"] > len(data)}
        return {"hex": data[:4096].hex(" "), "truncated": artifact["size"] > 4096}

    @app.post("/api/cases/{case_id}/jobs", status_code=202)
    def analyze(case_id: str, data: AnalysisRequest):
        with queue_lock:
            if len([j for j in store.list("jobs") if j["status"] in ("queued", "running")]) >= 8:
                raise HTTPException(429, "Analysis queue is full; wait or cancel a queued job")
            return create_job(store, case_id, data.artifact_ids, data.profile, data.budget)

    @app.post("/api/cases/{case_id}/jobs/{job_id}/cancel")
    def cancel(case_id: str, job_id: str):
        job = store.get("jobs", job_id, case_id)
        return job if job["status"] in TERMINAL else store.patch("jobs", job_id, cancel_requested=True)

    @app.get("/api/cases/{case_id}/jobs/{job_id}/events")
    async def events(case_id: str, job_id: str, request: Request, after: int = 0):
        store.get("jobs", job_id, case_id)
        last = request.headers.get("last-event-id", "")
        if last.isdigit():
            after = max(after, int(last))

        async def stream():
            cursor = after
            while not await request.is_disconnected():
                rows = store.events(job_id, cursor)
                for event in rows:
                    cursor = event["seq"]
                    yield f"id: {cursor}\nevent: progress\ndata: {json.dumps(event)}\n\n"
                if store.get("jobs", job_id)["status"] in TERMINAL and len(rows) < 300:
                    yield "event: done\ndata: {}\n\n"
                    break
                yield ": keep-alive\n\n"
                await asyncio.sleep(0.5)

        return StreamingResponse(
            stream(), media_type="text/event-stream", headers={"X-Accel-Buffering": "no"}
        )

    @app.patch("/api/cases/{case_id}/findings/{finding_id}")
    def review(case_id: str, finding_id: str, data: Review):
        store.get("findings", finding_id, case_id)
        return store.patch("findings", finding_id, review=data.model_dump())

    @app.post("/api/cases/{case_id}/assistant/preview")
    def assistant_preview(case_id: str, data: AssistantRequest):
        return disclosure(store, case_id, data)

    @app.post("/api/cases/{case_id}/assistant")
    async def assistant_answer(case_id: str, data: AssistantRequest):
        try:
            return await answer(store, case_id, data)
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from exc
        except httpx.TimeoutException as exc:
            raise HTTPException(504, "Provider timed out. Retry or use the deterministic guide.") from exc
        except httpx.HTTPStatusError as exc:
            detail = (
                "Provider quota/rate limit reached"
                if exc.response.status_code == 429
                else f"Provider returned HTTP {exc.response.status_code}"
            )
            raise HTTPException(502, detail) from exc
        except (httpx.HTTPError, ProviderResponseError, KeyError, json.JSONDecodeError) as exc:
            raise HTTPException(
                502, "Provider failed or returned invalid output. No answer was accepted."
            ) from exc

    @app.get("/api/cases/{case_id}/report.json")
    def export_json(case_id: str):
        return Response(
            json.dumps(report_data(store, case_id), indent=2, ensure_ascii=True),
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="steganalysis-report.json"'},
        )

    @app.get("/api/cases/{case_id}/report.html")
    def export_html(case_id: str):
        return HTMLResponse(
            html_report(store, case_id),
            headers={"Content-Disposition": 'attachment; filename="steganalysis-report.html"'},
        )

    distribution = Path(
        os.getenv("STEG_FRONTEND_DIR", str(Path(__file__).resolve().parents[1] / "frontend" / "dist"))
    )
    if (distribution / "assets").exists():
        app.mount("/assets", StaticFiles(directory=distribution / "assets"), name="assets")

    @app.get("/{path:path}")
    def frontend(path: str):
        if path.startswith("api/"):
            raise HTTPException(404, "Unknown API route")
        index = distribution / "index.html"
        if index.exists():
            return FileResponse(index, media_type="text/html")
        return HTMLResponse(
            "<h1>StegAnalysis API is running</h1><p>Build the frontend: cd frontend &amp;&amp; npm ci &amp;&amp; npm run build</p>"
        )

    return app


def app_factory() -> FastAPI:
    return create_app()
