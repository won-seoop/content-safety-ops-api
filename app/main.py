from pathlib import Path

from fastapi import FastAPI, Response
from fastapi.responses import HTMLResponse

from app.api.moderations import router as moderations_router
from app.api.ops import router as ops_router

app = FastAPI(
    title="Content Safety Ops API",
    description="Rule based content moderation API for operations policy automation.",
    version="0.1.0",
)

app.include_router(moderations_router)
app.include_router(ops_router)


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return Path("app/static/index.html").read_text(encoding="utf-8")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    return Response(status_code=204)
