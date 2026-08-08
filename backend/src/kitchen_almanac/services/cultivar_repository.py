from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from kitchen_almanac.cultivar_catalog import (
    EXTRACTOR_VERSION,
    CultivarCatalog,
    source_document_id,
    source_record_sha256,
)
from kitchen_almanac.db_models import (
    CommercialSeedListing,
    Crop,
    Cultivar,
    CultivarAlias,
    CultivarDatasetVersion,
    CultivarEvidenceClaim,
    CultivarSourceIdentifier,
    DatasetVersion,
    SourceDocument,
)


class CultivarCatalogDependencyError(ValueError):
    pass


def load_cultivar_catalog(session: Session, catalog: CultivarCatalog) -> bool:
    """Publish an approved cultivar snapshot against its exact crop catalog."""

    already_loaded = session.get(CultivarDatasetVersion, catalog.id) is not None

    crop_dataset = session.get(DatasetVersion, catalog.crop_dataset_id)
    if crop_dataset is None or not crop_dataset.active:
        raise CultivarCatalogDependencyError(
            f"Load and activate crop catalog {catalog.crop_dataset_id!r} first."
        )

    snapshot_source = session.get(SourceDocument, catalog.source_id)
    if snapshot_source is None:
        snapshot_source = SourceDocument(
            id=catalog.source_id,
            title=catalog.source_title,
            source_path=catalog.source_path,
            sha256=catalog.source_sha256,
            media_type=catalog.source_media_type,
            retrieved_at=datetime.now(UTC),
        )
        session.add(snapshot_source)

    source_documents: dict[str, SourceDocument] = {}
    for source_data in catalog.data["sources"]:
        document_id = source_document_id(source_data)
        source_sha = source_data.get("sha256", source_record_sha256(source_data))
        document = session.get(SourceDocument, document_id) or session.scalar(
            select(SourceDocument).where(SourceDocument.sha256 == source_sha)
        )
        if document is None:
            document = SourceDocument(
                id=document_id,
                title=source_data["title"],
                source_path=source_data.get(
                    "source_path", f"{catalog.source_path}#sources/{source_data['key']}"
                ),
                source_url=source_data["url"],
                publisher=source_data["publisher"],
                sha256=source_sha,
                media_type=source_data.get("media_type", "application/json"),
                retrieved_at=datetime.fromisoformat(
                    source_data["retrieved_at"].replace("Z", "+00:00")
                ),
                license=source_data["license"],
                source_scope=source_data.get("scope"),
            )
            session.add(document)
        elif document.source_scope != source_data.get("scope"):
            document.source_scope = source_data.get("scope")
        source_documents[source_data["key"]] = document

    if already_loaded:
        session.commit()
        return False

    session.execute(update(CultivarDatasetVersion).values(active=False))
    version = CultivarDatasetVersion(
        id=catalog.id,
        schema_version=catalog.schema_version,
        parser_version=catalog.parser_version,
        crop_dataset_version_id=catalog.crop_dataset_id,
        source_document_id=snapshot_source.id,
        active=True,
        loaded_at=datetime.now(UTC),
    )
    session.add(version)
    session.flush()

    crops = {
        crop.slug: crop
        for crop in session.scalars(
            select(Crop).where(Crop.dataset_version_id == catalog.crop_dataset_id)
        )
    }
    referenced_crop_slugs = {
        item["crop_slug"] for item in [*catalog.data["crop_baselines"], *catalog.data["cultivars"]]
    }
    missing_crops = referenced_crop_slugs - crops.keys()
    if missing_crops:
        raise CultivarCatalogDependencyError(
            f"Cultivar snapshot references missing crops: {sorted(missing_crops)!r}."
        )

    for baseline in catalog.data["crop_baselines"]:
        crop = crops[baseline["crop_slug"]]
        for trait in baseline["traits"]:
            session.add(
                _evidence_claim(
                    catalog.id,
                    "crop_baseline",
                    crop.id,
                    trait,
                    source_documents,
                )
            )

    cultivars: dict[str, Cultivar] = {}
    for cultivar_data in catalog.data["cultivars"]:
        cultivar_id = f"{catalog.id}:{cultivar_data['slug']}"
        cultivar = Cultivar(
            id=cultivar_id,
            cultivar_dataset_version_id=catalog.id,
            crop_id=crops[cultivar_data["crop_slug"]].id,
            slug=cultivar_data["slug"],
            canonical_name=cultivar_data["canonical_name"],
            crop_type=cultivar_data["crop_type"],
            description=cultivar_data["description"],
            review_status=cultivar_data["review_status"],
        )
        cultivar.aliases = [CultivarAlias(alias=alias) for alias in cultivar_data["aliases"]]
        cultivar.source_identifiers = [
            CultivarSourceIdentifier(
                source_document_id=source_documents[identifier["source_key"]].id,
                source_identifier=identifier["source_identifier"],
                name_in_source=identifier["name_in_source"],
            )
            for identifier in cultivar_data["source_identifiers"]
        ]
        session.add(cultivar)
        cultivars[cultivar_data["slug"]] = cultivar
        for trait in cultivar_data["traits"]:
            session.add(
                _evidence_claim(
                    catalog.id,
                    "cultivar",
                    cultivar_id,
                    trait,
                    source_documents,
                )
            )

    session.flush()
    for listing in catalog.data["commercial_listings"]:
        session.add(
            CommercialSeedListing(
                id=f"{catalog.id}:{listing['id']}",
                cultivar_dataset_version_id=catalog.id,
                cultivar_id=cultivars[listing["cultivar_slug"]].id,
                source_document_id=source_documents[listing["source_key"]].id,
                vendor=listing["vendor"],
                listing_name=listing["listing_name"],
                source_identifier=listing["source_identifier"],
                review_status=listing["review_status"],
            )
        )
    session.commit()
    return True


def _evidence_claim(
    catalog_id: str,
    subject_kind: str,
    subject_id: str,
    trait: dict,
    source_documents: dict[str, SourceDocument],
) -> CultivarEvidenceClaim:
    source = source_documents[trait["source_key"]]
    return CultivarEvidenceClaim(
        cultivar_dataset_version_id=catalog_id,
        subject_kind=subject_kind,
        subject_id=subject_id,
        field_name=trait["field_name"],
        normalized_value=trait["normalized_value"],
        unit=trait["unit"],
        confidence=trait["confidence"],
        source_document_id=source.id,
        source_excerpt=trait["source_excerpt"],
        source_locator=trait["source_locator"],
        extraction_method="manual_review",
        extractor_version=EXTRACTOR_VERSION,
        review_status="approved",
    )
