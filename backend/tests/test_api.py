from __future__ import annotations

from collections.abc import Iterator
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from kitchen_almanac.catalog import DEFAULT_SOURCE, build_catalog
from kitchen_almanac.database import Base, get_session, make_engine
from kitchen_almanac.main import app
from kitchen_almanac.services.catalog_repository import load_catalog


@pytest.fixture
def catalog_client() -> Iterator[TestClient]:
    engine = make_engine(
        "sqlite:///:memory:",
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
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def garden_profile(catalog_client: TestClient) -> dict[str, object]:
    response = catalog_client.post(
        "/api/garden-profiles",
        json={
            "name": "Backyard garden",
            "postal_code": "20910-1234",
            "target_year": date.today().year + 1,
            "experience_level": "beginner",
            "growing_methods": ["containers", "raised_bed"],
        },
    )
    assert response.status_code == 201
    return response.json()


def test_health() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "kitchen-almanac-api",
        "version": "0.1.0",
    }


def test_crop_list_uses_active_catalog(catalog_client: TestClient) -> None:
    response = catalog_client.get("/api/crops?category=perennial")

    assert response.status_code == 200
    payload = response.json()
    assert payload["dataset_id"].startswith("kitchen-almanac-v1-")
    assert [crop["canonical_name"] for crop in payload["crops"]] == [
        "Artichokes",
        "Asparagus",
    ]


def test_garden_profile_captures_location_and_growing_context(
    catalog_client: TestClient,
) -> None:
    response = catalog_client.post(
        "/api/garden-profiles",
        json={
            "name": "  Patio pots  ",
            "postal_code": "20910-1234",
            "target_year": date.today().year,
            "experience_level": "intermediate",
            "growing_methods": ["containers", "containers", "in_ground"],
        },
    )

    assert response.status_code == 201
    profile = response.json()
    assert profile["name"] == "Patio pots"
    assert profile["location_input"] == "20910-1234"
    assert profile["postal_code"] == "20910"
    assert profile["latitude"] is None
    assert profile["location_status"] == "postal_code_pending"
    assert profile["growing_methods"] == ["in_ground", "containers"]

    fetched = catalog_client.get(f"/api/garden-profiles/{profile['id']}")
    assert fetched.status_code == 200
    assert fetched.json() == profile


def test_garden_profile_accepts_coordinates(catalog_client: TestClient) -> None:
    response = catalog_client.post(
        "/api/garden-profiles",
        json={
            "latitude": 38.9907,
            "longitude": -77.0261,
            "growing_methods": ["raised_bed"],
        },
    )

    assert response.status_code == 201
    profile = response.json()
    assert profile["postal_code"] is None
    assert profile["location_input"] == "38.990700,-77.026100"
    assert profile["location_status"] == "coordinates_provided"


@pytest.mark.parametrize(
    "payload",
    [
        {"postal_code": "not-a-zip", "growing_methods": ["containers"]},
        {"latitude": 38.9, "growing_methods": ["containers"]},
        {"postal_code": "20910", "growing_methods": []},
        {
            "postal_code": "20910",
            "target_year": date.today().year - 1,
            "growing_methods": ["containers"],
        },
    ],
)
def test_garden_profile_rejects_invalid_context(
    catalog_client: TestClient,
    payload: dict[str, object],
) -> None:
    response = catalog_client.post("/api/garden-profiles", json=payload)

    assert response.status_code == 422


def test_wishlist_resolves_aliases_and_preserves_uncertain_entries(
    catalog_client: TestClient,
    garden_profile: dict[str, object],
) -> None:
    response = catalog_client.post(
        "/api/wishlists",
        json={
            "text": "Tomato\nbeans\nDragon fruit\nzucchini\nTomato",
            "garden_profile_id": garden_profile["id"],
        },
    )

    assert response.status_code == 201
    wishlist = response.json()
    assert wishlist["garden_profile_id"] == garden_profile["id"]
    entries = wishlist["entries"]
    assert [entry["original_text"] for entry in entries] == [
        "Tomato",
        "beans",
        "Dragon fruit",
        "zucchini",
        "Tomato",
    ]
    assert entries[0]["status"] == "resolved"
    assert entries[0]["resolved_crop"]["canonical_name"] == "Tomatoes"
    assert entries[1]["status"] == "needs_confirmation"
    assert [candidate["canonical_name"] for candidate in entries[1]["candidates"]] == [
        "Fava Beans",
        "Shell Beans",
        "String Beans",
    ]
    assert entries[2]["status"] == "unresolved"
    assert entries[3]["resolved_crop"]["canonical_name"] == "Summer Squash"
    assert entries[4]["original_text"] == "Tomato"


def test_wishlist_entries_can_be_confirmed_or_kept_custom(
    catalog_client: TestClient,
    garden_profile: dict[str, object],
) -> None:
    created = catalog_client.post(
        "/api/wishlists",
        json={
            "text": "beans\nDragon fruit",
            "garden_profile_id": garden_profile["id"],
        },
    ).json()
    beans, dragon_fruit = created["entries"]

    confirmed_response = catalog_client.patch(
        f"/api/wishlists/{created['id']}/entries/{beans['id']}",
        json={"crop_slug": "string-beans"},
    )
    assert confirmed_response.status_code == 200
    confirmed = confirmed_response.json()
    confirmed_beans = confirmed["entries"][0]
    assert confirmed_beans["status"] == "resolved"
    assert confirmed_beans["resolution_method"] == "user_confirmed"
    assert confirmed_beans["resolved_crop"]["canonical_name"] == "String Beans"
    assert confirmed_beans["original_text"] == "beans"

    reverted_response = catalog_client.patch(
        f"/api/wishlists/{created['id']}/entries/{beans['id']}",
        json={"keep_custom": True},
    )
    reverted = reverted_response.json()["entries"][0]
    assert reverted["status"] == "custom"
    assert reverted["resolved_crop"] is None

    custom_response = catalog_client.patch(
        f"/api/wishlists/{created['id']}/entries/{dragon_fruit['id']}",
        json={"keep_custom": True},
    )
    assert custom_response.status_code == 200
    custom = custom_response.json()["entries"][1]
    assert custom["status"] == "custom"
    assert custom["resolution_method"] == "custom"
    assert custom["resolved_crop"] is None

    fetched = catalog_client.get(f"/api/wishlists/{created['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["entries"][1]["status"] == "custom"


def test_wishlist_rejects_empty_input(
    catalog_client: TestClient,
    garden_profile: dict[str, object],
) -> None:
    response = catalog_client.post(
        "/api/wishlists",
        json={"text": " \n ", "garden_profile_id": garden_profile["id"]},
    )
    assert response.status_code == 422


def test_wishlist_requires_an_existing_garden_profile(catalog_client: TestClient) -> None:
    response = catalog_client.post(
        "/api/wishlists",
        json={
            "text": "Tomatoes",
            "garden_profile_id": "00000000-0000-0000-0000-000000000000",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Garden profile not found."
