from __future__ import annotations

import copy
import hashlib
import json
import re
import tempfile
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from kitchen_almanac.cultivar_catalog import REPOSITORY_ROOT, validate_cultivar_catalog

SCHEMA_VERSION = "1.0.0"
EXTRACTOR_VERSION = "rutgers-fs129-html-regex-v1.0.0"
CORPUS_ROOT = REPOSITORY_ROOT / "data/source/cultivars/rutgers-home-garden"
DEFAULT_MANIFEST = CORPUS_ROOT / "manifest.v1.json"
DEFAULT_STAGED = CORPUS_ROOT / "structured-evidence.v1.json"
DEFAULT_DECISIONS = CORPUS_ROOT / "review-decisions.v1.json"
ALLOWED_ACTIONS = {"approve_create", "approve_replace", "hold"}
ALLOWED_APPLICABILITY = {"home_garden_candidate", "requires_location_adaptation"}


class RutgersHomeGardenError(ValueError):
    """Raised when a reviewed Rutgers home-garden source cannot be reproduced."""


@dataclass(frozen=True)
class FactSpec:
    candidate_id: str
    crop_id: str
    field_name: str
    normalized_value: object
    unit: str | None
    confidence: str
    applicability: str
    source_locator: str
    source_excerpt: str
    pattern: str


@dataclass(frozen=True)
class CropRow:
    crop_id: str
    label: str
    in_row_inches: int
    between_row_inches: int
    starting_text: str
    starting_method: object
    month_text: str
    months: tuple[int, ...]
    yield_text: str
    yield_amount: int
    yield_unit: str


SINGLE_CROP_ROWS = (
    CropRow(
        "beets",
        "Beets",
        3,
        15,
        "seed",
        "direct_sow",
        "Ap,Ma,Ju,Jl",
        (4, 5, 6, 7),
        "14 lb.",
        14,
        "pounds_per_10ft_row",
    ),
    CropRow(
        "broccoli",
        "Broccoli",
        15,
        30,
        "transplant",
        "transplant",
        "Ap,Ma,Jl,Au",
        (4, 5, 7, 8),
        "8 heads",
        8,
        "heads_per_10ft_row",
    ),
    CropRow(
        "brussels-sprouts",
        "Brussels Sprouts",
        18,
        30,
        "transplant",
        "transplant",
        "Jl",
        (7,),
        "5 lb.",
        5,
        "pounds_per_10ft_row",
    ),
    CropRow(
        "cabbage",
        "Cabbage",
        18,
        24,
        "transplant",
        "transplant",
        "Ap,Jl",
        (4, 7),
        "7 heads",
        7,
        "heads_per_10ft_row",
    ),
    CropRow(
        "cauliflower",
        "Cauliflower",
        24,
        30,
        "transplant",
        "transplant",
        "Jl",
        (7,),
        "5 heads",
        5,
        "heads_per_10ft_row",
    ),
    CropRow(
        "collards",
        "Collards",
        18,
        24,
        "seed",
        "direct_sow",
        "Ap,Ma,Ju,Jl",
        (4, 5, 6, 7),
        "10 lb.",
        10,
        "pounds_per_10ft_row",
    ),
    CropRow(
        "cucumbers",
        "Cucumbers",
        36,
        30,
        "seed or trp.",
        ["direct_sow", "transplant"],
        "Ju,Jl",
        (6, 7),
        "8 lb.",
        8,
        "pounds_per_10ft_row",
    ),
    CropRow(
        "kale",
        "Kale",
        15,
        18,
        "seed",
        "direct_sow",
        "Jl,Au",
        (7, 8),
        "24 lb.",
        24,
        "pounds_per_10ft_row",
    ),
    CropRow(
        "kohlrabi",
        "Kohlrabi",
        4,
        15,
        "seed or trp.",
        ["direct_sow", "transplant"],
        "Ap,Ma,Jl,Au",
        (4, 5, 7, 8),
        "20 bulb.",
        20,
        "bulbs_per_10ft_row",
    ),
    CropRow(
        "tomatoes",
        "Tomatoes",
        24,
        36,
        "transplants",
        "transplant",
        "Ma,Ju",
        (5, 6),
        "50 lb.",
        50,
        "pounds_per_10ft_row",
    ),
)


