from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "2.2.0"
PARSER_VERSION = "2.2.0"
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SOURCE = REPOSITORY_ROOT / "Six Seasons Reference.md"
DEFAULT_TAXONOMY_SOURCE = (
    REPOSITORY_ROOT
    / "data"
    / "source"
    / "cultivars"
    / "mid-atlantic-2026-2027"
    / "commodity-crosswalk.v1.json"
)
DEFAULT_BROWSE_TAXONOMY_SOURCE = (
    REPOSITORY_ROOT
    / "data"
    / "source"
    / "catalog"
    / "gardener-browse-taxonomy.v1.json"
)
DEFAULT_OUTPUT = REPOSITORY_ROOT / "data" / "seed" / "kitchen-almanac-catalog.v2.json"

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

CROP_GROUPS = {"Specialty Melons"}
PERENNIAL_CROPS = {"Asparagus", "Horseradish", "Strawberries"}
SPECIALTY_SYSTEMS: set[str] = set()

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

# The Rutgers taxonomy is canonical. This crosswalk only carries forward
# seasonal appearances from the original reference where a reviewed mapping
# exists; it is not used to decide which crops are published.
LEGACY_CROP_IDS: dict[str, str] = {
    "asparagus": "asparagus",
    "snap-beans": "string-beans",
    "lima-beans": "shell-beans",
    "beets": "beets",
    "carrots": "carrots",
    "celery": "celery",
    "broccoli": "broccoli",
    "brussels-sprouts": "brussels-sprouts",
    "cabbage": "cabbage",
    "cauliflower": "cauliflower",
    "collards": "collards",
    "kale": "kale",
    "kohlrabi": "kohlrabi",
    "cucumbers": "cucumbers",
    "eggplant": "eggplant",
    "garlic": "onion-family",
    "mustard-greens": "lettuces-and-early-greens",
    "turnip-greens": "turnips",
    "leeks": "onion-family",
    "lettuce": "lettuces-and-early-greens",
    "endive": "lettuces-and-early-greens",
    "escarole": "lettuces-and-early-greens",
    "onions": "onions",
    "parsnips": "parsnips",
    "succulent-peas": "english-peas",
    "sweet-peppers": "sweet-peppers-and-chiles",
    "hot-peppers": "sweet-peppers-and-chiles",
    "potatoes": "potatoes",
    "winter-squash": "winter-squash",
    "radishes": "radishes",
    "rutabagas": "rutabaga",
    "turnips": "turnips",
    "summer-squash": "summer-squash",
    "sweet-corn": "corn",
    "tomatoes": "tomatoes",
}

# Only one-to-one mappings inherit the old identity's aliases. Split concepts
# use explicit Rutgers-aligned aliases so broad labels do not create ambiguous
# exact matches.
LEGACY_ALIAS_INHERITANCE = {
    "asparagus",
    "beets",
    "broccoli",
    "brussels-sprouts",
    "cabbage",
    "carrots",
    "cauliflower",
    "celery",
    "collards",
    "cucumbers",
    "eggplant",
    "kale",
    "kohlrabi",
    "onions",
    "parsnips",
    "potatoes",
    "radishes",
    "rutabagas",
    "snap-beans",
    "succulent-peas",
    "summer-squash",
    "sweet-corn",
    "tomatoes",
    "turnips",
    "winter-squash",
}

