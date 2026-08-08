from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import update
from sqlalchemy.orm import Session

from kitchen_almanac.db_models import (
    LocationDatasetVersion,
    PostalCodeLocation,
    SourceDocument,
)
from kitchen_almanac.location_data import LocationDataset


def load_location_dataset(session: Session, dataset: LocationDataset) -> bool:
    """Load one immutable postal-area coordinate snapshot and activate it."""

    if session.get(LocationDatasetVersion, dataset.id) is not None:
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

    session.execute(update(LocationDatasetVersion).values(active=False))
    version = LocationDatasetVersion(
        id=dataset.id,
        schema_version=dataset.schema_version,
        parser_version=dataset.parser_version,
        source_document_id=source.id,
        active=True,
        loaded_at=datetime.now(UTC),
    )
    session.add(version)
    session.flush()

    session.add_all(
        [
            PostalCodeLocation(
                location_dataset_version_id=dataset.id,
                postal_code=location.postal_code,
                latitude=location.latitude,
                longitude=location.longitude,
                coordinate_method=location.coordinate_method,
                source_locator=location.source_locator,
            )
            for location in dataset.locations
        ]
    )
    session.commit()
    return True
