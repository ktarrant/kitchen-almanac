from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0.0"
PARSER_VERSION = "1.0.0"
EXTRACTOR_VERSION = "manual-review-1.0.0"
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SOURCE = REPOSITORY_ROOT / "data/seed/cultivar-catalog.v1.json"


class CultivarCatalogError(ValueError):
    """Raised when the reviewed cultivar source snapshot is invalid."""


@dataclass(frozen=True)
class CultivarCatalog:
    id: str
    schema_version: str
    parser_version: str
    crop_dataset_id: str
    source_id: str
    source_title: str
    source_path: str
    source_sha256: str
    source_media_type: str
    data: dict[str, Any]


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def source_record_sha256(source: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_bytes(source)).hexdigest()


def source_document_id(source: dict[str, Any]) -> str:
    return f"cultivar-source-{source_record_sha256(source)[:16]}"


def _relative_path(path: Path) -> str:
    try:
        return path.relative_to(REPOSITORY_ROOT).as_posix()
    except ValueError:
        return path.name


def _validate_traits(
    traits: object,
    *,
    subject: str,
    source_keys: set[str],
) -> list[str]:
    errors: list[str] = []
    if not isinstance(traits, list):
        return [f"Traits for {subject} must be a list."]
    field_names = [trait.get("field_name") for trait in traits if isinstance(trait, dict)]
    if len(field_names) != len(traits) or any(not field for field in field_names):
        errors.append(f"Every trait for {subject} must have a field name.")
    if len(field_names) != len(set(field_names)):
        errors.append(f"Trait fields for {subject} must be unique.")
    for trait in traits:
        if not isinstance(trait, dict):
            continue
        required = {
            "field_name",
            "normalized_value",
            "unit",
            "confidence",
            "source_key",
            "source_excerpt",
            "source_locator",
        }
        missing = required - trait.keys()
        if missing:
            errors.append(f"Trait for {subject} is missing {sorted(missing)!r}.")
        if trait.get("source_key") not in source_keys:
            errors.append(f"Trait for {subject} references an unknown source.")
        if trait.get("confidence") not in {"low", "medium", "high"}:
            errors.append(f"Trait for {subject} has an invalid confidence.")
    return errors


