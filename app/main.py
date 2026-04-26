from pathlib import Path
import time

from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse

from app.api.moderations import router as moderations_router
from app.api.ops import router as ops_router
from app.core.metrics import metrics_registry

app = FastAPI(
    title="Content Safety Ops API",
    description="Rule based content moderation API for operations policy automation.",
    version="0.1.0",
)

app.include_router(moderations_router)
app.include_router(ops_router)


@app.middleware("http")
async def collect_metrics(request: Request, call_next):
    started_at = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        latency_ms = (time.perf_counter() - started_at) * 1000
        metrics_registry.record(
            request.method,
            request.url.path,
            status_code,
            latency_ms,
        )


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return Path("app/static/index.html").read_text(encoding="utf-8")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    return Response(status_code=204)
