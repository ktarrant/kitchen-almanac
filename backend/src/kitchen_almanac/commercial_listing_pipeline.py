from __future__ import annotations

import copy
from datetime import datetime
from pathlib import Path
from typing import Any

from kitchen_almanac.cultivar_catalog import REPOSITORY_ROOT
from kitchen_almanac.cultivar_pipeline import CultivarPipelineError, read_pipeline_json

SCHEMA_VERSION = "1.0.0"
DEFAULT_LISTINGS = REPOSITORY_ROOT / "data/source/cultivars/reviewed-commercial-listings.v1.json"
ALLOWED_AVAILABILITY = {"in_stock", "out_of_stock", "unknown", "retired"}
ELIGIBLE_AVAILABILITY = ALLOWED_AVAILABILITY - {"retired"}
ALLOWED_MATCH_METHODS = {"exact_name", "reviewed_alias"}


def validate_commercial_listing_source(data: object) -> list[str]:
    if not isinstance(data, dict):
        return ["Commercial listing source must be a JSON object."]
    required = {
        "schema_version",
        "allowed_vendors",
        "eligibility_policy",
        "sources",
        "listings",
    }
    missing = required - data.keys()
    if missing:
        return [f"Commercial listing source is missing {sorted(missing)!r}."]
    errors: list[str] = []
    if data["schema_version"] != SCHEMA_VERSION:
        errors.append(f"Unsupported commercial listing schema {data['schema_version']!r}.")

    vendors = data["allowed_vendors"]
    if not isinstance(vendors, list) or vendors != sorted(set(vendors), key=str.casefold):
        errors.append("Allowed commercial vendors must be sorted and unique.")

    policy = data["eligibility_policy"]
    if not isinstance(policy, dict) or policy != {
        "requires_reviewed_listing": True,
        "eligible_availability": sorted(ELIGIBLE_AVAILABILITY),
    }:
        errors.append("Commercial listing eligibility policy does not match the search gate.")

    sources = data["sources"]
    if not isinstance(sources, list):
        return [*errors, "Commercial listing sources must be a list."]
    source_keys = [source.get("key") for source in sources if isinstance(source, dict)]
    if len(source_keys) != len(sources) or len(source_keys) != len(set(source_keys)):
        errors.append("Commercial listing source keys must be present and unique.")
    source_by_key = {
        source["key"]: source
        for source in sources
        if isinstance(source, dict) and isinstance(source.get("key"), str)
    }
    for source in sources:
        if not isinstance(source, dict):
            errors.append("Every commercial listing source must be an object.")
            continue
        source_required = {
            "key",
            "title",
            "publisher",
            "url",
            "retrieved_at",
            "license",
            "scope",
        }
        if source_required - source.keys():
            errors.append(f"Commercial source {source.get('key')!r} is incomplete.")
            continue
        if source["publisher"] not in vendors:
            errors.append(f"Commercial source {source['key']!r} uses an unapproved vendor.")
        try:
            datetime.fromisoformat(str(source["retrieved_at"]).replace("Z", "+00:00"))
        except ValueError:
            errors.append(f"Commercial source {source['key']!r} has an invalid timestamp.")

    listings = data["listings"]
    if not isinstance(listings, list):
        return [*errors, "Commercial listings must be a list."]
    listing_ids: list[str] = []
    vendor_identifiers: list[tuple[str, str]] = []
    for listing in listings:
        if not isinstance(listing, dict):
            errors.append("Every commercial listing must be an object.")
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
            errors.append(f"Commercial listing {listing.get('id')!r} is incomplete.")
            continue
        listing_ids.append(listing["id"])
        vendor_identifiers.append((listing["vendor"], listing["source_identifier"]))
        source = source_by_key.get(listing["source_key"])
        if source is None:
            errors.append(f"Commercial listing {listing['id']!r} has an unknown source.")
        elif source["publisher"] != listing["vendor"]:
            errors.append(f"Commercial listing {listing['id']!r} vendor does not match source.")
        if listing["vendor"] not in vendors:
            errors.append(f"Commercial listing {listing['id']!r} uses an unapproved vendor.")
        if listing["availability_status"] not in ALLOWED_AVAILABILITY:
            errors.append(f"Commercial listing {listing['id']!r} has invalid availability.")
        if listing["identity_match_method"] not in ALLOWED_MATCH_METHODS:
            errors.append(f"Commercial listing {listing['id']!r} has invalid identity matching.")
        if listing["review_status"] != "approved":
            errors.append(f"Commercial listing {listing['id']!r} is not approved.")
        try:
            datetime.fromisoformat(str(listing["observed_at"]).replace("Z", "+00:00"))
        except ValueError:
            errors.append(f"Commercial listing {listing['id']!r} has an invalid observation.")
    if len(listing_ids) != len(set(listing_ids)):
        errors.append("Commercial listing IDs must be unique.")
    if len(vendor_identifiers) != len(set(vendor_identifiers)):
        errors.append("Commercial vendor identifiers must be unique.")
    return errors


def apply_reviewed_commercial_listings(
    catalog: dict[str, Any], listing_data: dict[str, Any]
) -> dict[str, Any]:
    errors = validate_commercial_listing_source(listing_data)
    if errors:
        raise CultivarPipelineError(" ".join(errors))
    output = copy.deepcopy(catalog)
    cultivars = {cultivar["slug"] for cultivar in output["cultivars"]}
    sources = {source["key"]: source for source in output["sources"]}
    for source in listing_data["sources"]:
        existing = sources.get(source["key"])
        if existing is not None and existing != source:
            raise CultivarPipelineError(
                f"Commercial source {source['key']!r} conflicts with catalog metadata."
            )
        sources[source["key"]] = source

    listings: list[dict[str, Any]] = []
    for listing in listing_data["listings"]:
        if listing["cultivar_slug"] not in cultivars:
            raise CultivarPipelineError(
                f"Commercial listing {listing['id']!r} targets an unknown cultivar."
            )
        listings.append(copy.deepcopy(listing))
    output["sources"] = sorted(sources.values(), key=lambda source: source["key"])
    output["commercial_listings"] = sorted(listings, key=lambda listing: listing["id"])
    return output


def load_and_apply_reviewed_commercial_listings(
    catalog: dict[str, Any], path: Path = DEFAULT_LISTINGS
) -> dict[str, Any]:
    return apply_reviewed_commercial_listings(
        catalog, read_pipeline_json(path, "reviewed commercial listings")
    )
