from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from kitchen_almanac.catalog import DEFAULT_SOURCE, build_catalog
from kitchen_almanac.cultivar_catalog import build_cultivar_catalog
from kitchen_almanac.database import Base, make_engine
from kitchen_almanac.db_models import (
    CommercialSeedListing,
    Cultivar,
    CultivarDatasetVersion,
    CultivarEvidenceClaim,
    SourceDocument,
)
from kitchen_almanac.services.catalog_repository import load_catalog
from kitchen_almanac.services.cultivar_repository import load_cultivar_catalog


def test_cultivar_catalog_load_is_idempotent_and_keeps_listings_separate() -> None:
    engine = make_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        load_catalog(session, build_catalog(DEFAULT_SOURCE))
        catalog = build_cultivar_catalog()
        assert load_cultivar_catalog(session, catalog) is True
        assert load_cultivar_catalog(session, catalog) is False

        active = session.scalar(
            select(CultivarDatasetVersion).where(CultivarDatasetVersion.active.is_(True))
        )
        assert active is not None
        assert active.id == catalog.id
        assert session.scalar(select(func.count()).select_from(Cultivar)) == 21
        assert session.scalar(select(func.count()).select_from(CultivarEvidenceClaim)) == 126

        listing = session.scalar(select(CommercialSeedListing))
        assert listing is not None
        assert listing.listing_name == "San Marzano 2 Tomato Seeds"
        assert listing.source_identifier == "TM660-20"
        assert listing.cultivar_id == f"{catalog.id}:san-marzano-2"

        regional_source = session.scalar(
            select(SourceDocument).where(
                SourceDocument.source_path.like(
                    "data/source/cultivars/mid-atlantic-2026-2027/%"
                )
            )
        )
        assert regional_source is not None
        assert regional_source.source_scope == (
            "Current regional commercial recommendation; not written specifically "
            "for home gardeners"
        )
