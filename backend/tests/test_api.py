from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta

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
            "support_available": True,
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
    assert payload["dataset_id"] == "cultivar-catalog-v1-8971e569e94bd713"
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


@pytest.mark.parametrize(
    ("query", "expected_slugs"),
    [
        ("cucumbers", ["marketmore-76", "eureka", "tasty-green", "corinto", "picolino"]),
        ("zucchini", ["dunja", "eight-ball", "gentry", "sunburst"]),
        ("Provider", ["provider"]),
    ],
)
def test_expanded_catalog_is_searchable(
    catalog_client: TestClient,
    garden_profile: dict[str, object],
    query: str,
    expected_slugs: list[str],
) -> None:
    response = catalog_client.get(
        "/api/catalog/search",
        params={"q": query, "garden_profile_id": garden_profile["id"]},
    )

    assert response.status_code == 200
    assert [item["cultivar"]["slug"] for item in response.json()["cultivars"]] == expected_slugs


def test_expanded_cultivar_evidence_retains_source_scope(catalog_client: TestClient) -> None:
    response = catalog_client.get("/api/cultivars?q=Provider")

    assert response.status_code == 200
    provider = response.json()["cultivars"][0]
    regional_claim = next(
        trait for trait in provider["traits"] if trait["field_name"] == "regional_recommendation"
    )
    assert regional_claim["normalized_value"] == {
        "region": "mid_atlantic",
        "production_context": "commercial",
    }
    assert regional_claim["source"]["scope"] == (
        "Current regional commercial recommendation; not written specifically for home gardeners"
    )
    assert regional_claim["source"]["sha256"] == (
        "174b0596cf199e757e8253ee64b049bba6789fcfe0745a540193a451c37dfeff"
    )


def test_catalog_search_returns_crop_and_related_cultivars(
    catalog_client: TestClient,
    garden_profile: dict[str, object],
) -> None:
    response = catalog_client.get(
        "/api/catalog/search",
        params={"q": "tomatoes", "garden_profile_id": garden_profile["id"]},
    )

    assert response.status_code == 200
    results = response.json()
    assert results["normalized_query"] == "tomatoes"
    assert results["crop_choices"][0] == {
        "crop": {
            "slug": "tomatoes",
            "canonical_name": "Tomatoes",
            "planning_category": "annual_crop",
        },
        "score": 1.0,
        "matched_alias": "Tomatoes",
        "match_method": "exact",
    }
    assert len(results["crop_choices"]) == 1
    assert results["cultivars"][0]["cultivar"]["slug"] == "mountain-merit"
    assert {item["cultivar"]["slug"] for item in results["cultivars"]} == {
        "mountain-merit",
        "juliet",
        "sun-gold",
        "brandywine-red",
        "cherokee-purple",
        "green-zebra",
        "san-marzano",
        "san-marzano-2",
    }
    assert {item["match_method"] for item in results["cultivars"]} == {"related_crop"}
    assert results["cultivars"][0]["suitability"]["result_group"] == "best_documented_fit"
    assert results["cultivars"][0]["suitability"]["score"] == 80
    assert results["cultivars"][0]["research_quality"] == {
        "algorithm_version": "research-quality-v1.0.0",
        "score": 95,
        "tier": "well_researched",
        "source_count": 2,
        "cultivar_specific_trait_count": 17,
        "strengths": [
            "At least one reviewed source documents this cultivar.",
            "Two or more independent reviewed sources document this cultivar.",
            "Cultivar-specific maturity evidence is available.",
            "Growth or flowering habit is documented.",
            "Plant size or spacing is documented.",
            "Harvest characteristics or uses are documented.",
            "Disease-resistance evidence is documented.",
            "Regional recommendation, award, or trial evidence is available.",
        ],
        "missing_evidence": [],
    }


