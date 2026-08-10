from __future__ import annotations

import copy
import json

from kitchen_almanac.cultivar_pipeline import DEFAULT_BASE
from kitchen_almanac.rutgers_extraction import (
    DEFAULT_DECISIONS,
    DEFAULT_STAGED,
    apply_reviewed_crop_baselines,
    read_json,
    validate_review_decisions,
    validate_structured_evidence,
)


def test_structured_evidence_is_pinned_and_fully_reviewed() -> None:
    staged = read_json(DEFAULT_STAGED, "structured Rutgers evidence")
    decisions = read_json(DEFAULT_DECISIONS, "structured Rutgers review decisions")

    assert validate_structured_evidence(staged) == []
    assert validate_review_decisions(staged, decisions) == []
    assert len(staged["candidates"]) == 34
    assert {item["action"] for item in decisions["decisions"]} == {
        "approve_create",
        "corroborate_existing",
        "hold",
    }
    assert sum(item["action"] == "approve_create" for item in decisions["decisions"]) == 26


def test_approved_candidates_build_four_cited_crop_baselines() -> None:
    base = json.loads(DEFAULT_BASE.read_text())
    staged = read_json(DEFAULT_STAGED, "structured Rutgers evidence")
    decisions = read_json(DEFAULT_DECISIONS, "structured Rutgers review decisions")

    expanded = apply_reviewed_crop_baselines(base, staged, decisions)
    baselines = {item["crop_slug"]: item["traits"] for item in expanded["crop_baselines"]}

    assert {"cucumbers", "snap-beans", "summer-squash", "tomatoes"} <= set(baselines)
    assert len(baselines["cucumbers"]) == 11
    assert len(baselines["snap-beans"]) == 6
    assert len(baselines["summer-squash"]) == 9
    assert len(baselines["tomatoes"]) == 14
    tomato_traits = {item["field_name"]: item for item in baselines["tomatoes"]}
    assert tomato_traits["soil_ph"]["normalized_value"] == 6.5
    assert tomato_traits["lime_below_ph"]["normalized_value"] == 6.0
    assert tomato_traits["plant_spacing"]["source_key"] == "umd-tomatoes-2025"
    assert tomato_traits["harvest_guidance"]["source_key"] == (
        "mid-atlantic-tomatoes-2026-2027"
    )
    assert tomato_traits["critical_watering_stages"]["normalized_value"] == [
        "early_flowering",
        "fruit_set",
        "fruit_enlargement",
    ]
    assert tomato_traits["water_management_guidance"]["source_key"] == (
        "mid-atlantic-tomatoes-2026-2027"
    )
    assert all(
        trait["field_name"] != "regional_planting_window"
        for traits in baselines.values()
        for trait in traits
    )


def test_review_gate_rejects_commercial_or_unadapted_publication() -> None:
    staged = read_json(DEFAULT_STAGED, "structured Rutgers evidence")
    decisions = read_json(DEFAULT_DECISIONS, "structured Rutgers review decisions")
    changed = copy.deepcopy(decisions)
    commercial = next(
        item
        for item in changed["decisions"]
        if item["candidate_id"] == "rutgers-2026-string-beans-commercial-spacing"
    )
    commercial["action"] = "approve_create"

    errors = validate_review_decisions(staged, changed)

    assert "cannot be accepted" in " ".join(errors)


def test_review_decisions_reject_changed_staging() -> None:
    staged = read_json(DEFAULT_STAGED, "structured Rutgers evidence")
    decisions = read_json(DEFAULT_DECISIONS, "structured Rutgers review decisions")
    changed = copy.deepcopy(staged)
    changed["candidates"][0]["normalized_value"] = "changed after review"

    assert "do not pin" in " ".join(validate_review_decisions(changed, decisions))
