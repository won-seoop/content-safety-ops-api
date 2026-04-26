from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.moderation_log import ModerationLog
from app.models.rule import Rule
from app.schemas.moderation import ModerationLogResponse
from app.schemas.rule import RuleCreateRequest, RuleResponse, RuleStatusUpdateRequest

router = APIRouter(prefix="/api/ops", tags=["ops"])


@router.post("/rules", response_model=RuleResponse, status_code=201)
def create_rule(payload: RuleCreateRequest, db: Session = Depends(get_db)) -> Rule:
    exists = db.query(Rule).filter(Rule.rule_name == payload.rule_name).first()
    if exists:
        raise HTTPException(status_code=409, detail="ruleName already exists")

    rule = Rule(**payload.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.get("/rules", response_model=list[RuleResponse])
def list_rules(db: Session = Depends(get_db)) -> list[Rule]:
    return db.query(Rule).order_by(Rule.id.asc()).all()


@router.patch("/rules/{rule_id}/status", response_model=RuleResponse)
def update_rule_status(
    rule_id: int,
    payload: RuleStatusUpdateRequest,
    db: Session = Depends(get_db),
) -> Rule:
    rule = db.get(Rule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="rule not found")

    rule.enabled = payload.enabled
    db.commit()
    db.refresh(rule)
    return rule


@router.get("/moderation-logs", response_model=list[ModerationLogResponse])
def list_moderation_logs(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> list[ModerationLog]:
    return (
        db.query(ModerationLog)
        .order_by(ModerationLog.created_at.desc(), ModerationLog.id.desc())
        .offset(offset)
        .limit(min(limit, 100))
        .all()
    )

