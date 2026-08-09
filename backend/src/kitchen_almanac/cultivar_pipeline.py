from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from kitchen_almanac.cultivar_catalog import (
    REPOSITORY_ROOT,
    CultivarCatalogError,
    validate_cultivar_catalog,
)
from kitchen_almanac.services.wishlist_resolver import normalize_term

STAGING_SCHEMA_VERSION = "1.0.0"
DEFAULT_BASE = REPOSITORY_ROOT / "data/source/cultivars/reviewed-cultivars.v1.json"
DEFAULT_STAGED = REPOSITORY_ROOT / "data/source/cultivars/staged-mid-atlantic.v1.json"
DEFAULT_DECISIONS = REPOSITORY_ROOT / "data/source/cultivars/review-decisions.v1.json"
DEFAULT_OUTPUT = REPOSITORY_ROOT / "data/seed/cultivar-catalog.v1.json"
SUPPORTED_ATTRIBUTES = {
    "crop_type",
    "days_to_maturity",
    "maturity_basis",
    "growth_habit",
    "flowering_habit",
    "fruit_color",
    "fruit_length_inches",
    "fruit_shape",
    "heat_tolerant",
    "hybrid",
    "leaf_type",
    "season_class",
    "uses",
    "disease_resistance",
}


class CultivarPipelineError(ValueError):
    """Raised when staged cultivar evidence cannot be safely published."""


@dataclass(frozen=True)
class ReconciliationItem:
    candidate_id: str
    proposed_name: str
    exact_matches: tuple[str, ...]
    possible_match: str | None
    possible_match_score: float
    decision: str | None


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def staging_sha256(staged: object) -> str:
    return hashlib.sha256(_canonical_bytes(staged)).hexdigest()


def read_pipeline_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise CultivarPipelineError(f"Could not read {label}: {error}") from error
    if not isinstance(value, dict):
        raise CultivarPipelineError(f"{label.capitalize()} must be a JSON object.")
    return value


