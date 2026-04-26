import asyncio
import time

import redis
from fastapi import APIRouter, Depends, HTTPException
from httpx import AsyncClient
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.metrics import metrics_registry
from app.db.session import engine
from app.db.session import get_db
from app.models.moderation_log import ModerationLog
from app.models.rule import Rule
from app.schemas.moderation import ModerationLogResponse
from app.schemas.rule import RuleCreateRequest, RuleResponse, RuleStatusUpdateRequest

router = APIRouter(prefix="/api/ops", tags=["ops"])


class LoadTestRequest(BaseModel):
    total_requests: int = Field(default=100, alias="totalRequests", ge=1, le=1000)
    concurrency: int = Field(default=10, ge=1, le=100)
    mode: str = Field(default="cached", pattern="^(cached|unique)$")


class LoadTestResponse(BaseModel):
    total_requests: int = Field(alias="totalRequests")
    concurrency: int
    mode: str
    success_count: int = Field(alias="successCount")
    error_count: int = Field(alias="errorCount")
    total_duration_ms: float = Field(alias="totalDurationMs")
    requests_per_second: float = Field(alias="requestsPerSecond")
    avg_latency_ms: float = Field(alias="avgLatencyMs")
    p95_latency_ms: float = Field(alias="p95LatencyMs")
    min_latency_ms: float = Field(alias="minLatencyMs")
    max_latency_ms: float = Field(alias="maxLatencyMs")


def get_db_pool_metrics() -> dict[str, int | str]:
    pool = engine.pool

    def call_metric(name: str) -> int | str:
        metric = getattr(pool, name, None)
        if not callable(metric):
            return "n/a"
        try:
            return metric()
        except Exception:
            return "n/a"

    return {
        "class": pool.__class__.__name__,
        "size": call_metric("size"),
        "checkedIn": call_metric("checkedin"),
        "checkedOut": call_metric("checkedout"),
        "overflow": call_metric("overflow"),
    }


def get_redis_ping_ms() -> float | None:
    client = redis.Redis.from_url(get_settings().redis_url, decode_responses=True)
    started_at = time.perf_counter()
    try:
        client.ping()
        return round((time.perf_counter() - started_at) * 1000, 2)
    except Exception:
        return None
    finally:
        client.close()


def build_bottleneck_hints(metrics: dict, db_pool: dict, redis_ping_ms: float | None) -> list[str]:
    hints = []
    if metrics["p95LatencyMs"] >= 500:
        hints.append("API p95 지연이 500ms 이상입니다. DB 쿼리, Redis 연결, 동시 요청 수를 우선 확인하세요.")
    if metrics["errorRate"] >= 0.01:
        hints.append("5xx 에러율이 1% 이상입니다. 애플리케이션 로그와 DB/Redis 연결 실패 여부를 확인하세요.")
    if isinstance(db_pool["size"], int) and isinstance(db_pool["checkedOut"], int):
        if db_pool["size"] > 0 and db_pool["checkedOut"] >= db_pool["size"]:
            hints.append("DB checked-out 커넥션이 pool size에 도달했습니다. 커넥션풀 부족 또는 느린 쿼리 가능성이 있습니다.")
    if isinstance(db_pool["overflow"], int) and db_pool["overflow"] > 0:
        hints.append("DB pool overflow가 발생했습니다. 순간 동시성이 pool size를 초과했습니다.")
    if redis_ping_ms is None:
        hints.append("Redis ping 실패가 감지되었습니다. 캐시 장애 시 DB 룰 조회 부하가 증가할 수 있습니다.")
    elif redis_ping_ms >= 100:
        hints.append("Redis ping 지연이 100ms 이상입니다. 캐시 응답 지연이 API p95에 영향을 줄 수 있습니다.")
    if metrics["memoryRssMb"] >= 300:
        hints.append("프로세스 RSS 메모리가 300MB 이상입니다. 부하 중 지속 증가하면 OOM 위험을 확인하세요.")
    if not hints:
        hints.append("현재 수집된 지표에서는 명확한 병목 신호가 없습니다.")
    return hints


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


@router.get("/metrics")
def get_ops_metrics() -> dict:
    metrics = metrics_registry.snapshot()
    db_pool = get_db_pool_metrics()
    redis_ping_ms = get_redis_ping_ms()
    return {
        **metrics,
        "dbPool": db_pool,
        "redis": {
            "pingMs": redis_ping_ms,
            "status": "ok" if redis_ping_ms is not None else "error",
        },
        "bottleneckHints": build_bottleneck_hints(metrics, db_pool, redis_ping_ms),
    }


@router.post("/load-test", response_model=LoadTestResponse)
async def run_load_test(payload: LoadTestRequest) -> LoadTestResponse:
    semaphore = asyncio.Semaphore(payload.concurrency)
    latencies: list[float] = []
    statuses: list[int | None] = []

    async def send_request(client: AsyncClient, index: int) -> None:
        suffix = "" if payload.mode == "cached" else f" #{index}"
        request_body = {
            "userId": 1 + (index % 10),
            "title": f"아이폰 싸게 팝니다{suffix}",
            "content": f"선입금하면 택배 보내드려요. 카톡 주세요.{suffix}",
            "price": 100000,
            "category": "DIGITAL",
        }

        async with semaphore:
            started_at = time.perf_counter()
            try:
                response = await client.post("/api/moderations/check", json=request_body)
                statuses.append(response.status_code)
            except Exception:
                statuses.append(None)
            finally:
                latencies.append((time.perf_counter() - started_at) * 1000)

    started_at = time.perf_counter()
    async with AsyncClient(base_url="http://127.0.0.1:8000", timeout=10.0) as client:
        await asyncio.gather(
            *(send_request(client, index) for index in range(payload.total_requests))
        )
    total_duration_ms = (time.perf_counter() - started_at) * 1000

    sorted_latencies = sorted(latencies)
    p95_index = max(0, int(len(sorted_latencies) * 0.95) - 1)
    success_count = sum(1 for status in statuses if status and 200 <= status < 300)
    error_count = payload.total_requests - success_count

    return LoadTestResponse(
        totalRequests=payload.total_requests,
        concurrency=payload.concurrency,
        mode=payload.mode,
        successCount=success_count,
        errorCount=error_count,
        totalDurationMs=round(total_duration_ms, 2),
        requestsPerSecond=round(payload.total_requests / (total_duration_ms / 1000), 2),
        avgLatencyMs=round(sum(latencies) / len(latencies), 2),
        p95LatencyMs=round(sorted_latencies[p95_index], 2),
        minLatencyMs=round(sorted_latencies[0], 2),
        maxLatencyMs=round(sorted_latencies[-1], 2),
    )
