from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from zipfile import ZipFile

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from kitchen_almanac.database import Base, make_engine
from kitchen_almanac.db_models import LocationDatasetVersion, PostalCodeLocation, SourceDocument
from kitchen_almanac.location_data import DEFAULT_SOURCE, LocationDataError, build_location_dataset
from kitchen_almanac.services.location_repository import load_location_dataset


def test_census_snapshot_parses_reproducibly() -> None:
    dataset = build_location_dataset(DEFAULT_SOURCE)

    assert dataset.id == "census-zcta-2025-51516a4283bab5cd"
    assert len(dataset.locations) == 33_791
    silver_spring = next(
        location for location in dataset.locations if location.postal_code == "20910"
    )
    assert silver_spring.latitude == 39.00286
    assert silver_spring.longitude == -77.036646
    assert silver_spring.coordinate_method == "census_zcta_representative_point"


def test_location_snapshot_rejects_unexpected_columns(tmp_path: Path) -> None:
    source = tmp_path / "bad-zcta.zip"
    with ZipFile(source, "w") as archive:
        archive.writestr("bad.txt", "postal_code|latitude|longitude\n20910|39|-77\n")

    with pytest.raises(LocationDataError, match="unexpected column layout"):
        build_location_dataset(source)


def test_location_load_is_idempotent() -> None:
    engine = make_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    complete_dataset = build_location_dataset(DEFAULT_SOURCE)
    dataset = replace(
        complete_dataset,
        id=f"{complete_dataset.id}-test",
        locations=complete_dataset.locations[:2],
    )

    with Session(engine) as session:
        assert load_location_dataset(session, dataset) is True
        assert load_location_dataset(session, dataset) is False
        assert session.scalar(select(func.count()).select_from(PostalCodeLocation)) == 2

        active = session.scalar(
            select(LocationDatasetVersion).where(LocationDatasetVersion.active.is_(True))
        )
        assert active is not None
        assert active.id == dataset.id
        source = session.get(SourceDocument, dataset.source_id)
        assert source is not None
        assert source.sha256 == dataset.source_sha256
        assert source.publisher == "United States Census Bureau"
