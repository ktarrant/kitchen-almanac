from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from kitchen_almanac.database import Base


class SourceDocument(Base):
    __tablename__ = "source_documents"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    source_path: Mapped[str] = mapped_column(String(500))
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    publisher: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sha256: Mapped[str] = mapped_column(String(64), unique=True)
    media_type: Mapped[str] = mapped_column(String(100))
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    license: Mapped[str | None] = mapped_column(String(255), nullable=True)


class DatasetVersion(Base):
    __tablename__ = "dataset_versions"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(30))
    parser_version: Mapped[str] = mapped_column(String(30))
    source_document_id: Mapped[str] = mapped_column(ForeignKey("source_documents.id"))
    active: Mapped[bool] = mapped_column(Boolean, default=False)
    loaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    source_document: Mapped[SourceDocument] = relationship()


class Crop(Base):
    __tablename__ = "crops"
    __table_args__ = (UniqueConstraint("dataset_version_id", "slug"),)

    id: Mapped[str] = mapped_column(String(180), primary_key=True)
    dataset_version_id: Mapped[str] = mapped_column(ForeignKey("dataset_versions.id"), index=True)
    slug: Mapped[str] = mapped_column(String(100))
    canonical_name: Mapped[str] = mapped_column(String(255))
    planning_category: Mapped[str] = mapped_column(String(40))

    aliases: Mapped[list[CropAlias]] = relationship(cascade="all, delete-orphan")
    appearances: Mapped[list[CropSeasonAppearance]] = relationship(cascade="all, delete-orphan")


class CropAlias(Base):
    __tablename__ = "crop_aliases"
    __table_args__ = (UniqueConstraint("crop_id", "alias"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    crop_id: Mapped[str] = mapped_column(ForeignKey("crops.id"), index=True)
    alias: Mapped[str] = mapped_column(String(255))


class CropSeasonAppearance(Base):
    __tablename__ = "crop_season_appearances"
    __table_args__ = (UniqueConstraint("crop_id", "season", "source_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    crop_id: Mapped[str] = mapped_column(ForeignKey("crops.id"), index=True)
    season: Mapped[str] = mapped_column(String(40))
    source_name: Mapped[str] = mapped_column(String(255))
    source_line: Mapped[int] = mapped_column(Integer)
    position: Mapped[int] = mapped_column(Integer)


class CatalogCorrection(Base):
    __tablename__ = "catalog_corrections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_version_id: Mapped[str] = mapped_column(ForeignKey("dataset_versions.id"), index=True)
    source_name: Mapped[str] = mapped_column(String(255))
    canonical_name: Mapped[str] = mapped_column(String(255))
    correction_type: Mapped[str] = mapped_column(String(50))
    reason: Mapped[str] = mapped_column(Text)


class EvidenceClaim(Base):
    __tablename__ = "evidence_claims"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_version_id: Mapped[str] = mapped_column(ForeignKey("dataset_versions.id"), index=True)
    subject_type: Mapped[str] = mapped_column(String(80))
    subject_id: Mapped[str] = mapped_column(String(180), index=True)
    field_name: Mapped[str] = mapped_column(String(120))
    normalized_value: Mapped[dict | list | str | int | float | bool] = mapped_column(JSON)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    confidence: Mapped[str] = mapped_column(String(20))
    source_document_id: Mapped[str] = mapped_column(ForeignKey("source_documents.id"), index=True)
    source_excerpt: Mapped[str] = mapped_column(Text)
    source_locator: Mapped[str] = mapped_column(String(500))
    extraction_method: Mapped[str] = mapped_column(String(80))
    extractor_version: Mapped[str] = mapped_column(String(80))