def _table_row_pattern(
    label: str,
    in_row: int,
    between_row: int,
    starting: str,
    months: str,
    yield_text: str,
) -> str:
    cells = [label, str(in_row), str(between_row), starting, months, yield_text]
    return r"\s*".join(rf"<td>\s*{re.escape(cell)}\s*</td>" for cell in cells)


def _row_specs(row: CropRow) -> tuple[FactSpec, ...]:
    pattern = _table_row_pattern(
        row.label,
        row.in_row_inches,
        row.between_row_inches,
        row.starting_text,
        row.month_text,
        row.yield_text,
    )
    locator = f"FS129 > Vegetable Planting Guide > {row.label}"
    common = {
        "crop_id": row.crop_id,
        "confidence": "high",
        "source_locator": locator,
        "pattern": pattern,
    }
    return (
        FactSpec(
            candidate_id=f"rutgers-fs129-{row.crop_id}-plant-spacing",
            field_name="plant_spacing",
            normalized_value={"minimum": row.in_row_inches, "maximum": row.in_row_inches},
            unit="inches",
            applicability="home_garden_candidate",
            source_excerpt=(
                f"The home-garden table gives {row.in_row_inches} inches within the row."
            ),
            **common,
        ),
        FactSpec(
            candidate_id=f"rutgers-fs129-{row.crop_id}-row-spacing",
            field_name="row_spacing",
            normalized_value={
                "minimum": row.between_row_inches,
                "maximum": row.between_row_inches,
            },
            unit="inches",
            applicability="home_garden_candidate",
            source_excerpt=(
                f"The home-garden table gives {row.between_row_inches} inches between rows."
            ),
            **common,
        ),
        FactSpec(
            candidate_id=f"rutgers-fs129-{row.crop_id}-starting-method",
            field_name="starting_method",
            normalized_value=row.starting_method,
            unit=None,
            applicability="home_garden_candidate",
            source_excerpt="The home-garden table identifies the supported starting method.",
            **common,
        ),
        FactSpec(
            candidate_id=f"rutgers-fs129-{row.crop_id}-yield-per-row",
            field_name="yield_per_10ft_row",
            normalized_value={"minimum": row.yield_amount, "maximum": row.yield_amount},
            unit=row.yield_unit,
            applicability="home_garden_candidate",
            source_excerpt=(
                f"The home-garden table estimates {row.yield_text.rstrip('.')} per ten feet of row."
            ),
            **common,
        ),
        FactSpec(
            candidate_id=f"rutgers-fs129-{row.crop_id}-new-jersey-planting-months",
            field_name="new_jersey_planting_months",
            normalized_value=list(row.months),
            unit="calendar_month",
            applicability="requires_location_adaptation",
            source_excerpt=(
                "The table provides New Jersey planting months that require a location adapter."
            ),
            **common,
        ),
    )


LIGHT_PATTERN = (
    r"<p>If you cannot identify a location with full sun, leafy vegetables, such as lettuce "
    r"and spinach, require the least direct sunlight, only 4 to 5 hours\. Root vegetables "
    r"require 5 to 6 hours, and fruiting vegetables, such as tomatoes, cucumbers, and "
    r"zucchini, require at least 8 hours\. No vegetables can grow in total shade\.</p>"
)


