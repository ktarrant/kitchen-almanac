from __future__ import annotations

from typing import Annotated

from fastapi import Depends, FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from kitchen_almanac import __version__
from kitchen_almanac.config import get_settings
from kitchen_almanac.database import get_session
from kitchen_almanac.db_models import Crop, DatasetVersion
from kitchen_almanac.schemas import CropListResponse, CropSummary, HealthResponse

app = FastAPI(
    title="Kitchen Almanac",
    version=__version__,
    description="Evidence-backed, location-aware garden planning API.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="kitchen-almanac-api", version=__version__)


@app.get("/api/crops", response_model=CropListResponse)
def list_crops(
    session: Annotated[Session, Depends(get_session)],
    category: Annotated[str | None, Query()] = None,
) -> CropListResponse:
    active_dataset = session.scalar(select(DatasetVersion).where(DatasetVersion.active.is_(True)))
    if active_dataset is None:
        return CropListResponse(dataset_id=None, crops=[])

    query = (
        select(Crop)
        .where(Crop.dataset_version_id == active_dataset.id)
        .options(selectinload(Crop.aliases), selectinload(Crop.appearances))
        .order_by(Crop.canonical_name)
    )
    if category:
        query = query.where(Crop.planning_category == category)

    crops = session.scalars(query).all()
    return CropListResponse(
        dataset_id=active_dataset.id,
        crops=[
            CropSummary(
                slug=crop.slug,
                canonical_name=crop.canonical_name,
                planning_category=crop.planning_category,
                aliases=sorted(alias.alias for alias in crop.aliases),
                seasons=sorted({appearance.season for appearance in crop.appearances}),
            )
            for crop in crops
        ],
    )