def test_catalog_search_ranks_specific_cultivars_without_auto_selecting(
    catalog_client: TestClient,
    garden_profile: dict[str, object],
) -> None:
    response = catalog_client.get(
        "/api/catalog/search",
        params={
            "q": "San Marzano tomatoes",
            "garden_profile_id": garden_profile["id"],
        },
    )

    assert response.status_code == 200
    results = response.json()
    assert [item["cultivar"]["slug"] for item in results["cultivars"]] == [
        "san-marzano",
        "san-marzano-2",
    ]
    assert results["cultivars"][0]["match_method"] == "exact"
    assert results["cultivars"][0]["score"] == 1.0
    assert results["cultivars"][1]["match_method"] == "prefix"
    assert results["crop_choices"][0]["crop"]["slug"] == "tomatoes"
    assert results["crop_choices"][0]["match_method"] == "crop_context"


@pytest.mark.parametrize("query", ["san marzno tomatoes", "san marzno tomatos"])
def test_catalog_search_offers_fuzzy_cultivar_suggestions(
    catalog_client: TestClient,
    garden_profile: dict[str, object],
    query: str,
) -> None:
    response = catalog_client.get(
        "/api/catalog/search",
        params={"q": query, "garden_profile_id": garden_profile["id"]},
    )

    assert response.status_code == 200
    results = response.json()
    assert [item["cultivar"]["slug"] for item in results["cultivars"]] == [
        "san-marzano",
        "san-marzano-2",
    ]
    assert results["cultivars"][0]["match_method"] == "fuzzy"
    assert results["cultivars"][0]["score"] < 1


def test_catalog_search_matches_misspelled_crop_and_commercial_identifier(
    catalog_client: TestClient,
    garden_profile: dict[str, object],
) -> None:
    crop_response = catalog_client.get(
        "/api/catalog/search",
        params={"q": "tomatos", "garden_profile_id": garden_profile["id"]},
    )
    assert crop_response.status_code == 200
    crop_results = crop_response.json()
    assert crop_results["crop_choices"][0]["crop"]["slug"] == "tomatoes"
    assert crop_results["crop_choices"][0]["match_method"] == "fuzzy"
    assert len(crop_results["crop_choices"]) == 1
    assert crop_results["cultivars"][0]["cultivar"]["slug"] == "mountain-merit"
    assert {item["cultivar"]["slug"] for item in crop_results["cultivars"]} == {
        "mountain-merit",
        "juliet",
        "sun-gold",
        "brandywine-red",
        "cherokee-purple",
        "green-zebra",
        "san-marzano",
        "san-marzano-2",
    }

    listing_response = catalog_client.get(
        "/api/catalog/search",
        params={"q": "TM660-20", "garden_profile_id": garden_profile["id"]},
    )
    assert listing_response.status_code == 200
    listing_results = listing_response.json()
    assert [item["cultivar"]["slug"] for item in listing_results["cultivars"]] == [
        "san-marzano-2"
    ]
    assert listing_results["cultivars"][0]["match_method"] == "commercial_listing"


def test_catalog_search_requires_an_existing_garden_profile(
    catalog_client: TestClient,
) -> None:
    response = catalog_client.get(
        "/api/catalog/search",
        params={
            "q": "tomatoes",
            "garden_profile_id": "00000000-0000-0000-0000-000000000000",
        },
    )

    assert response.status_code == 404