RUTGERS_ALIASES: dict[str, tuple[str, ...]] = {
    "snap-beans": ("green bean", "green beans", "snap bean", "string bean", "string beans"),
    "lima-beans": ("butter bean", "butter beans", "lima bean"),
    "beets": ("beet",),
    "carrots": ("carrot",),
    "brussels-sprouts": ("brussel sprouts", "brussels sprout"),
    "cabbage": ("cabbages",),
    "chinese-cabbage": ("bok choy", "napa cabbage", "pak choi"),
    "collards": ("collard", "collard greens"),
    "cucumbers": ("cucumber",),
    "edamame": ("edamame soybeans", "vegetable soybeans"),
    "eggplant": ("aubergine", "aubergines"),
    "mustard-greens": ("mustard green",),
    "turnip-greens": ("turnip green",),
    "leeks": ("leek",),
    "lettuce": ("lettuces",),
    "muskmelons": ("cantaloupe", "cantaloupes", "muskmelon"),
    "specialty-melons": ("specialty melon",),
    "onions": ("onion",),
    "parsnips": ("parsnip",),
    "succulent-peas": ("english pea", "english peas", "garden pea", "garden peas", "shelling peas"),
    "sweet-peppers": ("bell pepper", "bell peppers", "sweet pepper"),
    "hot-peppers": ("chile", "chiles", "chili", "chilies", "hot pepper"),
    "potatoes": ("potato",),
    "pumpkins": ("pumpkin",),
    "radishes": ("radish",),
    "rutabagas": ("rutabaga", "swede", "swedes"),
    "turnips": ("turnip",),
    "strawberries": ("strawberry",),
    "summer-squash": ("courgette", "courgettes", "zucchini"),
    "sweet-corn": ("corn",),
    "sweet-potatoes": ("sweet potato",),
    "tomatoes": ("tomato",),
    "watermelons": ("watermelon",),
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    if not slug:
        raise CatalogError(f"Cannot create a slug from {value!r}.")
    return slug


def _sorted_aliases(values: list[str]) -> list[str]:
    unique: dict[str, str] = {}
    for value in values:
        unique.setdefault(value.casefold(), value)
    return sorted(unique.values(), key=str.casefold)


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
    return f"kitchen-almanac-v2-{_sha256(_canonical_bytes(payload_without_id))[:16]}"


def build_catalog(
    source_path: Path = DEFAULT_SOURCE,
    taxonomy_path: Path = DEFAULT_TAXONOMY_SOURCE,
    browse_taxonomy_path: Path = DEFAULT_BROWSE_TAXONOMY_SOURCE,
) -> dict[str, Any]:
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

    legacy_crops = []
    for crop in crops_by_name.values():
        aliases = [
            crop["canonical_name"],
            *crop["source_names"],
            *COMMON_ALIASES.get(crop["canonical_name"], ()),
        ]
        legacy_crops.append(
            {
                **crop,
                "aliases": _sorted_aliases(aliases),
                "source_names": sorted(crop["source_names"]),
                "appearances": sorted(
                    crop["appearances"],
                    key=lambda item: (SEASON_ORDER.index(item["season"]), item["position"]),
                ),
            }
        )

    try:
        taxonomy_bytes = taxonomy_path.read_bytes()
        taxonomy = json.loads(taxonomy_bytes)
    except (OSError, json.JSONDecodeError) as error:
        raise CatalogError(f"Cannot read Rutgers crop taxonomy {taxonomy_path}: {error}") from error
    sections = taxonomy.get("sections") if isinstance(taxonomy, dict) else None
    if not isinstance(sections, list) or not sections:
        raise CatalogError("Rutgers crop taxonomy must contain commodity sections.")

    try:
        browse_taxonomy_bytes = browse_taxonomy_path.read_bytes()
        browse_taxonomy = json.loads(browse_taxonomy_bytes)
    except (OSError, json.JSONDecodeError) as error:
        raise CatalogError(
            f"Cannot read gardener browse taxonomy {browse_taxonomy_path}: {error}"
        ) from error
    browse_categories = (
        browse_taxonomy.get("categories") if isinstance(browse_taxonomy, dict) else None
    )
    if not isinstance(browse_categories, list) or not browse_categories:
        raise CatalogError("Gardener browse taxonomy must contain categories.")
    browse_category_by_crop_id: dict[str, dict[str, Any]] = {}
    for category in browse_categories:
        if not all(
            isinstance(category.get(field), expected_type)
            for field, expected_type in (
                ("key", str),
                ("title", str),
                ("position", int),
                ("crop_ids", list),
            )
        ):
            raise CatalogError(
                "Every gardener browse category needs a key, title, position, and crop IDs."
            )
        for crop_id in category["crop_ids"]:
            if crop_id in browse_category_by_crop_id:
                raise CatalogError(
                    f"Gardener browse crop {crop_id!r} belongs to more than one category."
                )
            browse_category_by_crop_id[crop_id] = category

    legacy_by_id = {crop["id"]: crop for crop in legacy_crops}
    crops: list[dict[str, Any]] = []
    taxonomy_ids: list[str] = []
    for section in sections:
        for concept in section.get("crops", []):
            crop_id = concept.get("id")
            canonical_name = concept.get("name")
            if not isinstance(crop_id, str) or not isinstance(canonical_name, str):
                raise CatalogError("Every Rutgers crop concept needs an ID and name.")
            taxonomy_ids.append(crop_id)
            browse_category = browse_category_by_crop_id.get(crop_id)
            if browse_category is None:
                raise CatalogError(
                    f"Rutgers crop {crop_id!r} is missing from the gardener browse taxonomy."
                )
            legacy_id = LEGACY_CROP_IDS.get(crop_id)
            legacy = legacy_by_id.get(legacy_id) if legacy_id else None
            aliases = [canonical_name, *RUTGERS_ALIASES.get(crop_id, ())]
            if legacy and crop_id in LEGACY_ALIAS_INHERITANCE:
                aliases.extend(legacy["aliases"])
            crops.append(
                {
                    "id": crop_id,
                    "canonical_name": canonical_name,
                    "planning_category": _planning_category(canonical_name),
                    "aliases": _sorted_aliases(aliases),
                    "source_names": legacy["source_names"] if legacy else [],
                    "appearances": legacy["appearances"] if legacy else [],
                    "taxonomy": {
                        "system": "rutgers_mid_atlantic_commodity",
                        "commodity_key": section["key"],
                        "commodity_title": section["title"],
                        "commodity_position": section["position"],
                        "rutgers_crop_id": crop_id,
                        "legacy_catalog_crop_id": legacy_id,
                        "legacy_catalog_name": legacy["canonical_name"] if legacy else None,
                    },
                    "browse_category": {
                        "system": browse_taxonomy["taxonomy_id"],
                        "key": browse_category["key"],
                        "title": browse_category["title"],
                        "position": browse_category["position"],
                    },
                }
            )
    if len(taxonomy_ids) != len(set(taxonomy_ids)):
        raise CatalogError("Rutgers crop concept IDs must be unique.")
    unknown_browse_crop_ids = set(browse_category_by_crop_id) - set(taxonomy_ids)
    if unknown_browse_crop_ids:
        raise CatalogError(
            "Gardener browse taxonomy contains unknown crop IDs: "
            f"{sorted(unknown_browse_crop_ids)!r}."
        )

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "parser_version": PARSER_VERSION,
        "source": {
            "id": f"sha256:{_sha256(taxonomy_bytes)}",
            "title": "Rutgers Mid-Atlantic reviewed commodity crosswalk",
            "path": taxonomy_path.relative_to(REPOSITORY_ROOT).as_posix(),
            "media_type": "application/json",
            "sha256": _sha256(taxonomy_bytes),
            "publisher": "Rutgers NJAES Cooperative Extension",
            "source_url": "https://njaes.rutgers.edu/pubs/publication.php?pid=e001",
            "source_scope": "reviewed crop identity taxonomy",
            "corpus_id": taxonomy["corpus_id"],
            "full_manual_sha256": taxonomy["full_manual_sha256"],
        },
        "season_source": {
            "id": f"sha256:{_sha256(source_bytes)}",
            "title": "Six Seasons Reference",
            "path": source_path.name,
            "media_type": "text/markdown",
            "sha256": _sha256(source_bytes),
            "source_scope": "legacy seasonal appearance metadata",
        },
        "browse_taxonomy": {
            "id": f"sha256:{_sha256(browse_taxonomy_bytes)}",
            "taxonomy_id": browse_taxonomy["taxonomy_id"],
            "title": "Kitchen Almanac gardener browse taxonomy",
            "path": browse_taxonomy_path.relative_to(REPOSITORY_ROOT).as_posix(),
            "media_type": "application/json",
            "sha256": _sha256(browse_taxonomy_bytes),
            "source_scope": browse_taxonomy["review_scope"],
        },
        "corrections": sorted(corrections_by_source.values(), key=lambda item: item["source_name"]),
        "crops": sorted(crops, key=lambda item: item["id"]),
    }
    return {"dataset_id": _dataset_id(payload), **payload}


