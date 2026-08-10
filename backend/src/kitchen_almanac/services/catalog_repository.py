from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import update
from sqlalchemy.orm import Session

from kitchen_almanac.db_models import (
    CatalogCorrection,
    Crop,
    CropAlias,
    CropSeasonAppearance,
    DatasetVersion,
    SourceDocument,
)


def load_catalog(session: Session, catalog: dict[str, Any]) -> bool:
    """Load a validated catalog once and make it the active dataset.

    Returns True when a new dataset was inserted and False when it was already
    present. An existing version is not rewritten, which keeps published data
    immutable.
    """

    dataset_id = catalog["dataset_id"]
    if session.get(DatasetVersion, dataset_id) is not None:
        return False

    source_data = catalog["source"]
    source = session.get(SourceDocument, source_data["id"])
    if source is None:
        source = SourceDocument(
            id=source_data["id"],
            title=source_data["title"],
            source_path=source_data["path"],
            source_url=source_data.get("source_url"),
            publisher=source_data.get("publisher"),
            sha256=source_data["sha256"],
            media_type=source_data["media_type"],
            source_scope=source_data.get("source_scope"),
        )
        session.add(source)

    session.execute(update(DatasetVersion).values(active=False))
    dataset = DatasetVersion(
        id=dataset_id,
        schema_version=catalog["schema_version"],
        parser_version=catalog["parser_version"],
        source_document_id=source.id,
        active=True,
        loaded_at=datetime.now(UTC),
    )
    session.add(dataset)
    # The remaining rows use explicit foreign-key IDs rather than ORM
    # relationships, so publish the source and dataset before their dependents.
    # PostgreSQL enforces this ordering even within a transaction.
    session.flush()

    for correction in catalog["corrections"]:
        session.add(CatalogCorrection(dataset_version_id=dataset_id, **correction))

    for crop_data in catalog["crops"]:
        crop_id = f"{dataset_id}:{crop_data['id']}"
        taxonomy = crop_data["taxonomy"]
        browse_category = crop_data["browse_category"]
        crop = Crop(
            id=crop_id,
            dataset_version_id=dataset_id,
            slug=crop_data["id"],
            canonical_name=crop_data["canonical_name"],
            planning_category=crop_data["planning_category"],
            commodity_section_key=taxonomy["commodity_key"],
            commodity_section_title=taxonomy["commodity_title"],
            commodity_section_position=taxonomy["commodity_position"],
            browse_category_key=browse_category["key"],
            browse_category_title=browse_category["title"],
            browse_category_position=browse_category["position"],
        )
        crop.aliases = [CropAlias(alias=alias) for alias in crop_data["aliases"]]
        crop.appearances = [
            CropSeasonAppearance(
                season=appearance["season"],
                source_name=appearance["source_name"],
                source_line=appearance["source_line"],
                position=appearance["position"],
            )
            for appearance in crop_data["appearances"]
        ]
        session.add(crop)

    session.commit()
    return True
