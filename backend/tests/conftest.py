import hashlib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import Session

from backend.db import Base, get_db
from backend.main import app
from backend.models import Bus


TEST_API_KEY = "test-bus-api-key"
TEST_READ_TOKEN = "test-read-token"
TEST_ADMIN_TOKEN = "test-admin-token"


@pytest.fixture(scope="session")
def test_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return engine


@pytest.fixture()
def db_session(test_engine):
    with Session(test_engine) as session:
        yield session


@pytest.fixture()
def client(test_engine, monkeypatch):
    def override_get_db():
        with Session(test_engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    monkeypatch.setenv("READ_TOKEN", TEST_READ_TOKEN)
    monkeypatch.setenv("ADMIN_TOKEN", TEST_ADMIN_TOKEN)

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture()
def bus(db_session):
    bus = Bus(
        bus_id="TEST-BUS-001",
        camera_id="TEST-CAM-001",
        route_id="TEST-R-01",
        api_key_hash=hashlib.sha256(
            TEST_API_KEY.encode("utf-8")
        ).hexdigest(),
    )
    db_session.add(bus)
    db_session.commit()
    db_session.refresh(bus)

    yield bus

    db_session.rollback()
    db_session.query(Bus).filter(Bus.bus_id == bus.bus_id).delete()
    db_session.commit()
