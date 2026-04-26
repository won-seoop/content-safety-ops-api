import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.cache import get_redis
from app.db.seed import seed_rules
from app.db.session import Base, get_db
from app.main import app


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.get_calls = 0
        self.setex_calls = 0

    def get(self, key: str) -> str | None:
        self.get_calls += 1
        return self.store.get(key)

    def setex(self, key: str, ttl: int, value: str) -> bool:
        self.setex_calls += 1
        self.store[key] = value
        return True

    def close(self) -> None:
        return None


@pytest.fixture
def db_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    seed_rules(db)
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def fake_redis() -> FakeRedis:
    return FakeRedis()


@pytest.fixture
def client(db_session: Session, fake_redis: FakeRedis) -> TestClient:
    def override_db():
        yield db_session

    def override_redis():
        yield fake_redis

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_redis] = override_redis
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