def test_suitability_assessment_is_versioned_explainable_and_deterministic(
    catalog_client: TestClient,
    garden_profile: dict[str, object],
) -> None:
    parameters = {
        "garden_profile_id": garden_profile["id"],
        "cultivar_slug": "mountain-merit",
    }
    first = catalog_client.get("/api/suitability", params=parameters)
    second = catalog_client.get("/api/suitability", params=parameters)

    assert first.status_code == 200
    assert second.status_code == 200
    assessment = first.json()
    assert second.json() == assessment
    assert assessment["algorithm_version"] == "suitability-v1.1.0"
    assert assessment["cultivar_dataset_id"] == "cultivar-catalog-v1-8971e569e94bd713"
    assert assessment["input_fingerprint"].startswith("sha256:")
    assert assessment["status"] == "suitable"
    assert assessment["score"] == 80
    assert assessment["result_group"] == "best_documented_fit"
    assert assessment["constraints"] == []
    factors = {factor["code"]: factor for factor in assessment["factors"]}
    assert factors["maturity_window"]["points"] == 20
    assert {item["origin"] for item in factors["maturity_window"]["evidence"]} == {
        "cultivar_catalog",
        "climate_normal",
    }
    regional = factors["regional_evidence"]
    assert regional["evidence"][0]["source_scope"] == (
        "Current regional commercial recommendation; not written specifically for home gardeners"
    )
    assert assessment["assumptions"] == [
        "Mid-Atlantic applicability uses an approximate coordinate envelope "
        "(36.5–42.5°N, 83–73°W), not a political-boundary lookup."
    ]
    assert [item["code"] for item in assessment["dimensions"]] == [
        "maturity_window",
        "temperature_gdd",
        "photoperiod",
        "disease_pressure",
        "growing_method",
        "support",
        "space",
        "container_fit",
        "intended_use",
        "regional_evidence",
        "evidence_quality",
    ]
    assert assessment["evidence_quality"] == 80


def test_suitability_treats_protected_culture_as_a_constraint(
    catalog_client: TestClient,
    garden_profile: dict[str, object],
) -> None:
    response = catalog_client.get(
        "/api/suitability",
        params={"garden_profile_id": garden_profile["id"], "cultivar_slug": "corinto"},
    )

    assert response.status_code == 200
    assessment = response.json()
    assert assessment["status"] == "not_recommended"
    assert assessment["result_group"] == "constrained"
    assert "protected culture" in assessment["constraints"][0]
    protected_factor = next(
        factor for factor in assessment["factors"] if factor["code"] == "growing_method"
    )
    assert {item["field_name"] for item in protected_factor["evidence"]} == {
        "crop_type",
        "growing_methods",
    }


def test_suitability_refuses_to_score_without_climate_evidence(
    catalog_client: TestClient,
) -> None:
    profile = catalog_client.post(
        "/api/garden-profiles",
        json={"postal_code": "00000", "growing_methods": ["containers"]},
    ).json()

    response = catalog_client.get(
        "/api/suitability",
        params={"garden_profile_id": profile["id"], "cultivar_slug": "provider"},
    )

    assert response.status_code == 200
    assessment = response.json()
    assert assessment["status"] == "insufficient_evidence"
    assert assessment["score"] is None
    assert assessment["result_group"] == "insufficient_evidence"
    assert "A frost-free growing-season normal for this garden" in assessment["missing_evidence"]
    assert "Cultivar-specific photoperiod sensitivity" in assessment["missing_evidence"]
    assert "The largest available container volume" in assessment["missing_evidence"]


def test_suitability_enforces_support_and_space_constraints(
    catalog_client: TestClient,
) -> None:
    profile = catalog_client.post(
        "/api/garden-profiles",
        json={
            "postal_code": "20910",
            "growing_methods": ["raised_bed"],
            "support_available": False,
            "max_plant_spread_inches": 12,
        },
    ).json()

    climbing = catalog_client.get(
        "/api/suitability",
        params={"garden_profile_id": profile["id"], "cultivar_slug": "san-marzano-2"},
    ).json()
    compact = catalog_client.get(
        "/api/suitability",
        params={"garden_profile_id": profile["id"], "cultivar_slug": "mountain-merit"},
    ).json()

    assert climbing["status"] == "not_recommended"
    assert any("cannot provide" in constraint for constraint in climbing["constraints"])
    assert compact["status"] == "not_recommended"
    assert any("12-inch" in constraint for constraint in compact["constraints"])
    assert next(item for item in compact["dimensions"] if item["code"] == "space")[
        "status"
    ] == "constraint"


