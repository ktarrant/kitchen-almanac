from __future__ import annotations

import re
from datetime import date, datetime
from enum import StrEnum
from typing import Literal

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


class CatalogEvidenceSourceResponse(BaseModel):
    source_document_id: str
    title: str
    publisher: str | None
    source_url: str | None
    sha256: str
    retrieved_at: datetime | None
    license: str | None
    scope: str | None
    source_locator: str


class CultivarTraitResponse(BaseModel):
    field_name: str
    normalized_value: dict | list | str | int | float | bool
    unit: str | None
    confidence: str
    inherited_from_crop: bool
    review_status: str
    source_excerpt: str
    extraction_method: str
    extractor_version: str
    source: CatalogEvidenceSourceResponse


class CultivarSourceIdentifierResponse(BaseModel):
    source_identifier: str
    name_in_source: str
    source: CatalogEvidenceSourceResponse


class CommercialSeedListingResponse(BaseModel):
    id: str
    record_kind: str = "commercial_seed_listing"
    vendor: str
    listing_name: str
    source_identifier: str
    availability_status: Literal["in_stock", "out_of_stock", "unknown", "retired"]
    observed_at: datetime
    identity_match_method: Literal["exact_name", "reviewed_alias"]
    review_status: str
    source: CatalogEvidenceSourceResponse


class CultivarResponse(BaseModel):
    id: str
    slug: str
    canonical_name: str
    crop_slug: str
    crop_name: str
    crop_type: str | None
    description: str | None
    review_status: str
    aliases: list[str]
    traits: list[CultivarTraitResponse]
    source_identifiers: list[CultivarSourceIdentifierResponse]
    commercial_listings: list[CommercialSeedListingResponse]


class CultivarListResponse(BaseModel):
    dataset_id: str | None
    crop_dataset_id: str | None
    cultivars: list[CultivarResponse]


class SuitabilityEvidenceReference(BaseModel):
    field_name: str
    value: dict | list | str | int | float | bool
    origin: str
    source_document_id: str | None = None
    title: str | None = None
    publisher: str | None = None
    source_url: str | None = None
    source_locator: str | None = None
    source_scope: str | None = None
    inherited_from_crop: bool = False


class SuitabilityFactorResponse(BaseModel):
    code: str
    effect: str
    points: int
    explanation: str
    evidence: list[SuitabilityEvidenceReference]


class SuitabilityDimensionResponse(BaseModel):
    code: str
    label: str
    status: str
    explanation: str
    evidence: list[SuitabilityEvidenceReference]


class SuitabilityAssessmentResponse(BaseModel):
    garden_profile_id: str
    cultivar_slug: str
    cultivar_dataset_id: str
    algorithm_version: str
    input_fingerprint: str
    status: str
    score: int | None = Field(default=None, ge=0, le=100)
    evidence_quality: int = Field(ge=0, le=100)
    result_group: str
    summary: str
    factors: list[SuitabilityFactorResponse]
    dimensions: list[SuitabilityDimensionResponse]
    constraints: list[str]
    assumptions: list[str]
    missing_evidence: list[str]


class GrowGuideSectionResponse(BaseModel):
    code: str
    title: str
    status: Literal["documented", "partial", "missing", "conflict"]
    summary: str
    instructions: list[str]
    confidence: str | None
    provenance: Literal["cultivar", "crop_baseline", "mixed", "none"]
    evidence: list[SuitabilityEvidenceReference]
    missing_evidence: list[str]


class GrowGuideTimelineEventResponse(BaseModel):
    code: str
    title: str
    start_date: date
    end_date: date | None = None
    summary: str
    confidence: str
    evidence: list[SuitabilityEvidenceReference]


class GrowGuideResponse(BaseModel):
    garden_profile_id: str
    garden_name: str
    target_year: int
    cultivar_slug: str
    cultivar_name: str
    crop_slug: str
    crop_name: str
    cultivar_dataset_id: str
    crop_dataset_id: str
    algorithm_version: str
    input_fingerprint: str
    summary: str
    sections: list[GrowGuideSectionResponse]
    timeline: list[GrowGuideTimelineEventResponse]
    conflicts: list[str]
    assumptions: list[str]
    missing_evidence: list[str]


class CatalogCropChoice(BaseModel):
    slug: str
    canonical_name: str
    planning_category: str


class CatalogCropSearchResult(BaseModel):
    crop: CatalogCropChoice
    score: float = Field(ge=0, le=1)
    matched_alias: str
    match_method: str


class CultivarResearchQualityResponse(BaseModel):
    algorithm_version: str
    score: int = Field(ge=0, le=100)
    tier: Literal["well_researched", "documented", "limited"]
    source_count: int = Field(ge=0)
    cultivar_specific_trait_count: int = Field(ge=0)
    strengths: list[str]
    missing_evidence: list[str]