def validate_staged_cultivars(
    staged: object,
    *,
    verify_snapshots: bool = False,
) -> list[str]:
    if not isinstance(staged, dict):
        return ["Staged cultivar data must be a JSON object."]
    required = {"schema_version", "crop_dataset_id", "sources", "candidates"}
    missing = required - staged.keys()
    if missing:
        return [f"Staged cultivar data is missing keys: {sorted(missing)!r}."]
    errors: list[str] = []
    if staged["schema_version"] != STAGING_SCHEMA_VERSION:
        errors.append(f"Unsupported staging schema {staged['schema_version']!r}.")

    sources = staged["sources"]
    if not isinstance(sources, list):
        return [*errors, "Staged sources must be a list."]
    source_keys = [source.get("key") for source in sources if isinstance(source, dict)]
    if len(source_keys) != len(sources) or len(source_keys) != len(set(source_keys)):
        errors.append("Staged source keys must be present and unique.")
    for source in sources:
        if not isinstance(source, dict):
            errors.append("Every staged source must be an object.")
            continue
        required_source = {
            "key",
            "title",
            "publisher",
            "url",
            "source_path",
            "sha256",
            "media_type",
            "retrieved_at",
            "license",
            "scope",
        }
        missing_source = required_source - source.keys()
        if missing_source:
            errors.append(
                f"Staged source {source.get('key')!r} is missing "
                f"{sorted(missing_source)!r}."
            )
            continue
        if len(source["sha256"]) != 64:
            errors.append(f"Staged source {source['key']!r} has an invalid SHA-256 digest.")
        if verify_snapshots:
            source_path = REPOSITORY_ROOT / source["source_path"]
            if not source_path.is_file():
                errors.append(
                    f"Staged source snapshot {source['source_path']!r} does not exist. "
                    "Run `kitchen-almanac cultivars fetch` first."
                )
            else:
                actual_sha = hashlib.sha256(source_path.read_bytes()).hexdigest()
                if actual_sha != source["sha256"]:
                    errors.append(f"Staged source {source['key']!r} checksum does not match.")

    candidates = staged["candidates"]
    if not isinstance(candidates, list):
        return [*errors, "Staged candidates must be a list."]
    candidate_ids = [item.get("id") for item in candidates if isinstance(item, dict)]
    if len(candidate_ids) != len(candidates) or len(candidate_ids) != len(set(candidate_ids)):
        errors.append("Candidate IDs must be present and unique.")
    proposed_slugs = [
        item.get("proposed_slug")
        for item in candidates
        if isinstance(item, dict) and item.get("record_kind", "identity") == "identity"
    ]
    if len(proposed_slugs) != len(set(proposed_slugs)):
        errors.append("Proposed cultivar slugs must be unique.")
    normalized_alias_owners: dict[str, str] = {}
    for candidate in candidates:
        if not isinstance(candidate, dict):
            errors.append("Every cultivar candidate must be an object.")
            continue
        required_candidate = {
            "id",
            "crop_slug",
            "proposed_slug",
            "name_in_source",
            "aliases",
            "description",
            "source_key",
            "source_identifier",
            "source_locator",
            "attributes",
        }
        missing_candidate = required_candidate - candidate.keys()
        if missing_candidate:
            errors.append(
                f"Candidate {candidate.get('id')!r} is missing {sorted(missing_candidate)!r}."
            )
            continue
        if candidate["source_key"] not in source_keys:
            errors.append(f"Candidate {candidate['id']!r} references an unknown source.")
        record_kind = candidate.get("record_kind", "identity")
        if record_kind not in {"identity", "enrichment"}:
            errors.append(f"Candidate {candidate['id']!r} has an invalid record kind.")
        aliases = candidate["aliases"]
        if not isinstance(aliases, list) or aliases != sorted(set(aliases), key=str.casefold):
            errors.append(f"Candidate {candidate['id']!r} aliases must be sorted and unique.")
        elif record_kind == "identity":
            for alias in {candidate["name_in_source"], *aliases}:
                normalized_alias = normalize_term(alias)
                owner = normalized_alias_owners.setdefault(normalized_alias, candidate["id"])
                if owner != candidate["id"]:
                    errors.append(
                        f"Candidates {owner!r} and {candidate['id']!r} share alias {alias!r}."
                    )
        attributes = candidate["attributes"]
        if not isinstance(attributes, dict):
            errors.append(f"Candidate {candidate['id']!r} attributes must be an object.")
        else:
            unsupported = attributes.keys() - SUPPORTED_ATTRIBUTES
            if unsupported:
                errors.append(
                    f"Candidate {candidate['id']!r} has unsupported attributes "
                    f"{sorted(unsupported)!r}."
                )
        manual_traits = candidate.get("traits", [])
        if not isinstance(manual_traits, list):
            errors.append(f"Candidate {candidate['id']!r} traits must be a list.")
        else:
            manual_fields = [
                trait.get("field_name") for trait in manual_traits if isinstance(trait, dict)
            ]
            if len(manual_fields) != len(manual_traits) or len(manual_fields) != len(
                set(manual_fields)
            ):
                errors.append(
                    f"Candidate {candidate['id']!r} manual trait fields must be present and unique."
                )
            for trait in manual_traits:
                if not isinstance(trait, dict):
                    continue
                required_trait = {
                    "field_name",
                    "normalized_value",
                    "unit",
                    "confidence",
                    "source_excerpt",
                }
                missing_trait = required_trait - trait.keys()
                if missing_trait:
                    errors.append(
                        f"Candidate {candidate['id']!r} trait is missing "
                        f"{sorted(missing_trait)!r}."
                    )
                if trait.get("confidence") not in {"low", "medium", "high"}:
                    errors.append(
                        f"Candidate {candidate['id']!r} trait has invalid confidence."
                    )
    return errors


