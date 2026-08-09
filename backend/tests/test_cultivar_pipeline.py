from __future__ import annotations

import copy
import json

import pytest

from kitchen_almanac.cultivar_catalog import DEFAULT_SOURCE
from kitchen_almanac.cultivar_pipeline import (
    DEFAULT_BASE,
    DEFAULT_DECISIONS,
    DEFAULT_STAGED,
    CultivarPipelineError,
    build_expanded_snapshot,
    publish_staged_catalog,
    reconcile_candidates,
    staging_sha256,
    validate_review_decisions,
    validate_staged_cultivars,
    write_expanded_snapshot,
)


def read_json(path) -> dict:
    return json.loads(path.read_text())


def test_staged_evidence_is_pinned_and_fully_reviewed() -> None:
    base = read_json(DEFAULT_BASE)
    staged = read_json(DEFAULT_STAGED)
    decisions = read_json(DEFAULT_DECISIONS)

    assert validate_staged_cultivars(staged) == []
    assert validate_review_decisions(staged, decisions) == []
    report = reconcile_candidates(base, staged, decisions)
    assert len(report) == 33
    assert {item.decision for item in report} == {"create", "enrich"}
    assert all(not item.exact_matches for item in report)


def test_expanded_snapshot_is_deterministic_and_covers_five_crops(tmp_path) -> None:
    expanded = build_expanded_snapshot()
    committed = read_json(DEFAULT_SOURCE)

    assert expanded == committed
    assert len(expanded["cultivars"]) == 30
    crop_counts = {
        crop_slug: sum(item["crop_slug"] == crop_slug for item in expanded["cultivars"])
        for crop_slug in {item["crop_slug"] for item in expanded["cultivars"]}
    }
    assert crop_counts == {
        "beets": 9,
        "cucumbers": 5,
        "string-beans": 4,
        "summer-squash": 4,
        "tomatoes": 8,
    }
    baseline_counts = {
        baseline["crop_slug"]: len(baseline["traits"]) for baseline in expanded["crop_baselines"]
    }
    assert baseline_counts == {
        "cucumbers": 7,
        "string-beans": 6,
        "summer-squash": 7,
        "tomatoes": 10,
    }

    provider = next(item for item in expanded["cultivars"] if item["slug"] == "provider")
    maturity = next(
        trait for trait in provider["traits"] if trait["field_name"] == "days_to_maturity"
    )
    assert maturity["normalized_value"] == {"minimum": 55, "maximum": 55, "basis": "seed"}
    assert maturity["source_key"] == "mid-atlantic-beans-2026-2027"
    assert {item["source_key"] for item in provider["source_identifiers"]} == {
        "mid-atlantic-beans-2026-2027",
        "vce-home-variety-trials-2025",
    }
    trial_rating = next(
        trait for trait in provider["traits"] if trait["field_name"] == "trial_overall_rating"
    )
    assert trial_rating["normalized_value"] == 5.97

    mountain_merit = next(
        item for item in expanded["cultivars"] if item["slug"] == "mountain-merit"
    )
    mountain_traits = {trait["field_name"]: trait for trait in mountain_merit["traits"]}
    assert mountain_traits["days_to_maturity"]["normalized_value"] == {
        "minimum": 75,
        "maximum": 75,
        "basis": "transplant",
    }
    assert mountain_traits["plant_spacing"]["normalized_value"] == {
        "minimum": 24,
        "maximum": 24,
    }

    generated = tmp_path / "cultivars.json"
    write_expanded_snapshot(expanded, generated)
    assert generated.read_bytes() == DEFAULT_SOURCE.read_bytes()


def test_staging_rejects_changed_source_snapshots_and_stale_decisions() -> None:
    staged = read_json(DEFAULT_STAGED)
    decisions = read_json(DEFAULT_DECISIONS)

    bad_source = copy.deepcopy(staged)
    bad_source["sources"][0]["sha256"] = "not-a-sha"
    assert "invalid SHA-256" in " ".join(validate_staged_cultivars(bad_source))

    changed_stage = copy.deepcopy(staged)
    changed_stage["candidates"][0]["description"] = "Changed after review."
    assert "do not pin" in " ".join(validate_review_decisions(changed_stage, decisions))


def test_create_decision_cannot_duplicate_an_existing_identity() -> None:
    base = read_json(DEFAULT_BASE)
    staged = read_json(DEFAULT_STAGED)
    decisions = read_json(DEFAULT_DECISIONS)
    staged["candidates"][0]["name_in_source"] = "San Marzano"
    staged["candidates"][0]["aliases"] = ["San Marzano"]
    decisions["staging_sha256"] = staging_sha256(staged)

    with pytest.raises(CultivarPipelineError, match="collides with"):
        publish_staged_catalog(base, staged, decisions)


def test_enrichment_decision_requires_a_matching_existing_identity() -> None:
    base = read_json(DEFAULT_BASE)
    staged = read_json(DEFAULT_STAGED)
    decisions = read_json(DEFAULT_DECISIONS)
    enrichment = next(
        candidate
        for candidate in staged["candidates"]
        if candidate["id"] == "vce-2025-sun-gold-evidence"
    )
    enrichment["name_in_source"] = "Different Tomato"
    enrichment["aliases"] = ["Different Tomato"]
    decisions["staging_sha256"] = staging_sha256(staged)

    with pytest.raises(CultivarPipelineError, match="does not match"):
        publish_staged_catalog(base, staged, decisions)
