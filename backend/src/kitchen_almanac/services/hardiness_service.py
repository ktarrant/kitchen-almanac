from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from kitchen_almanac.db_models import (
    ClimateDatasetVersion,
    GardenProfile,
    LocationEvidenceClaim,
)
from kitchen_almanac.hardiness_data import (
    DATASET_KIND,
    EXTRACTOR_VERSION,
    REPOSITORY_ROOT,
    sample_hardiness,
)


def _source_path(source_path: str) -> Path:
    path = Path(source_path)
    return path if path.is_absolute() else REPOSITORY_ROOT / path


def enrich_garden_hardiness(session: Session, profile: GardenProfile) -> bool:
    if profile.latitude is None or profile.longitude is None:
        return False

    dataset = session.scalar(
        select(ClimateDatasetVersion).where(
            ClimateDatasetVersion.dataset_kind == DATASET_KIND,
            ClimateDatasetVersion.active.is_(True),
        )
    )
    if dataset is None:
        return False

    existing_claim = session.scalar(
        select(LocationEvidenceClaim).where(
            LocationEvidenceClaim.garden_profile_id == profile.id,
            LocationEvidenceClaim.climate_dataset_version_id == dataset.id,
            LocationEvidenceClaim.field_name == "usda_hardiness",
        )
    )
    if existing_claim is not None:
        return False

    source = dataset.source_document
    sample = sample_hardiness(
        _source_path(source.source_path),
        latitude=profile.latitude,
        longitude=profile.longitude,
        expected_sha256=source.sha256,
    )
    if sample is None:
        return False

    session.add(
        LocationEvidenceClaim(
            garden_profile_id=profile.id,
            climate_dataset_version_id=dataset.id,
            field_name="usda_hardiness",
            normalized_value={
                "zone": sample.zone,
                "mean_annual_extreme_minimum_f": sample.mean_annual_extreme_minimum_f,
                "raster_value_hundredths_f": sample.raster_value,
            },
            unit="degrees_fahrenheit",
            confidence=(
                "medium"
                if profile.coordinate_method == "census_zcta_representative_point"
                else "high"
            ),
            source_document_id=source.id,
            source_excerpt=(
                "Raster values represent hundredths of a degree Fahrenheit for the "
                "1991–2020 mean annual extreme minimum."
            ),
            source_locator=sample.source_locator,
            extraction_method="containing_raster_cell",
            extractor_version=EXTRACTOR_VERSION,
            created_at=datetime.now(UTC),
        )
    )
    session.flush()
    return True


def enrich_all_garden_hardiness(session: Session) -> int:
    profiles = session.scalars(
        select(GardenProfile).where(
            GardenProfile.latitude.is_not(None),
            GardenProfile.longitude.is_not(None),
        )
    ).all()
    enriched = sum(enrich_garden_hardiness(session, profile) for profile in profiles)
    session.commit()
    return enriched
