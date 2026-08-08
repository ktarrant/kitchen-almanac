from __future__ import annotations

import copy

import pytest

from kitchen_almanac.catalog import (
    DEFAULT_OUTPUT,
    DEFAULT_SOURCE,
    CatalogError,
    build_catalog,
    validate_catalog,
    write_catalog,
)


def crop_named(catalog: dict, name: str) -> dict:
    return next(crop for crop in catalog["crops"] if crop["canonical_name"] == name)


def test_reference_build_has_expected_shape() -> None:
    catalog = build_catalog(DEFAULT_SOURCE)

    assert len(catalog["crops"]) == 37
    assert sum(len(crop["appearances"]) for crop in catalog["crops"]) == 41
    assert len(catalog["corrections"]) == 10
    assert validate_catalog(catalog, DEFAULT_SOURCE) == []


def test_source_corrections_are_explicit_and_original_labels_survive() -> None:
    catalog = build_catalog(DEFAULT_SOURCE)
    rutabaga = crop_named(catalog, "Rutabaga")

    assert rutabaga["source_names"] == ["Rutabage"]
    assert rutabaga["appearances"][0]["source_name"] == "Rutabage"
    assert {
        "source_name": "Rutabage",
        "canonical_name": "Rutabaga",
        "correction_type": "spelling",
        "reason": "Correct an apparent spelling error in the source reference.",
    } in catalog["corrections"]


def test_categories_capture_nonstandard_planning_systems() -> None:
    catalog = build_catalog(DEFAULT_SOURCE)

    assert crop_named(catalog, "Asparagus")["planning_category"] == "perennial"
    assert crop_named(catalog, "Onion Family")["planning_category"] == "crop_group"
    assert crop_named(catalog, "Mushrooms")["planning_category"] == "specialty_system"
    assert crop_named(catalog, "Tomatoes")["planning_category"] == "annual_crop"


def test_seasonal_variants_merge_without_losing_appearances() -> None:
    catalog = build_catalog(DEFAULT_SOURCE)
    carrots = crop_named(catalog, "Carrots")

    assert carrots["source_names"] == ["Carrots (Early Season)", "Carrots (Late Season)"]
    assert [item["season"] for item in carrots["appearances"]] == ["Early Summer", "Fall"]


def test_build_output_is_byte_reproducible(tmp_path) -> None:
    catalog = build_catalog(DEFAULT_SOURCE)
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"

    write_catalog(catalog, first)
    write_catalog(build_catalog(DEFAULT_SOURCE), second)

    assert first.read_bytes() == second.read_bytes()
    assert first.read_bytes() == DEFAULT_OUTPUT.read_bytes()


def test_validator_rejects_silent_label_change() -> None:
    catalog = build_catalog(DEFAULT_SOURCE)
    tampered = copy.deepcopy(catalog)
    tomato = crop_named(tampered, "Tomatoes")
    tomato["canonical_name"] = "Tomato"

    errors = validate_catalog(tampered)

    assert any("without a correction record" in error for error in errors)


def test_parser_rejects_unknown_headings(tmp_path) -> None:
    source = tmp_path / "bad-reference.md"
    source.write_text("Monsoon:\n  Tomatoes\n", encoding="utf-8")

    with pytest.raises(CatalogError, match="Unknown season heading"):
        build_catalog(source)
