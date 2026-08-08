from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class CropSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    slug: str
    canonical_name: str
    planning_category: str
    aliases: list[str]
    seasons: list[str]


class CropListResponse(BaseModel):
    dataset_id: str | None
    crops: list[CropSummary]
