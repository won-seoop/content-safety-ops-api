from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.moderation_log import ModerationLog
from app.models.rule import Rule
from tests.conftest import FakeRedis


def post_check(client: TestClient, title: str, content: str, price: int = 100000):
    return client.post(
        "/api/moderations/check",
        json={
            "userId": 1,
            "title": title,
            "content": content,
            "price": price,
            "category": "DIGITAL",
        },
    )


def test_normal_content_is_allow(client: TestClient):
    response = post_check(client, "아이폰 판매합니다", "직거래 가능합니다.")

    assert response.status_code == 200
    assert response.json()["decision"] == "ALLOW"
    assert response.json()["riskScore"] == 0
    assert response.json()["matchedRules"] == []


def test_prepayment_keyword_is_review(client: TestClient):
    response = post_check(client, "아이폰 판매합니다", "선입금하면 택배 보내드려요.")

    assert response.status_code == 200
    assert response.json()["decision"] == "REVIEW"
    assert response.json()["riskScore"] == 40
    assert response.json()["matchedRules"] == ["PREPAYMENT_KEYWORD"]


def test_multiple_review_keywords_reach_block_threshold(client: TestClient):
    response = post_check(client, "아이폰 급처", "선입금 후 카톡으로 계좌 보내드려요.")

    assert response.status_code == 200
    assert response.json()["decision"] == "BLOCK"
    assert response.json()["riskScore"] == 120
    assert set(response.json()["matchedRules"]) == {
        "PREPAYMENT_KEYWORD",
        "EXTERNAL_CONTACT_KAKAO",
        "BANK_ACCOUNT_KEYWORD",
        "TOO_CHEAP_KEYWORD",
    }


def test_illegal_keyword_is_block(client: TestClient):
    response = post_check(client, "불법 물품", "거래합니다.")

    assert response.status_code == 200
    assert response.json()["decision"] == "BLOCK"
    assert response.json()["riskScore"] == 80
    assert response.json()["matchedRules"] == ["ILLEGAL_KEYWORD"]


def test_same_content_uses_redis_cache(
    client: TestClient,
    db_session: Session,
    fake_redis: FakeRedis,
):
    first = post_check(client, "아이폰 판매", "선입금하면 카톡 주세요.")
    assert first.status_code == 200
    assert first.json()["riskScore"] == 70
    assert fake_redis.setex_calls == 1

    db_session.query(Rule).delete()
    db_session.commit()

    second = post_check(client, "아이폰 판매", "선입금하면 카톡 주세요.")
    assert second.status_code == 200
    assert second.json() == first.json()
    assert fake_redis.get_calls == 2
    assert fake_redis.setex_calls == 1
    assert db_session.query(ModerationLog).count() == 1

