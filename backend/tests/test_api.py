from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from kitchen_almanac.catalog import DEFAULT_SOURCE, build_catalog
from kitchen_almanac.cultivar_catalog import build_cultivar_catalog
from kitchen_almanac.database import Base, get_session, make_engine
from kitchen_almanac.db_models import (
    ClimateDatasetVersion,
    ClimateStationNormal,
    LocationDatasetVersion,
    PostalCodeLocation,
    SourceDocument,
)
from kitchen_almanac.main import app
from kitchen_almanac.services.catalog_repository import load_catalog
from kitchen_almanac.services.cultivar_repository import load_cultivar_catalog


@pytest.fixture
def catalog_client() -> Iterator[TestClient]:
    engine = make_engine(
        "sqlite:///:memory:",
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        load_catalog(session, build_catalog(DEFAULT_SOURCE))
        load_cultivar_catalog(session, build_cultivar_catalog())
        source = SourceDocument(
            id="census-zcta-test-source",
            title="Test Census ZCTA source",
            source_path="test-zcta.txt",
            source_url="https://www.census.gov/test-zcta",
            publisher="United States Census Bureau",
            sha256="0" * 64,
            media_type="text/plain",
            retrieved_at=datetime(2026, 8, 8, tzinfo=UTC),
            license="U.S. Government work",
        )
        dataset = LocationDatasetVersion(
            id="census-zcta-test",
            schema_version="1.0.0",
            parser_version="1.0.0",
            source_document_id=source.id,
            active=True,
            loaded_at=datetime(2026, 8, 8, tzinfo=UTC),
        )
        session.add_all([source, dataset])
        session.flush()
        session.add(
            PostalCodeLocation(
                location_dataset_version_id=dataset.id,
                postal_code="20910",
                latitude=39.00286,
                longitude=-77.036646,
                coordinate_method="census_zcta_representative_point",
                source_locator="test-zcta.txt:GEOID=20910",
            )
        )
        hardiness_source = SourceDocument(
            id="sha256:c8510c4e04ea32311a5d41e1b4a92543816977424e6b35decf5e80c44a3600a0",
            title="2023 USDA Plant Hardiness Zone Map CONUS raster",
            source_path="data/source/usda/phzm-2023/2023ConusNAD83_Clip.tif",
            source_url="https://ndownloader.figshare.com/files/44868940",
            publisher="USDA Agricultural Research Service and OSU PRISM Climate Group",
            sha256="c8510c4e04ea32311a5d41e1b4a92543816977424e6b35decf5e80c44a3600a0",
            media_type="image/tiff",
            retrieved_at=datetime(2026, 8, 8, tzinfo=UTC),
            license="Creative Commons Attribution 4.0 International",
        )
        hardiness_dataset = ClimateDatasetVersion(
            id="usda-phzm-2023-c8510c4e04ea3231",
            dataset_kind="usda_hardiness_2023",
            schema_version="1.0.0",
            parser_version="1.0.0",
            source_document_id=hardiness_source.id,
            active=True,
            loaded_at=datetime(2026, 8, 8, tzinfo=UTC),
        )
        session.add_all([hardiness_source, hardiness_dataset])
        noaa_source = SourceDocument(
            id="noaa-normals-test-source",
            title="Test NOAA climate normals",
            source_path="test-noaa.tar.gz",
            source_url="https://www.ncei.noaa.gov/test-normals",
            publisher="NOAA National Centers for Environmental Information",
            sha256="1" * 64,
            media_type="application/gzip",
            retrieved_at=datetime(2026, 8, 8, tzinfo=UTC),
            license="U.S. Government public data; dataset citation required",
        )
        noaa_dataset = ClimateDatasetVersion(
            id="noaa-normals-test",
            dataset_kind="noaa_normals_1991_2020",
            schema_version="1.0.0",
            parser_version="1.0.0",
            source_document_id=noaa_source.id,
            active=True,
            loaded_at=datetime(2026, 8, 8, tzinfo=UTC),
        )
        session.add_all([noaa_source, noaa_dataset])
        session.flush()
        session.add_all(
            [
                ClimateStationNormal(
                    climate_dataset_version_id=noaa_dataset.id,
                    station_id="USW00013743",
                    name="WASHINGTON REAGAN AP, VA US",
                    latitude=38.8483,
                    longitude=-77.0342,
                    elevation_m=3.0,
                    annual_mean_f=59.3,
                    annual_minimum_f=50.8,
                    annual_maximum_f=67.8,
                    annual_precipitation_in=41.82,
                    growing_degree_days_base_50_f=4709.0,
                    last_spring_frost_50="03/24",
                    first_fall_frost_50="11/18",
                    growing_season_days_50=241,
                    completeness_class="S",
                    minimum_years=25,
                    source_locator="USW00013743.csv",
                ),
                ClimateStationNormal(
                    climate_dataset_version_id=noaa_dataset.id,
                    station_id="TEST00000001",
                    name="DISTANT TEST STATION",
                    latitude=40.0,
                    longitude=-78.0,
                    elevation_m=100.0,
                    annual_mean_f=50.0,
                    annual_minimum_f=40.0,
                    annual_maximum_f=60.0,
                    annual_precipitation_in=35.0,
                    growing_degree_days_base_50_f=3000.0,
                    last_spring_frost_50="05/01",
                    first_fall_frost_50="10/01",
                    growing_season_days_50=153,
                    completeness_class="S",
                    minimum_years=30,
                    source_locator="TEST00000001.csv",
                ),
            ]
        )
        session.commit()

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


def test_cultivar_catalog_exposes_overrides_inheritance_and_distinct_listings(
    catalog_client: TestClient,
) -> None:
    response = catalog_client.get("/api/cultivars?q=San%20Marzano")

    assert response.status_code == 200
    payload = response.json()
    assert payload["dataset_id"] == "cultivar-catalog-v1-0b017ec1ab06c2d4"
    assert payload["crop_dataset_id"] == "kitchen-almanac-v1-f76ca812f62c8c39"
    assert [item["canonical_name"] for item in payload["cultivars"]] == [
        "San Marzano",
        "San Marzano 2",
    ]

    san_marzano, san_marzano_2 = payload["cultivars"]
    maturity = next(
        trait for trait in san_marzano["traits"] if trait["field_name"] == "days_to_maturity"
    )
    assert maturity["normalized_value"] == {
        "minimum": 60,
        "maximum": 80,
        "basis": "unspecified",
    }
    assert maturity["inherited_from_crop"] is False
    assert maturity["extraction_method"] == "manual_review"
    assert maturity["source_excerpt"]
    sun = next(trait for trait in san_marzano["traits"] if trait["field_name"] == "sun_hours")
    assert sun["inherited_from_crop"] is True
    assert sun["source"]["publisher"] == "University of Maryland Extension"

    assert san_marzano_2["source_identifiers"][0]["source_identifier"] == "variety_id=3146"
    assert san_marzano_2["aliases"] == ["San Marzano 2", "San Marzano II"]
    listing = san_marzano_2["commercial_listings"][0]
    assert listing["record_kind"] == "commercial_seed_listing"
    assert listing["listing_name"] == "San Marzano 2 Tomato Seeds"
    assert listing["source_identifier"] == "TM660-20"
    assert listing["id"] != san_marzano_2["id"]


def test_cultivar_alias_and_type_queries_are_supported(catalog_client: TestClient) -> None:
    alias_response = catalog_client.get("/api/cultivars?q=San%20Marzano%20II")
    assert [item["slug"] for item in alias_response.json()["cultivars"]] == ["san-marzano-2"]

    type_response = catalog_client.get("/api/cultivars?q=paste&crop_slug=tomatoes")
    assert [item["slug"] for item in type_response.json()["cultivars"]] == [
        "san-marzano",
        "san-marzano-2",
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
    assert profile["latitude"] == 39.00286
    assert profile["longitude"] == -77.036646
    assert profile["location_status"] == "postal_code_resolved"
    assert profile["coordinate_method"] == "census_zcta_representative_point"
    assert profile["location_source"] == {
        "dataset_id": "census-zcta-test",
        "source_document_id": "census-zcta-test-source",
        "title": "Test Census ZCTA source",
        "publisher": "United States Census Bureau",
        "source_url": "https://www.census.gov/test-zcta",
        "sha256": "0" * 64,
        "retrieved_at": "2026-08-08T00:00:00",
        "source_locator": "test-zcta.txt:GEOID=20910",
        "coordinate_method": "census_zcta_representative_point",
    }
    assert profile["hardiness"]["zone"] == "7b"
    assert profile["hardiness"]["mean_annual_extreme_minimum_f"] == 7.37
    assert profile["hardiness"]["confidence"] == "medium"
    assert profile["hardiness"]["source"]["dataset_id"] == ("usda-phzm-2023-c8510c4e04ea3231")
    assert profile["hardiness"]["source"]["source_locator"] == (
        "2023ConusNAD83_Clip.tif:band=1,row=1312,column=5758;WGS84=39.002860,-77.036646"
    )
    normals = profile["climate_normals"]
    assert normals["station_id"] == "USW00013743"
    assert normals["station_name"] == "WASHINGTON REAGAN AP, VA US"
    assert normals["station_distance_km"] == 17.2
    assert normals["last_spring_frost_50"] == "03/24"
    assert normals["first_fall_frost_50"] == "11/18"
    assert normals["growing_season_days_50"] == 241
    assert normals["frost_probability"] == 0.5
    assert normals["confidence"] == "high"
    assert normals["source"]["dataset_id"] == "noaa-normals-test"
    assert normals["source"]["extraction_method"] == ("nearest_qualifying_station_haversine")
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
    assert profile["coordinate_method"] == "user_provided"
    assert profile["location_source"] is None
    assert profile["hardiness"] is not None
    assert profile["hardiness"]["confidence"] == "high"
    assert profile["climate_normals"] is not None


def test_garden_profile_retains_an_unmapped_postal_code(catalog_client: TestClient) -> None:
    response = catalog_client.post(
        "/api/garden-profiles",
        json={"postal_code": "00000", "growing_methods": ["containers"]},
    )

    assert response.status_code == 201
    profile = response.json()
    assert profile["location_status"] == "postal_code_pending"
    assert profile["latitude"] is None
    assert profile["coordinate_method"] is None
    assert profile["location_source"] is None
    assert profile["hardiness"] is None
    assert profile["climate_normals"] is None


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
