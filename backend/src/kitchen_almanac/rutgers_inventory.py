from __future__ import annotations

import hashlib
import json
import re
import tempfile
import urllib.request
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pypdf import PdfReader

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
CORPUS_ROOT = REPOSITORY_ROOT / "data/source/cultivars/mid-atlantic-2026-2027"
DEFAULT_MANIFEST = CORPUS_ROOT / "corpus-manifest.v1.json"
DEFAULT_REPORT = CORPUS_ROOT / "coverage-report.v1.json"
SCHEMA_VERSION = "1.0.0"
SECTION_KINDS = {"commodity", "general", "irrigation", "soil_nutrient"}
REQUIRED_EXTRACTION_POLICY = {
    "default": "review_required",
    "chemical_controls": "quarantined",
    "insect_and_disease_sections": "threat_names_and_nonchemical_practices_only",
    "commercial_rates": "commercial_context_only",
    "database_publication": "prohibited_without_review",
}


class RutgersInventoryError(ValueError):
    """Raised when the Rutgers source corpus cannot be inventoried safely."""


@dataclass(frozen=True)
class CoverageRule:
    key: str
    markers: tuple[tuple[str, re.Pattern[str]], ...]
    detected_status: str
    use_policy: str


def _marker(label: str, pattern: str) -> tuple[str, re.Pattern[str]]:
    return label, re.compile(pattern, re.IGNORECASE | re.MULTILINE)


COVERAGE_RULES = (
    CoverageRule(
        "cultivar_recommendations",
        (
            _marker("recommended varieties", r"^\s*recommended varieties\b"),
            _marker("recommended snap bean varieties", r"^\s*recommended snap bean varieties\b"),
            _marker("recommended lima bean varieties", r"^\s*recommended lima beans? varieties\b"),
        ),
        "review_required",
        "identity_and_traits_after_review",
    ),
    CoverageRule(
        "soil_ph",
        (
            _marker("soil pH", r"\bsoil\s+pH\b"),
            _marker("slightly acid soils", r"\bslightly acid soils?\b"),
        ),
        "review_required",
        "home_garden_candidate_after_review",
    ),
    CoverageRule(
        "nutrient_management",
        (
            _marker(
                "recommended nutrients based on soil tests",
                r"recommended nutrients based on soil tests",
            ),
            _marker("nutrient management", r"\bnutrient management\b"),
            _marker("plant tissue testing", r"\bplant tissue testing\b"),
        ),
        "restricted_review",
        "principles_may_be_adapted; commercial_rates_are_context_only",
    ),
    CoverageRule(
        "planting_and_spacing",
        (
            _marker("planting", r"^\s*planting(?::|\s*$|\s+and harvesting dates)"),
            _marker("planting dates", r"^\s*planting dates\s*$"),
            _marker("spacing", r"^\s*spacing\s*$"),
            _marker(
                "seeding, transplanting, and spacing",
                r"^\s*seeding, transplanting, and spacing\s*$",
            ),
            _marker("space rows", r"\bspace rows?\b"),
            _marker("transplanting", r"^\s*transplanting:\s*$"),
        ),
        "review_required",
        "adapt_to_home_garden_units_and_context_after_review",
    ),
    CoverageRule(
        "irrigation",
        (
            _marker(
                "irrigation heading",
                r"^\s*(?:[A-Z]\.\s+)?irrigation(?: management)?\s*$",
            ),
            _marker("irrigation plan", r"\birrigation plan\b"),
        ),
        "review_required",
        "adapt_to_home_garden_methods_after_review",
    ),
    CoverageRule(
        "harvest_and_storage",
        (
            _marker("harvest heading", r"^\s*harvest\s*$"),
            _marker(
                "harvest and post-harvest considerations",
                r"^\s*harvest and post-harvest considerations\s*$",
            ),
            _marker("post-harvest handling", r"^\s*post-harvest handling\s*$"),
        ),
        "review_required",
        "adapt_to_home_garden_scale_after_review",
    ),
    CoverageRule(
        "weed_management",
        (_marker("weed control", r"^\s*weed control\s*$"),),
        "restricted_review",
        "cultural_and_manual_methods_only",
    ),
    CoverageRule(
        "insect_threats",
        (_marker("insect control", r"^\s*insect control\s*$"),),
        "restricted_review",
        "threat_names_and_nonchemical_practices_only",
    ),
    CoverageRule(
        "disease_threats",
        (_marker("disease control", r"^\s*disease control\s*$"),),
        "restricted_review",
        "threat_names_resistance_and_nonchemical_practices_only",
    ),
    CoverageRule(
        "food_safety",
        (
            _marker("food safety concerns", r"\bfood safety concerns\b"),
            _marker("good agricultural practices", r"\bgood agricultural practices\b"),
        ),
        "review_required",
        "home_garden_candidate_after_review",
    ),
    CoverageRule(
        "chemical_controls",
        (
            _marker("pesticide", r"\bpesticides?\b"),
            _marker("herbicide", r"\bherbicides?\b"),
            _marker("insecticide", r"\binsecticides?\b"),
            _marker("fungicide", r"\bfungicides?\b"),
            _marker("fumigant", r"\bfumigants?\b|\bfumigation\b"),
        ),
        "quarantined",
        "never_publish_to_beginner_guidance",
    ),
)


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    )


