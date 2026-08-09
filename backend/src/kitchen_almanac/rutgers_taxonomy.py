from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from kitchen_almanac.catalog import DEFAULT_OUTPUT as DEFAULT_CROP_CATALOG
from kitchen_almanac.cultivar_catalog import DEFAULT_SOURCE as DEFAULT_CULTIVAR_CATALOG
from kitchen_almanac.rutgers_inventory import (
    CORPUS_ROOT,
    COVERAGE_RULES,
    DEFAULT_MANIFEST,
    REPOSITORY_ROOT,
    RutgersInventoryError,
    read_manifest,
)

SCHEMA_VERSION = "1.0.0"
DEFAULT_CROSSWALK = CORPUS_ROOT / "commodity-crosswalk.v1.json"
DEFAULT_REPORT = CORPUS_ROOT / "taxonomy-coverage-report.v1.json"
MAPPING_STATUSES = {"exact", "broader_catalog_identity", "missing_catalog_identity"}
COVERAGE_STATUSES = {"supported", "partial", "absent"}


class RutgersTaxonomyError(ValueError):
    """Raised when the full-manual commodity taxonomy cannot be reproduced."""


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n"


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise RutgersTaxonomyError(f"Could not read {label}: {error}") from error
    if not isinstance(value, dict):
        raise RutgersTaxonomyError(f"{label.capitalize()} must be a JSON object.")
    return value


def _repository_path(relative_path: str) -> Path:
    path = (REPOSITORY_ROOT / relative_path).resolve()
    if not path.is_relative_to(REPOSITORY_ROOT.resolve()):
        raise RutgersTaxonomyError(f"Source path escapes the repository: {relative_path!r}.")
    return path


