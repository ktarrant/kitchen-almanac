from __future__ import annotations

import copy
import json

from kitchen_almanac import rutgers_taxonomy
from kitchen_almanac.rutgers_inventory import DEFAULT_MANIFEST, read_manifest


def _read_json(path) -> dict:
    return json.loads(path.read_text())


def test_full_manual_crosswalk_covers_every_commodity_section() -> None:
    manifest = read_manifest(DEFAULT_MANIFEST, verify_snapshots=True)
    crop_catalog = _read_json(rutgers_taxonomy.DEFAULT_CROP_CATALOG)
    crosswalk = _read_json(rutgers_taxonomy.DEFAULT_CROSSWALK)

    assert (
        rutgers_taxonomy.validate_crosswalk(
            crosswalk,
            manifest=manifest,
            crop_catalog=crop_catalog,
            verify_full_manual=True,
        )
        == []
    )
    assert len(crosswalk["sections"]) == 31
    assert sum(len(section["crops"]) for section in crosswalk["sections"]) == 47
    assert crosswalk["sections"][0]["manual_start_page"] == 161
    assert crosswalk["sections"][-1]["manual_start_page"] == 476


def test_taxonomy_report_exposes_mapping_and_minimum_evidence_gaps() -> None:
    report = _read_json(rutgers_taxonomy.DEFAULT_REPORT)

    assert report["summary"]["mapping_status_counts"] == {"exact": 47}
    assert report["summary"]["retained_section_pdf_count"] == 6
    assert report["summary"]["catalog_cultivar_count"] == 46
    assert report["summary"]["searchable_cultivar_count"] == 38
    assert report["summary"]["minimum_useful_crop_count"] == 0

    crops = {crop["rutgers_crop_id"]: crop for crop in report["crops"]}
    assert crops["tomatoes"]["minimum_useful_coverage"]["soil"]["status"] == "partial"
    assert crops["tomatoes"]["minimum_useful_coverage"]["containers"]["status"] == ("absent")
    assert crops["beets"]["searchable_cultivar_count"] == 9
    assert crops["broccoli"]["searchable_cultivar_count"] == 3
    assert crops["chinese-cabbage"]["mapping_status"] == "exact"
    assert crops["hot-peppers"]["mapping_status"] == "exact"
    assert crops["watermelons"]["mapping_status"] == "exact"

    queue = {item["section_key"]: item["readiness"] for item in report["expansion_queue"]}
    assert queue["mid-atlantic-cole-crops-2026-2027"] == "retained"
    assert queue["mid-atlantic-peppers-2026-2027"] == "ready_for_evidence_cohort"


def test_committed_taxonomy_report_is_deterministic() -> None:
    assert rutgers_taxonomy.validate_committed_taxonomy_report() == []


def test_crosswalk_rejects_unreviewed_catalog_identity() -> None:
    crosswalk = _read_json(rutgers_taxonomy.DEFAULT_CROSSWALK)
    changed = copy.deepcopy(crosswalk)
    changed["sections"][0]["crops"][0]["catalog_crop_id"] = "not-a-crop"
    crop_catalog = _read_json(rutgers_taxonomy.DEFAULT_CROP_CATALOG)

    errors = rutgers_taxonomy.validate_crosswalk(changed, crop_catalog=crop_catalog)

    assert "unknown catalog crop" in " ".join(errors)
