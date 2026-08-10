from __future__ import annotations

import copy
import json

from kitchen_almanac.cultivar_pipeline import DEFAULT_BASE
from kitchen_almanac.rutgers_extraction import (
    DEFAULT_DECISIONS as COMMERCIAL_DECISIONS,
)
from kitchen_almanac.rutgers_extraction import DEFAULT_STAGED as COMMERCIAL_STAGED
from kitchen_almanac.rutgers_extraction import (
    apply_reviewed_crop_baselines as apply_commercial_baselines,
)
from kitchen_almanac.rutgers_extraction import read_json as read_commercial_json
from kitchen_almanac.rutgers_home_garden import (
    DEFAULT_DECISIONS,
    DEFAULT_STAGED,
    apply_reviewed_crop_baselines,
    read_json,
    validate_review_decisions,
    validate_structured_evidence,
)


def _commercial_base() -> dict:
    base = json.loads(DEFAULT_BASE.read_text())
    return apply_commercial_baselines(
        base,
        read_commercial_json(COMMERCIAL_STAGED, "commercial staged evidence"),
        read_commercial_json(COMMERCIAL_DECISIONS, "commercial decisions"),
    )


def test_fs129_evidence_is_pinned_and_fully_reviewed() -> None:
    staged = read_json(DEFAULT_STAGED, "structured FS129 evidence")
    decisions = read_json(DEFAULT_DECISIONS, "FS129 review decisions")

    assert validate_structured_evidence(staged) == []
    assert validate_review_decisions(staged, decisions) == []
    assert len(staged["candidates"]) == 64
    action_counts = {
        action: sum(item["action"] == action for item in decisions["decisions"])
        for action in {item["action"] for item in decisions["decisions"]}
    }
    assert action_counts == {"approve_create": 44, "approve_replace": 6, "hold": 14}


def test_fs129_builds_home_garden_baselines_without_publishing_calendar_months() -> None:
    staged = read_json(DEFAULT_STAGED, "structured FS129 evidence")
    decisions = read_json(DEFAULT_DECISIONS, "FS129 review decisions")

    expanded = apply_reviewed_crop_baselines(_commercial_base(), staged, decisions)
    baselines = {
        item["crop_slug"]: {trait["field_name"]: trait for trait in item["traits"]}
        for item in expanded["crop_baselines"]
    }

    assert len(baselines) == 12
    assert baselines["cucumbers"]["sun_hours"]["normalized_value"] == {
        "minimum": 8,
        "preferred_condition": "full_sun",
    }
    assert baselines["cucumbers"]["plant_spacing"]["normalized_value"] == {
        "minimum": 36,
        "maximum": 36,
    }
    assert baselines["cucumbers"]["plant_spacing"]["source_key"] == (
        "rutgers-fs129-home-garden-2020"
    )
    assert baselines["cucumbers"]["row_spacing"]["normalized_value"] == {
        "minimum": 30,
        "maximum": 30,
    }
    assert baselines["cucumbers"]["yield_per_10ft_row"]["unit"] == ("pounds_per_10ft_row")
    assert baselines["tomatoes"]["sun_hours"]["source_key"] == "umd-tomatoes-2025"
    assert baselines["tomatoes"]["plant_spacing"]["source_key"] == "umd-tomatoes-2025"
    assert baselines["tomatoes"]["starting_method"]["source_key"] == (
        "rutgers-fs129-home-garden-2020"
    )
    assert all("new_jersey_planting_months" not in traits for traits in baselines.values())


def test_fs129_review_rejects_changed_staging() -> None:
    staged = read_json(DEFAULT_STAGED, "structured FS129 evidence")
    decisions = read_json(DEFAULT_DECISIONS, "FS129 review decisions")
    changed = copy.deepcopy(staged)
    changed["candidates"][0]["normalized_value"] = "changed after review"

    assert "do not pin" in " ".join(validate_review_decisions(changed, decisions))