def _normalized_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def validate_crosswalk(
    crosswalk: object,
    *,
    manifest: dict[str, Any] | None = None,
    crop_catalog: dict[str, Any] | None = None,
    verify_full_manual: bool = False,
) -> list[str]:
    if not isinstance(crosswalk, dict):
        return ["Rutgers commodity crosswalk must be a JSON object."]
    required = {
        "schema_version",
        "corpus_id",
        "full_manual_sha256",
        "reviewed_at",
        "review_scope",
        "minimum_useful_crop_fields",
        "sections",
    }
    missing = required - crosswalk.keys()
    if missing:
        return [f"Rutgers commodity crosswalk is missing {sorted(missing)!r}."]

    errors: list[str] = []
    if crosswalk["schema_version"] != SCHEMA_VERSION:
        errors.append(f"Unsupported Rutgers taxonomy schema {crosswalk['schema_version']!r}.")

    fields = crosswalk["minimum_useful_crop_fields"]
    if not isinstance(fields, list) or not fields:
        errors.append("Minimum useful crop fields must be a non-empty list.")
    else:
        field_names = [field.get("field") for field in fields if isinstance(field, dict)]
        if len(field_names) != len(fields) or len(field_names) != len(set(field_names)):
            errors.append("Minimum useful crop field names must be present and unique.")
        for field in fields:
            if not isinstance(field, dict) or set(field) != {"field", "required_trait_fields"}:
                errors.append("Every minimum useful crop field needs a name and trait list.")
                continue
            traits = field["required_trait_fields"]
            if not isinstance(traits, list) or traits != sorted(set(traits)):
                errors.append(f"Minimum field {field['field']!r} traits must be sorted and unique.")

    sections = crosswalk["sections"]
    if not isinstance(sections, list) or not sections:
        return [*errors, "Rutgers commodity sections must be a non-empty list."]
    positions: list[int] = []
    section_keys: list[str] = []
    section_urls: list[str] = []
    start_pages: list[int] = []
    concept_ids: list[str] = []
    catalog_crop_ids = (
        {crop["id"] for crop in crop_catalog.get("crops", [])} if crop_catalog else set()
    )
    for section in sections:
        if not isinstance(section, dict):
            errors.append("Every Rutgers commodity section must be an object.")
            continue
        required_section = {
            "position",
            "key",
            "title",
            "url",
            "manual_start_page",
            "crops",
        }
        if required_section - section.keys():
            errors.append(f"Rutgers section {section.get('key')!r} is incomplete.")
            continue
        positions.append(section["position"])
        section_keys.append(section["key"])
        section_urls.append(section["url"])
        start_pages.append(section["manual_start_page"])
        if not section["url"].startswith("https://njaes.rutgers.edu/"):
            errors.append(f"Rutgers section {section['key']!r} has a non-Rutgers URL.")
        if not isinstance(section["crops"], list) or not section["crops"]:
            errors.append(f"Rutgers section {section['key']!r} must identify crop concepts.")
            continue
        for crop in section["crops"]:
            required_crop = {
                "id",
                "name",
                "mapping_status",
                "catalog_crop_id",
                "review_note",
            }
            if not isinstance(crop, dict) or required_crop - crop.keys():
                errors.append(f"Rutgers section {section['key']!r} has an incomplete crop mapping.")
                continue
            concept_ids.append(crop["id"])
            status = crop["mapping_status"]
            catalog_crop_id = crop["catalog_crop_id"]
            if status not in MAPPING_STATUSES:
                errors.append(f"Rutgers crop {crop['id']!r} has an invalid mapping status.")
            if status == "missing_catalog_identity" and catalog_crop_id is not None:
                errors.append(
                    f"Missing Rutgers crop {crop['id']!r} cannot claim a catalog identity."
                )
            if status != "missing_catalog_identity" and not isinstance(catalog_crop_id, str):
                errors.append(f"Mapped Rutgers crop {crop['id']!r} needs a catalog identity.")
            if crop_catalog and catalog_crop_id and catalog_crop_id not in catalog_crop_ids:
                errors.append(
                    f"Rutgers crop {crop['id']!r} references unknown catalog crop "
                    f"{catalog_crop_id!r}."
                )

    if positions != list(range(1, len(sections) + 1)):
        errors.append("Rutgers commodity positions must be contiguous and source ordered.")
    if len(section_keys) != len(set(section_keys)):
        errors.append("Rutgers commodity section keys must be unique.")
    if len(section_urls) != len(set(section_urls)):
        errors.append("Rutgers commodity section URLs must be unique.")
    if start_pages != sorted(set(start_pages)):
        errors.append("Rutgers commodity start pages must be unique and increasing.")
    if len(concept_ids) != len(set(concept_ids)):
        errors.append("Rutgers crop concept IDs must be unique.")

    if manifest is not None:
        full_manual = manifest["full_manual"]
        if crosswalk["corpus_id"] != manifest["corpus_id"]:
            errors.append("Rutgers crosswalk corpus ID does not match the manifest.")
        if crosswalk["full_manual_sha256"] != full_manual["sha256"]:
            errors.append("Rutgers crosswalk full-manual checksum does not match the manifest.")
        if start_pages and start_pages[-1] > full_manual["commodity_end_manual_page"]:
            errors.append("Rutgers commodity page range exceeds the manual commodity chapter.")
        if verify_full_manual and not errors:
            errors.extend(_validate_crosswalk_against_manual(crosswalk, full_manual))
    return errors


def read_crosswalk(
    path: Path = DEFAULT_CROSSWALK,
    *,
    manifest: dict[str, Any] | None = None,
    crop_catalog: dict[str, Any] | None = None,
    verify_full_manual: bool = False,
) -> dict[str, Any]:
    crosswalk = _read_json(path, "Rutgers commodity crosswalk")
    errors = validate_crosswalk(
        crosswalk,
        manifest=manifest,
        crop_catalog=crop_catalog,
        verify_full_manual=verify_full_manual,
    )
    if errors:
        raise RutgersTaxonomyError(" ".join(errors))
    return crosswalk