def test_suitability_matches_protected_culture_intended_use_and_disease_concern(
    catalog_client: TestClient,
) -> None:
    protected_profile = catalog_client.post(
        "/api/garden-profiles",
        json={
            "postal_code": "20910",
            "growing_methods": ["protected"],
            "support_available": True,
            "intended_uses": ["fresh"],
        },
    ).json()
    protected = catalog_client.get(
        "/api/suitability",
        params={"garden_profile_id": protected_profile["id"], "cultivar_slug": "corinto"},
    ).json()
    assert protected["status"] == "suitable"
    assert next(item for item in protected["dimensions"] if item["code"] == "growing_method")[
        "status"
    ] == "fit"

    priority_profile = catalog_client.post(
        "/api/garden-profiles",
        json={
            "postal_code": "20910",
            "growing_methods": ["raised_bed"],
            "support_available": True,
            "intended_uses": ["fresh"],
            "disease_concerns": ["late_blight"],
        },
    ).json()
    priority = catalog_client.get(
        "/api/suitability",
        params={"garden_profile_id": priority_profile["id"], "cultivar_slug": "mountain-merit"},
    ).json()
    factor_codes = {factor["code"] for factor in priority["factors"]}
    assert {"disease_pressure", "intended_use"} <= factor_codes
    assert next(
        item for item in priority["dimensions"] if item["code"] == "disease_pressure"
    )["status"] == "fit"


def test_suitability_reports_container_and_preference_evidence_gaps(
    catalog_client: TestClient,
) -> None:
    profile = catalog_client.post(
        "/api/garden-profiles",
        json={
            "postal_code": "20910",
            "growing_methods": ["containers"],
            "support_available": True,
            "max_container_volume_gallons": 15,
            "intended_uses": ["pickling"],
            "disease_concerns": ["late_blight"],
        },
    ).json()
    response = catalog_client.get(
        "/api/suitability",
        params={"garden_profile_id": profile["id"], "cultivar_slug": "provider"},
    )

    assert response.status_code == 200
    assessment = response.json()
    assert assessment["status"] == "conditional"
    assert "A minimum container volume" in " ".join(assessment["missing_evidence"])
    assert "Use evidence for: pickling" in assessment["missing_evidence"]
    assert next(
        item for item in assessment["dimensions"] if item["code"] == "disease_pressure"
    )["status"] == "not_applicable"


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
            "support_available": False,
            "max_plant_spread_inches": 18,
            "max_container_volume_gallons": 10,
            "intended_uses": ["pickling", "fresh", "pickling"],
            "disease_concerns": ["late_blight", "early_blight", "late_blight"],
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
    assert profile["support_available"] is False
    assert profile["max_plant_spread_inches"] == 18
    assert profile["max_container_volume_gallons"] == 10
    assert profile["intended_uses"] == ["fresh", "pickling"]
    assert profile["disease_concerns"] == ["early_blight", "late_blight"]

    fetched = catalog_client.get(f"/api/garden-profiles/{profile['id']}")
    assert fetched.status_code == 200
    assert fetched.json() == profile

    listed = catalog_client.get("/api/garden-profiles")
    assert listed.status_code == 200
    assert listed.json()["profiles"][0] == profile


def test_garden_profiles_are_listed_newest_first(catalog_client: TestClient) -> None:
    first = catalog_client.post(
        "/api/garden-profiles",
        json={"name": "First", "postal_code": "20910", "growing_methods": ["containers"]},
    ).json()
    second = catalog_client.post(
        "/api/garden-profiles",
        json={"name": "Second", "postal_code": "20851", "growing_methods": ["in_ground"]},
    ).json()

    response = catalog_client.get("/api/garden-profiles")

    assert response.status_code == 200
    profiles = response.json()["profiles"]
    assert [profile["id"] for profile in profiles[:2]] == [second["id"], first["id"]]