def validate_review_decisions(staged: dict[str, Any], decisions: object) -> list[str]:
    if not isinstance(decisions, dict):
        return ["Review decisions must be a JSON object."]
    required = {"schema_version", "staging_sha256", "reviewed_at", "reviewer", "decisions"}
    missing = required - decisions.keys()
    if missing:
        return [f"Review decisions are missing keys: {sorted(missing)!r}."]
    errors: list[str] = []
    if decisions["schema_version"] != STAGING_SCHEMA_VERSION:
        errors.append(f"Unsupported decision schema {decisions['schema_version']!r}.")
    if decisions["staging_sha256"] != staging_sha256(staged):
        errors.append("Review decisions do not pin the current staged data.")
    if not isinstance(decisions["reviewer"], str) or not decisions["reviewer"].strip():
        errors.append("Review decisions must identify a reviewer.")
    try:
        datetime.fromisoformat(str(decisions["reviewed_at"]).replace("Z", "+00:00"))
    except ValueError:
        errors.append("Review decisions have an invalid review timestamp.")
    values = decisions["decisions"]
    if not isinstance(values, list):
        return [*errors, "Decision records must be a list."]
    staged_ids = {candidate["id"] for candidate in staged["candidates"]}
    decision_ids = {
        decision.get("candidate_id") for decision in values if isinstance(decision, dict)
    }
    if decision_ids != staged_ids or len(decision_ids) != len(values):
        errors.append("Every staged candidate requires exactly one review decision.")
    for decision in values:
        if not isinstance(decision, dict):
            errors.append("Every review decision must be an object.")
            continue
        action = decision.get("action")
        if action not in {"create", "link", "enrich", "reject"}:
            errors.append(f"Candidate {decision.get('candidate_id')!r} has an invalid action.")
        if action == "create" and not decision.get("canonical_slug"):
            errors.append(
                f"Create decision {decision.get('candidate_id')!r} needs a canonical slug."
            )
        if action == "link" and not decision.get("canonical_slug"):
            errors.append(f"Link decision {decision.get('candidate_id')!r} needs a target slug.")
        if action == "enrich" and not decision.get("canonical_slug"):
            errors.append(
                f"Enrichment decision {decision.get('candidate_id')!r} needs a target slug."
            )
    return errors


def reconcile_candidates(
    base: dict[str, Any],
    staged: dict[str, Any],
    decisions: dict[str, Any] | None = None,
) -> list[ReconciliationItem]:
    aliases_by_slug = {
        cultivar["slug"]: {
            normalize_term(cultivar["canonical_name"]),
            *(normalize_term(alias) for alias in cultivar["aliases"]),
        }
        for cultivar in base["cultivars"]
    }
    decision_by_id = {
        decision["candidate_id"]: decision["action"]
        for decision in (decisions or {}).get("decisions", [])
    }
    report: list[ReconciliationItem] = []
    for candidate in staged["candidates"]:
        names = {
            normalize_term(candidate["name_in_source"]),
            *(normalize_term(alias) for alias in candidate["aliases"]),
        }
        exact = tuple(
            sorted(slug for slug, aliases in aliases_by_slug.items() if names & aliases)
        )
        scored = [
            (
                max(
                    SequenceMatcher(None, name, alias).ratio()
                    for name in names
                    for alias in aliases
                ),
                slug,
            )
            for slug, aliases in aliases_by_slug.items()
        ]
        best_score, best_slug = max(scored, default=(0.0, ""))
        report.append(
            ReconciliationItem(
                candidate_id=candidate["id"],
                proposed_name=candidate["name_in_source"],
                exact_matches=exact,
                possible_match=best_slug if best_score >= 0.84 else None,
                possible_match_score=round(best_score, 4),
                decision=decision_by_id.get(candidate["id"]),
            )
        )
    return report


def _trait(
    *,
    field_name: str,
    value: object,
    unit: str | None,
    candidate: dict[str, Any],
    excerpt: str,
    confidence: str = "high",
) -> dict[str, Any]:
    return {
        "field_name": field_name,
        "normalized_value": value,
        "unit": unit,
        "confidence": confidence,
        "source_key": candidate["source_key"],
        "source_excerpt": excerpt,
        "source_locator": candidate["source_locator"],
    }


