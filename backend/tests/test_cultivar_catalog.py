from __future__ import annotations

import copy
import json

from kitchen_almanac.cultivar_catalog import (
    DEFAULT_SOURCE,
    build_cultivar_catalog,
    validate_cultivar_catalog,
)


def test_reviewed_cultivar_snapshot_is_valid_and_deterministic() -> None:
    catalog = build_cultivar_catalog()

    assert catalog.id == "cultivar-catalog-v1-0b017ec1ab06c2d4"
    assert catalog.crop_dataset_id == "kitchen-almanac-v1-f76ca812f62c8c39"
    assert [item["slug"] for item in catalog.data["cultivars"]] == [
        "san-marzano",
        "san-marzano-2",
    ]
    assert catalog.data["commercial_listings"][0]["id"] == "reimer-tm660-20"


def test_unapproved_or_unattributed_cultivar_data_cannot_publish() -> None:
    data = json.loads(DEFAULT_SOURCE.read_text())
    unapproved = copy.deepcopy(data)
    unapproved["cultivars"][0]["review_status"] = "draft"
    assert "is not approved" in " ".join(validate_cultivar_catalog(unapproved))

    unattributed = copy.deepcopy(data)
    unattributed["cultivars"][0]["traits"][0]["source_key"] = "missing-source"
    assert "unknown source" in " ".join(validate_cultivar_catalog(unattributed))