def test_garden_profile_deletion_removes_only_its_planning_data(
    catalog_client: TestClient,
) -> None:
    deleted_profile = catalog_client.post(
        "/api/garden-profiles",
        json={"name": "Delete me", "postal_code": "20910", "growing_methods": ["containers"]},
    ).json()
    retained_profile = catalog_client.post(
        "/api/garden-profiles",
        json={"name": "Keep me", "postal_code": "20851", "growing_methods": ["in_ground"]},
    ).json()
    deleted_wishlist = catalog_client.post(
        "/api/wishlists",
        json={
            "text": "beans\nTomato",
            "garden_profile_id": deleted_profile["id"],
        },
    ).json()
    retained_wishlist = catalog_client.post(
        "/api/wishlists/builder",
        json={"garden_profile_id": retained_profile["id"], "name": "Keep this list"},
    ).json()
    cultivars_before = catalog_client.get("/api/cultivars").json()

    response = catalog_client.delete(f"/api/garden-profiles/{deleted_profile['id']}")

    assert response.status_code == 204
    assert response.content == b""
    assert catalog_client.get(f"/api/garden-profiles/{deleted_profile['id']}").status_code == 404
    assert catalog_client.get(f"/api/wishlists/{deleted_wishlist['id']}").status_code == 404
    assert catalog_client.get(f"/api/garden-profiles/{retained_profile['id']}").status_code == 200
    assert catalog_client.get(f"/api/wishlists/{retained_wishlist['id']}").status_code == 200
    assert catalog_client.get("/api/cultivars").json() == cultivars_before

    missing_profile_id = "00000000-0000-0000-0000-000000000000"
    missing = catalog_client.delete(f"/api/garden-profiles/{missing_profile_id}")
    assert missing.status_code == 404


def test_grow_guide_combines_cultivar_crop_and_local_climate_evidence(
    catalog_client: TestClient,
    garden_profile: dict[str, object],
) -> None:
    response = catalog_client.get(
        "/api/grow-guides",
        params={
            "garden_profile_id": garden_profile["id"],
            "cultivar_slug": "mountain-merit",
        },
    )

    assert response.status_code == 200
    guide = response.json()
    assert guide["cultivar_name"] == "Mountain Merit"
    assert guide["crop_name"] == "Tomatoes"
    assert guide["algorithm_version"] == "grow-guide-v1.2.0"
    assert len(guide["input_fingerprint"]) == 64
    assert [section["code"] for section in guide["sections"]] == [
        "light",
        "soil",
        "water",
        "spacing",
        "containers",
        "trellising",
        "starting_method",
        "planting",
        "maintenance",
        "companions",
        "harvest",
    ]
    sections = {section["code"]: section for section in guide["sections"]}
    assert sections["light"]["provenance"] == "crop_baseline"
    assert sections["light"]["evidence"][0]["publisher"] == "University of Maryland Extension"
    assert sections["spacing"]["provenance"] == "cultivar"
    assert sections["spacing"]["summary"] == "Space plants 24 inches apart."
    assert sections["soil"]["status"] == "documented"
    assert sections["soil"]["summary"] == (
        "Aim for a soil pH of 6.5. Use a soil test to determine lime needs when pH falls "
        "below 6.0."
    )
    assert sections["soil"]["evidence"][0]["publisher"] == (
        "Rutgers NJAES Cooperative Extension"
    )
    assert sections["water"]["status"] == "partial"
    assert sections["water"]["summary"] == (
        "Use soil texture and root-zone moisture—not a fixed schedule—to guide watering "
        "frequency and volume."
    )
    assert sections["water"]["instructions"][-1] == (
        "Pay closest attention to moisture during early flowering, fruit set, and fruit "
        "enlargement."
    )
    assert {item["field_name"] for item in sections["water"]["evidence"]} == {
        "critical_watering_stages",
        "water_management_guidance",
    }
    assert sections["water"]["missing_evidence"] == ["Reviewed watering quantity"]
    assert sections["trellising"]["status"] == "partial"
    assert sections["starting_method"]["summary"] == "Starting method: transplant."
    assert sections["planting"]["status"] == "documented"
    assert sections["harvest"]["instructions"][-2:] == [
        "Choose harvest ripeness for the intended use; fully ripe is appropriate for direct use.",
        "Handle fruit carefully and harvest often during peak production.",
    ]
    assert all(
        section["evidence"]
        for section in guide["sections"]
        if section["status"] == "documented"
    )

    target_year = int(garden_profile["target_year"])
    planting_date = date(target_year, 3, 24)
    events = {event["code"]: event for event in guide["timeline"]}
    assert events["outdoor_planting_boundary"]["start_date"] == planting_date.isoformat()
    assert events["estimated_first_harvest"]["start_date"] == (
        planting_date + timedelta(days=75)
    ).isoformat()
    assert events["estimated_first_harvest"]["end_date"] == (
        planting_date + timedelta(days=75)
    ).isoformat()
    assert len(events["estimated_first_harvest"]["evidence"]) == 2
    assert "Soil pH or soil-condition guidance" not in guide["missing_evidence"]

    repeated = catalog_client.get(
        "/api/grow-guides",
        params={
            "garden_profile_id": garden_profile["id"],
            "cultivar_slug": "mountain-merit",
        },
    )
    assert repeated.json() == guide