def validate_cultivar_catalog(data: object) -> list[str]:
    if not isinstance(data, dict):
        return ["Cultivar source must be a JSON object."]
    errors: list[str] = []
    required = {
        "schema_version",
        "crop_dataset_id",
        "review_status",
        "sources",
        "crop_baselines",
        "cultivars",
        "commercial_listings",
    }
    missing = required - data.keys()
    if missing:
        return [f"Cultivar source is missing keys: {', '.join(sorted(missing))}."]
    if data["schema_version"] != SCHEMA_VERSION:
        errors.append(f"Unsupported cultivar schema {data['schema_version']!r}.")
    if data["review_status"] != "approved":
        errors.append("The cultivar snapshot must be approved before publication.")
    if not isinstance(data["crop_dataset_id"], str) or not data["crop_dataset_id"]:
        errors.append("The cultivar snapshot must name its crop dataset.")

    sources = data["sources"]
    if not isinstance(sources, list):
        return [*errors, "Sources must be a list."]
    source_keys = {
        source.get("key") for source in sources if isinstance(source, dict) and source.get("key")
    }
    if len(source_keys) != len(sources):
        errors.append("Source keys must be present and unique.")
    for source in sources:
        if not isinstance(source, dict):
            continue
        source_required = {"key", "title", "publisher", "url", "retrieved_at", "license"}
        if source_required - source.keys():
            errors.append(f"Source {source.get('key')!r} is incomplete.")
        try:
            datetime.fromisoformat(str(source.get("retrieved_at", "")).replace("Z", "+00:00"))
        except ValueError:
            errors.append(f"Source {source.get('key')!r} has an invalid retrieval time.")
        snapshot_fields = {"source_path", "sha256", "media_type"}
        present_snapshot_fields = snapshot_fields & source.keys()
        if present_snapshot_fields and present_snapshot_fields != snapshot_fields:
            errors.append(
                f"Source {source.get('key')!r} must provide source_path, sha256, "
                "and media_type together."
            )
        elif present_snapshot_fields and len(source["sha256"]) != 64:
            errors.append(f"Source {source.get('key')!r} has an invalid SHA-256 digest.")

    baselines = data["crop_baselines"]
    if not isinstance(baselines, list):
        errors.append("Crop baselines must be a list.")
        baselines = []
    baseline_slugs = [item.get("crop_slug") for item in baselines if isinstance(item, dict)]
    if len(baseline_slugs) != len(set(baseline_slugs)):
        errors.append("Crop baseline slugs must be unique.")
    for baseline in baselines:
        if isinstance(baseline, dict):
            errors.extend(
                _validate_traits(
                    baseline.get("traits"),
                    subject=f"crop {baseline.get('crop_slug')!r}",
                    source_keys=source_keys,
                )
            )

    cultivars = data["cultivars"]
    if not isinstance(cultivars, list):
        errors.append("Cultivars must be a list.")
        cultivars = []
    cultivar_slugs = [item.get("slug") for item in cultivars if isinstance(item, dict)]
    if len(cultivar_slugs) != len(set(cultivar_slugs)):
        errors.append("Cultivar slugs must be unique.")
    for cultivar in cultivars:
        if not isinstance(cultivar, dict):
            continue
        cultivar_required = {
            "slug",
            "canonical_name",
            "crop_slug",
            "crop_type",
            "description",
            "review_status",
            "aliases",
            "source_identifiers",
            "traits",
        }
        missing_cultivar = cultivar_required - cultivar.keys()
        if missing_cultivar:
            errors.append(f"Cultivar {cultivar.get('slug')!r} is incomplete.")
        if cultivar.get("review_status") != "approved":
            errors.append(f"Cultivar {cultivar.get('slug')!r} is not approved.")
        aliases = cultivar.get("aliases")
        if not isinstance(aliases, list) or aliases != sorted(set(aliases), key=str.casefold):
            errors.append(
                f"Aliases for cultivar {cultivar.get('slug')!r} must be sorted and unique."
            )
        if cultivar.get("canonical_name") not in (aliases or []):
            errors.append(f"Cultivar {cultivar.get('slug')!r} must include its name as an alias.")
        identifiers = cultivar.get("source_identifiers")
        if not isinstance(identifiers, list) or not identifiers:
            errors.append(f"Cultivar {cultivar.get('slug')!r} requires a source identifier.")
        else:
            for identifier in identifiers:
                required_identifier = {
                    "source_key",
                    "source_identifier",
                    "name_in_source",
                }
                if not isinstance(identifier, dict) or required_identifier - identifier.keys():
                    errors.append(
                        f"Cultivar {cultivar.get('slug')!r} has an incomplete source identifier."
                    )
                    continue
                if identifier.get("source_key") not in source_keys:
                    errors.append(f"Cultivar {cultivar.get('slug')!r} has an unknown source.")
        errors.extend(
            _validate_traits(
                cultivar.get("traits"),
                subject=f"cultivar {cultivar.get('slug')!r}",
                source_keys=source_keys,
            )
        )

    listings = data["commercial_listings"]
    if not isinstance(listings, list):
        errors.append("Commercial listings must be a list.")
        listings = []
    listing_ids = [item.get("id") for item in listings if isinstance(item, dict)]
    if len(listing_ids) != len(set(listing_ids)):
        errors.append("Commercial listing IDs must be unique.")
    for listing in listings:
        if not isinstance(listing, dict):
            continue
        listing_required = {
            "id",
            "cultivar_slug",
            "source_key",
            "vendor",
            "listing_name",
            "source_identifier",
            "availability_status",
            "observed_at",
            "identity_match_method",
            "review_status",
        }
        if listing_required - listing.keys():
            errors.append(f"Listing {listing.get('id')!r} is incomplete.")
        if listing.get("cultivar_slug") not in cultivar_slugs:
            errors.append(f"Listing {listing.get('id')!r} references an unknown cultivar.")
        if listing.get("source_key") not in source_keys:
            errors.append(f"Listing {listing.get('id')!r} references an unknown source.")
        if listing.get("review_status") != "approved":
            errors.append(f"Listing {listing.get('id')!r} is not approved.")
        if listing.get("availability_status") not in {
            "in_stock",
            "out_of_stock",
            "unknown",
            "retired",
        }:
            errors.append(f"Listing {listing.get('id')!r} has invalid availability.")
        if listing.get("identity_match_method") not in {"exact_name", "reviewed_alias"}:
            errors.append(f"Listing {listing.get('id')!r} has invalid identity matching.")
        try:
            datetime.fromisoformat(str(listing.get("observed_at", "")).replace("Z", "+00:00"))
        except ValueError:
            errors.append(f"Listing {listing.get('id')!r} has an invalid observation time.")
    return errors


def build_cultivar_catalog(source_path: Path = DEFAULT_SOURCE) -> CultivarCatalog:
    try:
        source_bytes = source_path.read_bytes()
        data = json.loads(source_bytes)
    except (OSError, json.JSONDecodeError) as error:
        raise CultivarCatalogError(f"Could not read cultivar source: {error}") from error
    errors = validate_cultivar_catalog(data)
    if errors:
        raise CultivarCatalogError(" ".join(errors))
    source_sha = hashlib.sha256(source_bytes).hexdigest()
    dataset_id = f"cultivar-catalog-v1-{source_sha[:16]}"
    return CultivarCatalog(
        id=dataset_id,
        schema_version=SCHEMA_VERSION,
        parser_version=PARSER_VERSION,
        crop_dataset_id=data["crop_dataset_id"],
        source_id=f"source-{dataset_id}",
        source_title="Kitchen Almanac reviewed cultivar evidence v1",
        source_path=_relative_path(source_path.resolve()),
        source_sha256=source_sha,
        source_media_type="application/json",
        data=data,
    )
