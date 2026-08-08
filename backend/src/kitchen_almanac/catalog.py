from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.1.0"
PARSER_VERSION = "1.1.0"
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SOURCE = REPOSITORY_ROOT / "Six Seasons Reference.md"
DEFAULT_OUTPUT = REPOSITORY_ROOT / "data" / "seed" / "kitchen-almanac-catalog.v1.json"

SEASON_ORDER = (
    "Spring",
    "Early Summer",
    "Midsummer",
    "Late Summer",
    "Fall",
    "Winter",
)


class CatalogError(ValueError):
    """Raised when source or generated catalog data violates the catalog contract."""


@dataclass(frozen=True)
class CorrectionRule:
    canonical_name: str
    correction_type: str
    reason: str


CORRECTION_RULES: dict[str, CorrectionRule] = {
    "Beets (Early Season)": CorrectionRule(
        "Beets", "season_qualifier", "Early Season is represented by the appearance season."
    ),
    "Carrots (Early Season)": CorrectionRule(
        "Carrots", "season_qualifier", "Early Season is represented by the appearance season."
    ),
    "Onion Family (Early Season)": CorrectionRule(
        "Onion Family",
        "season_qualifier",
        "Early Season is represented by the appearance season.",
    ),
    "Potatoes (Early Season)": CorrectionRule(
        "Potatoes", "season_qualifier", "Early Season is represented by the appearance season."
    ),
    "Turnips (Early Season)": CorrectionRule(
        "Turnips", "season_qualifier", "Early Season is represented by the appearance season."
    ),
    "Carrots (Late Season)": CorrectionRule(
        "Carrots", "season_qualifier", "Late Season is represented by the appearance season."
    ),
    "Onions (Storage)": CorrectionRule(
        "Onions", "harvest_form", "Storage is retained in the original source label."
    ),
    "Potatoes (Late Season)": CorrectionRule(
        "Potatoes", "season_qualifier", "Late Season is represented by the appearance season."
    ),
    "Rutabage": CorrectionRule(
        "Rutabaga", "spelling", "Correct an apparent spelling error in the source reference."
    ),
    "Turnips (Late Season)": CorrectionRule(
        "Turnips", "season_qualifier", "Late Season is represented by the appearance season."
    ),
}

CROP_GROUPS = {
    "Dried Corn and Polenta",
    "Lettuces and Early Greens",
    "Onion Family",
    "Sweet Peppers and Chiles",
}
PERENNIAL_CROPS = {"Artichokes", "Asparagus"}
SPECIALTY_SYSTEMS = {"Mushrooms"}