def test_grow_guide_reports_missing_context_and_unknown_records(
    catalog_client: TestClient,
) -> None:
    profile = catalog_client.post(
        "/api/garden-profiles",
        json={"postal_code": "00000", "growing_methods": ["containers"]},
    ).json()

    response = catalog_client.get(
        "/api/grow-guides",
        params={"garden_profile_id": profile["id"], "cultivar_slug": "mountain-merit"},
    )
    assert response.status_code == 200
    guide = response.json()
    assert guide["timeline"] == []
    planting = next(section for section in guide["sections"] if section["code"] == "planting")
    assert planting["status"] == "partial"
    assert planting["missing_evidence"] == ["Local probable last-spring-freeze date"]

    missing_cultivar = catalog_client.get(
        "/api/grow-guides",
        params={"garden_profile_id": profile["id"], "cultivar_slug": "not-a-cultivar"},
    )
    assert missing_cultivar.status_code == 404
    missing_profile = catalog_client.get(
        "/api/grow-guides",
        params={
            "garden_profile_id": "00000000-0000-0000-0000-000000000000",
            "cultivar_slug": "mountain-merit",
        },
    )
    assert missing_profile.status_code == 404


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
            "growing_methods": ["containers"],
            "max_plant_spread_inches": 5,
        },
        {
            "postal_code": "20910",
            "growing_methods": ["containers"],
            "max_container_volume_gallons": 0.5,
        },
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


def test_active_wishlist_is_restored_per_profile(catalog_client: TestClient) -> None:
    first_profile = catalog_client.post(
        "/api/garden-profiles",
        json={"name": "First", "postal_code": "20910", "growing_methods": ["containers"]},
    ).json()
    second_profile = catalog_client.post(
        "/api/garden-profiles",
        json={"name": "Second", "postal_code": "20851", "growing_methods": ["in_ground"]},
    ).json()

    empty = catalog_client.get(
        f"/api/garden-profiles/{first_profile['id']}/wishlists/active"
    )
    assert empty.status_code == 200
    assert empty.json() is None

    older = catalog_client.post(
        "/api/wishlists/builder",
        json={"garden_profile_id": first_profile["id"], "name": "Older"},
    ).json()
    newer = catalog_client.post(
        "/api/wishlists/builder",
        json={"garden_profile_id": first_profile["id"], "name": "Newer"},
    ).json()

    active = catalog_client.get(
        f"/api/garden-profiles/{first_profile['id']}/wishlists/active"
    )
    assert active.status_code == 200
    assert active.json()["id"] == newer["id"]

    updated = catalog_client.post(
        f"/api/wishlists/{older['id']}/entries",
        json={
            "original_text": "tomatoes",
            "selection_kind": "crop",
            "crop_slug": "tomatoes",
        },
    )
    assert updated.status_code == 201
    active = catalog_client.get(
        f"/api/garden-profiles/{first_profile['id']}/wishlists/active"
    )
    assert active.json()["id"] == older["id"]
    assert active.json()["entries"][0]["resolved_crop"]["slug"] == "tomatoes"

    second_empty = catalog_client.get(
        f"/api/garden-profiles/{second_profile['id']}/wishlists/active"
    )
    assert second_empty.status_code == 200
    assert second_empty.json() is None

    missing = catalog_client.get(
        "/api/garden-profiles/00000000-0000-0000-0000-000000000000/wishlists/active"
    )
    assert missing.status_code == 404


