from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from kitchen_almanac.db_models import CultivarDatasetVersion, GardenProfile
from kitchen_almanac.schemas import (
    CultivarResponse,
    CultivarTraitResponse,
    SuitabilityAssessmentResponse,
    SuitabilityEvidenceReference,
    SuitabilityFactorResponse,
)
from kitchen_almanac.services.cultivar_service import list_cultivars
from kitchen_almanac.services.garden_profile_service import GardenProfileNotFoundError

SUITABILITY_ALGORITHM_VERSION = "suitability-v1.0.0"
MATURITY_BUFFER_DAYS = 21
MID_ATLANTIC_BOUNDS = {
    "minimum_latitude": 36.5,
    "maximum_latitude": 42.5,
    "minimum_longitude": -83.0,
    "maximum_longitude": -73.0,
}


class CultivarNotFoundError(LookupError):
    pass


class SuitabilityUnavailableError(RuntimeError):
    pass


def _trait(cultivar: CultivarResponse, field_name: str) -> CultivarTraitResponse | None:
    return next((item for item in cultivar.traits if item.field_name == field_name), None)


def _trait_reference(trait: CultivarTraitResponse) -> SuitabilityEvidenceReference:
    source = trait.source
    return SuitabilityEvidenceReference(
        field_name=trait.field_name,
        value=trait.normalized_value,
        origin="crop_baseline" if trait.inherited_from_crop else "cultivar_catalog",
        source_document_id=source.source_document_id,
        title=source.title,
        publisher=source.publisher,
        source_url=source.source_url,
        source_locator=source.source_locator,
        source_scope=source.scope,
        inherited_from_crop=trait.inherited_from_crop,
    )


def _profile_reference(
    profile: GardenProfile,
    *,
    field_name: str,
    value: dict | list | str | int | float | bool,
) -> SuitabilityEvidenceReference:
    source = profile.location_dataset.source_document if profile.location_dataset else None
    return SuitabilityEvidenceReference(
        field_name=field_name,
        value=value,
        origin="garden_profile",
        source_document_id=source.id if source else None,
        title=source.title if source else None,
        publisher=source.publisher if source else None,
        source_url=source.source_url if source else None,
        source_locator=profile.coordinate_source_locator,
    )


def _climate_reference(claim) -> SuitabilityEvidenceReference:
    source = claim.source_document
    return SuitabilityEvidenceReference(
        field_name=claim.field_name,
        value=claim.normalized_value,
        origin="climate_normal",
        source_document_id=source.id,
        title=source.title,
        publisher=source.publisher,
        source_url=source.source_url,
        source_locator=claim.source_locator,
    )


def _is_mid_atlantic(profile: GardenProfile) -> bool:
    if profile.latitude is None or profile.longitude is None:
        return False
    return (
        MID_ATLANTIC_BOUNDS["minimum_latitude"]
        <= profile.latitude
        <= MID_ATLANTIC_BOUNDS["maximum_latitude"]
        and MID_ATLANTIC_BOUNDS["minimum_longitude"]
        <= profile.longitude
        <= MID_ATLANTIC_BOUNDS["maximum_longitude"]
    )


