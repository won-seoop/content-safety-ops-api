from fastapi import APIRouter, Depends
from redis import Redis
from sqlalchemy.orm import Session

from app.core.cache import get_redis
from app.db.session import get_db
from app.schemas.moderation import ModerationCheckRequest, ModerationCheckResponse
from app.services.moderation import check_content

router = APIRouter(prefix="/api/moderations", tags=["moderations"])


@router.post("/check", response_model=ModerationCheckResponse)
def check_moderation(
    payload: ModerationCheckRequest,
    db: Session = Depends(get_db),
    cache: Redis = Depends(get_redis),
) -> ModerationCheckResponse:
    return check_content(db=db, cache=cache, payload=payload)