def _light_spec(crop_id: str, minimum: int, *, confidence: str, mapping: str) -> FactSpec:
    return FactSpec(
        candidate_id=f"rutgers-fs129-{crop_id}-sun-hours",
        crop_id=crop_id,
        field_name="sun_hours",
        normalized_value={"minimum": minimum, "preferred_condition": "full_sun"},
        unit="hours_per_day",
        confidence=confidence,
        applicability="home_garden_candidate",
        source_locator="FS129 > Planning a Vegetable Garden > Location and sunlight",
        source_excerpt=(
            f"FS129 supports at least {minimum} direct-sun hours through its {mapping}."
        ),
        pattern=LIGHT_PATTERN,
    )


SNAP_BEAN_BUSH_PATTERN = _table_row_pattern("Beans, Snap, bush", 4, 24, "seed", "Ma,Ju,Jl", "6 lb.")
SNAP_BEAN_POLE_PATTERN = _table_row_pattern(
    "Beans, snap., pole", 36, 24, "seed", "Ma,Ju,Jl", "7 lb."
)
SNAP_BEAN_PATTERN = rf"{SNAP_BEAN_BUSH_PATTERN}.*?{SNAP_BEAN_POLE_PATTERN}"

SUMMER_SQUASH_BUSH_PATTERN = _table_row_pattern(
    "Squash, bush", 24, 48, "seeds or trp.", "Ju,Jl", "25 fruit"
)
SUMMER_SQUASH_VINE_PATTERN = _table_row_pattern(
    "Squash, vine", 36, 72, "seeds or trp.", "Ju", "20 fruits"
)
SUMMER_SQUASH_PATTERN = rf"{SUMMER_SQUASH_BUSH_PATTERN}.*?{SUMMER_SQUASH_VINE_PATTERN}"


