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

    assert catalog.id == "cultivar-catalog-v1-e6ac44d644368dd3"
    assert catalog.crop_dataset_id == "kitchen-almanac-v2-c1e82a4b00502686"
    assert [item["slug"] for item in catalog.data["cultivars"]] == [
        "avalanche",
        "blue-vantage",
        "brandywine-red",
        "bulls-blood",
        "caraflex",
        "champion-collards",
        "cheddar-cauliflower",
        "cherokee-purple",
        "chioggia-guardsmark",
        "cobra",
        "corinto",
        "cylindra",
        "dagan",
        "de-cicco",
        "dunja",
        "early-wonder",
        "eight-ball",
        "eureka",
        "gentry",
        "graffiti-cauliflower",
        "green-magic-broccoli",
        "green-top-bunching",
        "green-zebra",
        "gypsy-broccoli",
        "juliet",
        "kolibri-kohlrabi",
        "lacinato",
        "marketmore-76",
        "marte",
        "maxibel",
        "merlin",
        "mountain-merit",
        "pablo",
        "picolino",
        "provider",
        "quickstar-kohlrabi",
        "red-ace",
        "red-russian-kale",
        "roma-ii",
        "san-marzano",
        "san-marzano-2",
        "silvia-brussels-sprouts",
        "sun-gold",
        "sunburst",
        "tasty-green",
        "vates-collards",
    ]
    assert catalog.data["commercial_listings"][0]["id"] == "reimer-bn11-50"


def test_unapproved_or_unattributed_cultivar_data_cannot_publish() -> None:
    data = json.loads(DEFAULT_SOURCE.read_text())
    unapproved = copy.deepcopy(data)
    unapproved["cultivars"][0]["review_status"] = "draft"
    assert "is not approved" in " ".join(validate_cultivar_catalog(unapproved))

    unattributed = copy.deepcopy(data)
    unattributed["cultivars"][0]["traits"][0]["source_key"] = "missing-source"
    assert "unknown source" in " ".join(validate_cultivar_catalog(unattributed))
