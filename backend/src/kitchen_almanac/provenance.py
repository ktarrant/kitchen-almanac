from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, HttpUrl, model_validator


class Confidence(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class MeasurementRange(BaseModel):
    """A normalized scalar or range that always carries its unit."""

    low: float
    expected: float
    high: float
    unit: str = Field(min_length=1)

    @model_validator(mode="after")
    def ordered_values(self) -> MeasurementRange:
        if not self.low <= self.expected <= self.high:
            raise ValueError("Measurement values must satisfy low <= expected <= high.")
        return self


class SourceDocumentRecord(BaseModel):
    id: str
    title: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    media_type: str
    local_path: str | None = None
    source_url: HttpUrl | None = None
    publisher: str | None = None
    retrieved_at: datetime | None = None
    license: str | None = None


class EvidenceClaim(BaseModel):
    dataset_version_id: str
    subject_type: str
    subject_id: str
    field_name: str
    normalized_value: str | int | float | bool
    unit: str | None = None
    confidence: Confidence
    source_document_id: str
    source_excerpt: str
    source_locator: str
    extraction_method: str
    extractor_version: str