FACT_SPECS = (
    *(spec for row in SINGLE_CROP_ROWS for spec in _row_specs(row)),
    FactSpec(
        candidate_id="rutgers-fs129-snap-beans-home-garden-profiles",
        crop_id="snap-beans",
        field_name="home_garden_profiles",
        normalized_value=[
            {
                "growth_habit": "bush",
                "plant_spacing": {"minimum": 4, "maximum": 4},
                "row_spacing": {"minimum": 24, "maximum": 24},
                "yield_per_10ft_row": {"minimum": 6, "maximum": 6},
                "yield_unit": "pounds_per_10ft_row",
            },
            {
                "growth_habit": "pole",
                "plant_spacing": {"minimum": 36, "maximum": 36},
                "row_spacing": {"minimum": 24, "maximum": 24},
                "yield_per_10ft_row": {"minimum": 7, "maximum": 7},
                "yield_unit": "pounds_per_10ft_row",
            },
        ],
        unit=None,
        confidence="high",
        applicability="home_garden_candidate",
        source_locator="FS129 > Vegetable Planting Guide > Snap beans, bush and pole",
        source_excerpt=(
            "The home-garden table distinguishes bush and pole spacing and row-yield profiles."
        ),
        pattern=SNAP_BEAN_PATTERN,
    ),
    FactSpec(
        candidate_id="rutgers-fs129-snap-beans-starting-method",
        crop_id="snap-beans",
        field_name="starting_method",
        normalized_value="direct_sow",
        unit=None,
        confidence="high",
        applicability="home_garden_candidate",
        source_locator="FS129 > Vegetable Planting Guide > Snap beans, bush and pole",
        source_excerpt="Both snap-bean growth habits are listed as seed-started.",
        pattern=SNAP_BEAN_PATTERN,
    ),
    FactSpec(
        candidate_id="rutgers-fs129-snap-beans-new-jersey-planting-months",
        crop_id="snap-beans",
        field_name="new_jersey_planting_months",
        normalized_value=[5, 6, 7],
        unit="calendar_month",
        confidence="high",
        applicability="requires_location_adaptation",
        source_locator="FS129 > Vegetable Planting Guide > Snap beans, bush and pole",
        source_excerpt="The New Jersey table lists May through July for snap beans.",
        pattern=SNAP_BEAN_PATTERN,
    ),
    FactSpec(
        candidate_id="rutgers-fs129-summer-squash-plant-spacing",
        crop_id="summer-squash",
        field_name="plant_spacing",
        normalized_value={"minimum": 24, "maximum": 36},
        unit="inches",
        confidence="high",
        applicability="home_garden_candidate",
        source_locator="FS129 > Vegetable Planting Guide > Squash, bush and vine",
        source_excerpt="The table gives 24 inches for bush squash and 36 inches for vine squash.",
        pattern=SUMMER_SQUASH_PATTERN,
    ),
    FactSpec(
        candidate_id="rutgers-fs129-summer-squash-row-spacing",
        crop_id="summer-squash",
        field_name="row_spacing",
        normalized_value={"minimum": 48, "maximum": 72},
        unit="inches",
        confidence="high",
        applicability="home_garden_candidate",
        source_locator="FS129 > Vegetable Planting Guide > Squash, bush and vine",
        source_excerpt="The table gives 48–72 inches between bush and vine squash rows.",
        pattern=SUMMER_SQUASH_PATTERN,
    ),
    FactSpec(
        candidate_id="rutgers-fs129-summer-squash-starting-method",
        crop_id="summer-squash",
        field_name="starting_method",
        normalized_value=["direct_sow", "transplant"],
        unit=None,
        confidence="high",
        applicability="home_garden_candidate",
        source_locator="FS129 > Vegetable Planting Guide > Squash, bush and vine",
        source_excerpt="The table supports seed or transplant starts for both squash habits.",
        pattern=SUMMER_SQUASH_PATTERN,
    ),
    FactSpec(
        candidate_id="rutgers-fs129-summer-squash-yield-per-row",
        crop_id="summer-squash",
        field_name="yield_per_10ft_row",
        normalized_value={"minimum": 20, "maximum": 25},
        unit="fruit_per_10ft_row",
        confidence="high",
        applicability="home_garden_candidate",
        source_locator="FS129 > Vegetable Planting Guide > Squash, bush and vine",
        source_excerpt="The table estimates 20–25 squash fruit per ten feet of row by habit.",
        pattern=SUMMER_SQUASH_PATTERN,
    ),
    FactSpec(
        candidate_id="rutgers-fs129-summer-squash-new-jersey-planting-months",
        crop_id="summer-squash",
        field_name="new_jersey_planting_months",
        normalized_value=[6, 7],
        unit="calendar_month",
        confidence="high",
        applicability="requires_location_adaptation",
        source_locator="FS129 > Vegetable Planting Guide > Squash, bush and vine",
        source_excerpt="The New Jersey table lists June and July across squash habits.",
        pattern=SUMMER_SQUASH_PATTERN,
    ),
    _light_spec("beets", 5, confidence="medium", mapping="root-vegetable category"),
    _light_spec("collards", 4, confidence="medium", mapping="leafy-vegetable category"),
    _light_spec("cucumbers", 8, confidence="high", mapping="explicit cucumber example"),
    _light_spec("kale", 4, confidence="medium", mapping="leafy-vegetable category"),
    _light_spec("summer-squash", 8, confidence="medium", mapping="zucchini example"),
    _light_spec("tomatoes", 8, confidence="high", mapping="explicit tomato example"),
)


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def staging_sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise RutgersHomeGardenError(f"Could not read {label}: {error}") from error
    if not isinstance(value, dict):
        raise RutgersHomeGardenError(f"{label.capitalize()} must be a JSON object.")
    return value