def _fingerprint(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return f"sha256:{hashlib.sha256(encoded.encode()).hexdigest()}"


def assess_cultivar(
    profile: GardenProfile,
    cultivar: CultivarResponse,
    *,
    cultivar_dataset_id: str,
) -> SuitabilityAssessmentResponse:
    factors: list[SuitabilityFactorResponse] = []
    constraints: list[str] = []
    assumptions: list[str] = []
    missing_evidence: list[str] = []
    score = 50

    climate_claim = next(
        (
            claim
            for claim in profile.location_evidence
            if claim.field_name == "noaa_climate_normals"
        ),
        None,
    )
    maturity = _trait(cultivar, "days_to_maturity")
    regional = _trait(cultivar, "regional_recommendation")
    growth_habit = _trait(cultivar, "growth_habit")
    disease_resistance = _trait(cultivar, "disease_resistance")
    profile_setup = _profile_reference(
        profile,
        field_name="growing_methods",
        value=profile.growing_methods,
    )

    if climate_claim is None:
        missing_evidence.append("A frost-free growing-season normal for this garden")
    elif maturity is None:
        missing_evidence.append("Days to maturity for this cultivar or its crop baseline")
    else:
        climate_value = climate_claim.normalized_value
        maturity_value = maturity.normalized_value
        if isinstance(climate_value, dict) and isinstance(maturity_value, dict):
            season_days = int(climate_value["growing_season_days_50"])
            minimum_days = int(maturity_value["minimum"])
            maximum_days = int(maturity_value["maximum"])
            planning_window = season_days - MATURITY_BUFFER_DAYS
            evidence = [_trait_reference(maturity), _climate_reference(climate_claim)]
            if maximum_days <= planning_window:
                score += 20
                factors.append(
                    SuitabilityFactorResponse(
                        code="maturity_window",
                        effect="positive",
                        points=20,
                        explanation=(
                            f"Its documented {minimum_days}–{maximum_days}-day maturity range "
                            f"fits within the {season_days}-day typical frost-free season, "
                            f"including a {MATURITY_BUFFER_DAYS}-day planning buffer."
                        ),
                        evidence=evidence,
                    )
                )
            elif minimum_days <= season_days:
                score += 5
                factors.append(
                    SuitabilityFactorResponse(
                        code="maturity_window",
                        effect="caution",
                        points=5,
                        explanation=(
                            f"The {minimum_days}–{maximum_days}-day maturity range can fit the "
                            f"{season_days}-day typical season, but not with the full "
                            f"{MATURITY_BUFFER_DAYS}-day planning buffer."
                        ),
                        evidence=evidence,
                    )
                )
                missing_evidence.append("A planting date that confirms enough usable warm days")
            else:
                score -= 45
                constraint = (
                    f"The earliest documented maturity ({minimum_days} days) exceeds the "
                    f"typical {season_days}-day frost-free season."
                )
                constraints.append(constraint)
                factors.append(
                    SuitabilityFactorResponse(
                        code="maturity_window",
                        effect="constraint",
                        points=-45,
                        explanation=constraint,
                        evidence=evidence,
                    )
                )
            if maturity_value.get("basis") == "unspecified":
                assumptions.append(
                    "The maturity source does not say whether days are counted from seed or "
                    "transplant; the range is compared directly with the frost-free window."
                )

    regional_value = regional.normalized_value if regional else None
    regional_applies = (
        isinstance(regional_value, dict)
        and regional_value.get("region") == "mid_atlantic"
        and _is_mid_atlantic(profile)
    )
    if regional_applies and regional is not None:
        score += 15
        factors.append(
            SuitabilityFactorResponse(
                code="regional_recommendation",
                effect="positive",
                points=15,
                explanation=(
                    "This cultivar appears in a current Mid-Atlantic Extension recommendation. "
                    "The source is for commercial production, so it is supporting regional "
                    "evidence rather than a home-garden guarantee."
                ),
                evidence=[
                    _trait_reference(regional),
                    _profile_reference(
                        profile,
                        field_name="coordinates",
                        value={"latitude": profile.latitude, "longitude": profile.longitude},
                    ),
                ],
            )
        )
        assumptions.append(
            "Mid-Atlantic applicability uses an approximate coordinate envelope "
            "(36.5–42.5°N, 83–73°W), not a political-boundary lookup."
        )

    protected_type = (cultivar.crop_type or "").startswith("protected_")
    if protected_type:
        score -= 30
        constraint = (
            "This cultivar is documented for protected culture, but the garden profile does "
            "not include a greenhouse or high-tunnel growing method."
        )
        constraints.append(constraint)
        crop_type = _trait(cultivar, "crop_type")
        factors.append(
            SuitabilityFactorResponse(
                code="protected_culture",
                effect="constraint",
                points=-30,
                explanation=constraint,
                evidence=[
                    *([_trait_reference(crop_type)] if crop_type else []),
                    profile_setup,
                ],
            )
        )

    habit_value = growth_habit.normalized_value if growth_habit else None
    if habit_value in {"determinate", "bush"} and profile.experience_level == "beginner":
        score += 5
        factors.append(
            SuitabilityFactorResponse(
                code="growth_habit_complexity",
                effect="positive",
                points=5,
                explanation=(
                    "The compact growth habit is comparatively straightforward for a beginner."
                ),
                evidence=[
                    _trait_reference(growth_habit),
                    _profile_reference(
                        profile,
                        field_name="experience_level",
                        value=profile.experience_level,
                    ),
                ],
            )
        )
    elif habit_value in {"indeterminate", "pole"}:
        score -= 5
        factors.append(
            SuitabilityFactorResponse(
                code="support_requirement",
                effect="caution",
                points=-5,
                explanation=(
                    "The documented climbing or indeterminate habit will need a support plan."
                ),
                evidence=[_trait_reference(growth_habit)],
            )
        )
        assumptions.append("A suitable cage, stake, or trellis can be added to the garden setup.")

    if disease_resistance is not None:
        score += 5
        factors.append(
            SuitabilityFactorResponse(
                code="documented_disease_resistance",
                effect="positive",
                points=5,
                explanation=(
                    "Documented disease resistance improves resilience, but local disease "
                    "pressure has not yet been modeled."
                ),
                evidence=[_trait_reference(disease_resistance)],
            )
        )

    evidence_quality = 0
    if climate_claim is not None:
        evidence_quality += 40
    if maturity is not None:
        evidence_quality += 25 if maturity.inherited_from_crop else 35
    if regional is not None:
        evidence_quality += 15
    if growth_habit is not None:
        evidence_quality += 10
    evidence_quality = min(evidence_quality, 100)

    if climate_claim is None:
        status = "insufficient_evidence"
        final_score = None
        summary = "Climate evidence is missing, so Kitchen Almanac cannot score this cultivar yet."
    elif constraints:
        status = "not_recommended"
        final_score = max(0, min(score, 100))
        summary = "A documented constraint conflicts with the current garden setup or season."
    elif missing_evidence:
        status = "conditional"
        final_score = max(0, min(score, 100))
        summary = "The available evidence is promising, but a key fact is still missing."
    else:
        status = "suitable"
        final_score = max(0, min(score, 100))
        summary = "The documented maturity and garden context show no current hard conflict."

    if status == "suitable" and regional_applies:
        result_group = "best_documented_fit"
    elif status == "suitable":
        result_group = "other_documented"
    elif status == "conditional":
        result_group = "conditional"
    elif status == "not_recommended":
        result_group = "constrained"
    else:
        result_group = "insufficient_evidence"

    fingerprint_payload = {
        "algorithm_version": SUITABILITY_ALGORITHM_VERSION,
        "cultivar_dataset_id": cultivar_dataset_id,
        "garden_profile": {
            "id": profile.id,
            "latitude": profile.latitude,
            "longitude": profile.longitude,
            "experience_level": profile.experience_level,
            "growing_methods": profile.growing_methods,
        },
        "cultivar": cultivar.model_dump(mode="json"),
        "climate_claim": (
            {
                "dataset_id": climate_claim.climate_dataset_version_id,
                "value": climate_claim.normalized_value,
                "source_document_id": climate_claim.source_document_id,
            }
            if climate_claim is not None
            else None
        ),
    }
    return SuitabilityAssessmentResponse(
        garden_profile_id=profile.id,
        cultivar_slug=cultivar.slug,
        cultivar_dataset_id=cultivar_dataset_id,
        algorithm_version=SUITABILITY_ALGORITHM_VERSION,
        input_fingerprint=_fingerprint(fingerprint_payload),
        status=status,
        score=final_score,
        evidence_quality=evidence_quality,
        result_group=result_group,
        summary=summary,
        factors=factors,
        constraints=constraints,
        assumptions=assumptions,
        missing_evidence=missing_evidence,
    )


def get_suitability_assessment(
    session: Session,
    *,
    garden_profile_id: str,
    cultivar_slug: str,
) -> SuitabilityAssessmentResponse:
    profile = session.scalar(
        select(GardenProfile)
        .where(GardenProfile.id == garden_profile_id)
        .options(
            selectinload(GardenProfile.location_dataset),
            selectinload(GardenProfile.location_evidence),
        )
    )
    if profile is None:
        raise GardenProfileNotFoundError(garden_profile_id)
    dataset = session.scalar(
        select(CultivarDatasetVersion).where(CultivarDatasetVersion.active.is_(True))
    )
    if dataset is None:
        raise SuitabilityUnavailableError("Load a cultivar catalog before assessing suitability.")
    cultivar = next(
        (item for item in list_cultivars(session).cultivars if item.slug == cultivar_slug),
        None,
    )
    if cultivar is None:
        raise CultivarNotFoundError(cultivar_slug)
    return assess_cultivar(profile, cultivar, cultivar_dataset_id=dataset.id)
