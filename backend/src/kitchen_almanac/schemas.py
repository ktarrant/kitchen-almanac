from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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


class WishlistCreateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=12_000)
    name: str = Field(default="My garden wishlist", min_length=1, max_length=120)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Wishlist name cannot be blank.")
        return value

    @field_validator("text")
    @classmethod
    def validate_wishlist_lines(cls, value: str) -> str:
        lines = [line.strip() for line in value.splitlines() if line.strip()]
        if not lines:
            raise ValueError("Enter at least one crop.")
        if len(lines) > 100:
            raise ValueError("A wishlist may contain at most 100 entries.")
        if any(len(line) > 120 for line in lines):
            raise ValueError("Each wishlist entry must be 120 characters or fewer.")
        return value


class WishlistEntryUpdateRequest(BaseModel):
    crop_slug: str | None = Field(default=None, max_length=100)
    keep_custom: bool = False

    @model_validator(mode="after")
    def require_one_action(self) -> WishlistEntryUpdateRequest:
        if (self.crop_slug is None) == (not self.keep_custom):
            raise ValueError("Choose one crop or keep the entry as custom.")
        return self


class WishlistCropMatch(BaseModel):
    slug: str
    canonical_name: str
    planning_category: str


class WishlistCandidateResponse(WishlistCropMatch):
    score: float = Field(ge=0, le=1)
    matched_alias: str


class WishlistEntryResponse(BaseModel):
    id: str
    position: int
    original_text: str
    normalized_text: str
    status: str
    resolution_method: str | None
    resolved_crop: WishlistCropMatch | None
    candidates: list[WishlistCandidateResponse]


class WishlistResponse(BaseModel):
    id: str
    dataset_id: str
    name: str
    created_at: datetime
    updated_at: datetime
    entries: list[WishlistEntryResponse]