def _candidate_traits(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    name = candidate["name_in_source"]
    values = candidate["attributes"]
    traits: list[dict[str, Any]] = []
    if candidate.get("include_regional_recommendation", True):
        traits.append(
            _trait(
                field_name="regional_recommendation",
                value={"region": "mid_atlantic", "production_context": "commercial"},
                unit=None,
                candidate=candidate,
                excerpt=(
                    f"The regional Extension table includes {name} among its recommended varieties."
                ),
            )
        )
    simple_fields = {
        "crop_type": (None, "type"),
        "growth_habit": (None, "growth habit"),
        "flowering_habit": (None, "flowering habit"),
        "fruit_color": (None, "fruit color"),
        "fruit_shape": (None, "fruit shape"),
        "heat_tolerant": (None, "heat tolerance"),
        "hybrid": (None, "hybrid status"),
        "leaf_type": (None, "leaf type"),
        "season_class": (None, "maturity season"),
        "uses": (None, "listed uses"),
        "disease_resistance": (None, "reported disease resistance"),
    }
    for field_name, (unit, label) in simple_fields.items():
        if field_name in values:
            traits.append(
                _trait(
                    field_name=field_name,
                    value=values[field_name],
                    unit=unit,
                    candidate=candidate,
                    excerpt=f"The table reports {label} for {name}.",
                )
            )
    if "days_to_maturity" in values:
        days = values["days_to_maturity"]
        traits.append(
            _trait(
                field_name="days_to_maturity",
                value={
                    "minimum": days,
                    "maximum": days,
                    "basis": values.get("maturity_basis", "seed"),
                },
                unit="days",
                candidate=candidate,
                excerpt=f"The table reports {days} days for {name}.",
            )
        )
    if "fruit_length_inches" in values:
        traits.append(
            _trait(
                field_name="fruit_length",
                value=values["fruit_length_inches"],
                unit="inches",
                candidate=candidate,
                excerpt=f"The table reports the characteristic fruit length for {name}.",
            )
        )
    for manual in candidate.get("traits", []):
        traits.append(
            {
                "field_name": manual["field_name"],
                "normalized_value": manual["normalized_value"],
                "unit": manual["unit"],
                "confidence": manual["confidence"],
                "source_key": candidate["source_key"],
                "source_excerpt": manual["source_excerpt"],
                "source_locator": manual.get("source_locator", candidate["source_locator"]),
            }
        )
    return sorted(traits, key=lambda trait: trait["field_name"])


def publish_staged_catalog(
    base: dict[str, Any],
    staged: dict[str, Any],
    decisions: dict[str, Any],
    *,
    verify_snapshots: bool = False,
) -> dict[str, Any]:
    errors = [
        *validate_staged_cultivars(staged, verify_snapshots=verify_snapshots),
        *validate_review_decisions(staged, decisions),
        *validate_cultivar_catalog(base),
    ]
    if errors:
        raise CultivarPipelineError(" ".join(errors))

    report_by_id = {
        item.candidate_id: item for item in reconcile_candidates(base, staged, decisions)
    }
    output = copy.deepcopy(base)
    sources = {source["key"]: source for source in output["sources"]}
    for source in staged["sources"]:
        if source["key"] in sources and sources[source["key"]] != source:
            raise CultivarPipelineError(
                f"Staged source key {source['key']!r} would replace different source metadata."
            )
        sources[source["key"]] = source
    output["sources"] = sorted(sources.values(), key=lambda source: source["key"])
    cultivars = {cultivar["slug"]: cultivar for cultivar in output["cultivars"]}
    candidate_by_id = {candidate["id"]: candidate for candidate in staged["candidates"]}

    for decision in decisions["decisions"]:
        if decision["action"] == "reject":
            continue
        candidate = candidate_by_id[decision["candidate_id"]]
        slug = decision["canonical_slug"]
        report = report_by_id[candidate["id"]]
        if decision["action"] == "create":
            if slug in cultivars:
                raise CultivarPipelineError(
                    f"Create decision would duplicate cultivar slug {slug!r}."
                )
            if report.exact_matches:
                raise CultivarPipelineError(
                    f"Create decision for {candidate['id']!r} collides with "
                    f"{report.exact_matches!r}."
                )
            canonical_name = decision.get("canonical_name", candidate["name_in_source"])
            aliases = sorted(
                {
                    canonical_name,
                    candidate["name_in_source"],
                    *candidate["aliases"],
                    *decision.get("aliases", []),
                },
                key=str.casefold,
            )
            cultivar = {
                "slug": slug,
                "canonical_name": canonical_name,
                "crop_slug": candidate["crop_slug"],
                "crop_type": candidate["attributes"].get("crop_type"),
                "description": decision.get("description", candidate["description"]),
                "review_status": "approved",
                "aliases": aliases,
                "source_identifiers": [],
                "traits": [],
            }
            cultivars[slug] = cultivar
        elif decision["action"] == "link":
            cultivar = cultivars.get(slug)
            if cultivar is None:
                raise CultivarPipelineError(f"Link decision targets unknown cultivar {slug!r}.")
            if slug not in report.exact_matches and report.possible_match != slug:
                raise CultivarPipelineError(
                    f"Link decision for {candidate['id']!r} is not supported by identity matching."
                )
            cultivar["aliases"] = sorted(
                {
                    *cultivar["aliases"],
                    candidate["name_in_source"],
                    *candidate["aliases"],
                },
                key=str.casefold,
            )
        else:
            cultivar = cultivars.get(slug)
            if cultivar is None:
                raise CultivarPipelineError(
                    f"Enrichment decision targets unknown cultivar {slug!r}."
                )
            if candidate.get("record_kind") != "enrichment":
                raise CultivarPipelineError(
                    f"Enrichment decision for {candidate['id']!r} needs an enrichment record."
                )
            candidate_names = {
                normalize_term(candidate["name_in_source"]),
                *(normalize_term(alias) for alias in candidate["aliases"]),
            }
            cultivar_names = {
                normalize_term(cultivar["canonical_name"]),
                *(normalize_term(alias) for alias in cultivar["aliases"]),
            }
            if not candidate_names & cultivar_names:
                raise CultivarPipelineError(
                    f"Enrichment candidate {candidate['id']!r} does not match {slug!r}."
                )

        cultivar["source_identifiers"].append(
            {
                "source_key": candidate["source_key"],
                "source_identifier": candidate["source_identifier"],
                "name_in_source": candidate["name_in_source"],
            }
        )
        existing_fields = {trait["field_name"] for trait in cultivar["traits"]}
        cultivar["traits"].extend(
            trait
            for trait in _candidate_traits(candidate)
            if trait["field_name"] not in existing_fields
        )
        cultivar["traits"] = sorted(cultivar["traits"], key=lambda trait: trait["field_name"])
        cultivar["source_identifiers"] = sorted(
            cultivar["source_identifiers"],
            key=lambda item: (item["source_key"], item["source_identifier"]),
        )

    output["cultivars"] = sorted(cultivars.values(), key=lambda cultivar: cultivar["slug"])
    publication_errors = validate_cultivar_catalog(output)
    if publication_errors:
        raise CultivarCatalogError(" ".join(publication_errors))
    return output


def build_expanded_snapshot(
    base_path: Path = DEFAULT_BASE,
    staged_path: Path = DEFAULT_STAGED,
    decisions_path: Path = DEFAULT_DECISIONS,
    *,
    verify_snapshots: bool = False,
) -> dict[str, Any]:
    return publish_staged_catalog(
        read_pipeline_json(base_path, "base cultivar catalog"),
        read_pipeline_json(staged_path, "staged cultivar data"),
        read_pipeline_json(decisions_path, "cultivar review decisions"),
        verify_snapshots=verify_snapshots,
    )


def write_expanded_snapshot(data: dict[str, Any], output_path: Path = DEFAULT_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n")


def fetch_staged_sources(staged_path: Path = DEFAULT_STAGED) -> tuple[int, int]:
    staged = read_pipeline_json(staged_path, "staged cultivar data")
    errors = validate_staged_cultivars(staged)
    if errors:
        raise CultivarPipelineError(" ".join(errors))

    fetched = 0
    present = 0
    for source in staged["sources"]:
        destination = REPOSITORY_ROOT / source["source_path"]
        if destination.is_file():
            actual_sha = hashlib.sha256(destination.read_bytes()).hexdigest()
            if actual_sha != source["sha256"]:
                raise CultivarPipelineError(
                    f"Existing source snapshot {source['source_path']!r} has the wrong checksum."
                )
            present += 1
            continue

        destination.parent.mkdir(parents=True, exist_ok=True)
        request = urllib.request.Request(
            source["url"],
            headers={"User-Agent": "Kitchen-Almanac/0.1 cultivar-source-fetcher"},
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                content = response.read()
        except OSError as error:
            raise CultivarPipelineError(
                f"Could not fetch source {source['key']!r}: {error}"
            ) from error
        actual_sha = hashlib.sha256(content).hexdigest()
        if actual_sha != source["sha256"]:
            raise CultivarPipelineError(
                f"Downloaded source {source['key']!r} does not match its reviewed checksum."
            )
        with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as temporary:
            temporary.write(content)
            temporary_path = Path(temporary.name)
        temporary_path.replace(destination)
        fetched += 1
    return fetched, present
