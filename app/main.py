from fastapi import FastAPI

from app.api.moderations import router as moderations_router
from app.api.ops import router as ops_router

app = FastAPI(
    title="Content Safety Ops API",
    description="Rule based content moderation API for operations policy automation.",
    version="0.1.0",
)

app.include_router(moderations_router)
app.include_router(ops_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