def validate_manifest(manifest: object, *, verify_snapshot: bool = False) -> list[str]:
    if not isinstance(manifest, dict):
        return ["Rutgers home-garden manifest must be an object."]
    required = {"schema_version", "corpus_id", "source", "extraction_policy"}
    if required - manifest.keys():
        return ["Rutgers home-garden manifest is incomplete."]
    errors: list[str] = []
    if manifest["schema_version"] != SCHEMA_VERSION:
        errors.append("Unsupported Rutgers home-garden manifest schema.")
    source = manifest["source"]
    required_source = {
        "key",
        "title",
        "publisher",
        "publication_number",
        "published_at",
        "retrieved_at",
        "audience",
        "region",
        "url",
        "source_path",
        "sha256",
        "media_type",
        "license",
        "scope",
    }
    if not isinstance(source, dict) or required_source - source.keys():
        return [*errors, "Rutgers home-garden source metadata is incomplete."]
    if source["publication_number"] != "FS129":
        errors.append("The home-garden source must retain publication number FS129.")
    if source["audience"] != "home vegetable gardeners":
        errors.append("The home-garden source must retain its intended audience.")
    if source["media_type"] != "text/html":
        errors.append("The FS129 snapshot must be HTML.")
    if not re.fullmatch(r"[0-9a-f]{64}", str(source["sha256"])):
        errors.append("The FS129 snapshot digest is invalid.")
    try:
        datetime.fromisoformat(str(source["retrieved_at"]).replace("Z", "+00:00"))
    except ValueError:
        errors.append("The FS129 retrieval timestamp is invalid.")
    if verify_snapshot:
        path = REPOSITORY_ROOT / source["source_path"]
        if not path.is_file():
            errors.append("The FS129 snapshot is missing; run `kitchen-almanac rutgers fetch`.")
        elif _file_sha256(path) != source["sha256"]:
            errors.append("The FS129 snapshot checksum does not match its manifest.")
    return errors