def read_manifest(
    path: Path = DEFAULT_MANIFEST, *, verify_snapshots: bool = False
) -> dict[str, Any]:
    try:
        manifest = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise RutgersInventoryError(f"Could not read Rutgers corpus manifest: {error}") from error

    errors = validate_manifest(manifest, verify_snapshots=verify_snapshots)
    if errors:
        raise RutgersInventoryError(" ".join(errors))
    return manifest


def validate_manifest(manifest: object, *, verify_snapshots: bool = False) -> list[str]:
    if not isinstance(manifest, dict):
        return ["Rutgers corpus manifest must be a JSON object."]
    required = {
        "schema_version",
        "corpus_id",
        "publication",
        "extraction_policy",
        "full_manual",
        "documents",
    }
    missing = required - manifest.keys()
    if missing:
        return [f"Rutgers corpus manifest is missing keys: {sorted(missing)!r}."]

    errors: list[str] = []
    if manifest["schema_version"] != SCHEMA_VERSION:
        errors.append(f"Unsupported Rutgers manifest schema {manifest['schema_version']!r}.")
    publication = manifest["publication"]
    required_publication = {
        "title",
        "publisher",
        "landing_page",
        "edition",
        "region",
        "audience",
        "retrieved_at",
        "license",
    }
    if not isinstance(publication, dict) or required_publication - publication.keys():
        errors.append("Rutgers publication metadata is incomplete.")
    elif publication["audience"] != "commercial vegetable growers":
        errors.append("Rutgers publication audience must retain its commercial-grower scope.")
    if manifest["extraction_policy"] != REQUIRED_EXTRACTION_POLICY:
        errors.append("Rutgers extraction policy does not match the required safety boundary.")

    full_manual = manifest["full_manual"]
    required_full_manual = {
        "key",
        "title",
        "url",
        "source_path",
        "sha256",
        "media_type",
        "page_count",
        "toc_pdf_page",
        "manual_page_offset",
        "commodity_end_manual_page",
        "fetch_method",
        "form_data",
    }
    if not isinstance(full_manual, dict) or required_full_manual - full_manual.keys():
        errors.append("Rutgers full-manual metadata is incomplete.")
    else:
        if full_manual["media_type"] != "application/pdf":
            errors.append("Rutgers full manual must be a PDF.")
        if not re.fullmatch(r"[0-9a-f]{64}", str(full_manual["sha256"])):
            errors.append("Rutgers full manual has an invalid SHA-256 digest.")
        if full_manual["fetch_method"] != "form_post" or not full_manual["form_data"]:
            errors.append("Rutgers full manual must retain its reproducible form POST metadata.")
        for field in (
            "page_count",
            "toc_pdf_page",
            "manual_page_offset",
            "commodity_end_manual_page",
        ):
            if not isinstance(full_manual[field], int) or full_manual[field] < 1:
                errors.append(f"Rutgers full manual has an invalid {field!r} value.")
        if verify_snapshots:
            _validate_full_manual_snapshot(full_manual, errors)

    documents = manifest["documents"]
    if not isinstance(documents, list) or not documents:
        return [*errors, "Rutgers corpus documents must be a non-empty list."]

    keys: list[str] = []
    paths: list[str] = []
    for document in documents:
        if not isinstance(document, dict):
            errors.append("Every Rutgers corpus document must be an object.")
            continue
        required_document = {
            "key",
            "title",
            "url",
            "source_path",
            "sha256",
            "media_type",
            "section_kind",
            "crop_ids",
        }
        missing_document = required_document - document.keys()
        if missing_document:
            errors.append(
                f"Rutgers document {document.get('key')!r} is missing "
                f"{sorted(missing_document)!r}."
            )
            continue
        keys.append(document["key"])
        paths.append(document["source_path"])
        if document["section_kind"] not in SECTION_KINDS:
            errors.append(f"Rutgers document {document['key']!r} has an invalid section kind.")
        if document["media_type"] != "application/pdf":
            errors.append(f"Rutgers document {document['key']!r} must be a PDF.")
        if not re.fullmatch(r"[0-9a-f]{64}", str(document["sha256"])):
            errors.append(f"Rutgers document {document['key']!r} has an invalid SHA-256 digest.")
        crop_ids = document["crop_ids"]
        if (
            not isinstance(crop_ids, list)
            or any(not isinstance(crop_id, str) or not crop_id for crop_id in crop_ids)
            or crop_ids != sorted(set(crop_ids))
        ):
            errors.append(
                f"Rutgers document {document['key']!r} crop IDs must be sorted and unique."
            )
        if document["section_kind"] == "commodity" and not crop_ids:
            errors.append(f"Commodity document {document['key']!r} must identify a crop.")
        if document["section_kind"] != "commodity" and crop_ids:
            errors.append(f"Shared document {document['key']!r} cannot claim crop-level coverage.")

        if verify_snapshots:
            source_path = _repository_path(document["source_path"])
            if not source_path.is_file():
                errors.append(
                    f"Rutgers snapshot {document['source_path']!r} does not exist. "
                    "Run `kitchen-almanac rutgers fetch` first."
                )
            elif _file_sha256(source_path) != document["sha256"]:
                errors.append(f"Rutgers document {document['key']!r} checksum does not match.")

    if len(keys) != len(set(keys)):
        errors.append("Rutgers document keys must be unique.")
    if len(paths) != len(set(paths)):
        errors.append("Rutgers source paths must be unique.")
    return errors


