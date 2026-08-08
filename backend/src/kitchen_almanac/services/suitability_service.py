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
    SuitabilityDimensionResponse,
    SuitabilityEvidenceReference,
    SuitabilityFactorResponse,
)
from kitchen_almanac.services.cultivar_service import list_cultivars
from kitchen_almanac.services.garden_profile_service import GardenProfileNotFoundError

SUITABILITY_ALGORITHM_VERSION = "suitability-v1.1.0"
MATURITY_BUFFER_DAYS = 21
MID_ATLANTIC_BOUNDS = {
    "minimum_latitude": 36.5,
    "maximum_latitude": 42.5,
    "minimum_longitude": -83.0,
    "maximum_longitude": -73.0,
}
DIMENSION_WEIGHTS = {
    "maturity_window": 30,
    "temperature_gdd": 10,
    "photoperiod": 5,
    "disease_pressure": 10,
    "growing_method": 10,
    "support": 10,
    "space": 10,
    "container_fit": 5,
    "intended_use": 5,
    "regional_evidence": 10,
}
TOMATO_DISEASE_CONCERNS = {
    "early_blight",
    "fusarium_wilt",
    "late_blight",
    "root_knot_nematode",
    "tomato_mosaic_virus",
    "tomato_spotted_wilt_virus",
    "verticillium_wilt",
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
    location_fact = field_name == "coordinates"
    source = (
        profile.location_dataset.source_document
        if location_fact and profile.location_dataset
        else None
    )
    return SuitabilityEvidenceReference(
        field_name=field_name,
        value=value,
        origin="garden_profile",
        source_document_id=source.id if source else None,
        title=source.title if source else None,
        publisher=source.publisher if source else None,
        source_url=source.source_url if source else None,
        source_locator=profile.coordinate_source_locator if location_fact else None,
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


def _dimension(
    *,
    code: str,
    label: str,
    status: str,
    explanation: str,
    evidence: list[SuitabilityEvidenceReference] | None = None,
) -> SuitabilityDimensionResponse:
    return SuitabilityDimensionResponse(
        code=code,
        label=label,
        status=status,
        explanation=explanation,
        evidence=evidence or [],
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


def _append_once(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


def _numeric_minimum(value: object) -> float | None:
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, dict):
        minimum = value.get("minimum")
        if isinstance(minimum, int | float):
            return float(minimum)
    return None


def _documented_uses(
    cultivar: CultivarResponse,
) -> tuple[set[str], list[SuitabilityEvidenceReference], bool]:
    uses: set[str] = set()
    evidence: list[SuitabilityEvidenceReference] = []
    inferred = False
    uses_trait = _trait(cultivar, "uses")
    if uses_trait is not None and isinstance(uses_trait.normalized_value, list):
        uses.update(str(item) for item in uses_trait.normalized_value)
        evidence.append(_trait_reference(uses_trait))

    crop_type = _trait(cultivar, "crop_type")
    type_values: set[str] = set()
    if crop_type is not None:
        raw_value = crop_type.normalized_value
        if isinstance(raw_value, list):
            type_values.update(str(item) for item in raw_value)
        else:
            type_values.add(str(raw_value))
    type_tokens = " ".join({cultivar.crop_type or "", *type_values}).replace("_", " ")
    derived: set[str] = set()
    if any(token in type_tokens for token in ("paste", "plum", "processing")):
        derived.update({"sauce", "canning", "processing"})
    if "pickling" in type_tokens:
        derived.add("pickling")
    if any(
        token in type_tokens
        for token in ("slicer", "cherry", "grape", "beefsteak", "globe", "snacking")
    ):
        derived.add("fresh")
    if any(token in type_tokens for token in ("cherry", "grape", "snacking")):
        derived.add("snacking")
    if derived - uses:
        uses.update(derived)
        inferred = True
        if crop_type is not None:
            evidence.append(_trait_reference(crop_type))
    return uses, evidence, inferred


def _evidence_quality(dimensions: list[SuitabilityDimensionResponse]) -> int:
    numerator = 0
    denominator = 0
    for dimension in dimensions:
        weight = DIMENSION_WEIGHTS.get(dimension.code)
        if weight is None or dimension.status == "not_applicable":
            continue
        denominator += weight
        if dimension.status != "unknown":
            numerator += weight
    return round(100 * numerator / denominator) if denominator else 0


def assess_cultivar(
    profile: GardenProfile,
    cultivar: CultivarResponse,
    *,
    cultivar_dataset_id: str,
) -> SuitabilityAssessmentResponse:
    factors: list[SuitabilityFactorResponse] = []
    dimensions: list[SuitabilityDimensionResponse] = []
    constraints: list[str] = []
    assumptions: list[str] = []
    missing_evidence: list[str] = []
    decision_gaps: list[str] = []
    score = 40

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
    crop_type = _trait(cultivar, "crop_type")
    spacing = _trait(cultivar, "plant_spacing")
    container_volume = _trait(cultivar, "container_volume_gallons")
    gdd_requirement = _trait(cultivar, "gdd_requirement")
    temperature_requirement = _trait(cultivar, "temperature_requirement")
    photoperiod = _trait(cultivar, "photoperiod_requirement")

    climate_evidence = [_climate_reference(climate_claim)] if climate_claim else []
    if climate_claim is None:
        gap = "A frost-free growing-season normal for this garden"
        _append_once(missing_evidence, gap)
        _append_once(decision_gaps, gap)
        dimensions.append(
            _dimension(
                code="maturity_window",
                label="Maturity window",
                status="unknown",
                explanation=(
                    "No climate normal is available for the garden, so maturity cannot be "
                    "compared."
                ),
            )
        )
    elif maturity is None:
        gap = "Days to maturity for this cultivar or its crop baseline"
        _append_once(missing_evidence, gap)
        _append_once(decision_gaps, gap)
        dimensions.append(
            _dimension(
                code="maturity_window",
                label="Maturity window",
                status="unknown",
                explanation=(
                    "The garden season is known, but this cultivar has no maturity evidence."
                ),
                evidence=climate_evidence,
            )
        )
    else:
        climate_value = climate_claim.normalized_value
        maturity_value = maturity.normalized_value
        if isinstance(climate_value, dict) and isinstance(maturity_value, dict):
            season_days = int(climate_value["growing_season_days_50"])
            minimum_days = int(maturity_value["minimum"])
            maximum_days = int(maturity_value["maximum"])
            planning_window = season_days - MATURITY_BUFFER_DAYS
            evidence = [_trait_reference(maturity), *climate_evidence]
            if maximum_days <= planning_window:
                score += 20
                explanation = (
                    f"Its documented {minimum_days}–{maximum_days}-day maturity range fits "
                    f"within the {season_days}-day typical frost-free season, including a "
                    f"{MATURITY_BUFFER_DAYS}-day planning buffer."
                )
                effect = "positive"
                dimension_status = "fit"
                points = 20
            elif minimum_days <= season_days:
                score += 5
                explanation = (
                    f"The {minimum_days}–{maximum_days}-day maturity range can fit the "
                    f"{season_days}-day typical season, but not with the full "
                    f"{MATURITY_BUFFER_DAYS}-day planning buffer."
                )
                effect = "caution"
                dimension_status = "caution"
                points = 5
                gap = "A planting date that confirms enough usable warm days"
                _append_once(missing_evidence, gap)
                _append_once(decision_gaps, gap)
            else:
                score -= 45
                explanation = (
                    f"The earliest documented maturity ({minimum_days} days) exceeds the "
                    f"typical {season_days}-day frost-free season."
                )
                effect = "constraint"
                dimension_status = "constraint"
                points = -45
                constraints.append(explanation)
            factors.append(
                SuitabilityFactorResponse(
                    code="maturity_window",
                    effect=effect,
                    points=points,
                    explanation=explanation,
                    evidence=evidence,
                )
            )
            dimensions.append(
                _dimension(
                    code="maturity_window",
                    label="Maturity window",
                    status=dimension_status,
                    explanation=explanation,
                    evidence=evidence,
                )
            )
            if maturity_value.get("basis") == "unspecified":
                assumptions.append(
                    "The maturity source does not say whether days are counted from seed or "
                    "transplant; the range is compared directly with the frost-free window."
                )

    if climate_claim is None:
        dimensions.append(
            _dimension(
                code="temperature_gdd",
                label="Temperature and heat units",
                status="unknown",
                explanation="No climate normal is available for a temperature or GDD comparison.",
            )
        )
    elif gdd_requirement is None and temperature_requirement is None:
        gap = "Cultivar-specific temperature or growing-degree-day requirements"
        _append_once(missing_evidence, gap)
        dimensions.append(
            _dimension(
                code="temperature_gdd",
                label="Temperature and heat units",
                status="unknown",
                explanation=(
                    "The NOAA climate normal includes temperature and GDD₅₀, but the cultivar "
                    "catalog has no comparable requirement, so this dimension does not change "
                    "the score."
                ),
                evidence=climate_evidence,
            )
        )
    elif gdd_requirement is not None:
        climate_value = climate_claim.normalized_value
        required_gdd = _numeric_minimum(gdd_requirement.normalized_value)
        available_gdd = (
            float(climate_value["growing_degree_days_base_50_f"])
            if isinstance(climate_value, dict)
            else None
        )
        evidence = [_trait_reference(gdd_requirement), *climate_evidence]
        if required_gdd is None or available_gdd is None:
            gap = "Comparable numeric GDD values for the cultivar and garden"
            _append_once(missing_evidence, gap)
            dimensions.append(
                _dimension(
                    code="temperature_gdd",
                    label="Temperature and heat units",
                    status="unknown",
                    explanation=(
                        "The GDD evidence is present but not comparable in its current form."
                    ),
                    evidence=evidence,
                )
            )
        elif required_gdd <= available_gdd:
            score += 5
            explanation = (
                f"The garden's {available_gdd:.0f} GDD₅₀ normal meets the cultivar's "
                f"documented {required_gdd:.0f} GDD requirement."
            )
            factors.append(
                SuitabilityFactorResponse(
                    code="temperature_gdd",
                    effect="positive",
                    points=5,
                    explanation=explanation,
                    evidence=evidence,
                )
            )
            dimensions.append(
                _dimension(
                    code="temperature_gdd",
                    label="Temperature and heat units",
                    status="fit",
                    explanation=explanation,
                    evidence=evidence,
                )
            )
        else:
            score -= 35
            explanation = (
                f"The cultivar requires {required_gdd:.0f} GDD, exceeding the garden's "
                f"{available_gdd:.0f} GDD₅₀ normal."
            )
            constraints.append(explanation)
            factors.append(
                SuitabilityFactorResponse(
                    code="temperature_gdd",
                    effect="constraint",
                    points=-35,
                    explanation=explanation,
                    evidence=evidence,
                )
            )
            dimensions.append(
                _dimension(
                    code="temperature_gdd",
                    label="Temperature and heat units",
                    status="constraint",
                    explanation=explanation,
                    evidence=evidence,
                )
            )
    else:
        gap = "A seasonal temperature model comparable with the cultivar requirement"
        _append_once(missing_evidence, gap)
        dimensions.append(
            _dimension(
                code="temperature_gdd",
                label="Temperature and heat units",
                status="unknown",
                explanation=(
                    "A cultivar temperature requirement is documented, but the current climate "
                    "normal is not yet modeled at the necessary seasonal resolution."
                ),
                evidence=[_trait_reference(temperature_requirement), *climate_evidence],
            )
        )

    if photoperiod is None:
        gap = "Cultivar-specific photoperiod sensitivity"
        _append_once(missing_evidence, gap)
        dimensions.append(
            _dimension(
                code="photoperiod",
                label="Photoperiod",
                status="unknown",
                explanation=(
                    "No cultivar photoperiod requirement is documented, so day length does not "
                    "change the score."
                ),
            )
        )
    elif photoperiod.normalized_value == "day_neutral":
        explanation = "The cultivar is documented as day-neutral."
        factors.append(
            SuitabilityFactorResponse(
                code="photoperiod",
                effect="positive",
                points=2,
                explanation=explanation,
                evidence=[_trait_reference(photoperiod)],
            )
        )
        score += 2
        dimensions.append(
            _dimension(
                code="photoperiod",
                label="Photoperiod",
                status="fit",
                explanation=explanation,
                evidence=[_trait_reference(photoperiod)],
            )
        )
    else:
        gap = "A planting date and day-length comparison for this photoperiod-sensitive cultivar"
        _append_once(missing_evidence, gap)
        _append_once(decision_gaps, gap)
        dimensions.append(
            _dimension(
                code="photoperiod",
                label="Photoperiod",
                status="unknown",
                explanation=(
                    "Photoperiod sensitivity is documented, but no planting date is selected."
                ),
                evidence=[_trait_reference(photoperiod)],
            )
        )

    disease_profile = _profile_reference(
        profile,
        field_name="disease_concerns",
        value=profile.disease_concerns,
    )
    applicable_disease_concerns = (
        sorted(set(profile.disease_concerns) & TOMATO_DISEASE_CONCERNS)
        if cultivar.crop_slug == "tomatoes"
        else []
    )
    if profile.disease_concerns and not applicable_disease_concerns:
        dimensions.append(
            _dimension(
                code="disease_pressure",
                label="Disease pressure",
                status="not_applicable",
                explanation=(
                    "The selected disease concerns are tomato-specific and do not apply to this "
                    "crop."
                ),
                evidence=[disease_profile],
            )
        )
    elif not applicable_disease_concerns:
        dimensions.append(
            _dimension(
                code="disease_pressure",
                label="Disease pressure",
                status="not_applicable",
                explanation="No recurring disease concerns were selected for this garden.",
                evidence=[disease_profile],
            )
        )
    else:
        resistance_values = (
            {str(item) for item in disease_resistance.normalized_value}
            if disease_resistance is not None
            and isinstance(disease_resistance.normalized_value, list)
            else set()
        )
        matched_diseases = sorted(set(applicable_disease_concerns) & resistance_values)
        unmatched_diseases = sorted(set(applicable_disease_concerns) - resistance_values)
        disease_evidence = [disease_profile]
        if disease_resistance is not None:
            disease_evidence.insert(0, _trait_reference(disease_resistance))
        if matched_diseases:
            points = min(8, len(matched_diseases) * 4)
            score += points
            explanation = (
                "Documented resistance matches the garden's concern about "
                f"{', '.join(item.replace('_', ' ') for item in matched_diseases)}."
            )
            factors.append(
                SuitabilityFactorResponse(
                    code="disease_pressure",
                    effect="positive",
                    points=points,
                    explanation=explanation,
                    evidence=disease_evidence,
                )
            )
            dimension_status = "fit" if not unmatched_diseases else "caution"
        else:
            explanation = "No documented resistance matches the garden's selected disease concerns."
            dimension_status = "caution"
        if unmatched_diseases:
            gap = "Resistance evidence for: " + ", ".join(
                item.replace("_", " ") for item in unmatched_diseases
            )
            _append_once(missing_evidence, gap)
            _append_once(decision_gaps, gap)
        dimensions.append(
            _dimension(
                code="disease_pressure",
                label="Disease pressure",
                status=dimension_status,
                explanation=explanation,
                evidence=disease_evidence,
            )
        )

    profile_setup = _profile_reference(
        profile,
        field_name="growing_methods",
        value=profile.growing_methods,
    )
    protected_type = (cultivar.crop_type or "").startswith("protected_")
    method_evidence = [*([_trait_reference(crop_type)] if crop_type else []), profile_setup]
    if protected_type and "protected" not in profile.growing_methods:
        score -= 30
        explanation = (
            "This cultivar is documented for protected culture, but the garden profile does "
            "not include a greenhouse or high-tunnel setup."
        )
        constraints.append(explanation)
        factors.append(
            SuitabilityFactorResponse(
                code="growing_method",
                effect="constraint",
                points=-30,
                explanation=explanation,
                evidence=method_evidence,
            )
        )
        method_status = "constraint"
    elif protected_type:
        score += 5
        explanation = "The cultivar's protected-culture designation matches the garden setup."
        factors.append(
            SuitabilityFactorResponse(
                code="growing_method",
                effect="positive",
                points=5,
                explanation=explanation,
                evidence=method_evidence,
            )
        )
        method_status = "fit"
    else:
        explanation = "No documented protected-culture requirement conflicts with the setup."
        method_status = "fit"
    dimensions.append(
        _dimension(
            code="growing_method",
            label="Growing method",
            status=method_status,
            explanation=explanation,
            evidence=method_evidence,
        )
    )

    habit_value = growth_habit.normalized_value if growth_habit else None
    support_required = habit_value in {"indeterminate", "pole"}
    support_evidence = [
        *([_trait_reference(growth_habit)] if growth_habit else []),
        _profile_reference(
            profile,
            field_name="support_available",
            value=profile.support_available if profile.support_available is not None else "unknown",
        ),
    ]
    if support_required and profile.support_available is True:
        score += 3
        explanation = "The garden can provide support for the climbing or indeterminate habit."
        factors.append(
            SuitabilityFactorResponse(
                code="support",
                effect="positive",
                points=3,
                explanation=explanation,
                evidence=support_evidence,
            )
        )
        support_status = "fit"
    elif support_required and profile.support_available is False:
        score -= 25
        explanation = (
            "The cultivar needs support for its climbing or indeterminate habit, but the garden "
            "cannot provide it."
        )
        constraints.append(explanation)
        factors.append(
            SuitabilityFactorResponse(
                code="support",
                effect="constraint",
                points=-25,
                explanation=explanation,
                evidence=support_evidence,
            )
        )
        support_status = "constraint"
    elif support_required:
        explanation = "The cultivar needs support, and support availability has not been specified."
        gap = "Whether a cage, stake, or trellis can be provided"
        _append_once(missing_evidence, gap)
        _append_once(decision_gaps, gap)
        support_status = "caution"
    elif growth_habit is not None:
        explanation = "The documented growth habit does not require climbing support."
        support_status = "fit"
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
    else:
        explanation = "No cultivar growth-habit evidence is available to assess support needs."
        gap = "Growth habit or support requirements for this cultivar"
        _append_once(missing_evidence, gap)
        if profile.support_available is not True:
            _append_once(decision_gaps, gap)
        support_status = "unknown"
    dimensions.append(
        _dimension(
            code="support",
            label="Support",
            status=support_status,
            explanation=explanation,
            evidence=support_evidence,
        )
    )

    if profile.max_plant_spread_inches is None:
        dimensions.append(
            _dimension(
                code="space",
                label="Plant space",
                status="not_applicable",
                explanation="No maximum per-plant width was selected for this garden.",
                evidence=[
                    _profile_reference(
                        profile,
                        field_name="max_plant_spread_inches",
                        value="unspecified",
                    )
                ],
            )
        )
    elif spacing is None:
        gap = "Documented plant spacing for this cultivar or crop baseline"
        _append_once(missing_evidence, gap)
        _append_once(decision_gaps, gap)
        dimensions.append(
            _dimension(
                code="space",
                label="Plant space",
                status="unknown",
                explanation=(
                    f"The garden allows {profile.max_plant_spread_inches} inches per plant, but "
                    "the catalog has no comparable spacing fact."
                ),
                evidence=[
                    _profile_reference(
                        profile,
                        field_name="max_plant_spread_inches",
                        value=profile.max_plant_spread_inches,
                    )
                ],
            )
        )
    else:
        minimum_spacing = _numeric_minimum(spacing.normalized_value)
        space_evidence = [
            _trait_reference(spacing),
            _profile_reference(
                profile,
                field_name="max_plant_spread_inches",
                value=profile.max_plant_spread_inches,
            ),
        ]
        if minimum_spacing is None:
            gap = "Comparable numeric spacing evidence"
            _append_once(missing_evidence, gap)
            _append_once(decision_gaps, gap)
            space_status = "unknown"
            explanation = "The spacing evidence is not numeric enough for comparison."
        elif minimum_spacing <= profile.max_plant_spread_inches:
            score += 5
            explanation = (
                f"The documented minimum spacing of {minimum_spacing:g} inches fits the "
                f"garden's {profile.max_plant_spread_inches}-inch per-plant limit."
            )
            space_status = "fit"
            factors.append(
                SuitabilityFactorResponse(
                    code="space",
                    effect="positive",
                    points=5,
                    explanation=explanation,
                    evidence=space_evidence,
                )
            )
        else:
            score -= 25
            explanation = (
                f"The documented minimum spacing is {minimum_spacing:g} inches, exceeding the "
                f"garden's {profile.max_plant_spread_inches}-inch per-plant limit."
            )
            space_status = "constraint"
            constraints.append(explanation)
            factors.append(
                SuitabilityFactorResponse(
                    code="space",
                    effect="constraint",
                    points=-25,
                    explanation=explanation,
                    evidence=space_evidence,
                )
            )
        dimensions.append(
            _dimension(
                code="space",
                label="Plant space",
                status=space_status,
                explanation=explanation,
                evidence=space_evidence,
            )
        )

    container_only = set(profile.growing_methods) == {"containers"}
    if not container_only:
        dimensions.append(
            _dimension(
                code="container_fit",
                label="Container fit",
                status="not_applicable",
                explanation="The garden includes a non-container growing method for this plant.",
                evidence=[profile_setup],
            )
        )
    elif profile.max_container_volume_gallons is None:
        gap = "The largest available container volume"
        _append_once(missing_evidence, gap)
        _append_once(decision_gaps, gap)
        dimensions.append(
            _dimension(
                code="container_fit",
                label="Container fit",
                status="unknown",
                explanation="This is a container-only garden, but container volume is unspecified.",
                evidence=[profile_setup],
            )
        )
    elif container_volume is None:
        gap = "A minimum container volume for this cultivar or crop baseline"
        _append_once(missing_evidence, gap)
        _append_once(decision_gaps, gap)
        dimensions.append(
            _dimension(
                code="container_fit",
                label="Container fit",
                status="unknown",
                explanation=(
                    f"The garden has a {profile.max_container_volume_gallons:g}-gallon container, "
                    "but the catalog has no comparable cultivar requirement."
                ),
                evidence=[
                    profile_setup,
                    _profile_reference(
                        profile,
                        field_name="max_container_volume_gallons",
                        value=profile.max_container_volume_gallons,
                    ),
                ],
            )
        )
    else:
        required_volume = _numeric_minimum(container_volume.normalized_value)
        container_evidence = [
            _trait_reference(container_volume),
            _profile_reference(
                profile,
                field_name="max_container_volume_gallons",
                value=profile.max_container_volume_gallons,
            ),
        ]
        if required_volume is None:
            gap = "Comparable numeric container-volume evidence"
            _append_once(missing_evidence, gap)
            _append_once(decision_gaps, gap)
            container_status = "unknown"
            explanation = "The container evidence is not numeric enough for comparison."
        elif required_volume <= profile.max_container_volume_gallons:
            score += 5
            explanation = (
                f"The {profile.max_container_volume_gallons:g}-gallon container meets the "
                f"documented {required_volume:g}-gallon minimum."
            )
            container_status = "fit"
            factors.append(
                SuitabilityFactorResponse(
                    code="container_fit",
                    effect="positive",
                    points=5,
                    explanation=explanation,
                    evidence=container_evidence,
                )
            )
        else:
            score -= 25
            explanation = (
                f"The cultivar needs at least {required_volume:g} gallons, exceeding the "
                f"available {profile.max_container_volume_gallons:g}-gallon container."
            )
            container_status = "constraint"
            constraints.append(explanation)
            factors.append(
                SuitabilityFactorResponse(
                    code="container_fit",
                    effect="constraint",
                    points=-25,
                    explanation=explanation,
                    evidence=container_evidence,
                )
            )
        dimensions.append(
            _dimension(
                code="container_fit",
                label="Container fit",
                status=container_status,
                explanation=explanation,
                evidence=container_evidence,
            )
        )

    intended_use_profile = _profile_reference(
        profile,
        field_name="intended_uses",
        value=profile.intended_uses,
    )
    if not profile.intended_uses:
        dimensions.append(
            _dimension(
                code="intended_use",
                label="Intended use",
                status="not_applicable",
                explanation="No culinary-use preference was selected.",
                evidence=[intended_use_profile],
            )
        )
    else:
        supported_uses, use_evidence, inferred_uses = _documented_uses(cultivar)
        matched_uses = sorted(set(profile.intended_uses) & supported_uses)
        unmatched_uses = sorted(set(profile.intended_uses) - supported_uses)
        evidence = [*use_evidence, intended_use_profile]
        if matched_uses:
            score += 5
            explanation = (
                "Documented use or crop type matches "
                f"{', '.join(item.replace('_', ' ') for item in matched_uses)}."
            )
            factors.append(
                SuitabilityFactorResponse(
                    code="intended_use",
                    effect="positive",
                    points=5,
                    explanation=explanation,
                    evidence=evidence,
                )
            )
            use_status = "fit" if not unmatched_uses else "caution"
            if inferred_uses:
                assumptions.append(
                    "Culinary fit may be inferred from a documented crop type such as paste, "
                    "pickling, slicer, cherry, or grape; it is not treated as an exclusive use."
                )
        else:
            explanation = "The catalog does not document a match for the selected culinary use."
            use_status = "caution"
        if unmatched_uses:
            gap = "Use evidence for: " + ", ".join(
                item.replace("_", " ") for item in unmatched_uses
            )
            _append_once(missing_evidence, gap)
            _append_once(decision_gaps, gap)
        dimensions.append(
            _dimension(
                code="intended_use",
                label="Intended use",
                status=use_status,
                explanation=explanation,
                evidence=evidence,
            )
        )

    regional_value = regional.normalized_value if regional else None
    regional_applies = (
        isinstance(regional_value, dict)
        and regional_value.get("region") == "mid_atlantic"
        and _is_mid_atlantic(profile)
    )
    coordinate_evidence = _profile_reference(
        profile,
        field_name="coordinates",
        value={"latitude": profile.latitude, "longitude": profile.longitude},
    )
    if regional_applies and regional is not None:
        score += 15
        explanation = (
            "This cultivar appears in a current Mid-Atlantic Extension recommendation. The "
            "source is for commercial production, so it is supporting regional evidence rather "
            "than a home-garden guarantee."
        )
        regional_evidence = [_trait_reference(regional), coordinate_evidence]
        factors.append(
            SuitabilityFactorResponse(
                code="regional_evidence",
                effect="positive",
                points=15,
                explanation=explanation,
                evidence=regional_evidence,
            )
        )
        dimensions.append(
            _dimension(
                code="regional_evidence",
                label="Regional evidence",
                status="fit",
                explanation=explanation,
                evidence=regional_evidence,
            )
        )
        assumptions.append(
            "Mid-Atlantic applicability uses an approximate coordinate envelope "
            "(36.5–42.5°N, 83–73°W), not a political-boundary lookup."
        )
    elif regional is not None:
        dimensions.append(
            _dimension(
                code="regional_evidence",
                label="Regional evidence",
                status="not_applicable",
                explanation="The documented regional recommendation does not cover this location.",
                evidence=[_trait_reference(regional), coordinate_evidence],
            )
        )
    else:
        gap = "Regional trial or recommendation evidence for this cultivar"
        _append_once(missing_evidence, gap)
        dimensions.append(
            _dimension(
                code="regional_evidence",
                label="Regional evidence",
                status="unknown",
                explanation=(
                    "No regional trial or recommendation evidence is attached to this cultivar."
                ),
                evidence=[coordinate_evidence],
            )
        )

    evidence_quality = _evidence_quality(dimensions)
    quality_status = "fit" if evidence_quality >= 75 else "caution"
    dimensions.append(
        _dimension(
            code="evidence_quality",
            label="Evidence coverage",
            status=quality_status,
            explanation=(
                f"{evidence_quality}% of the weighted, applicable suitability dimensions have "
                "comparable evidence. Unknown dimensions do not add or subtract score points."
            ),
        )
    )

    if climate_claim is None:
        status = "insufficient_evidence"
        final_score = None
        summary = "Climate evidence is missing, so Kitchen Almanac cannot score this cultivar yet."
    elif constraints:
        status = "not_recommended"
        final_score = max(0, min(score, 100))
        summary = "A documented constraint conflicts with the current garden setup or season."
    elif decision_gaps:
        status = "conditional"
        final_score = max(0, min(score, 100))
        summary = (
            "The available evidence is promising, but a selected constraint needs more evidence."
        )
    else:
        status = "suitable"
        final_score = max(0, min(score, 100))
        summary = (
            "No hard conflict appears in the dimensions supported by current evidence; remaining "
            "catalog gaps are listed below."
        )

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
            "support_available": profile.support_available,
            "max_plant_spread_inches": profile.max_plant_spread_inches,
            "max_container_volume_gallons": profile.max_container_volume_gallons,
            "intended_uses": profile.intended_uses,
            "disease_concerns": profile.disease_concerns,
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
        dimensions=dimensions,
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
