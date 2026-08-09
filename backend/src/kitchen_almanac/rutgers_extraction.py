from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from kitchen_almanac.cultivar_catalog import validate_cultivar_catalog
from kitchen_almanac.rutgers_inventory import (
    DEFAULT_MANIFEST,
    REPOSITORY_ROOT,
    RutgersInventoryError,
    read_manifest,
)

SCHEMA_VERSION = "1.0.0"
EXTRACTOR_VERSION = "rutgers-structured-regex-v1.0.0"
CORPUS_ROOT = REPOSITORY_ROOT / "data/source/cultivars/mid-atlantic-2026-2027"
DEFAULT_STAGED = CORPUS_ROOT / "structured-evidence.v1.json"
DEFAULT_DECISIONS = CORPUS_ROOT / "structured-review-decisions.v1.json"
ALLOWED_FIELDS = {
    "commercial_row_configuration",
    "harvest_guidance",
    "lime_below_ph",
    "plant_spacing",
    "regional_planting_window",
    "soil_ph",
    "starting_method",
}
ALLOWED_SCOPES = {
    "commercial_context_only",
    "home_garden_candidate",
    "requires_location_adaptation",
}
ALLOWED_ACTIONS = {"approve_create", "corroborate_existing", "hold", "reject"}


class RutgersExtractionError(ValueError):
    """Raised when structured Rutgers evidence cannot be reproduced or published."""


@dataclass(frozen=True)
class ExtractionSpec:
    candidate_id: str
    crop_id: str
    source_key: str
    source_page: int
    field_name: str
    normalized_value: object
    unit: str | None
    confidence: str
    applicability: str
    source_locator: str
    source_excerpt: str
    pattern: str


def _ph_specs(
    *, crop_id: str, source_label: str, target: float, lime_below: float
) -> tuple[ExtractionSpec, ExtractionSpec]:
    pattern = rf"{source_label}\s+{target:.1f}\s+{lime_below:.1f}"
    common = {
        "crop_id": crop_id,
        "source_key": "mid-atlantic-soil-nutrient-2026-2027",
        "source_page": 5,
        "confidence": "high",
        "applicability": "home_garden_candidate",
        "source_locator": "PDF page 5, Table B-1: Target Soil pH Values for Vegetable Crops",
        "pattern": pattern,
    }
    return (
        ExtractionSpec(
            candidate_id=f"rutgers-2026-{crop_id}-soil-ph",
            field_name="soil_ph",
            normalized_value=target,
            unit=None,
            source_excerpt=f"The crop table gives {crop_id} a target soil pH of {target:.1f}.",
            **common,
        ),
        ExtractionSpec(
            candidate_id=f"rutgers-2026-{crop_id}-lime-below-ph",
            field_name="lime_below_ph",
            normalized_value=lime_below,
            unit=None,
            source_excerpt=(
                f"The crop table marks pH {lime_below:.1f} as the threshold below which to lime."
            ),
            **common,
        ),
    )