def _validate_crosswalk_against_manual(
    crosswalk: dict[str, Any], full_manual: dict[str, Any]
) -> list[str]:
    source_path = _repository_path(full_manual["source_path"])
    try:
        reader = PdfReader(source_path)
        toc_text = _normalized_text(
            reader.pages[full_manual["toc_pdf_page"] - 1].extract_text() or ""
        )
    except Exception as error:
        return [f"Could not inspect the Rutgers full-manual table of contents: {error}"]
    errors: list[str] = []
    offset = full_manual["manual_page_offset"]
    for section in crosswalk["sections"]:
        expected = _normalized_text(f"{section['title']} {section['manual_start_page']}")
        if expected not in toc_text:
            errors.append(f"Rutgers table of contents does not confirm {section['title']!r}.")
            continue
        pdf_page = section["manual_start_page"] + offset
        page_text = _normalized_text(reader.pages[pdf_page - 1].extract_text() or "")
        first_crop = _normalized_text(section["crops"][0]["name"])
        title_words = _normalized_text(section["title"]).split(":", 1)[0]
        if first_crop not in page_text and title_words not in page_text:
            errors.append(
                f"Rutgers section {section['key']!r} does not start on expected PDF page "
                f"{pdf_page}."
            )
    return errors


def _section_coverage(
    pages: list[str], *, pdf_start_page: int, manual_page_offset: int
) -> tuple[list[dict[str, Any]], str]:
    coverage: list[dict[str, Any]] = []
    for rule in COVERAGE_RULES:
        pages_by_marker: dict[str, list[int]] = {}
        page_numbers: set[int] = set()
        for label, pattern in rule.markers:
            matches = [
                pdf_start_page + offset for offset, text in enumerate(pages) if pattern.search(text)
            ]
            if matches:
                pages_by_marker[label] = matches
                page_numbers.update(matches)
        coverage.append(
            {
                "field": rule.key,
                "status": rule.detected_status if page_numbers else "not_detected",
                "pdf_pages": sorted(page_numbers),
                "manual_pages": sorted(page - manual_page_offset for page in page_numbers),
                "matched_markers": pages_by_marker,
                "use_policy": rule.use_policy,
            }
        )
    text_sha256 = hashlib.sha256("\f".join(pages).encode("utf-8")).hexdigest()
    return coverage, text_sha256


def _field_status(required: list[str], available: set[str]) -> dict[str, Any]:
    present = sorted(set(required) & available)
    missing = sorted(set(required) - available)
    status = "supported" if not missing else "partial" if present else "absent"
    return {"status": status, "present": present, "missing": missing}


