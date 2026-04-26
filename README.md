# content-safety-ops-api

당근 운영개발팀 전환형 인턴 지원용 백엔드 포트폴리오 프로젝트입니다. 사용자가 작성한 게시글을 운영정책 룰 기반으로 자동 검수하고, 스팸/사기/어뷰징 위험도를 계산해 `ALLOW`, `REVIEW`, `BLOCK` 중 하나로 판정합니다.

## 문제 상황

운영팀은 매일 많은 게시글을 검수해야 하고, 반복적인 정책 위반 키워드 탐지와 위험도 판단은 수작업으로 처리하면 속도와 일관성이 떨어집니다. 특히 선입금, 외부 연락 유도, 불법 거래 같은 패턴은 빠르게 감지해 운영자가 우선순위를 잡을 수 있어야 합니다.

## 선택한 해결 방법

- 운영정책 룰을 DB에 저장하고 활성화된 룰만 검수에 사용합니다.
- 제목과 본문에서 키워드를 매칭하고 룰 점수를 합산해 위험도를 계산합니다.
- 점수 기준은 `0~39 ALLOW`, `40~79 REVIEW`, `80 이상 BLOCK`입니다.
- `title + content + price + category` 조합의 SHA-256 해시를 Redis key로 사용해 동일 콘텐츠 재검수는 5분 동안 캐시 응답합니다.
- 검수 결과와 매칭된 룰은 PostgreSQL에 로그로 저장합니다.

## 기술 스택

- Python 3.11+
- FastAPI
- PostgreSQL
- SQLAlchemy
- Alembic
- Pydantic
- Redis
- Docker Compose
- pytest

## 시스템 흐름

1. 클라이언트가 `POST /api/moderations/check`로 콘텐츠를 전송합니다.
2. 서버가 `title + content + price + category`로 `contentHash`를 생성합니다.
3. Redis에서 `moderation:content:{contentHash}` key를 조회합니다.
4. cache hit이면 룰 계산과 DB 조회 없이 즉시 응답합니다.
5. cache miss이면 활성화된 룰을 DB에서 조회해 키워드를 매칭합니다.
6. 위험 점수와 판정을 계산합니다.
7. 검수 로그를 PostgreSQL에 저장하고 Redis에 5분 TTL로 결과를 저장합니다.

## ERD 설명

### rules

운영정책 룰을 저장합니다.

| 필드 | 설명 |
| --- | --- |
| id | 룰 ID |
| ruleName | 룰 이름 |
| keyword | 감지 키워드 |
| score | 위험 점수 |
| action | 기본 액션 힌트 |
| category | 정책 카테고리 |
| enabled | 룰 활성화 여부 |
| createdAt | 생성 시각 |
| updatedAt | 수정 시각 |

### moderation_logs

검수 요청의 판정 결과를 저장합니다.

| 필드 | 설명 |
| --- | --- |
| id | 로그 ID |
| userId | 작성자 ID |
| title | 게시글 제목 |
| contentHash | 콘텐츠 해시 |
| riskScore | 위험 점수 |
| decision | 최종 판정 |
| matchedRules | 매칭된 룰 이름 목록 |
| reason | 판정 사유 |
| createdAt | 생성 시각 |

## API 명세

FastAPI 자동 문서는 실행 후 `http://localhost:8000/docs`에서 확인할 수 있습니다.

### 콘텐츠 검수

`POST /api/moderations/check`

```json
{
  "userId": 1,
  "title": "아이폰 싸게 팝니다",
  "content": "선입금하면 택배 보내드려요. 카톡 주세요.",
  "price": 100000,
  "category": "DIGITAL"
}
```

```json
{
  "decision": "REVIEW",
  "riskScore": 70,
  "matchedRules": ["PREPAYMENT_KEYWORD", "EXTERNAL_CONTACT_KAKAO"],
  "reason": "운영정책상 검토가 필요한 키워드가 감지되었습니다."
}
```

### 운영정책 룰 관리

- `POST /api/ops/rules`
- `GET /api/ops/rules`
- `PATCH /api/ops/rules/{id}/status`

### 검수 로그 조회

- `GET /api/ops/moderation-logs?limit=50&offset=0`

## 실행 방법

```bash
docker compose up --build
```

앱 컨테이너 시작 시 Alembic migration을 적용하고 초기 seed rule을 저장합니다.

## 테스트 방법

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest
```

테스트는 SQLite와 fake Redis를 사용해 외부 서비스 없이 실행됩니다.

## Redis 캐싱 전략

- hash source: `title + content + price + category`
- hash algorithm: SHA-256
- Redis key: `moderation:content:{contentHash}`
- TTL: 5분
- cache hit: 룰 계산과 DB 조회를 생략하고 캐시된 검수 응답 반환
- cache miss: DB 룰 기반 검수, 로그 저장, Redis 저장

## 당근 운영개발팀 JD와의 연결점

- 운영정책을 데이터화해 반복 검수를 자동화합니다.
- 운영자가 룰을 추가/비활성화할 수 있는 API를 제공합니다.
- 검수 로그를 남겨 운영 판단 근거와 사후 분석이 가능합니다.
- Redis 캐싱으로 동일 콘텐츠 재검수 비용을 낮춥니다.
- 실제 AI 호출 없이도 운영 자동화의 기본 흐름을 실행 가능한 API로 구현했습니다.

## 확장 방향

- pgvector 기반 유사 위험 문구 탐지
- AI 보조 판단
- 신고 시스템 연동
- Slack/Discord 장애 알림
- 운영자 관리자 화면

## 주요 curl 예시

```bash
curl -X POST http://localhost:8000/api/moderations/check \
  -H "Content-Type: application/json" \
  -d '{
    "userId": 1,
    "title": "아이폰 싸게 팝니다",
    "content": "선입금하면 택배 보내드려요. 카톡 주세요.",
    "price": 100000,
    "category": "DIGITAL"
  }'
```

```bash
curl http://localhost:8000/api/ops/rules
```

```bash
curl -X POST http://localhost:8000/api/ops/rules \
  -H "Content-Type: application/json" \
  -d '{
    "ruleName": "WIRE_TRANSFER_KEYWORD",
    "keyword": "송금",
    "score": 30,
    "action": "REVIEW",
    "category": "FRAUD",
    "enabled": true
  }'
```

```bash
curl -X PATCH http://localhost:8000/api/ops/rules/1/status \
  -H "Content-Type: application/json" \
  -d '{"enabled": false}'
```

```bash
curl "http://localhost:8000/api/ops/moderation-logs?limit=20&offset=0"
```

