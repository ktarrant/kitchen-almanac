from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from kitchen_almanac.database import Base, make_engine
from kitchen_almanac.db_models import ClimateDatasetVersion, SourceDocument
from kitchen_almanac.hardiness_data import (
    DEFAULT_SOURCE,
    HardinessDataError,
    build_hardiness_dataset,
    hardiness_zone_from_centi_fahrenheit,
    sample_hardiness,
)
from kitchen_almanac.services.climate_repository import load_hardiness_dataset


@pytest.mark.parametrize(
    ("temperature", "zone"),
    [
        (-6500, "1a"),
        (-6000, "1a"),
        (-5500, "1b"),
        (0, "7a"),
        (499, "7a"),
        (500, "7b"),
        (6999, "13b"),
        (7500, "13b"),
    ],
)
def test_hardiness_zone_boundaries(temperature: int, zone: str) -> None:
    assert hardiness_zone_from_centi_fahrenheit(temperature) == zone


def test_usda_snapshot_samples_reproducibly() -> None:
    dataset = build_hardiness_dataset(DEFAULT_SOURCE)
    sample = sample_hardiness(
        DEFAULT_SOURCE,
        latitude=39.00286,
        longitude=-77.036646,
        expected_sha256=dataset.source_sha256,
    )

    assert dataset.id == "usda-phzm-2023-c8510c4e04ea3231"
    assert sample is not None
    assert sample.zone == "7b"
    assert sample.mean_annual_extreme_minimum_f == 7.37
    assert sample.raster_value == 737
    assert sample.row == 1312
    assert sample.column == 5758


def test_hardiness_sampling_rejects_a_changed_snapshot() -> None:
    with pytest.raises(HardinessDataError, match="checksum"):
        sample_hardiness(
            DEFAULT_SOURCE,
            latitude=39.00286,
            longitude=-77.036646,
            expected_sha256="0" * 64,
        )


def test_hardiness_dataset_load_is_idempotent() -> None:
    engine = make_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    dataset = build_hardiness_dataset(DEFAULT_SOURCE)

    with Session(engine) as session:
        assert load_hardiness_dataset(session, dataset) is True
        assert load_hardiness_dataset(session, dataset) is False
        active = session.scalar(
            select(ClimateDatasetVersion).where(ClimateDatasetVersion.active.is_(True))
        )
        assert active is not None
        assert active.id == dataset.id
        source = session.get(SourceDocument, dataset.source_id)
        assert source is not None
        assert source.sha256 == dataset.source_sha256
        assert source.license == "Creative Commons Attribution 4.0 International"