def test_wishlist_entries_can_be_removed_and_reindexed(
    catalog_client: TestClient,
    garden_profile: dict[str, object],
) -> None:
    wishlist = catalog_client.post(
        "/api/wishlists",
        json={
            "text": "beans\nTomato\nDragon fruit",
            "garden_profile_id": garden_profile["id"],
        },
    ).json()
    beans, tomato, dragon_fruit = wishlist["entries"]
    assert beans["candidates"]

    removed = catalog_client.delete(
        f"/api/wishlists/{wishlist['id']}/entries/{beans['id']}"
    )
    assert removed.status_code == 200
    assert [entry["id"] for entry in removed.json()["entries"]] == [
        tomato["id"],
        dragon_fruit["id"],
    ]
    assert [entry["position"] for entry in removed.json()["entries"]] == [1, 2]

    other = catalog_client.post(
        "/api/wishlists/builder",
        json={"garden_profile_id": garden_profile["id"]},
    ).json()
    wrong_wishlist = catalog_client.delete(
        f"/api/wishlists/{other['id']}/entries/{tomato['id']}"
    )
    assert wrong_wishlist.status_code == 404
    assert [entry["id"] for entry in catalog_client.get(
        f"/api/wishlists/{wishlist['id']}"
    ).json()["entries"]] == [tomato["id"], dragon_fruit["id"]]

    removed = catalog_client.delete(
        f"/api/wishlists/{wishlist['id']}/entries/{tomato['id']}"
    ).json()
    removed = catalog_client.delete(
        f"/api/wishlists/{wishlist['id']}/entries/{dragon_fruit['id']}"
    ).json()
    assert removed["entries"] == []


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


def test_wishlist_builder_adds_confirmed_and_custom_entries_one_at_a_time(
    catalog_client: TestClient,
    garden_profile: dict[str, object],
) -> None:
    created_response = catalog_client.post(
        "/api/wishlists/builder",
        json={"garden_profile_id": garden_profile["id"], "name": "Summer ideas"},
    )
    assert created_response.status_code == 201
    wishlist = created_response.json()
    assert wishlist["name"] == "Summer ideas"
    assert wishlist["entries"] == []
    assert wishlist["cultivar_dataset_id"] == "cultivar-catalog-v1-8971e569e94bd713"

    selections = [
        {
            "original_text": "San Marzano tomatoes",
            "selection_kind": "cultivar",
            "cultivar_slug": "san-marzano",
        },
        {
            "original_text": "tomatoes",
            "selection_kind": "crop",
            "crop_slug": "tomatoes",
        },
        {
            "original_text": "Black Krim tomatoes",
            "selection_kind": "custom_cultivar",
            "crop_slug": "tomatoes",
        },
        {"original_text": "Dragon fruit", "selection_kind": "custom_crop"},
    ]
    for selection in selections:
        added = catalog_client.post(
            f"/api/wishlists/{wishlist['id']}/entries",
            json=selection,
        )
        assert added.status_code == 201
        wishlist = added.json()

    cultivar, crop, custom_cultivar, custom_crop = wishlist["entries"]
    assert [entry["position"] for entry in wishlist["entries"]] == [1, 2, 3, 4]
    assert cultivar["resolved_cultivar"]["slug"] == "san-marzano"
    assert cultivar["resolved_crop"]["slug"] == "tomatoes"
    assert cultivar["cultivar_intent_text"] == "san marzano"
    assert crop["resolved_crop"]["slug"] == "tomatoes"
    assert crop["resolved_cultivar"] is None
    assert custom_cultivar["status"] == "custom"
    assert custom_cultivar["intent_kind"] == "cultivar"
    assert custom_cultivar["cultivar_intent_text"] == "black krim"
    assert custom_cultivar["resolved_crop"]["slug"] == "tomatoes"
    assert custom_crop["status"] == "custom"
    assert custom_crop["intent_kind"] == "crop"
    assert custom_crop["resolved_crop"] is None