def fetch_source(manifest_path: Path = DEFAULT_MANIFEST) -> tuple[int, int]:
    manifest = read_json(manifest_path, "Rutgers home-garden manifest")
    errors = validate_manifest(manifest)
    if errors:
        raise RutgersHomeGardenError(" ".join(errors))
    source = manifest["source"]
    destination = REPOSITORY_ROOT / source["source_path"]
    if destination.is_file() and _file_sha256(destination) == source["sha256"]:
        return 0, 1
    request = urllib.request.Request(  # noqa: S310
        source["url"], headers={"User-Agent": "Kitchen-Almanac/0.1 source-fetcher"}
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310
            contents = response.read()
    except OSError as error:
        raise RutgersHomeGardenError(f"Could not fetch Rutgers FS129: {error}") from error
    actual_sha = hashlib.sha256(contents).hexdigest()
    if actual_sha != source["sha256"]:
        raise RutgersHomeGardenError(
            f"Downloaded Rutgers FS129 has checksum {actual_sha}; expected {source['sha256']}."
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as temporary:
        temporary.write(contents)
        temporary_path = Path(temporary.name)
    temporary_path.replace(destination)
    return 1, 0


def build_structured_evidence(manifest_path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    manifest = read_json(manifest_path, "Rutgers home-garden manifest")
    errors = validate_manifest(manifest, verify_snapshot=True)
    if errors:
        raise RutgersHomeGardenError(" ".join(errors))
    source = manifest["source"]
    source_text = (REPOSITORY_ROOT / source["source_path"]).read_text(encoding="utf-8")
    candidates: list[dict[str, Any]] = []
    for spec in FACT_SPECS:
        match = re.search(spec.pattern, source_text, flags=re.IGNORECASE | re.DOTALL)
        if match is None:
            raise RutgersHomeGardenError(
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
                "source_key": source["key"],
                "source_locator": spec.source_locator,
                "source_excerpt": spec.source_excerpt,
                "source_span_sha256": hashlib.sha256(normalized_span.encode()).hexdigest(),
                "extraction_method": "deterministic_regex",
            }
        )
    source_record = {
        key: source[key]
        for key in (
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
        )
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "extractor_version": EXTRACTOR_VERSION,
        "corpus_id": manifest["corpus_id"],
        "manifest_sha256": _file_sha256(manifest_path),
        "publication_scope": source["audience"],
        "publication_policy": "review_required_before_catalog_publication",
        "sources": [source_record],
        "candidates": sorted(candidates, key=lambda candidate: candidate["id"]),
    }


def write_structured_evidence(value: dict[str, Any], path: Path = DEFAULT_STAGED) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n")


def validate_structured_evidence(staged: object) -> list[str]:
    if not isinstance(staged, dict):
        return ["Structured Rutgers home-garden evidence must be an object."]
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
    if required - staged.keys():
        return ["Structured Rutgers home-garden evidence is incomplete."]
    errors: list[str] = []
    if staged["schema_version"] != SCHEMA_VERSION:
        errors.append("Unsupported Rutgers home-garden evidence schema.")
    if staged["extractor_version"] != EXTRACTOR_VERSION:
        errors.append("Unsupported Rutgers home-garden extractor version.")
    if staged["publication_scope"] != "home vegetable gardeners":
        errors.append("FS129 evidence must retain its home-gardener scope.")
    sources = staged["sources"]
    source_keys = (
        {source.get("key") for source in sources if isinstance(source, dict) and source.get("key")}
        if isinstance(sources, list)
        else set()
    )
    if not isinstance(sources, list) or len(source_keys) != len(sources):
        errors.append("Structured FS129 source keys must be present and unique.")
    candidates = staged["candidates"]
    if not isinstance(candidates, list):
        return [*errors, "Structured FS129 candidates must be a list."]
    ids: list[str] = []
    crop_fields: list[tuple[str, str]] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            errors.append("Every FS129 candidate must be an object.")
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
            "source_locator",
            "source_excerpt",
            "source_span_sha256",
            "extraction_method",
        }
        if required_candidate - candidate.keys():
            errors.append(f"FS129 candidate {candidate.get('id')!r} is incomplete.")
            continue
        ids.append(candidate["id"])
        crop_fields.append((candidate["crop_id"], candidate["field_name"]))
        if candidate["applicability"] not in ALLOWED_APPLICABILITY:
            errors.append(f"FS129 candidate {candidate['id']!r} has invalid applicability.")
        if candidate["confidence"] not in {"low", "medium", "high"}:
            errors.append(f"FS129 candidate {candidate['id']!r} has invalid confidence.")
        if candidate["source_key"] not in source_keys:
            errors.append(f"FS129 candidate {candidate['id']!r} has an unknown source.")
        if not re.fullmatch(r"[0-9a-f]{64}", str(candidate["source_span_sha256"])):
            errors.append(f"FS129 candidate {candidate['id']!r} has an invalid span digest.")
    if len(ids) != len(set(ids)):
        errors.append("FS129 candidate IDs must be unique.")
    if len(crop_fields) != len(set(crop_fields)):
        errors.append("FS129 crop fields must be unique.")
    return errors


def validate_review_decisions(staged: dict[str, Any], decisions: object) -> list[str]:
    if not isinstance(decisions, dict):
        return ["FS129 review decisions must be an object."]
    required = {"schema_version", "staging_sha256", "reviewed_at", "reviewer", "decisions"}
    if required - decisions.keys():
        return ["FS129 review decisions are incomplete."]
    errors: list[str] = []
    if decisions["schema_version"] != SCHEMA_VERSION:
        errors.append("Unsupported FS129 review schema.")
    if decisions["staging_sha256"] != staging_sha256(staged):
        errors.append("FS129 review decisions do not pin the current staging data.")
    try:
        datetime.fromisoformat(str(decisions["reviewed_at"]).replace("Z", "+00:00"))
    except ValueError:
        errors.append("The FS129 review timestamp is invalid.")
    candidates = {candidate["id"]: candidate for candidate in staged["candidates"]}
    values = decisions["decisions"]
    if not isinstance(values, list):
        return [*errors, "FS129 decisions must be a list."]
    ids = [decision.get("candidate_id") for decision in values if isinstance(decision, dict)]
    if len(ids) != len(values) or set(ids) != candidates.keys():
        errors.append("Every FS129 candidate requires exactly one review decision.")
    if len(ids) != len(set(ids)):
        errors.append("FS129 review decision IDs must be unique.")
    for decision in values:
        if not isinstance(decision, dict):
            continue
        candidate = candidates.get(decision.get("candidate_id"))
        action = decision.get("action")
        if action not in ALLOWED_ACTIONS:
            errors.append(f"FS129 decision {decision.get('candidate_id')!r} is invalid.")
        if not isinstance(decision.get("rationale"), str) or not decision["rationale"].strip():
            errors.append(f"FS129 decision {decision.get('candidate_id')!r} needs a rationale.")
        if (
            candidate
            and candidate["applicability"] == "requires_location_adaptation"
            and action != "hold"
        ):
            errors.append(
                f"FS129 location-specific candidate {candidate['id']!r} must remain on hold."
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
        raise RutgersHomeGardenError(" ".join(errors))
    output = copy.deepcopy(base)
    candidates = {candidate["id"]: candidate for candidate in staged["candidates"]}
    baselines = {baseline["crop_slug"]: baseline for baseline in output["crop_baselines"]}
    sources = {source["key"]: source for source in output["sources"]}
    staged_sources = {source["key"]: source for source in staged["sources"]}
    published_source_keys: set[str] = set()
    for decision in decisions["decisions"]:
        action = decision["action"]
        if action == "hold":
            continue
        candidate = candidates[decision["candidate_id"]]
        baseline = baselines.setdefault(
            candidate["crop_id"], {"crop_slug": candidate["crop_id"], "traits": []}
        )
        traits = {trait["field_name"]: trait for trait in baseline["traits"]}
        existing = traits.get(candidate["field_name"])
        if action == "approve_create" and existing is not None:
            raise RutgersHomeGardenError(
                f"Approved FS129 candidate {candidate['id']!r} would replace an existing field."
            )
        if action == "approve_replace" and existing is None:
            raise RutgersHomeGardenError(
                f"FS129 replacement {candidate['id']!r} has no existing field to replace."
            )
        if existing is not None:
            baseline["traits"].remove(existing)
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
        baseline["traits"].sort(key=lambda trait: trait["field_name"])
        published_source_keys.add(candidate["source_key"])
    for source_key in published_source_keys:
        source = staged_sources[source_key]
        if source_key in sources and sources[source_key] != source:
            raise RutgersHomeGardenError(f"FS129 source {source_key!r} conflicts with the catalog.")
        sources[source_key] = source
    output["sources"] = sorted(sources.values(), key=lambda source: source["key"])
    output["crop_baselines"] = sorted(
        baselines.values(), key=lambda baseline: baseline["crop_slug"]
    )
    publication_errors = validate_cultivar_catalog(output)
    if publication_errors:
        raise RutgersHomeGardenError(" ".join(publication_errors))
    return output


def load_and_apply_reviewed_crop_baselines(
    base: dict[str, Any],
    staged_path: Path = DEFAULT_STAGED,
    decisions_path: Path = DEFAULT_DECISIONS,
) -> dict[str, Any]:
    staged = read_json(staged_path, "structured FS129 evidence")
    decisions = read_json(decisions_path, "FS129 review decisions")
    return apply_reviewed_crop_baselines(base, staged, decisions)


def validate_committed_extraction(
    staged_path: Path = DEFAULT_STAGED,
    decisions_path: Path = DEFAULT_DECISIONS,
    manifest_path: Path = DEFAULT_MANIFEST,
) -> list[str]:
    staged = read_json(staged_path, "structured FS129 evidence")
    decisions = read_json(decisions_path, "FS129 review decisions")
    errors = [
        *validate_structured_evidence(staged),
        *validate_review_decisions(staged, decisions),
    ]
    try:
        expected = build_structured_evidence(manifest_path)
    except RutgersHomeGardenError as error:
        return [*errors, str(error)]
    if staged != expected:
        errors.append("Structured FS129 evidence is stale; run `kitchen-almanac rutgers extract`.")
    return errors
