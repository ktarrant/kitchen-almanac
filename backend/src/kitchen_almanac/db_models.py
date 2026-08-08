from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
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
    source_scope: Mapped[str | None] = mapped_column(String(500), nullable=True)


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


class CultivarDatasetVersion(Base):
    __tablename__ = "cultivar_dataset_versions"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(30))
    parser_version: Mapped[str] = mapped_column(String(30))
    crop_dataset_version_id: Mapped[str] = mapped_column(
        ForeignKey("dataset_versions.id"), index=True
    )
    source_document_id: Mapped[str] = mapped_column(ForeignKey("source_documents.id"))
    active: Mapped[bool] = mapped_column(Boolean, default=False)
    loaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    crop_dataset: Mapped[DatasetVersion] = relationship()
    source_document: Mapped[SourceDocument] = relationship()


class Cultivar(Base):
    __tablename__ = "cultivars"
    __table_args__ = (UniqueConstraint("cultivar_dataset_version_id", "slug"),)

    id: Mapped[str] = mapped_column(String(180), primary_key=True)
    cultivar_dataset_version_id: Mapped[str] = mapped_column(
        ForeignKey("cultivar_dataset_versions.id"), index=True
    )
    crop_id: Mapped[str] = mapped_column(ForeignKey("crops.id"), index=True)
    slug: Mapped[str] = mapped_column(String(100))
    canonical_name: Mapped[str] = mapped_column(String(255))
    crop_type: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_status: Mapped[str] = mapped_column(String(20))

    crop: Mapped[Crop] = relationship()
    aliases: Mapped[list[CultivarAlias]] = relationship(cascade="all, delete-orphan")
    source_identifiers: Mapped[list[CultivarSourceIdentifier]] = relationship(
        cascade="all, delete-orphan"
    )
    commercial_listings: Mapped[list[CommercialSeedListing]] = relationship()


