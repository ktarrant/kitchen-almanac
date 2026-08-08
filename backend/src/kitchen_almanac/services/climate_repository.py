from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import update
from sqlalchemy.orm import Session

from kitchen_almanac.db_models import (
    ClimateDatasetVersion,
    ClimateStationNormal,
    SourceDocument,
)
from kitchen_almanac.hardiness_data import HardinessDataset
from kitchen_almanac.noaa_normals_data import NoaaNormalsDataset


def load_hardiness_dataset(session: Session, dataset: HardinessDataset) -> bool:
    """Register an immutable USDA raster snapshot and activate its version."""

    if session.get(ClimateDatasetVersion, dataset.id) is not None:
        return False

    source = session.get(SourceDocument, dataset.source_id)
    if source is None:
        source = SourceDocument(
            id=dataset.source_id,
            title=dataset.source_title,
            source_path=dataset.source_path,
            source_url=dataset.source_url,
            publisher=dataset.source_publisher,
            sha256=dataset.source_sha256,
            media_type=dataset.source_media_type,
            retrieved_at=dataset.source_retrieved_at,
            license=dataset.source_license,
        )
        session.add(source)

    session.execute(
        update(ClimateDatasetVersion)
        .where(ClimateDatasetVersion.dataset_kind == dataset.dataset_kind)
        .values(active=False)
    )
    session.add(
        ClimateDatasetVersion(
            id=dataset.id,
            dataset_kind=dataset.dataset_kind,
            schema_version=dataset.schema_version,
            parser_version=dataset.parser_version,
            source_document_id=source.id,
            active=True,
            loaded_at=datetime.now(UTC),
        )
    )
    session.commit()
    return True


def load_noaa_normals_dataset(session: Session, dataset: NoaaNormalsDataset) -> bool:
    """Load an immutable NOAA station-normal snapshot and activate its version."""

    if session.get(ClimateDatasetVersion, dataset.id) is not None:
        return False

    source = session.get(SourceDocument, dataset.source_id)
    if source is None:
        source = SourceDocument(
            id=dataset.source_id,
            title=dataset.source_title,
            source_path=dataset.source_path,
            source_url=dataset.source_url,
            publisher=dataset.source_publisher,
            sha256=dataset.source_sha256,
            media_type=dataset.source_media_type,
            retrieved_at=dataset.source_retrieved_at,
            license=dataset.source_license,
        )
        session.add(source)

    session.execute(
        update(ClimateDatasetVersion)
        .where(ClimateDatasetVersion.dataset_kind == dataset.dataset_kind)
        .values(active=False)
    )
    session.add(
        ClimateDatasetVersion(
            id=dataset.id,
            dataset_kind=dataset.dataset_kind,
            schema_version=dataset.schema_version,
            parser_version=dataset.parser_version,
            source_document_id=source.id,
            active=True,
            loaded_at=datetime.now(UTC),
        )
    )
    session.flush()
    session.add_all(
        [
            ClimateStationNormal(
                climate_dataset_version_id=dataset.id,
                station_id=station.station_id,
                name=station.name,
                latitude=station.latitude,
                longitude=station.longitude,
                elevation_m=station.elevation_m,
                annual_mean_f=station.annual_mean_f,
                annual_minimum_f=station.annual_minimum_f,
                annual_maximum_f=station.annual_maximum_f,
                annual_precipitation_in=station.annual_precipitation_in,
                growing_degree_days_base_50_f=station.growing_degree_days_base_50_f,
                last_spring_frost_50=station.last_spring_frost_50,
                first_fall_frost_50=station.first_fall_frost_50,
                growing_season_days_50=station.growing_season_days_50,
                completeness_class=station.completeness_class,
                minimum_years=station.minimum_years,
                source_locator=station.source_locator,
            )
            for station in dataset.stations
        ]
    )
    session.commit()
    return True