def fetch_sources(manifest_path: Path = DEFAULT_MANIFEST) -> tuple[int, int]:
    manifest = read_manifest(manifest_path)
    fetched = 0
    present = 0
    for document in [manifest["full_manual"], *manifest["documents"]]:
        destination = _repository_path(document["source_path"])
        if destination.is_file() and _file_sha256(destination) == document["sha256"]:
            present += 1
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            request: str | urllib.request.Request = document["url"]
            if document.get("fetch_method") == "form_post":
                request = urllib.request.Request(  # noqa: S310
                    document["url"],
                    data=document["form_data"].encode("ascii"),
                    method="POST",
                )
            with urllib.request.urlopen(request) as response:  # noqa: S310
                contents = response.read()
        except OSError as error:
            raise RutgersInventoryError(
                f"Could not fetch Rutgers document {document['key']!r}: {error}"
            ) from error
        actual_sha = hashlib.sha256(contents).hexdigest()
        if actual_sha != document["sha256"]:
            raise RutgersInventoryError(
                f"Downloaded Rutgers document {document['key']!r} has checksum {actual_sha}; "
                f"expected {document['sha256']}."
            )
        with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as temporary:
            temporary.write(contents)
            temporary_path = Path(temporary.name)
        temporary_path.replace(destination)
        fetched += 1
    return fetched, present