def build_taxonomy_coverage_report(
    *,
    manifest_path: Path = DEFAULT_MANIFEST,
    crosswalk_path: Path = DEFAULT_CROSSWALK,
    crop_catalog_path: Path = DEFAULT_CROP_CATALOG,
    cultivar_catalog_path: Path = DEFAULT_CULTIVAR_CATALOG,
) -> dict[str, Any]:
    try:
        manifest = read_manifest(manifest_path, verify_snapshots=True)
    except RutgersInventoryError as error:
        raise RutgersTaxonomyError(str(error)) from error
    crop_catalog = _read_json(crop_catalog_path, "crop catalog")
    cultivar_catalog = _read_json(cultivar_catalog_path, "cultivar catalog")
    crosswalk = read_crosswalk(
        crosswalk_path,
        manifest=manifest,
        crop_catalog=crop_catalog,
        verify_full_manual=True,
    )

    full_manual = manifest["full_manual"]
    reader = PdfReader(_repository_path(full_manual["source_path"]))
    crop_by_id = {crop["id"]: crop for crop in crop_catalog["crops"]}
    cultivar_by_slug = {cultivar["slug"]: cultivar for cultivar in cultivar_catalog["cultivars"]}
    cultivars_by_crop: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for cultivar in cultivar_catalog["cultivars"]:
        cultivars_by_crop[cultivar["crop_slug"]].append(cultivar)
    eligible_cultivar_slugs: set[str] = set()
    vendors_by_crop: dict[str, set[str]] = defaultdict(set)
    for listing in cultivar_catalog["commercial_listings"]:
        if listing["review_status"] != "approved" or listing["availability_status"] == "retired":
            continue
        cultivar = cultivar_by_slug[listing["cultivar_slug"]]
        eligible_cultivar_slugs.add(cultivar["slug"])
        vendors_by_crop[cultivar["crop_slug"]].add(listing["vendor"])

    source_by_key = {source["key"]: source for source in cultivar_catalog["sources"]}
    traits_by_crop: dict[str, set[str]] = defaultdict(set)
    publishers_by_crop: dict[str, set[str]] = defaultdict(set)
    for baseline in cultivar_catalog["crop_baselines"]:
        crop_id = baseline["crop_slug"]
        for trait in baseline["traits"]:
            traits_by_crop[crop_id].add(trait["field_name"])
            source = source_by_key[trait["source_key"]]
            if source.get("publisher"):
                publishers_by_crop[crop_id].add(source["publisher"])
    for cultivar in cultivar_catalog["cultivars"]:
        for trait in cultivar["traits"]:
            source = source_by_key[trait["source_key"]]
            if source.get("publisher"):
                publishers_by_crop[cultivar["crop_slug"]].add(source["publisher"])

    retained_section_keys = {
        document["key"]
        for document in manifest["documents"]
        if document["section_kind"] == "commodity"
    }
    sections: list[dict[str, Any]] = []
    crops: list[dict[str, Any]] = []
    mapping_counts: Counter[str] = Counter()
    field_status_counts: dict[str, Counter[str]] = defaultdict(Counter)
    mapped_catalog_ids: set[str] = set()
    minimum_useful_count = 0
    offset = full_manual["manual_page_offset"]
    commodity_end = full_manual["commodity_end_manual_page"]

    for index, section in enumerate(crosswalk["sections"]):
        manual_end = (
            crosswalk["sections"][index + 1]["manual_start_page"] - 1
            if index + 1 < len(crosswalk["sections"])
            else commodity_end
        )
        pdf_start = section["manual_start_page"] + offset
        pdf_end = manual_end + offset
        page_texts = [
            reader.pages[page - 1].extract_text() or "" for page in range(pdf_start, pdf_end + 1)
        ]
        detected_fields, text_sha256 = _section_coverage(
            page_texts,
            pdf_start_page=pdf_start,
            manual_page_offset=offset,
        )
        section_record = {
            "position": section["position"],
            "key": section["key"],
            "title": section["title"],
            "url": section["url"],
            "manual_page_range": {"start": section["manual_start_page"], "end": manual_end},
            "pdf_page_range": {"start": pdf_start, "end": pdf_end},
            "section_pdf_retained": section["key"] in retained_section_keys,
            "extracted_text_sha256": text_sha256,
            "detected_fields": detected_fields,
            "crop_concept_ids": [crop["id"] for crop in section["crops"]],
        }
        sections.append(section_record)

        for mapping in section["crops"]:
            mapping_counts[mapping["mapping_status"]] += 1
            catalog_crop_id = mapping["catalog_crop_id"]
            if catalog_crop_id:
                mapped_catalog_ids.add(catalog_crop_id)
            available_traits = traits_by_crop[catalog_crop_id] if catalog_crop_id else set()
            cultivar_records = cultivars_by_crop[catalog_crop_id] if catalog_crop_id else []
            searchable = sorted(
                cultivar["slug"]
                for cultivar in cultivar_records
                if cultivar["slug"] in eligible_cultivar_slugs
            )
            coverage: dict[str, dict[str, Any]] = {}
            for field in crosswalk["minimum_useful_crop_fields"]:
                name = field["field"]
                if name == "rutgers_source":
                    result = {"status": "supported", "present": [section["key"]], "missing": []}
                elif name == "identity":
                    status = (
                        "supported"
                        if mapping["mapping_status"] == "exact"
                        else "partial"
                        if mapping["mapping_status"] == "broader_catalog_identity"
                        else "absent"
                    )
                    result = {
                        "status": status,
                        "present": [catalog_crop_id] if catalog_crop_id else [],
                        "missing": [] if status == "supported" else [mapping["id"]],
                    }
                elif name == "cultivars":
                    result = {
                        "status": "supported" if cultivar_records else "absent",
                        "present": sorted(cultivar["slug"] for cultivar in cultivar_records),
                        "missing": [] if cultivar_records else ["reviewed_cultivar_records"],
                    }
                elif name == "commercial_availability":
                    result = {
                        "status": "supported" if searchable else "absent",
                        "present": searchable,
                        "missing": [] if searchable else ["approved_nonretired_listing"],
                    }
                else:
                    result = _field_status(field["required_trait_fields"], available_traits)
                coverage[name] = result
                field_status_counts[name][result["status"]] += 1

            minimum_useful = all(item["status"] == "supported" for item in coverage.values())
            if minimum_useful:
                minimum_useful_count += 1
            crops.append(
                {
                    "rutgers_crop_id": mapping["id"],
                    "rutgers_crop_name": mapping["name"],
                    "commodity_source": section["key"],
                    "mapping_status": mapping["mapping_status"],
                    "catalog_crop_id": catalog_crop_id,
                    "catalog_crop_name": (
                        crop_by_id[catalog_crop_id]["canonical_name"] if catalog_crop_id else None
                    ),
                    "review_note": mapping["review_note"],
                    "cultivar_count": len(cultivar_records),
                    "searchable_cultivar_count": len(searchable),
                    "published_crop_trait_fields": sorted(available_traits),
                    "evidence_publishers": sorted(publishers_by_crop[catalog_crop_id]),
                    "commercial_vendors": sorted(vendors_by_crop[catalog_crop_id]),
                    "minimum_useful_coverage": coverage,
                    "minimum_useful": minimum_useful,
                }
            )

    expansion_queue = []
    for section in sections:
        mappings = [crop for crop in crops if crop["commodity_source"] == section["key"]]
        statuses = {crop["mapping_status"] for crop in mappings}
        if section["section_pdf_retained"]:
            readiness = "retained"
        elif statuses == {"exact"}:
            readiness = "ready_for_evidence_cohort"
        else:
            readiness = "taxonomy_work_required"
        expansion_queue.append(
            {
                "position": section["position"],
                "section_key": section["key"],
                "title": section["title"],
                "readiness": readiness,
                "crop_concept_ids": section["crop_concept_ids"],
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "corpus_id": manifest["corpus_id"],
        "full_manual": {
            "source_path": full_manual["source_path"],
            "sha256": full_manual["sha256"],
            "page_count": full_manual["page_count"],
            "toc_pdf_page": full_manual["toc_pdf_page"],
            "manual_page_offset": offset,
        },
        "report_scope": (
            "Reviewed taxonomy and coverage inventory. Detected Rutgers fields are review "
            "candidates; minimum-useful coverage reflects only already published catalog evidence."
        ),
        "summary": {
            "commodity_section_count": len(sections),
            "rutgers_crop_concept_count": len(crops),
            "catalog_crop_count": len(crop_by_id),
            "retained_section_pdf_count": sum(
                section["section_pdf_retained"] for section in sections
            ),
            "catalog_cultivar_count": len(cultivar_catalog["cultivars"]),
            "searchable_cultivar_count": len(eligible_cultivar_slugs),
            "minimum_useful_crop_count": minimum_useful_count,
            "mapping_status_counts": dict(sorted(mapping_counts.items())),
            "minimum_field_status_counts": {
                field: dict(sorted(counts.items()))
                for field, counts in sorted(field_status_counts.items())
            },
        },
        "minimum_useful_crop_fields": crosswalk["minimum_useful_crop_fields"],
        "unrepresented_catalog_crop_ids": sorted(set(crop_by_id) - mapped_catalog_ids),
        "sections": sections,
        "crops": crops,
        "expansion_queue": expansion_queue,
    }


def write_taxonomy_coverage_report(report: dict[str, Any], path: Path = DEFAULT_REPORT) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_canonical_bytes(report))


def validate_committed_taxonomy_report(
    report_path: Path = DEFAULT_REPORT,
    *,
    manifest_path: Path = DEFAULT_MANIFEST,
    crosswalk_path: Path = DEFAULT_CROSSWALK,
    crop_catalog_path: Path = DEFAULT_CROP_CATALOG,
    cultivar_catalog_path: Path = DEFAULT_CULTIVAR_CATALOG,
) -> list[str]:
    try:
        current = _read_json(report_path, "Rutgers taxonomy coverage report")
        expected = build_taxonomy_coverage_report(
            manifest_path=manifest_path,
            crosswalk_path=crosswalk_path,
            crop_catalog_path=crop_catalog_path,
            cultivar_catalog_path=cultivar_catalog_path,
        )
    except RutgersTaxonomyError as error:
        return [str(error)]
    if current != expected:
        return [
            "Rutgers taxonomy coverage report is stale; run `kitchen-almanac rutgers taxonomy`."
        ]
    return []