EXTRACTION_SPECS = (
    *_ph_specs(
        crop_id="string-beans",
        source_label=r"Beans\s*-\s*lima,\s*snap",
        target=6.2,
        lime_below=6.0,
    ),
    *_ph_specs(crop_id="cucumbers", source_label="Cucumber", target=6.5, lime_below=6.0),
    *_ph_specs(
        crop_id="summer-squash",
        source_label=r"Squash\s*-\s*winter,\s*summer",
        target=6.5,
        lime_below=6.0,
    ),
    *_ph_specs(crop_id="tomatoes", source_label="Tomatoes", target=6.5, lime_below=6.0),
    ExtractionSpec(
        candidate_id="rutgers-2026-string-beans-starting-method",
        crop_id="string-beans",
        source_key="mid-atlantic-beans-2026-2027",
        source_page=6,
        field_name="starting_method",
        normalized_value="direct_sow",
        unit=None,
        confidence="medium",
        applicability="home_garden_candidate",
        source_locator="PDF page 6 (manual p. 173), Spacing > Snap Beans",
        source_excerpt="The snap-bean directions specify sowing seed directly in prepared rows.",
        pattern=r"Snap Beans\..*?Sow 1\s*-\s*1½\s+inches deep",
    ),
    ExtractionSpec(
        candidate_id="rutgers-2026-cucumbers-starting-method",
        crop_id="cucumbers",
        source_key="mid-atlantic-cucumbers-2026-2027",
        source_page=5,
        field_name="starting_method",
        normalized_value=["direct_sow", "transplant"],
        unit=None,
        confidence="medium",
        applicability="home_garden_candidate",
        source_locator="PDF page 5 (manual p. 224), Planting Dates",
        source_excerpt="The section covers both direct seeding and container-grown transplants.",
        pattern=r"Direct seeding starts.*?Container\s*-grown plug plants are started 3 weeks ahead",
    ),
    ExtractionSpec(
        candidate_id="rutgers-2026-summer-squash-starting-method",
        crop_id="summer-squash",
        source_key="mid-atlantic-summer-squash-2026-2027",
        source_page=5,
        field_name="starting_method",
        normalized_value=["direct_sow", "transplant"],
        unit=None,
        confidence="medium",
        applicability="home_garden_candidate",
        source_locator="PDF page 5 (manual p. 417), Seeding, Transplanting, and Spacing",
        source_excerpt="The section provides both seeding and transplanting directions.",
        pattern=r"Seeding, Transplanting, and Spacing.*?Transplants plants are planted",
    ),
    ExtractionSpec(
        candidate_id="rutgers-2026-tomatoes-starting-method",
        crop_id="tomatoes",
        source_key="mid-atlantic-tomatoes-2026-2027",
        source_page=8,
        field_name="starting_method",
        normalized_value="transplant",
        unit=None,
        confidence="medium",
        applicability="home_garden_candidate",
        source_locator="PDF page 8 (manual p. 457), Fresh Market Tomatoes",
        source_excerpt="The fresh-market production section establishes tomatoes as transplants.",
        pattern=r"tomatoes, start\s+transplanting April 10-20",
    ),
    ExtractionSpec(
        candidate_id="rutgers-2026-string-beans-commercial-spacing",
        crop_id="string-beans",
        source_key="mid-atlantic-beans-2026-2027",
        source_page=6,
        field_name="commercial_row_configuration",
        normalized_value={
            "row_spacing_inches": {"minimum": 30, "maximum": 36},
            "plants_per_foot": {"minimum": 6, "maximum": 10},
        },
        unit=None,
        confidence="high",
        applicability="commercial_context_only",
        source_locator="PDF page 6 (manual p. 173), Spacing > Snap Beans",
        source_excerpt="The commercial snap-bean row configuration combines row width and density.",
        pattern=r"Snap Beans\.\s+Rows 30-36 inches apart, 6\s*-10 plants/ft",
    ),
    ExtractionSpec(
        candidate_id="rutgers-2026-cucumbers-plant-spacing",
        crop_id="cucumbers",
        source_key="mid-atlantic-cucumbers-2026-2027",
        source_page=6,
        field_name="plant_spacing",
        normalized_value={"minimum": 6, "maximum": 12},
        unit="inches",
        confidence="medium",
        applicability="home_garden_candidate",
        source_locator="PDF page 6 (manual p. 225), Spacing",
        source_excerpt="In-row spacing spans 6–12 inches depending on cucumber type.",
        pattern=(
            r"Slicers:.*?plants 9\s*-12 inches apart.*?Hand Harvest Pickles:.*?"
            r"plants 6-8 inches apart"
        ),
    ),
    ExtractionSpec(
        candidate_id="rutgers-2026-summer-squash-plant-spacing",
        crop_id="summer-squash",
        source_key="mid-atlantic-summer-squash-2026-2027",
        source_page=5,
        field_name="plant_spacing",
        normalized_value={"minimum": 24, "maximum": 36},
        unit="inches",
        confidence="medium",
        applicability="home_garden_candidate",
        source_locator="PDF page 5 (manual p. 417), Seeding, Transplanting, and Spacing",
        source_excerpt="The in-row recommendation is two to three feet between plants.",
        pattern=r"Space rows 5\s*-6 ft apart\s+with plants 2-3 ft apart in the row",
    ),
    ExtractionSpec(
        candidate_id="rutgers-2026-tomatoes-plant-spacing",
        crop_id="tomatoes",
        source_key="mid-atlantic-tomatoes-2026-2027",
        source_page=8,
        field_name="plant_spacing",
        normalized_value={"minimum": 18, "maximum": 36},
        unit="inches",
        confidence="high",
        applicability="home_garden_candidate",
        source_locator="PDF page 8 (manual p. 457), Ground Culture",
        source_excerpt=(
            "In-row spacing spans 18–36 inches across determinate and indeterminate habits."
        ),
        pattern=(
            r"determinate-vined varieties.*?plants 18-24 inches.*?"
            r"indeterminate varieties.*?plants\s+24-36 inches"
        ),
    ),
    ExtractionSpec(
        candidate_id="rutgers-2026-string-beans-harvest-guidance",
        crop_id="string-beans",
        source_key="mid-atlantic-beans-2026-2027",
        source_page=7,
        field_name="harvest_guidance",
        normalized_value=["Pick fresh snap beans repeatedly when pods reach the desired size."],
        unit=None,
        confidence="medium",
        applicability="home_garden_candidate",
        source_locator="PDF page 7 (manual p. 174), Harvest and Post-Harvest Considerations",
        source_excerpt="Fresh-market snap beans are hand harvested repeatedly at the desired size.",
        pattern=(
            r"Fresh market snap beans are either hand harvested multiple times at the "
            r"desired size"
        ),
    ),
    ExtractionSpec(
        candidate_id="rutgers-2026-cucumbers-harvest-guidance",
        crop_id="cucumbers",
        source_key="mid-atlantic-cucumbers-2026-2027",
        source_page=7,
        field_name="harvest_guidance",
        normalized_value=[
            "Harvest at full varietal size while seeds are still soft.",
            "For slicers and hand-picked pickling cucumbers, harvest every two to three days.",
        ],
        unit=None,
        confidence="medium",
        applicability="home_garden_candidate",
        source_locator="PDF page 7 (manual p. 226), Harvest and Storage",
        source_excerpt=(
            "Harvest at varietal size with soft seeds; hand-picked crops need frequent "
            "picking."
        ),
        pattern=(
            r"harvested when they have reached full size.*?seeds are still soft.*?"
            r"2-3 day intervals"
        ),
    ),
    ExtractionSpec(
        candidate_id="rutgers-2026-summer-squash-harvest-guidance",
        crop_id="summer-squash",
        source_key="mid-atlantic-summer-squash-2026-2027",
        source_page=5,
        field_name="harvest_guidance",
        normalized_value=[
            "Harvest after fruit reaches the desired size but before seeds or rind harden.",
            "Handle fruit carefully to prevent bruising and scratching.",
        ],
        unit=None,
        confidence="medium",
        applicability="home_garden_candidate",
        source_locator="PDF page 5 (manual p. 417), Harvest and Post-Harvest Considerations",
        source_excerpt=(
            "Harvest before seeds or rind harden, and handle the delicate fruit carefully."
        ),
        pattern=(
            r"harvested after fruit reach the desired size.*?before they form hard seeds "
            r"or hard\s+rinds.*?Handle with care"
        ),
    ),
    ExtractionSpec(
        candidate_id="rutgers-2026-tomatoes-harvest-guidance",
        crop_id="tomatoes",
        source_key="mid-atlantic-tomatoes-2026-2027",
        source_page=9,
        field_name="harvest_guidance",
        normalized_value=[
            "Choose harvest ripeness for the intended use; fully ripe is appropriate for "
            "direct use.",
            "Handle fruit carefully and harvest often during peak production.",
        ],
        unit=None,
        confidence="medium",
        applicability="home_garden_candidate",
        source_locator="PDF page 9 (manual p. 458), Harvest and Post-Harvest Considerations",
        source_excerpt=(
            "Harvest stage depends on use; fruit needs careful handling and frequent picking."
        ),
        pattern=(
            r"harvested at the mature green stage.*?or fully ripe.*?handled with care.*?"
            r"Harvesting every day may\s+be required"
        ),
    ),
    ExtractionSpec(
        candidate_id="rutgers-2026-string-beans-regional-planting-window",
        crop_id="string-beans",
        source_key="mid-atlantic-beans-2026-2027",
        source_page=6,
        field_name="regional_planting_window",
        normalized_value={
            "market_snap": {"start": "04-10", "end": "08-10"},
            "cool_area_start_delay_days": 10,
            "cool_area_end_advance_days": 14,
        },
        unit=None,
        confidence="high",
        applicability="requires_location_adaptation",
        source_locator="PDF page 6 (manual p. 173), Planting and Harvesting Dates",
        source_excerpt=(
            "The regional table gives a market-snap window plus cooler-area adjustments."
        ),
        pattern=r"delay the start of planting by 10 days.*?Market Snap April 10\s*-\s*August 10",
    ),
    ExtractionSpec(
        candidate_id="rutgers-2026-cucumbers-regional-planting-window",
        crop_id="cucumbers",
        source_key="mid-atlantic-cucumbers-2026-2027",
        source_page=5,
        field_name="regional_planting_window",
        normalized_value={
            "southern_direct_seed_start": "late_april",
            "cool_area_direct_seed_start": "after_05-10",
            "successive_planting_end": "early_august",
        },
        unit=None,
        confidence="high",
        applicability="requires_location_adaptation",
        source_locator="PDF page 5 (manual p. 224), Planting Dates",
        source_excerpt=(
            "Direct-seeding dates vary across the Mid-Atlantic and extend into early August."
        ),
        pattern=r"Direct seeding starts late-April.*?after May 10.*?through early August",
    ),
    ExtractionSpec(
        candidate_id="rutgers-2026-summer-squash-regional-planting-window",
        crop_id="summer-squash",
        source_key="mid-atlantic-summer-squash-2026-2027",
        source_page=5,
        field_name="regional_planting_window",
        normalized_value={
            "southern": {"start": "04-15", "end": "08-15"},
            "cool_area": {"start": "05-10", "end": "08-01"},
        },
        unit=None,
        confidence="high",
        applicability="requires_location_adaptation",
        source_locator="PDF page 5 (manual p. 417), Seeding, Transplanting, and Spacing",
        source_excerpt="The seeding window varies between warmer and cooler Mid-Atlantic areas.",
        pattern=r"Seed April 15 through August 15.*?May 10 to August 1.*?cool areas",
    ),
    ExtractionSpec(
        candidate_id="rutgers-2026-tomatoes-regional-planting-window",
        crop_id="tomatoes",
        source_key="mid-atlantic-tomatoes-2026-2027",
        source_page=8,
        field_name="regional_planting_window",
        normalized_value={
            "southern_start": {"minimum": "04-10", "maximum": "04-20"},
            "northern_start": {"minimum": "05-10", "maximum": "05-25"},
        },
        unit=None,
        confidence="high",
        applicability="requires_location_adaptation",
        source_locator="PDF page 8 (manual p. 457), Fresh Market Tomatoes",
        source_excerpt=(
            "Transplanting starts differ between warmer southern and cooler northern areas."
        ),
        pattern=r"start\s+transplanting April 10-20.*?May 10-25 in cooler, northern\s+areas",
    ),
)


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def staging_sha256(staged: object) -> str:
    return hashlib.sha256(_canonical_bytes(staged)).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_record(document: dict[str, Any], publication: dict[str, Any]) -> dict[str, Any]:
    commodity = document["section_kind"] == "commodity"
    title = (
        f"{publication['title']}: {document['title']}" if commodity else document["title"]
    )
    return {
        "key": document["key"],
        "title": title,
        "publisher": publication["publisher"],
        "url": document["url"],
        "source_path": document["source_path"],
        "sha256": document["sha256"],
        "media_type": document["media_type"],
        "retrieved_at": "2026-08-08T00:00:00Z" if commodity else publication["retrieved_at"],
        "license": publication["license"],
        "scope": (
            "Current regional commercial recommendation; not written specifically for home "
            "gardeners"
            if commodity
            else "Regional commercial soil and nutrient guidance; crop pH values require "
            "home-garden review and per-acre rates remain commercial context only"
        ),
    }