class CultivarAlias(Base):
    __tablename__ = "cultivar_aliases"
    __table_args__ = (UniqueConstraint("cultivar_id", "alias"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cultivar_id: Mapped[str] = mapped_column(ForeignKey("cultivars.id"), index=True)
    alias: Mapped[str] = mapped_column(String(255))


class CultivarSourceIdentifier(Base):
    __tablename__ = "cultivar_source_identifiers"
    __table_args__ = (UniqueConstraint("cultivar_id", "source_document_id", "source_identifier"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cultivar_id: Mapped[str] = mapped_column(ForeignKey("cultivars.id"), index=True)
    source_document_id: Mapped[str] = mapped_column(ForeignKey("source_documents.id"), index=True)
    source_identifier: Mapped[str] = mapped_column(String(255))
    name_in_source: Mapped[str] = mapped_column(String(255))

    source_document: Mapped[SourceDocument] = relationship()


class CultivarEvidenceClaim(Base):
    __tablename__ = "cultivar_evidence_claims"
    __table_args__ = (
        UniqueConstraint(
            "cultivar_dataset_version_id",
            "subject_kind",
            "subject_id",
            "field_name",
            "source_document_id",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cultivar_dataset_version_id: Mapped[str] = mapped_column(
        ForeignKey("cultivar_dataset_versions.id"), index=True
    )
    subject_kind: Mapped[str] = mapped_column(String(30))
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
    review_status: Mapped[str] = mapped_column(String(20))

    source_document: Mapped[SourceDocument] = relationship()


class CommercialSeedListing(Base):
    __tablename__ = "commercial_seed_listings"
    __table_args__ = (
        UniqueConstraint("cultivar_dataset_version_id", "vendor", "source_identifier"),
    )

    id: Mapped[str] = mapped_column(String(180), primary_key=True)
    cultivar_dataset_version_id: Mapped[str] = mapped_column(
        ForeignKey("cultivar_dataset_versions.id"), index=True
    )
    cultivar_id: Mapped[str | None] = mapped_column(
        ForeignKey("cultivars.id"), nullable=True, index=True
    )
    source_document_id: Mapped[str] = mapped_column(ForeignKey("source_documents.id"), index=True)
    vendor: Mapped[str] = mapped_column(String(255))
    listing_name: Mapped[str] = mapped_column(String(255))
    source_identifier: Mapped[str] = mapped_column(String(255))
    review_status: Mapped[str] = mapped_column(String(20))

    source_document: Mapped[SourceDocument] = relationship()


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


class LocationDatasetVersion(Base):
    __tablename__ = "location_dataset_versions"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(30))
    parser_version: Mapped[str] = mapped_column(String(30))
    source_document_id: Mapped[str] = mapped_column(ForeignKey("source_documents.id"))
    active: Mapped[bool] = mapped_column(Boolean, default=False)
    loaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    source_document: Mapped[SourceDocument] = relationship()


class PostalCodeLocation(Base):
    __tablename__ = "postal_code_locations"
    __table_args__ = (UniqueConstraint("location_dataset_version_id", "postal_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    location_dataset_version_id: Mapped[str] = mapped_column(
        ForeignKey("location_dataset_versions.id"), index=True
    )
    postal_code: Mapped[str] = mapped_column(String(5), index=True)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    coordinate_method: Mapped[str] = mapped_column(String(50))
    source_locator: Mapped[str] = mapped_column(String(255))


class ClimateDatasetVersion(Base):
    __tablename__ = "climate_dataset_versions"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    dataset_kind: Mapped[str] = mapped_column(String(50), index=True)
    schema_version: Mapped[str] = mapped_column(String(30))
    parser_version: Mapped[str] = mapped_column(String(30))
    source_document_id: Mapped[str] = mapped_column(ForeignKey("source_documents.id"))
    active: Mapped[bool] = mapped_column(Boolean, default=False)
    loaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    source_document: Mapped[SourceDocument] = relationship()


class ClimateStationNormal(Base):
    __tablename__ = "climate_station_normals"
    __table_args__ = (UniqueConstraint("climate_dataset_version_id", "station_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    climate_dataset_version_id: Mapped[str] = mapped_column(
        ForeignKey("climate_dataset_versions.id"), index=True
    )
    station_id: Mapped[str] = mapped_column(String(20), index=True)
    name: Mapped[str] = mapped_column(String(255))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    elevation_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    annual_mean_f: Mapped[float] = mapped_column(Float)
    annual_minimum_f: Mapped[float] = mapped_column(Float)
    annual_maximum_f: Mapped[float] = mapped_column(Float)
    annual_precipitation_in: Mapped[float] = mapped_column(Float)
    growing_degree_days_base_50_f: Mapped[float] = mapped_column(Float)
    last_spring_frost_50: Mapped[str] = mapped_column(String(5))
    first_fall_frost_50: Mapped[str] = mapped_column(String(5))
    growing_season_days_50: Mapped[int] = mapped_column(Integer)
    completeness_class: Mapped[str] = mapped_column(String(1))
    minimum_years: Mapped[int] = mapped_column(Integer)
    source_locator: Mapped[str] = mapped_column(String(255))


class LocationEvidenceClaim(Base):
    __tablename__ = "location_evidence_claims"
    __table_args__ = (
        UniqueConstraint("garden_profile_id", "climate_dataset_version_id", "field_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    garden_profile_id: Mapped[str] = mapped_column(ForeignKey("garden_profiles.id"), index=True)
    climate_dataset_version_id: Mapped[str] = mapped_column(
        ForeignKey("climate_dataset_versions.id"), index=True
    )
    field_name: Mapped[str] = mapped_column(String(120))
    normalized_value: Mapped[dict | list | str | int | float | bool] = mapped_column(JSON)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    confidence: Mapped[str] = mapped_column(String(20))
    source_document_id: Mapped[str] = mapped_column(ForeignKey("source_documents.id"), index=True)
    source_excerpt: Mapped[str] = mapped_column(Text)
    source_locator: Mapped[str] = mapped_column(String(500))
    extraction_method: Mapped[str] = mapped_column(String(80))
    extractor_version: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    climate_dataset: Mapped[ClimateDatasetVersion] = relationship()
    source_document: Mapped[SourceDocument] = relationship()


class GardenProfile(Base):
    __tablename__ = "garden_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    country_code: Mapped[str] = mapped_column(String(2), default="US")
    location_input: Mapped[str] = mapped_column(String(255))
    postal_code: Mapped[str | None] = mapped_column(String(10), nullable=True, index=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    location_status: Mapped[str] = mapped_column(String(40))
    location_dataset_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("location_dataset_versions.id"), nullable=True, index=True
    )
    coordinate_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    coordinate_source_locator: Mapped[str | None] = mapped_column(String(255), nullable=True)
    target_year: Mapped[int] = mapped_column(Integer)
    experience_level: Mapped[str] = mapped_column(String(20))
    growing_methods: Mapped[list[str]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    location_dataset: Mapped[LocationDatasetVersion | None] = relationship()
    location_evidence: Mapped[list[LocationEvidenceClaim]] = relationship(
        cascade="all, delete-orphan",
        order_by="LocationEvidenceClaim.field_name",
    )
    wishlists: Mapped[list[Wishlist]] = relationship(back_populates="garden_profile")


class Wishlist(Base):
    __tablename__ = "wishlists"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    dataset_version_id: Mapped[str] = mapped_column(ForeignKey("dataset_versions.id"), index=True)
    cultivar_dataset_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("cultivar_dataset_versions.id"), nullable=True, index=True
    )
    garden_profile_id: Mapped[str | None] = mapped_column(
        ForeignKey("garden_profiles.id"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(120), default="My garden wishlist")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    garden_profile: Mapped[GardenProfile | None] = relationship(back_populates="wishlists")
    entries: Mapped[list[WishlistEntry]] = relationship(
        cascade="all, delete-orphan",
        order_by="WishlistEntry.position",
        back_populates="wishlist",
    )


class WishlistEntry(Base):
    __tablename__ = "wishlist_entries"
    __table_args__ = (UniqueConstraint("wishlist_id", "position"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    wishlist_id: Mapped[str] = mapped_column(ForeignKey("wishlists.id"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    original_text: Mapped[str] = mapped_column(String(120))
    normalized_text: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(30))
    resolution_method: Mapped[str | None] = mapped_column(String(30), nullable=True)
    resolved_crop_id: Mapped[str | None] = mapped_column(
        ForeignKey("crops.id"), nullable=True, index=True
    )
    intent_kind: Mapped[str] = mapped_column(String(30), default="crop")
    cultivar_intent_text: Mapped[str | None] = mapped_column(String(120), nullable=True)
    crop_type_intent: Mapped[str | None] = mapped_column(String(80), nullable=True)
    resolved_cultivar_id: Mapped[str | None] = mapped_column(
        ForeignKey("cultivars.id"), nullable=True, index=True
    )

    wishlist: Mapped[Wishlist] = relationship(back_populates="entries")
    resolved_crop: Mapped[Crop | None] = relationship(foreign_keys=[resolved_crop_id])
    resolved_cultivar: Mapped[Cultivar | None] = relationship(foreign_keys=[resolved_cultivar_id])
    candidates: Mapped[list[WishlistCandidate]] = relationship(
        cascade="all, delete-orphan",
        order_by="WishlistCandidate.rank",
        back_populates="entry",
    )
    cultivar_candidates: Mapped[list[WishlistCultivarCandidate]] = relationship(
        cascade="all, delete-orphan",
        order_by="WishlistCultivarCandidate.rank",
        back_populates="entry",
    )


class WishlistCandidate(Base):
    __tablename__ = "wishlist_candidates"
    __table_args__ = (
        UniqueConstraint("wishlist_entry_id", "crop_id"),
        UniqueConstraint("wishlist_entry_id", "rank"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    wishlist_entry_id: Mapped[str] = mapped_column(ForeignKey("wishlist_entries.id"), index=True)
    crop_id: Mapped[str] = mapped_column(ForeignKey("crops.id"), index=True)
    rank: Mapped[int] = mapped_column(Integer)
    score: Mapped[float] = mapped_column(Float)
    matched_alias: Mapped[str] = mapped_column(String(255))

    entry: Mapped[WishlistEntry] = relationship(back_populates="candidates")
    crop: Mapped[Crop] = relationship()


class WishlistCultivarCandidate(Base):
    __tablename__ = "wishlist_cultivar_candidates"
    __table_args__ = (
        UniqueConstraint("wishlist_entry_id", "cultivar_id"),
        UniqueConstraint("wishlist_entry_id", "rank"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    wishlist_entry_id: Mapped[str] = mapped_column(ForeignKey("wishlist_entries.id"), index=True)
    cultivar_id: Mapped[str] = mapped_column(ForeignKey("cultivars.id"), index=True)
    rank: Mapped[int] = mapped_column(Integer)
    score: Mapped[float] = mapped_column(Float)
    matched_alias: Mapped[str] = mapped_column(String(255))

    entry: Mapped[WishlistEntry] = relationship(back_populates="cultivar_candidates")
    cultivar: Mapped[Cultivar] = relationship()