class CatalogCultivarSearchResult(BaseModel):
    cultivar: CultivarResponse
    score: float = Field(ge=0, le=1)
    matched_alias: str
    match_method: str
    suitability: SuitabilityAssessmentResponse
    research_quality: CultivarResearchQualityResponse


class CatalogSearchResponse(BaseModel):
    query: str
    normalized_query: str
    crop_dataset_id: str
    cultivar_dataset_id: str | None
    crop_choices: list[CatalogCropSearchResult]
    cultivars: list[CatalogCultivarSearchResult]
    can_add_custom: bool = True


class ExperienceLevel(StrEnum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class GrowingMethod(StrEnum):
    IN_GROUND = "in_ground"
    RAISED_BED = "raised_bed"
    CONTAINERS = "containers"
    PROTECTED = "protected"


class IntendedUse(StrEnum):
    FRESH = "fresh"
    SNACKING = "snacking"
    SAUCE = "sauce"
    CANNING = "canning"
    PICKLING = "pickling"
    PROCESSING = "processing"


class DiseaseConcern(StrEnum):
    EARLY_BLIGHT = "early_blight"
    FUSARIUM_WILT = "fusarium_wilt"
    LATE_BLIGHT = "late_blight"
    ROOT_KNOT_NEMATODE = "root_knot_nematode"
    TOMATO_MOSAIC_VIRUS = "tomato_mosaic_virus"
    TOMATO_SPOTTED_WILT_VIRUS = "tomato_spotted_wilt_virus"
    VERTICILLIUM_WILT = "verticillium_wilt"


class GardenProfileCreateRequest(BaseModel):
    name: str = Field(default="My garden", min_length=1, max_length=120)
    country_code: str = Field(default="US", pattern=r"^US$")
    postal_code: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    target_year: int = Field(default_factory=lambda: date.today().year)
    experience_level: ExperienceLevel = ExperienceLevel.BEGINNER
    growing_methods: list[GrowingMethod] = Field(min_length=1, max_length=4)
    support_available: bool | None = None
    max_plant_spread_inches: int | None = Field(default=None, ge=6, le=120)
    max_container_volume_gallons: float | None = Field(default=None, ge=1, le=100)
    intended_uses: list[IntendedUse] = Field(default_factory=list, max_length=6)
    disease_concerns: list[DiseaseConcern] = Field(default_factory=list, max_length=7)

    @field_validator("name")
    @classmethod
    def validate_profile_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Garden name cannot be blank.")
        return value

    @field_validator("postal_code", mode="before")
    @classmethod
    def validate_postal_code(cls, value: object) -> object:
        if value is None:
            return None
        normalized = str(value).strip()
        if not re.fullmatch(r"\d{5}(?:-\d{4})?", normalized):
            raise ValueError("Enter a five-digit US ZIP code or ZIP+4.")
        return normalized

    @field_validator("growing_methods")
    @classmethod
    def normalize_growing_methods(cls, value: list[GrowingMethod]) -> list[GrowingMethod]:
        order = list(GrowingMethod)
        return [method for method in order if method in value]

    @field_validator("intended_uses")
    @classmethod
    def normalize_intended_uses(cls, value: list[IntendedUse]) -> list[IntendedUse]:
        return [item for item in IntendedUse if item in value]

    @field_validator("disease_concerns")
    @classmethod
    def normalize_disease_concerns(cls, value: list[DiseaseConcern]) -> list[DiseaseConcern]:
        return [item for item in DiseaseConcern if item in value]

    @model_validator(mode="after")
    def validate_location_and_year(self) -> GardenProfileCreateRequest:
        coordinates_supplied = self.latitude is not None or self.longitude is not None
        if coordinates_supplied and (self.latitude is None or self.longitude is None):
            raise ValueError("Latitude and longitude must be provided together.")
        if (self.postal_code is None) == (self.latitude is None):
            raise ValueError("Provide either a US ZIP code or a coordinate pair.")
        current_year = date.today().year
        if not current_year <= self.target_year <= current_year + 10:
            raise ValueError(f"Target year must be between {current_year} and {current_year + 10}.")
        return self


class LocationSourceResponse(BaseModel):
    dataset_id: str
    source_document_id: str
    title: str
    publisher: str | None
    source_url: str | None
    sha256: str
    retrieved_at: datetime | None
    source_locator: str
    coordinate_method: str


class EvidenceSourceResponse(BaseModel):
    dataset_id: str
    source_document_id: str
    title: str
    publisher: str | None
    source_url: str | None
    sha256: str
    retrieved_at: datetime | None
    license: str | None
    source_locator: str
    extraction_method: str
    extractor_version: str


class HardinessResponse(BaseModel):
    zone: str
    mean_annual_extreme_minimum_f: float
    confidence: str
    source: EvidenceSourceResponse


class ClimateNormalsResponse(BaseModel):
    station_id: str
    station_name: str
    station_latitude: float
    station_longitude: float
    station_elevation_m: float | None
    station_distance_km: float
    annual_mean_f: float
    annual_minimum_f: float
    annual_maximum_f: float
    annual_precipitation_in: float
    growing_degree_days_base_50_f: float
    last_spring_frost_50: str
    first_fall_frost_50: str
    growing_season_days_50: int
    frost_probability: float
    completeness_class: str
    minimum_years: int
    confidence: str
    source: EvidenceSourceResponse


class GardenProfileResponse(BaseModel):
    id: str
    name: str
    country_code: str
    location_input: str
    postal_code: str | None
    latitude: float | None
    longitude: float | None
    location_status: str
    coordinate_method: str | None
    location_source: LocationSourceResponse | None
    hardiness: HardinessResponse | None
    climate_normals: ClimateNormalsResponse | None
    target_year: int
    experience_level: ExperienceLevel
    growing_methods: list[GrowingMethod]
    support_available: bool | None
    max_plant_spread_inches: int | None
    max_container_volume_gallons: float | None
    intended_uses: list[IntendedUse]
    disease_concerns: list[DiseaseConcern]
    created_at: datetime
    updated_at: datetime


class GardenProfileListResponse(BaseModel):
    profiles: list[GardenProfileResponse]


class WishlistCreateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=12_000)
    name: str = Field(default="My garden wishlist", min_length=1, max_length=120)
    garden_profile_id: str = Field(min_length=36, max_length=36)

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


