from __future__ import annotations

import copy
import json

import pytest

from kitchen_almanac.commercial_listing_pipeline import (
    DEFAULT_LISTINGS,
    apply_reviewed_commercial_listings,
    validate_commercial_listing_source,
)
from kitchen_almanac.cultivar_pipeline import (
    DEFAULT_BASE,
    DEFAULT_DECISIONS,
    DEFAULT_STAGED,
    CultivarPipelineError,
    publish_staged_catalog,
    read_pipeline_json,
)


def test_reviewed_commercial_listings_are_valid() -> None:
    source = json.loads(DEFAULT_LISTINGS.read_text())

    assert validate_commercial_listing_source(source) == []
    assert len(source["listings"]) == 22
    assert {listing["availability_status"] for listing in source["listings"]} == {
        "in_stock",
        "out_of_stock",
    }


def test_listing_cannot_target_an_unknown_cultivar() -> None:
    catalog = publish_staged_catalog(
        read_pipeline_json(DEFAULT_BASE, "base"),
        read_pipeline_json(DEFAULT_STAGED, "staged"),
        read_pipeline_json(DEFAULT_DECISIONS, "decisions"),
    )
    listings = json.loads(DEFAULT_LISTINGS.read_text())
    changed = copy.deepcopy(listings)
    changed["listings"][0]["cultivar_slug"] = "not-a-cultivar"

    with pytest.raises(CultivarPipelineError, match="unknown cultivar"):
        apply_reviewed_commercial_listings(catalog, changed)


def test_retired_listing_is_valid_but_excluded_by_policy() -> None:
    source = json.loads(DEFAULT_LISTINGS.read_text())
    changed = copy.deepcopy(source)
    changed["listings"][0]["availability_status"] = "retired"

    assert validate_commercial_listing_source(changed) == []
    assert "retired" not in changed["eligibility_policy"]["eligible_availability"]
