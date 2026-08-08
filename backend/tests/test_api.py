from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from kitchen_almanac.catalog import DEFAULT_SOURCE, build_catalog
from kitchen_almanac.database import Base, get_session
from kitchen_almanac.main import app
from kitchen_almanac.services.catalog_repository import load_catalog


def test_health() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "kitchen-almanac-api",
        "version": "0.1.0",
    }


def test_crop_list_uses_active_catalog() -> None:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        load_catalog(session, build_catalog(DEFAULT_SOURCE))

    def test_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = test_session
    try:
        response = TestClient(app).get("/api/crops?category=perennial")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["dataset_id"].startswith("kitchen-almanac-v1-")
    assert [crop["canonical_name"] for crop in payload["crops"]] == [
        "Artichokes",
        "Asparagus",
    ]