class WishlistBuilderCreateRequest(BaseModel):
    garden_profile_id: str = Field(min_length=36, max_length=36)
    name: str = Field(default="My garden wishlist", min_length=1, max_length=120)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Wishlist name cannot be blank.")
        return value


class WishlistEntryCreateRequest(BaseModel):
    original_text: str = Field(min_length=1, max_length=120)
    selection_kind: str = Field(pattern=r"^(crop|cultivar|custom_cultivar|custom_crop)$")
    crop_slug: str | None = Field(default=None, max_length=100)
    cultivar_slug: str | None = Field(default=None, max_length=100)

    @field_validator("original_text")
    @classmethod
    def validate_original_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Entry wording cannot be blank.")
        return value

    @model_validator(mode="after")
    def validate_selection(self) -> WishlistEntryCreateRequest:
        if self.selection_kind == "crop" and (
            self.crop_slug is None or self.cultivar_slug is not None
        ):
            raise ValueError("A crop selection requires one crop.")
        if self.selection_kind == "cultivar" and (
            self.cultivar_slug is None or self.crop_slug is not None
        ):
            raise ValueError("A cultivar selection requires one cultivar.")
        if self.selection_kind == "custom_cultivar" and (
            self.crop_slug is None or self.cultivar_slug is not None
        ):
            raise ValueError("A custom cultivar requires its known crop.")
        if self.selection_kind == "custom_crop" and (
            self.crop_slug is not None or self.cultivar_slug is not None
        ):
            raise ValueError("A custom crop cannot reference a catalog selection.")
        return self


class WishlistEntryUpdateRequest(BaseModel):
    crop_slug: str | None = Field(default=None, max_length=100)
    cultivar_slug: str | None = Field(default=None, max_length=100)
    keep_custom: bool = False

    @model_validator(mode="after")
    def require_one_action(self) -> WishlistEntryUpdateRequest:
        actions = sum(
            (
                self.crop_slug is not None,
                self.cultivar_slug is not None,
                self.keep_custom,
            )
        )
        if actions != 1:
            raise ValueError("Choose one crop, one cultivar, or keep the entry as custom.")
        return self


class WishlistCropMatch(BaseModel):
    slug: str
    canonical_name: str
    planning_category: str


class WishlistCandidateResponse(WishlistCropMatch):
    score: float = Field(ge=0, le=1)
    matched_alias: str


class WishlistCultivarMatch(BaseModel):
    id: str
    slug: str
    canonical_name: str
    crop_slug: str
    crop_name: str
    crop_type: str | None


class WishlistCultivarCandidateResponse(WishlistCultivarMatch):
    score: float = Field(ge=0, le=1)
    matched_alias: str


class WishlistEntryResponse(BaseModel):
    id: str
    position: int
    original_text: str
    normalized_text: str
    status: str
    resolution_method: str | None
    intent_kind: str
    cultivar_intent_text: str | None
    crop_type_intent: str | None
    resolved_crop: WishlistCropMatch | None
    resolved_cultivar: WishlistCultivarMatch | None
    candidates: list[WishlistCandidateResponse]
    cultivar_candidates: list[WishlistCultivarCandidateResponse]


class WishlistResponse(BaseModel):
    id: str
    dataset_id: str
    cultivar_dataset_id: str | None
    garden_profile_id: str | None
    name: str
    created_at: datetime
    updated_at: datetime
    entries: list[WishlistEntryResponse]
