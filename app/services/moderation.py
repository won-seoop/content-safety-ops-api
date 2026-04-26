import hashlib
import json

from redis import Redis
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.moderation_log import ModerationLog
from app.models.rule import Rule
from app.schemas.moderation import ModerationCheckRequest, ModerationCheckResponse


def build_content_hash(payload: ModerationCheckRequest) -> str:
    source = f"{payload.title}|{payload.content}|{payload.price}|{payload.category}"
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def decide(risk_score: int) -> str:
    if risk_score >= 80:
        return "BLOCK"
    if risk_score >= 40:
        return "REVIEW"
    return "ALLOW"


def build_reason(decision: str, matched_rules: list[str]) -> str:
    if not matched_rules:
        return "운영정책 위반 키워드가 감지되지 않았습니다."
    if decision == "BLOCK":
        return "차단 기준에 해당하는 운영정책 위반 키워드가 감지되었습니다."
    return "운영정책상 검토가 필요한 키워드가 감지되었습니다."


def check_content(
    db: Session,
    cache: Redis,
    payload: ModerationCheckRequest,
) -> ModerationCheckResponse:
    content_hash = build_content_hash(payload)
    cache_key = f"moderation:content:{content_hash}"

    cached = cache.get(cache_key)
    if cached:
        return ModerationCheckResponse.model_validate_json(cached)

    target_text = f"{payload.title}\n{payload.content}".lower()
    rules = db.query(Rule).filter(Rule.enabled.is_(True)).all()
    matched_rules = [rule.rule_name for rule in rules if rule.keyword.lower() in target_text]
    risk_score = sum(rule.score for rule in rules if rule.rule_name in matched_rules)
    decision = decide(risk_score)
    reason = build_reason(decision, matched_rules)

    response = ModerationCheckResponse(
        decision=decision,
        riskScore=risk_score,
        matchedRules=matched_rules,
        reason=reason,
    )

    db.add(
        ModerationLog(
            user_id=payload.user_id,
            title=payload.title,
            content_hash=content_hash,
            risk_score=risk_score,
            decision=decision,
            matched_rules=matched_rules,
            reason=reason,
        )
    )
    db.commit()

    cache.setex(
        cache_key,
        get_settings().redis_ttl_seconds,
        json.dumps(response.model_dump(by_alias=True), ensure_ascii=False),
    )
    return response

