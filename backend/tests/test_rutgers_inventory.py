from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from kitchen_almanac import rutgers_inventory


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text())


def test_manifest_and_committed_report_define_review_only_corpus() -> None:
    manifest = _read_json(rutgers_inventory.DEFAULT_MANIFEST)
    report = _read_json(rutgers_inventory.DEFAULT_REPORT)

    assert rutgers_inventory.validate_manifest(manifest) == []
    assert manifest["full_manual"] == {
        "commodity_end_manual_page": 493,
        "fetch_method": "form_post",
        "form_data": "Submit=Download+Full+PDF",
        "key": "mid-atlantic-full-manual-2026-2027",
        "manual_page_offset": 14,
        "media_type": "application/pdf",
        "page_count": 512,
        "sha256": "605dd9e8bc9cd1cf565372f0181941a28caf23ba6614f438c33845815a47991d",
        "source_path": "data/source/cultivars/mid-atlantic-2026-2027/e001.pdf",
        "title": "2026/2027 Mid-Atlantic Commercial Vegetable Production Recommendations",
        "toc_pdf_page": 12,
        "url": "https://njaes.rutgers.edu/pubs/download.php?strPubID=E001",
    }
    assert len(manifest["documents"]) == 9
    assert {document["section_kind"] for document in manifest["documents"]} == {
        "commodity",
        "general",
        "irrigation",
        "soil_nutrient",
    }
    assert manifest["extraction_policy"]["chemical_controls"] == "quarantined"
    assert manifest["extraction_policy"]["database_publication"] == (
        "prohibited_without_review"
    )

    assert report["corpus_id"] == manifest["corpus_id"]
    assert report["summary"] == {
        "category_document_counts": {
            "chemical_controls": 9,
            "cultivar_recommendations": 5,
            "disease_threats": 7,
            "food_safety": 2,
            "harvest_and_storage": 7,
            "insect_threats": 7,
            "irrigation": 5,
            "nutrient_management": 8,
            "planting_and_spacing": 7,
            "soil_ph": 6,
            "weed_management": 7,
        },
        "crop_count": 12,
        "document_count": 9,
        "page_count": 205,
        "status_counts": {
            "not_detected": 29,
            "quarantined": 9,
            "restricted_review": 29,
            "review_required": 32,
        },
    }
    assert {item["crop_id"] for item in report["crop_coverage"]} == {
        "beets",
        "broccoli",
        "brussels-sprouts",
        "cabbage",
        "cauliflower",
        "collards",
        "cucumbers",
        "kale",
        "kohlrabi",
        "snap-beans",
        "summer-squash",
        "tomatoes",
    }
    manifest_digests = {item["key"]: item["sha256"] for item in manifest["documents"]}
    assert {item["key"]: item["source_sha256"] for item in report["documents"]} == (
        manifest_digests
    )


def test_inventory_classifies_home_candidates_and_quarantines_chemicals(
    monkeypatch,
) -> None:
    class Page:
        def extract_text(self) -> str:
            return """
Recommended Varieties
Soil pH should be checked.
Seeding, Transplanting, and Spacing
Space rows 3 feet apart.
Irrigation
Harvest
Weed Control
Insect Control
Disease Control
Apply a fungicide.
"""

    class Reader:
        pages = [Page()]

        def __init__(self, _path: Path) -> None:
            pass

    monkeypatch.setattr(rutgers_inventory, "PdfReader", Reader)
    document = {
        "key": "example",
        "title": "Example",
        "section_kind": "commodity",
        "crop_ids": ["tomatoes"],
        "source_path": "data/example.pdf",
        "sha256": "0" * 64,
    }

    report = rutgers_inventory._inventory_document(document)
    coverage = {item["field"]: item for item in report["coverage"]}

    assert coverage["cultivar_recommendations"]["status"] == "review_required"
    assert coverage["planting_and_spacing"]["pages"] == [1]
    assert coverage["weed_management"]["status"] == "restricted_review"
    assert coverage["insect_threats"]["use_policy"] == (
        "threat_names_and_nonchemical_practices_only"
    )
    assert coverage["chemical_controls"] == {
        "field": "chemical_controls",
        "status": "quarantined",
        "pages": [1],
        "matched_markers": {"fungicide": [1]},
        "use_policy": "never_publish_to_beginner_guidance",
    }


def test_manifest_checksum_validation_detects_changed_snapshot(tmp_path, monkeypatch) -> None:
    contents = b"not the reviewed PDF"
    snapshot = tmp_path / "source.pdf"
    snapshot.write_bytes(contents)
    manifest = _read_json(rutgers_inventory.DEFAULT_MANIFEST)
    document = copy.deepcopy(manifest["documents"][0])
    document["source_path"] = "source.pdf"
    document["sha256"] = hashlib.sha256(b"expected contents").hexdigest()
    manifest["documents"] = [document]
    monkeypatch.setattr(rutgers_inventory, "REPOSITORY_ROOT", tmp_path)
    monkeypatch.setattr(
        rutgers_inventory, "_validate_full_manual_snapshot", lambda _document, _errors: None
    )

    errors = rutgers_inventory.validate_manifest(manifest, verify_snapshots=True)

    assert errors == [f"Rutgers document {document['key']!r} checksum does not match."]


def test_manifest_rejects_relaxed_safety_policy() -> None:
    manifest = _read_json(rutgers_inventory.DEFAULT_MANIFEST)
    manifest["extraction_policy"]["chemical_controls"] = "review_required"

    assert rutgers_inventory.validate_manifest(manifest) == [
        "Rutgers extraction policy does not match the required safety boundary."
    ]