def test_wishlist_builder_validates_selection_shape(
    catalog_client: TestClient,
    garden_profile: dict[str, object],
) -> None:
    wishlist = catalog_client.post(
        "/api/wishlists/builder",
        json={"garden_profile_id": garden_profile["id"]},
    ).json()

    response = catalog_client.post(
        f"/api/wishlists/{wishlist['id']}/entries",
        json={
            "original_text": "tomatoes",
            "selection_kind": "cultivar",
            "crop_slug": "tomatoes",
        },
    )

    assert response.status_code == 422


def test_quick_import_preserves_cultivar_and_crop_type_intent(
    catalog_client: TestClient,
    garden_profile: dict[str, object],
) -> None:
    response = catalog_client.post(
        "/api/wishlists",
        json={
            "text": ("San Marzano tomatoes\nSan Marzano II\npaste tomato\nBlack Krim tomatoes"),
            "garden_profile_id": garden_profile["id"],
        },
    )

    assert response.status_code == 201
    wishlist = response.json()
    assert wishlist["cultivar_dataset_id"] == "cultivar-catalog-v1-8971e569e94bd713"
    san_marzano, san_marzano_2, paste, black_krim = wishlist["entries"]

    assert san_marzano["original_text"] == "San Marzano tomatoes"
    assert san_marzano["intent_kind"] == "cultivar"
    assert san_marzano["cultivar_intent_text"] == "san marzano"
    assert san_marzano["resolved_crop"]["slug"] == "tomatoes"
    assert san_marzano["resolved_cultivar"]["slug"] == "san-marzano"

    assert san_marzano_2["resolved_cultivar"]["slug"] == "san-marzano-2"
    assert san_marzano_2["resolution_method"] == "exact_cultivar_alias"

    assert paste["status"] == "needs_confirmation"
    assert paste["intent_kind"] == "crop_type"
    assert paste["crop_type_intent"] == "paste"
    assert [candidate["slug"] for candidate in paste["cultivar_candidates"]] == [
        "san-marzano",
        "san-marzano-2",
    ]

    assert black_krim["status"] == "unresolved"
    assert black_krim["resolved_crop"]["slug"] == "tomatoes"
    assert black_krim["resolved_cultivar"] is None
    assert black_krim["cultivar_intent_text"] == "black krim"

    selected = catalog_client.patch(
        f"/api/wishlists/{wishlist['id']}/entries/{paste['id']}",
        json={"cultivar_slug": "san-marzano-2"},
    )
    assert selected.status_code == 200
    selected_paste = selected.json()["entries"][2]
    assert selected_paste["status"] == "resolved"
    assert selected_paste["resolved_crop"]["slug"] == "tomatoes"
    assert selected_paste["resolved_cultivar"]["slug"] == "san-marzano-2"

    custom = catalog_client.patch(
        f"/api/wishlists/{wishlist['id']}/entries/{black_krim['id']}",
        json={"keep_custom": True},
    )
    assert custom.status_code == 200
    custom_black_krim = custom.json()["entries"][3]
    assert custom_black_krim["status"] == "custom"
    assert custom_black_krim["resolved_crop"]["slug"] == "tomatoes"
    assert custom_black_krim["cultivar_intent_text"] == "black krim"


def test_wishlist_entry_update_requires_exactly_one_action(
    catalog_client: TestClient,
    garden_profile: dict[str, object],
) -> None:
    created = catalog_client.post(
        "/api/wishlists",
        json={"text": "paste tomato", "garden_profile_id": garden_profile["id"]},
    ).json()
    entry = created["entries"][0]

    response = catalog_client.patch(
        f"/api/wishlists/{created['id']}/entries/{entry['id']}",
        json={"crop_slug": "tomatoes", "cultivar_slug": "san-marzano"},
    )
    assert response.status_code == 422


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
