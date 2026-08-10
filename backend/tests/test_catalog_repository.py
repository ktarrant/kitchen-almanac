from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from kitchen_almanac.catalog import DEFAULT_SOURCE, build_catalog
from kitchen_almanac.database import Base, make_engine
from kitchen_almanac.db_models import Crop, DatasetVersion
from kitchen_almanac.services.catalog_repository import load_catalog


def test_catalog_load_is_idempotent() -> None:
    engine = make_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    catalog = build_catalog(DEFAULT_SOURCE)

    with Session(engine) as session:
        assert load_catalog(session, catalog) is True
        assert load_catalog(session, catalog) is False
        assert session.scalar(select(func.count()).select_from(Crop)) == 47
        active = session.scalar(select(DatasetVersion).where(DatasetVersion.active.is_(True)))
        assert active is not None
        assert active.id == catalog["dataset_id"]
        asparagus = session.scalar(
            select(Crop).where(
                Crop.dataset_version_id == active.id,
                Crop.slug == "asparagus",
            )
        )
        assert asparagus is not None
        assert asparagus.commodity_section_key == "mid-atlantic-asparagus-2026-2027"
        assert asparagus.commodity_section_title == "Asparagus"
        assert asparagus.commodity_section_position == 1