def validate_catalog(
    catalog: dict[str, Any],
    source_path: Path | None = None,
    taxonomy_path: Path | None = None,
    browse_taxonomy_path: Path | None = None,
) -> list[str]:
    errors: list[str] = []

    required_keys = {
        "dataset_id",
        "schema_version",
        "parser_version",
        "source",
        "season_source",
        "browse_taxonomy",
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
        taxonomy = crop.get("taxonomy", {})
        legacy_name = taxonomy.get("legacy_catalog_name")
        if taxonomy.get("rutgers_crop_id") != crop.get("id"):
            errors.append(f"Crop {canonical_name!r} is not aligned to its Rutgers crop ID.")
        if not isinstance(taxonomy.get("commodity_key"), str):
            errors.append(f"Crop {canonical_name!r} needs a Rutgers commodity key.")
        if not isinstance(taxonomy.get("commodity_title"), str):
            errors.append(f"Crop {canonical_name!r} needs a Rutgers commodity title.")
        if not isinstance(taxonomy.get("commodity_position"), int):
            errors.append(f"Crop {canonical_name!r} needs a Rutgers commodity position.")
        browse_category = crop.get("browse_category", {})
        if not isinstance(browse_category.get("system"), str):
            errors.append(f"Crop {canonical_name!r} needs a browse taxonomy system.")
        if not isinstance(browse_category.get("key"), str):
            errors.append(f"Crop {canonical_name!r} needs a browse category key.")
        if not isinstance(browse_category.get("title"), str):
            errors.append(f"Crop {canonical_name!r} needs a browse category title.")
        if not isinstance(browse_category.get("position"), int):
            errors.append(f"Crop {canonical_name!r} needs a browse category position.")
        for source_name in crop.get("source_names", []):
            correction_target = legacy_name or canonical_name
            if source_name != correction_target:
                pair = (source_name, correction_target)
                referenced_corrections.add(pair)
                if pair not in corrections:
                    errors.append(
                        f"{source_name!r} becomes {correction_target!r} without a "
                        "correction record."
                    )

    unreferenced_corrections = corrections - referenced_corrections
    if unreferenced_corrections:
        errors.append(f"Unreferenced corrections: {sorted(unreferenced_corrections)!r}.")

    if source_path is not None:
        source_digest = _sha256(source_path.read_bytes())
        if catalog["season_source"].get("sha256") != source_digest:
            errors.append("Catalog season-source digest does not match the legacy source file.")

    if taxonomy_path is not None:
        taxonomy_digest = _sha256(taxonomy_path.read_bytes())
        if catalog["source"].get("sha256") != taxonomy_digest:
            errors.append("Catalog taxonomy digest does not match the Rutgers crosswalk.")
        taxonomy = json.loads(taxonomy_path.read_text(encoding="utf-8"))
        expected_crop_ids = sorted(
            crop["id"] for section in taxonomy["sections"] for crop in section["crops"]
        )
        if crop_ids != expected_crop_ids:
            errors.append("Catalog crop IDs do not exactly match the Rutgers crop taxonomy.")

    if browse_taxonomy_path is not None:
        browse_taxonomy_digest = _sha256(browse_taxonomy_path.read_bytes())
        if catalog["browse_taxonomy"].get("sha256") != browse_taxonomy_digest:
            errors.append("Catalog browse-taxonomy digest does not match its source file.")
        browse_taxonomy = json.loads(browse_taxonomy_path.read_text(encoding="utf-8"))
        expected_assignments = {
            crop_id: category["key"]
            for category in browse_taxonomy["categories"]
            for crop_id in category["crop_ids"]
        }
        actual_assignments = {
            crop["id"]: crop.get("browse_category", {}).get("key")
            for crop in catalog["crops"]
        }
        if actual_assignments != expected_assignments:
            errors.append("Catalog crops do not exactly match the gardener browse taxonomy.")

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