def build_coverage_report(manifest_path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    manifest = read_manifest(manifest_path, verify_snapshots=True)
    document_reports = [_inventory_document(document) for document in manifest["documents"]]
    shared_sources = [
        report["key"] for report in document_reports if report["section_kind"] != "commodity"
    ]
    crop_coverage: list[dict[str, Any]] = []
    for report in document_reports:
        if report["section_kind"] != "commodity":
            continue
        detected = [
            {
                "field": item["field"],
                "status": item["status"],
                "pages": item["pages"],
                "use_policy": item["use_policy"],
            }
            for item in report["coverage"]
            if item["status"] != "not_detected"
        ]
        for crop_id in report["crop_ids"]:
            crop_coverage.append(
                {
                    "crop_id": crop_id,
                    "commodity_source": report["key"],
                    "detected_fields": detected,
                    "corpus_wide_context_sources": shared_sources,
                }
            )

    category_counts = Counter()
    status_counts = Counter()
    for report in document_reports:
        for item in report["coverage"]:
            status_counts[item["status"]] += 1
            if item["status"] != "not_detected":
                category_counts[item["field"]] += 1

    return {
        "schema_version": SCHEMA_VERSION,
        "corpus_id": manifest["corpus_id"],
        "publication": manifest["publication"],
        "extraction_policy": manifest["extraction_policy"],
        "report_scope": (
            "Page-level source inventory only. Detected fields are review candidates, not "
            "published gardening guidance."
        ),
        "summary": {
            "document_count": len(document_reports),
            "page_count": sum(report["page_count"] for report in document_reports),
            "crop_count": len(crop_coverage),
            "category_document_counts": dict(sorted(category_counts.items())),
            "status_counts": dict(sorted(status_counts.items())),
        },
        "documents": document_reports,
        "crop_coverage": sorted(crop_coverage, key=lambda item: item["crop_id"]),
    }


def write_coverage_report(report: dict[str, Any], path: Path = DEFAULT_REPORT) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_canonical_bytes(report))


def validate_coverage_report(
    report_path: Path = DEFAULT_REPORT, manifest_path: Path = DEFAULT_MANIFEST
) -> list[str]:
    try:
        current = json.loads(report_path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        return [f"Could not read Rutgers coverage report: {error}"]
    expected = build_coverage_report(manifest_path)
    if current != expected:
        return ["Rutgers coverage report is stale; run `kitchen-almanac rutgers inventory`."]
    return []


def _inventory_document(document: dict[str, Any]) -> dict[str, Any]:
    source_path = _repository_path(document["source_path"])
    try:
        reader = PdfReader(source_path)
        pages = [page.extract_text() or "" for page in reader.pages]
    except Exception as error:
        raise RutgersInventoryError(
            f"Could not extract Rutgers document {document['key']!r}: {error}"
        ) from error

    coverage = []
    for rule in COVERAGE_RULES:
        pages_by_marker: dict[str, list[int]] = {}
        page_numbers: set[int] = set()
        for label, pattern in rule.markers:
            matches = [number for number, text in enumerate(pages, start=1) if pattern.search(text)]
            if matches:
                pages_by_marker[label] = matches
                page_numbers.update(matches)
        coverage.append(
            {
                "field": rule.key,
                "status": rule.detected_status if page_numbers else "not_detected",
                "pages": sorted(page_numbers),
                "matched_markers": pages_by_marker,
                "use_policy": rule.use_policy,
            }
        )

    text_bytes = "\f".join(pages).encode("utf-8")
    return {
        "key": document["key"],
        "title": document["title"],
        "section_kind": document["section_kind"],
        "crop_ids": document["crop_ids"],
        "source_path": document["source_path"],
        "source_sha256": document["sha256"],
        "page_count": len(pages),
        "extracted_text_sha256": hashlib.sha256(text_bytes).hexdigest(),
        "coverage": coverage,
    }


def _repository_path(relative_path: str) -> Path:
    path = (REPOSITORY_ROOT / relative_path).resolve()
    if not path.is_relative_to(REPOSITORY_ROOT.resolve()):
        raise RutgersInventoryError(f"Source path escapes the repository: {relative_path!r}.")
    return path


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_full_manual_snapshot(document: dict[str, Any], errors: list[str]) -> None:
    source_path = _repository_path(document["source_path"])
    if not source_path.is_file():
        errors.append(
            f"Rutgers snapshot {document['source_path']!r} does not exist. "
            "Run `kitchen-almanac rutgers fetch` first."
        )
        return
    if _file_sha256(source_path) != document["sha256"]:
        errors.append("Rutgers full manual checksum does not match.")
        return
    try:
        actual_pages = len(PdfReader(source_path).pages)
    except Exception as error:
        errors.append(f"Rutgers full manual cannot be read: {error}")
        return
    if actual_pages != document["page_count"]:
        errors.append(
            f"Rutgers full manual has {actual_pages} pages; expected {document['page_count']}."
        )