def build_structured_evidence(manifest_path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    manifest = read_manifest(manifest_path, verify_snapshots=True)
    documents = {document["key"]: document for document in manifest["documents"]}
    needed_keys = {spec.source_key for spec in EXTRACTION_SPECS}
    missing_sources = needed_keys - documents.keys()
    if missing_sources:
        raise RutgersExtractionError(
            f"Extraction specs reference missing sources: {missing_sources!r}."
        )

    pages_by_source: dict[str, list[str]] = {}
    candidates: list[dict[str, Any]] = []
    for spec in EXTRACTION_SPECS:
        if spec.source_key not in pages_by_source:
            source_path = REPOSITORY_ROOT / documents[spec.source_key]["source_path"]
            try:
                pages_by_source[spec.source_key] = [
                    page.extract_text() or "" for page in PdfReader(source_path).pages
                ]
            except Exception as error:
                raise RutgersExtractionError(
                    f"Could not extract source {spec.source_key!r}: {error}"
                ) from error
        pages = pages_by_source[spec.source_key]
        if spec.source_page > len(pages):
            raise RutgersExtractionError(
                f"Candidate {spec.candidate_id!r} references missing page {spec.source_page}."
            )
        match = re.search(
            spec.pattern,
            pages[spec.source_page - 1],
            flags=re.IGNORECASE | re.DOTALL,
        )
        if match is None:
            raise RutgersExtractionError(
                f"Candidate {spec.candidate_id!r} no longer matches its reviewed source span."
            )
        normalized_span = " ".join(match.group(0).split())
        candidates.append(
            {
                "id": spec.candidate_id,
                "crop_id": spec.crop_id,
                "field_name": spec.field_name,
                "normalized_value": spec.normalized_value,
                "unit": spec.unit,
                "confidence": spec.confidence,
                "applicability": spec.applicability,
                "source_key": spec.source_key,
                "source_page": spec.source_page,
                "source_locator": spec.source_locator,
                "source_excerpt": spec.source_excerpt,
                "source_span_sha256": hashlib.sha256(normalized_span.encode()).hexdigest(),
                "extraction_method": "deterministic_regex",
            }
        )

    sources = [
        _source_record(documents[key], manifest["publication"]) for key in sorted(needed_keys)
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "extractor_version": EXTRACTOR_VERSION,
        "corpus_id": manifest["corpus_id"],
        "manifest_sha256": _file_sha256(manifest_path),
        "publication_scope": "commercial vegetable growers",
        "publication_policy": "review_required_before_catalog_publication",
        "sources": sources,
        "candidates": sorted(candidates, key=lambda candidate: candidate["id"]),
    }


def write_structured_evidence(staged: dict[str, Any], path: Path = DEFAULT_STAGED) -> None:
    path.write_text(json.dumps(staged, indent=2, ensure_ascii=False, sort_keys=True) + "\n")


def read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise RutgersExtractionError(f"Could not read {label}: {error}") from error
    if not isinstance(value, dict):
        raise RutgersExtractionError(f"{label.capitalize()} must be a JSON object.")
    return value


def validate_structured_evidence(staged: object) -> list[str]:
    if not isinstance(staged, dict):
        return ["Structured Rutgers evidence must be a JSON object."]
    required = {
        "schema_version",
        "extractor_version",
        "corpus_id",
        "manifest_sha256",
        "publication_scope",
        "publication_policy",
        "sources",
        "candidates",
    }
    missing = required - staged.keys()
    if missing:
        return [f"Structured Rutgers evidence is missing keys: {sorted(missing)!r}."]
    errors: list[str] = []
    if staged["schema_version"] != SCHEMA_VERSION:
        errors.append(f"Unsupported Rutgers extraction schema {staged['schema_version']!r}.")
    if staged["extractor_version"] != EXTRACTOR_VERSION:
        errors.append(f"Unsupported Rutgers extractor {staged['extractor_version']!r}.")
    if staged["publication_scope"] != "commercial vegetable growers":
        errors.append("Structured evidence must retain the commercial publication scope.")
    if staged["publication_policy"] != "review_required_before_catalog_publication":
        errors.append("Structured evidence must require review before publication.")

    sources = staged["sources"]
    if not isinstance(sources, list):
        return [*errors, "Structured Rutgers sources must be a list."]
    source_keys = [source.get("key") for source in sources if isinstance(source, dict)]
    if len(source_keys) != len(sources) or len(source_keys) != len(set(source_keys)):
        errors.append("Structured Rutgers source keys must be present and unique.")
    for source in sources:
        if not isinstance(source, dict):
            continue
        required_source = {
            "key",
            "title",
            "publisher",
            "url",
            "source_path",
            "sha256",
            "media_type",
            "retrieved_at",
            "license",
            "scope",
        }
        if required_source - source.keys():
            errors.append(f"Structured Rutgers source {source.get('key')!r} is incomplete.")
        if not re.fullmatch(r"[0-9a-f]{64}", str(source.get("sha256"))):
            errors.append(f"Structured Rutgers source {source.get('key')!r} has an invalid digest.")
        if source.get("media_type") != "application/pdf":
            errors.append(f"Structured Rutgers source {source.get('key')!r} must be a PDF.")

    candidates = staged["candidates"]
    if not isinstance(candidates, list):
        return [*errors, "Structured Rutgers candidates must be a list."]
    candidate_ids: list[str] = []
    crop_fields: list[tuple[str, str]] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            errors.append("Every structured Rutgers candidate must be an object.")
            continue
        required_candidate = {
            "id",
            "crop_id",
            "field_name",
            "normalized_value",
            "unit",
            "confidence",
            "applicability",
            "source_key",
            "source_page",
            "source_locator",
            "source_excerpt",
            "source_span_sha256",
            "extraction_method",
        }
        missing_candidate = required_candidate - candidate.keys()
        if missing_candidate:
            errors.append(
                f"Candidate {candidate.get('id')!r} is missing {sorted(missing_candidate)!r}."
            )
            continue
        candidate_ids.append(candidate["id"])
        crop_fields.append((candidate["crop_id"], candidate["field_name"]))
        if candidate["field_name"] not in ALLOWED_FIELDS:
            errors.append(f"Candidate {candidate['id']!r} has an unsupported field.")
        if candidate["applicability"] not in ALLOWED_SCOPES:
            errors.append(f"Candidate {candidate['id']!r} has invalid applicability.")
        if candidate["confidence"] not in {"low", "medium", "high"}:
            errors.append(f"Candidate {candidate['id']!r} has invalid confidence.")
        if candidate["source_key"] not in source_keys:
            errors.append(f"Candidate {candidate['id']!r} references an unknown source.")
        if not isinstance(candidate["source_page"], int) or candidate["source_page"] < 1:
            errors.append(f"Candidate {candidate['id']!r} has an invalid source page.")
        if not isinstance(candidate["source_locator"], str) or not candidate[
            "source_locator"
        ].strip():
            errors.append(f"Candidate {candidate['id']!r} needs a source locator.")
        if not isinstance(candidate["source_excerpt"], str) or not candidate[
            "source_excerpt"
        ].strip():
            errors.append(f"Candidate {candidate['id']!r} needs a source summary.")
        if not re.fullmatch(r"[0-9a-f]{64}", str(candidate["source_span_sha256"])):
            errors.append(f"Candidate {candidate['id']!r} has an invalid source-span digest.")
        if candidate["extraction_method"] != "deterministic_regex":
            errors.append(f"Candidate {candidate['id']!r} has an invalid extraction method.")
    if len(candidate_ids) != len(set(candidate_ids)):
        errors.append("Structured Rutgers candidate IDs must be unique.")
    if len(crop_fields) != len(set(crop_fields)):
        errors.append("Structured Rutgers crop fields must be unique.")
    return errors


def validate_review_decisions(staged: dict[str, Any], decisions: object) -> list[str]:
    if not isinstance(decisions, dict):
        return ["Structured Rutgers review decisions must be a JSON object."]
    required = {"schema_version", "staging_sha256", "reviewed_at", "reviewer", "decisions"}
    missing = required - decisions.keys()
    if missing:
        return [f"Structured Rutgers review decisions are missing {sorted(missing)!r}."]
    errors: list[str] = []
    if decisions["schema_version"] != SCHEMA_VERSION:
        errors.append(f"Unsupported Rutgers decision schema {decisions['schema_version']!r}.")
    if decisions["staging_sha256"] != staging_sha256(staged):
        errors.append("Structured Rutgers review decisions do not pin the current staging data.")
    try:
        datetime.fromisoformat(str(decisions["reviewed_at"]).replace("Z", "+00:00"))
    except ValueError:
        errors.append("Structured Rutgers review timestamp is invalid.")
    if not isinstance(decisions["reviewer"], str) or not decisions["reviewer"].strip():
        errors.append("Structured Rutgers review must identify a reviewer.")

    candidates = {candidate["id"]: candidate for candidate in staged["candidates"]}
    values = decisions["decisions"]
    if not isinstance(values, list):
        return [*errors, "Structured Rutgers decision records must be a list."]
    decision_ids = [item.get("candidate_id") for item in values if isinstance(item, dict)]
    if len(decision_ids) != len(values) or set(decision_ids) != candidates.keys():
        errors.append("Every structured Rutgers candidate requires exactly one review decision.")
    if len(decision_ids) != len(set(decision_ids)):
        errors.append("Structured Rutgers review decision IDs must be unique.")
    for decision in values:
        if not isinstance(decision, dict):
            continue
        action = decision.get("action")
        candidate = candidates.get(decision.get("candidate_id"))
        if action not in ALLOWED_ACTIONS:
            errors.append(f"Decision {decision.get('candidate_id')!r} has an invalid action.")
        if not isinstance(decision.get("rationale"), str) or not decision["rationale"].strip():
            errors.append(f"Decision {decision.get('candidate_id')!r} needs a rationale.")
        if (
            candidate
            and candidate["applicability"] != "home_garden_candidate"
            and action not in {"hold", "reject"}
        ):
            errors.append(
                f"Candidate {candidate['id']!r} cannot be accepted with applicability "
                f"{candidate['applicability']!r}."
            )
    return errors


def apply_reviewed_crop_baselines(
    base: dict[str, Any], staged: dict[str, Any], decisions: dict[str, Any]
) -> dict[str, Any]:
    errors = [
        *validate_cultivar_catalog(base),
        *validate_structured_evidence(staged),
        *validate_review_decisions(staged, decisions),
    ]
    if errors:
        raise RutgersExtractionError(" ".join(errors))

    output = copy.deepcopy(base)
    candidates = {candidate["id"]: candidate for candidate in staged["candidates"]}
    baselines = {baseline["crop_slug"]: baseline for baseline in output["crop_baselines"]}
    sources = {source["key"]: source for source in output["sources"]}
    staged_sources = {source["key"]: source for source in staged["sources"]}

    for decision in decisions["decisions"]:
        candidate = candidates[decision["candidate_id"]]
        crop_id = candidate["crop_id"]
        baseline = baselines.setdefault(crop_id, {"crop_slug": crop_id, "traits": []})
        traits = {trait["field_name"]: trait for trait in baseline["traits"]}
        action = decision["action"]
        if action == "corroborate_existing":
            existing = traits.get(candidate["field_name"])
            if existing is None or existing["normalized_value"] != candidate["normalized_value"]:
                raise RutgersExtractionError(
                    f"Corroboration {candidate['id']!r} does not match an existing value."
                )
            if existing["unit"] != candidate["unit"]:
                raise RutgersExtractionError(
                    f"Corroboration {candidate['id']!r} does not match the existing unit."
                )
            continue
        if action != "approve_create":
            continue
        if candidate["field_name"] in traits:
            raise RutgersExtractionError(
                f"Approved candidate {candidate['id']!r} would replace an existing field."
            )
        source = staged_sources[candidate["source_key"]]
        if source["key"] in sources and sources[source["key"]] != source:
            raise RutgersExtractionError(
                f"Source {source['key']!r} conflicts with existing catalog metadata."
            )
        sources[source["key"]] = source
        baseline["traits"].append(
            {
                "field_name": candidate["field_name"],
                "normalized_value": candidate["normalized_value"],
                "unit": candidate["unit"],
                "confidence": candidate["confidence"],
                "source_key": candidate["source_key"],
                "source_excerpt": candidate["source_excerpt"],
                "source_locator": candidate["source_locator"],
            }
        )
        baseline["traits"] = sorted(
            baseline["traits"], key=lambda trait: trait["field_name"]
        )

    output["sources"] = sorted(sources.values(), key=lambda source: source["key"])
    output["crop_baselines"] = sorted(
        baselines.values(), key=lambda baseline: baseline["crop_slug"]
    )
    publication_errors = validate_cultivar_catalog(output)
    if publication_errors:
        raise RutgersExtractionError(" ".join(publication_errors))
    return output


def load_and_apply_reviewed_crop_baselines(
    base: dict[str, Any],
    staged_path: Path = DEFAULT_STAGED,
    decisions_path: Path = DEFAULT_DECISIONS,
) -> dict[str, Any]:
    staged = read_json(staged_path, "structured Rutgers evidence")
    decisions = read_json(decisions_path, "structured Rutgers review decisions")
    return apply_reviewed_crop_baselines(base, staged, decisions)


def validate_committed_extraction(
    staged_path: Path = DEFAULT_STAGED,
    decisions_path: Path = DEFAULT_DECISIONS,
    manifest_path: Path = DEFAULT_MANIFEST,
) -> list[str]:
    staged = read_json(staged_path, "structured Rutgers evidence")
    decisions = read_json(decisions_path, "structured Rutgers review decisions")
    errors = [
        *validate_structured_evidence(staged),
        *validate_review_decisions(staged, decisions),
    ]
    try:
        expected = build_structured_evidence(manifest_path)
    except (RutgersInventoryError, RutgersExtractionError) as error:
        return [*errors, str(error)]
    if staged != expected:
        errors.append(
            "Structured Rutgers evidence is stale; run `kitchen-almanac rutgers extract`."
        )
    return errors