# These aliases are curated application data, not inferred corrections to the
# source document. Keeping them here makes wishlist resolution reviewable and
# ensures they participate in the versioned catalog digest.
COMMON_ALIASES: dict[str, tuple[str, ...]] = {
    "Artichokes": ("artichoke",),
    "English Peas": ("english pea", "garden pea", "garden peas", "shelling peas"),
    "Fava Beans": ("broad bean", "broad beans", "fava bean"),
    "Lettuces and Early Greens": ("leafy greens", "lettuce", "salad greens"),
    "Onion Family": ("alliums",),
    "Radishes": ("radish",),
    "Sugar Snap Peas": ("snap pea", "snap peas", "sugar snap pea"),
    "Beets": ("beet",),
    "Carrots": ("carrot",),
    "Potatoes": ("potato",),
    "Turnips": ("turnip",),
    "Cucumbers": ("cucumber",),
    "String Beans": ("green bean", "green beans", "snap beans", "string bean"),
    "Summer Squash": ("courgette", "courgettes", "zucchini"),
    "Corn": ("sweet corn",),
    "Eggplant": ("aubergine", "aubergines"),
    "Sweet Peppers and Chiles": (
        "bell pepper",
        "bell peppers",
        "chile",
        "chiles",
        "chili",
        "chilies",
        "hot peppers",
        "pepper",
        "peppers",
        "sweet pepper",
        "sweet peppers",
    ),
    "Shell Beans": ("shell bean", "shelling beans"),
    "Tomatoes": ("tomato",),
    "Brussels Sprouts": ("brussel sprouts", "brussels sprout"),
    "Swiss Chard": ("chard",),
    "Collards": ("collard greens",),
    "Mushrooms": ("mushroom",),
    "Cabbage": ("cabbages",),
    "Celery Root": ("celeriac",),
    "Dried Corn and Polenta": ("flint corn", "polenta corn"),
    "Onions": ("onion",),
    "Parsnips": ("parsnip",),
    "Rutabaga": ("rutabagas", "swede", "swedes"),
    "Winter Squash": ("pumpkin", "pumpkins"),
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    if not slug:
        raise CatalogError(f"Cannot create a slug from {value!r}.")
    return slug


def _planning_category(canonical_name: str) -> str:
    if canonical_name in CROP_GROUPS:
        return "crop_group"
    if canonical_name in PERENNIAL_CROPS:
        return "perennial"
    if canonical_name in SPECIALTY_SYSTEMS:
        return "specialty_system"
    return "annual_crop"


def _parse_source(source_text: str) -> list[dict[str, Any]]:
    appearances: list[dict[str, Any]] = []
    current_season: str | None = None
    season_position = 0

    for line_number, raw_line in enumerate(source_text.splitlines(), start=1):
        if not raw_line.strip():
            continue

        if not raw_line.startswith((" ", "\t")) and raw_line.endswith(":"):
            heading = raw_line[:-1]
            if heading not in SEASON_ORDER:
                raise CatalogError(f"Unknown season heading {heading!r} on line {line_number}.")
            current_season = heading
            season_position = 0
            continue

        if current_season is None:
            raise CatalogError(f"Crop entry appears before a season heading on line {line_number}.")
        if not raw_line.startswith("  ") or raw_line.startswith("   "):
            raise CatalogError(
                f"Crop entry on line {line_number} must use exactly two leading spaces."
            )

        source_name = raw_line.strip()
        if not source_name:
            raise CatalogError(f"Empty crop entry on line {line_number}.")
        season_position += 1
        appearances.append(
            {
                "season": current_season,
                "source_name": source_name,
                "source_line": line_number,
                "position": season_position,
            }
        )

    headings_seen = {appearance["season"] for appearance in appearances}
    missing_headings = [season for season in SEASON_ORDER if season not in headings_seen]
    if missing_headings:
        raise CatalogError(f"Source is missing season sections: {', '.join(missing_headings)}.")
    return appearances


def _canonical_bytes(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()


def _dataset_id(payload_without_id: dict[str, Any]) -> str:
    return f"kitchen-almanac-v1-{_sha256(_canonical_bytes(payload_without_id))[:16]}"


def build_catalog(source_path: Path = DEFAULT_SOURCE) -> dict[str, Any]:
    source_bytes = source_path.read_bytes()
    source_text = source_bytes.decode("utf-8")
    appearances = _parse_source(source_text)

    corrections_by_source: dict[str, dict[str, str]] = {}
    crops_by_name: dict[str, dict[str, Any]] = {}

    for appearance in appearances:
        source_name = appearance["source_name"]
        rule = CORRECTION_RULES.get(source_name)
        canonical_name = rule.canonical_name if rule else source_name

        if canonical_name != source_name:
            if rule is None:
                raise CatalogError(
                    f"Source label {source_name!r} changed without an explicit correction rule."
                )
            corrections_by_source[source_name] = {
                "canonical_name": canonical_name,
                "correction_type": rule.correction_type,
                "reason": rule.reason,
                "source_name": source_name,
            }

        crop = crops_by_name.setdefault(
            canonical_name,
            {
                "canonical_name": canonical_name,
                "id": _slugify(canonical_name),
                "planning_category": _planning_category(canonical_name),
                "source_names": set(),
                "appearances": [],
            },
        )
        crop["source_names"].add(source_name)
        crop["appearances"].append(appearance)

    crops = []
    for crop in crops_by_name.values():
        aliases = {
            crop["canonical_name"],
            *crop["source_names"],
            *COMMON_ALIASES.get(crop["canonical_name"], ()),
        }
        crops.append(
            {
                **crop,
                "aliases": sorted(aliases, key=str.casefold),
                "source_names": sorted(crop["source_names"]),
                "appearances": sorted(
                    crop["appearances"],
                    key=lambda item: (SEASON_ORDER.index(item["season"]), item["position"]),
                ),
            }
        )

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "parser_version": PARSER_VERSION,
        "source": {
            "id": f"sha256:{_sha256(source_bytes)}",
            "title": "Six Seasons Reference",
            "path": source_path.name,
            "media_type": "text/markdown",
            "sha256": _sha256(source_bytes),
        },
        "corrections": sorted(corrections_by_source.values(), key=lambda item: item["source_name"]),
        "crops": sorted(crops, key=lambda item: item["id"]),
    }
    return {"dataset_id": _dataset_id(payload), **payload}


def validate_catalog(catalog: dict[str, Any], source_path: Path | None = None) -> list[str]:
    errors: list[str] = []

    required_keys = {
        "dataset_id",
        "schema_version",
        "parser_version",
        "source",
        "corrections",
        "crops",
    }
    missing_keys = required_keys - catalog.keys()
    if missing_keys:
        return [f"Catalog is missing keys: {', '.join(sorted(missing_keys))}."]

    payload_without_id = {key: value for key, value in catalog.items() if key != "dataset_id"}
    expected_dataset_id = _dataset_id(payload_without_id)
    if catalog["dataset_id"] != expected_dataset_id:
        errors.append(f"Dataset ID is {catalog['dataset_id']!r}; expected {expected_dataset_id!r}.")

    crop_ids = [crop.get("id") for crop in catalog["crops"]]
    if len(crop_ids) != len(set(crop_ids)):
        errors.append("Crop IDs must be unique.")
    if crop_ids != sorted(crop_ids):
        errors.append("Crops must be ordered by ID.")

    corrections = {
        (item.get("source_name"), item.get("canonical_name")) for item in catalog["corrections"]
    }
    referenced_corrections: set[tuple[str, str]] = set()
    for crop in catalog["crops"]:
        canonical_name = crop.get("canonical_name")
        aliases = crop.get("aliases", [])
        if aliases != sorted(set(aliases), key=str.casefold):
            errors.append(f"Aliases for {canonical_name!r} must be unique and sorted.")
        if canonical_name not in aliases:
            errors.append(f"Aliases for {canonical_name!r} must include its canonical name.")
        for source_name in crop.get("source_names", []):
            if source_name != canonical_name:
                pair = (source_name, canonical_name)
                referenced_corrections.add(pair)
                if pair not in corrections:
                    errors.append(
                        f"{source_name!r} becomes {canonical_name!r} without a correction record."
                    )
        if not crop.get("appearances"):
            errors.append(f"Crop {canonical_name!r} has no seasonal appearances.")

    unreferenced_corrections = corrections - referenced_corrections
    if unreferenced_corrections:
        errors.append(f"Unreferenced corrections: {sorted(unreferenced_corrections)!r}.")

    if source_path is not None:
        source_digest = _sha256(source_path.read_bytes())
        if catalog["source"].get("sha256") != source_digest:
            errors.append("Catalog source digest does not match the current source file.")

    return errors


def write_catalog(catalog: dict[str, Any], output_path: Path = DEFAULT_OUTPUT) -> None:
    errors = validate_catalog(catalog)
    if errors:
        raise CatalogError("Cannot write invalid catalog: " + " ".join(errors))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(_canonical_bytes(catalog))


def read_catalog(catalog_path: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    try:
        return json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CatalogError(f"Cannot read catalog {catalog_path}: {error}") from error
