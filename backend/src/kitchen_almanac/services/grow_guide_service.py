from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from kitchen_almanac.db_models import (
    CultivarDatasetVersion,
    GardenProfile,
    LocationEvidenceClaim,
)
from kitchen_almanac.schemas import (
    CultivarResponse,
    CultivarTraitResponse,
    GrowGuideActionResponse,
    GrowGuidePhaseResponse,
    GrowGuideResponse,
    GrowGuideSectionResponse,
    GrowGuideTimelineEventResponse,
    SuitabilityEvidenceReference,
)
from kitchen_almanac.services.cultivar_service import list_cultivars
from kitchen_almanac.services.garden_profile_service import GardenProfileNotFoundError
from kitchen_almanac.services.suitability_service import (
    CultivarNotFoundError,
    SuitabilityUnavailableError,
    assess_cultivar,
)

GROW_GUIDE_ALGORITHM_VERSION = "grow-guide-v1.5.0"


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


def _climate_reference(claim: LocationEvidenceClaim) -> SuitabilityEvidenceReference:
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


def _provenance(traits: list[CultivarTraitResponse]) -> str:
    if not traits:
        return "none"
    origins = {"crop_baseline" if trait.inherited_from_crop else "cultivar" for trait in traits}
    return origins.pop() if len(origins) == 1 else "mixed"


def _confidence(traits: list[CultivarTraitResponse]) -> str | None:
    if not traits:
        return None
    rank = {"low": 0, "medium": 1, "high": 2}
    return min((trait.confidence for trait in traits), key=lambda item: rank.get(item, -1))


def _range_text(value: object, *, unit: str | None = None) -> str:
    if isinstance(value, dict):
        minimum = value.get("minimum")
        maximum = value.get("maximum")
        if minimum is not None and maximum is not None:
            amount = str(minimum) if minimum == maximum else f"{minimum}–{maximum}"
            return f"{amount} {unit}".strip()
        return ", ".join(f"{key.replace('_', ' ')}: {item}" for key, item in value.items())
    if isinstance(value, list):
        return ", ".join(str(item).replace("_", " ") for item in value)
    if isinstance(value, bool):
        return "yes" if value else "no"
    return f"{value} {unit or ''}".strip().replace("_", " ")


def _human_list(values: list[object]) -> str:
    labels = [str(value).replace("_", " ") for value in values]
    if len(labels) < 2:
        return "".join(labels)
    if len(labels) == 2:
        return " and ".join(labels)
    return f"{', '.join(labels[:-1])}, and {labels[-1]}"


def _harvest_pattern_text(trait: CultivarTraitResponse) -> str:
    value = trait.normalized_value
    if isinstance(value, dict):
        window_minimum = value.get("window_minimum")
        window_maximum = value.get("window_maximum")
        if window_minimum is not None and window_maximum is not None:
            duration = (
                str(window_minimum)
                if window_minimum == window_maximum
                else f"{window_minimum}–{window_maximum}"
            )
            unit = trait.unit or "time units"
            if window_minimum == window_maximum == 1 and unit.endswith("s"):
                unit = unit[:-1]
            return f"Expect the harvest window to last {duration} {unit}."

        cluster_minimum = value.get("cluster_minimum")
        cluster_maximum = value.get("cluster_maximum")
        if cluster_minimum is not None and cluster_maximum is not None:
            cluster_size = (
                str(cluster_minimum)
                if cluster_minimum == cluster_maximum
                else f"{cluster_minimum}–{cluster_maximum}"
            )
            return f"Expect fruit in clusters of {cluster_size}."

    return f"Harvest pattern: {_range_text(value, unit=trait.unit)}."


def _section(
    *,
    code: str,
    title: str,
    status: str,
    summary: str,
    traits: list[CultivarTraitResponse] | None = None,
    instructions: list[str] | None = None,
    missing_evidence: list[str] | None = None,
    extra_evidence: list[SuitabilityEvidenceReference] | None = None,
) -> GrowGuideSectionResponse:
    section_traits = traits or []
    return GrowGuideSectionResponse(
        code=code,
        title=title,
        status=status,
        summary=summary,
        instructions=instructions or [],
        confidence=_confidence(section_traits),
        provenance=_provenance(section_traits),
        evidence=[*(_trait_reference(trait) for trait in section_traits), *(extra_evidence or [])],
        missing_evidence=missing_evidence or [],
    )


def _simple_trait_section(
    cultivar: CultivarResponse,
    *,
    code: str,
    title: str,
    field_name: str,
    missing_label: str,
    instruction_prefix: str,
) -> GrowGuideSectionResponse:
    trait = _trait(cultivar, field_name)
    if trait is None:
        missing_evidence = f"{missing_label[0].upper()}{missing_label[1:]}"
        return _section(
            code=code,
            title=title,
            status="missing",
            summary=f"No reviewed {missing_label} is available yet.",
            missing_evidence=[missing_evidence],
        )
    value = _range_text(trait.normalized_value, unit=trait.unit)
    return _section(
        code=code,
        title=title,
        status="documented",
        summary=f"{instruction_prefix} {value}.",
        instructions=[f"{instruction_prefix} {value}."],
        traits=[trait],
    )


def _soil_section(cultivar: CultivarResponse) -> GrowGuideSectionResponse:
    target = _trait(cultivar, "soil_ph")
    lime_below = _trait(cultivar, "lime_below_ph")
    if target is None:
        return _section(
            code="soil",
            title="Soil",
            status="missing",
            summary="No reviewed soil pH or soil-condition guidance is available yet.",
            missing_evidence=["Soil pH or soil-condition guidance"],
        )
    target_text = f"{float(target.normalized_value):.1f}"
    instructions = [f"Aim for a soil pH of {target_text}."]
    traits = [target]
    if lime_below:
        threshold = f"{float(lime_below.normalized_value):.1f}"
        instructions.append(
            f"Use a soil test to determine lime needs when pH falls below {threshold}."
        )
        traits.append(lime_below)
    return _section(
        code="soil",
        title="Soil",
        status="documented",
        summary=" ".join(instructions),
        instructions=instructions,
        traits=traits,
    )


def _water_section(cultivar: CultivarResponse) -> GrowGuideSectionResponse:
    amount = _trait(cultivar, "water_inches_per_week")
    management = _trait(cultivar, "water_management_guidance")
    stages = _trait(cultivar, "critical_watering_stages")
    traits = [trait for trait in (amount, management, stages) if trait is not None]
    if not traits:
        return _section(
            code="water",
            title="Water",
            status="missing",
            summary="No reviewed watering amount, timing, or management guidance is available yet.",
            missing_evidence=["Watering amount, timing, or management guidance"],
        )

    instructions: list[str] = []
    if amount:
        instructions.append(f"Provide {_range_text(amount.normalized_value, unit=amount.unit)}.")
    if management:
        values = (
            management.normalized_value
            if isinstance(management.normalized_value, list)
            else [management.normalized_value]
        )
        instructions.extend(str(value) for value in values)
    if stages:
        stages_text = (
            _human_list(stages.normalized_value)
            if isinstance(stages.normalized_value, list)
            else _range_text(stages.normalized_value)
        )
        instructions.append(f"Pay closest attention to moisture during {stages_text}.")

    missing_evidence: list[str] = []
    if amount is None:
        missing_evidence.append("Reviewed watering quantity")
    if management is None and stages is None:
        missing_evidence.append("Water-management timing or practices")
    return _section(
        code="water",
        title="Water",
        status="partial" if missing_evidence else "documented",
        summary=instructions[0],
        instructions=instructions,
        traits=traits,
        missing_evidence=missing_evidence,
    )


def _container_section(cultivar: CultivarResponse) -> GrowGuideSectionResponse:
    volume = _trait(cultivar, "container_volume_gallons")
    depth = _trait(cultivar, "container_depth_inches")
    plants = _trait(cultivar, "plants_per_container")
    traits = [trait for trait in (volume, depth, plants) if trait is not None]
    if volume is None:
        return _section(
            code="containers",
            title="Containers",
            status="missing",
            summary="No reviewed minimum container size is available yet.",
            missing_evidence=["Minimum container volume and depth"],
        )

    instructions = [
        f"Use {_range_text(volume.normalized_value, unit=volume.unit)} of growing media."
    ]
    missing_evidence: list[str] = []
    if depth:
        instructions.append(
            f"Choose a container {_range_text(depth.normalized_value, unit=depth.unit)} deep."
        )
    else:
        missing_evidence.append("Minimum container depth")
    if plants:
        if plants.normalized_value == 1:
            instructions.append("Grow one plant per container.")
        else:
            count = _range_text(plants.normalized_value, unit=plants.unit)
            instructions.append(f"Allow {count} per container.")

    return _section(
        code="containers",
        title="Containers",
        status="partial" if missing_evidence else "documented",
        summary=" ".join(instructions),
        instructions=instructions,
        traits=traits,
        missing_evidence=missing_evidence,
    )


def _support_section(cultivar: CultivarResponse) -> GrowGuideSectionResponse:
    support = _trait(cultivar, "support_required")
    habit = _trait(cultivar, "growth_habit")
    if support:
        required = support.normalized_value
        if required is True:
            instruction = "Install a cage, stake, or trellis before the plant becomes large."
        elif required is False:
            instruction = "This crop does not usually need a cage, stake, or trellis."
        else:
            instruction = f"Support guidance: {_range_text(required)}."
        return _section(
            code="trellising",
            title="Trellising and support",
            status="documented",
            summary=instruction,
            instructions=[instruction],
            traits=[support, *([habit] if habit else [])],
        )
    if habit:
        habit_text = _range_text(habit.normalized_value)
        return _section(
            code="trellising",
            title="Trellising and support",
            status="partial",
            summary=(
                f"The documented growth habit is {habit_text}, but support needs are not sourced."
            ),
            instructions=[f"Plan around a {habit_text} growth habit."],
            traits=[habit],
            missing_evidence=["Support or trellising requirement"],
        )
    return _section(
        code="trellising",
        title="Trellising and support",
        status="missing",
        summary="No reviewed growth-habit or support requirement is available yet.",
        missing_evidence=["Growth habit and support requirement"],
    )


def _parse_normal_date(value: str, year: int) -> date:
    month, day = (int(part) for part in value.split("/", maxsplit=1))
    return date(year, month, day)


def _build_sections(
    cultivar: CultivarResponse,
    climate_claim: LocationEvidenceClaim | None,
    target_year: int,
) -> tuple[list[GrowGuideSectionResponse], list[GrowGuideTimelineEventResponse], list[str]]:
    sections: list[GrowGuideSectionResponse] = []
    timeline: list[GrowGuideTimelineEventResponse] = []
    assumptions: list[str] = []

    sun = _trait(cultivar, "sun_hours")
    if sun and isinstance(sun.normalized_value, dict):
        value = sun.normalized_value
        minimum = value.get("minimum")
        preferred_minimum = value.get("preferred_minimum")
        preferred_maximum = value.get("preferred_maximum")
        preferred_condition = value.get("preferred_condition")
        preferred = (
            f"; {preferred_minimum}–{preferred_maximum} hours is preferred"
            if preferred_minimum is not None and preferred_maximum is not None
            else "; full sun is preferred"
            if preferred_condition == "full_sun"
            else ""
        )
        instruction = f"Provide at least {minimum} hours of direct sun per day{preferred}."
        sections.append(
            _section(
                code="light",
                title="Light",
                status="documented",
                summary=instruction,
                instructions=[instruction],
                traits=[sun],
            )
        )
    else:
        sections.append(
            _section(
                code="light",
                title="Light",
                status="missing",
                summary="No reviewed daily light requirement is available yet.",
                missing_evidence=["Daily light requirement"],
            )
        )

    sections.extend(
        [
            _soil_section(cultivar),
            _water_section(cultivar),
        ]
    )

    spacing = _trait(cultivar, "plant_spacing")
    row_spacing = _trait(cultivar, "row_spacing")
    if spacing:
        spacing_text = _range_text(spacing.normalized_value, unit=spacing.unit)
        instruction = f"Space plants {spacing_text} apart."
        instructions = [instruction]
        spacing_traits = [spacing]
        if row_spacing:
            row_spacing_text = _range_text(row_spacing.normalized_value, unit=row_spacing.unit)
            instructions.append(f"Allow {row_spacing_text} between rows.")
            spacing_traits.append(row_spacing)
        sections.append(
            _section(
                code="spacing",
                title="Spacing",
                status="documented",
                summary=instruction,
                instructions=instructions,
                traits=spacing_traits,
            )
        )
    else:
        sections.append(
            _section(
                code="spacing",
                title="Spacing",
                status="missing",
                summary="No reviewed plant-spacing range is available yet.",
                missing_evidence=["Plant spacing"],
            )
        )

    sections.append(_container_section(cultivar))
    sections.append(_support_section(cultivar))

    starting_method = _trait(cultivar, "starting_method")
    maturity = _trait(cultivar, "days_to_maturity")
    if starting_method:
        method = _range_text(starting_method.normalized_value)
        instructions = [f"Use {method} as the documented starting method."]
        missing_evidence: list[str] = []
        status = "documented"
        if method == "transplant":
            instructions.append(
                "Reviewed instructions for producing transplants from seed are not available yet."
            )
            missing_evidence.append("Seed-start production instructions (follow-up #13)")
            status = "partial"
        sections.append(
            _section(
                code="starting_method",
                title="Starting method",
                status=status,
                summary=instructions[0],
                instructions=instructions,
                traits=[starting_method],
                missing_evidence=missing_evidence,
            )
        )
    elif maturity and isinstance(maturity.normalized_value, dict):
        basis = str(maturity.normalized_value.get("basis", "unspecified")).replace("_", " ")
        sections.append(
            _section(
                code="starting_method",
                title="Starting method",
                status="partial",
                summary=(
                    f"Maturity is measured from {basis}, but that does not establish how to "
                    "start plants."
                ),
                instructions=[],
                traits=[maturity],
                missing_evidence=["Seed-starting or direct-sowing method"],
            )
        )
    else:
        sections.append(
            _section(
                code="starting_method",
                title="Starting method",
                status="missing",
                summary="No reviewed seed-starting or direct-sowing method is available yet.",
                missing_evidence=["Seed-starting or direct-sowing method"],
            )
        )

    frost_tender = _trait(cultivar, "frost_tender")
    climate_evidence = [_climate_reference(climate_claim)] if climate_claim else []
    planting_traits = [trait for trait in [frost_tender] if trait]
    if frost_tender and frost_tender.normalized_value is True and climate_claim:
        climate = climate_claim.normalized_value
        last_frost = _parse_normal_date(str(climate["last_spring_frost_50"]), target_year)
        first_frost = _parse_normal_date(str(climate["first_fall_frost_50"]), target_year)
        instruction = (
            f"Use {last_frost.isoformat()} as the typical outdoor planting boundary; "
            "local weather can still produce a later freeze."
        )
        sections.append(
            _section(
                code="planting",
                title="Planting",
                status="documented",
                summary=instruction,
                instructions=[instruction],
                traits=planting_traits,
                extra_evidence=climate_evidence,
                missing_evidence=["A weather forecast for the actual planting week"],
            )
        )
        timeline.extend(
            [
                GrowGuideTimelineEventResponse(
                    code="outdoor_planting_boundary",
                    title="Typical outdoor planting boundary",
                    start_date=last_frost,
                    summary=(
                        "The crop is frost-tender and this is the local 50% last-spring-freeze "
                        "normal, not a weather forecast."
                    ),
                    confidence=climate_claim.confidence,
                    evidence=[_trait_reference(frost_tender), *climate_evidence],
                ),
                GrowGuideTimelineEventResponse(
                    code="fall_frost_boundary",
                    title="Typical fall frost boundary",
                    start_date=first_frost,
                    summary=(
                        "The local 50% first-fall-freeze normal marks the typical season boundary."
                    ),
                    confidence=climate_claim.confidence,
                    evidence=climate_evidence,
                ),
            ]
        )
        assumptions.append(
            "Freeze dates are 1991–2020 climate normals at a 50% probability threshold, "
            "not forecasts."
        )
        if maturity and isinstance(maturity.normalized_value, dict):
            value = maturity.normalized_value
            if value.get("basis") == "transplant":
                minimum = int(value["minimum"])
                maximum = int(value["maximum"])
                timeline.append(
                    GrowGuideTimelineEventResponse(
                        code="estimated_first_harvest",
                        title="Evidence-based first harvest window",
                        start_date=last_frost + timedelta(days=minimum),
                        end_date=last_frost + timedelta(days=maximum),
                        summary=(
                            f"Calculated from the {minimum}–{maximum}-day transplant-based "
                            "maturity range and the typical outdoor planting boundary."
                        ),
                        confidence=_confidence([maturity]) or "unknown",
                        evidence=[_trait_reference(maturity), *climate_evidence],
                    )
                )
    elif frost_tender and frost_tender.normalized_value is True:
        sections.append(
            _section(
                code="planting",
                title="Planting",
                status="partial",
                summary="The crop is frost-tender, but local freeze normals are unavailable.",
                traits=planting_traits,
                missing_evidence=["Local probable last-spring-freeze date"],
            )
        )
    else:
        sections.append(
            _section(
                code="planting",
                title="Planting",
                status="missing",
                summary="No reviewed relative planting rule is available for this crop yet.",
                missing_evidence=["Relative planting rule"],
            )
        )

    disease = _trait(cultivar, "disease_resistance")
    if disease:
        sections.append(
            _section(
                code="maintenance",
                title="Maintenance",
                status="partial",
                summary=(
                    "Disease resistance is documented, but routine maintenance instructions "
                    "are not."
                ),
                instructions=[f"Documented resistance: {_range_text(disease.normalized_value)}."],
                traits=[disease],
                missing_evidence=["Routine maintenance instructions"],
            )
        )
    else:
        sections.append(
            _section(
                code="maintenance",
                title="Maintenance",
                status="missing",
                summary="No reviewed maintenance instructions are available yet.",
                missing_evidence=["Routine maintenance instructions"],
            )
        )

    sections.append(
        _simple_trait_section(
            cultivar,
            code="companions",
            title="Companion considerations",
            field_name="companion_considerations",
            missing_label="companion-planting evidence",
            instruction_prefix="Companion consideration:",
        )
    )

    harvest_guidance = _trait(cultivar, "harvest_guidance")
    harvest_traits = [
        trait
        for trait in [
            _trait(cultivar, "days_to_maturity"),
            _trait(cultivar, "harvest_pattern"),
            harvest_guidance,
        ]
        if trait
    ]
    if maturity and isinstance(maturity.normalized_value, dict):
        value = maturity.normalized_value
        basis = str(value.get("basis", "unspecified")).replace("_", " ")
        maturity_text = _range_text(value, unit=maturity.unit)
        instruction = (
            f"Expect the documented maturity range at {maturity_text}, measured from {basis}."
        )
        harvest_pattern = _trait(cultivar, "harvest_pattern")
        details = [instruction]
        if harvest_pattern:
            details.append(_harvest_pattern_text(harvest_pattern))
        if harvest_guidance:
            guidance = harvest_guidance.normalized_value
            details.extend(guidance if isinstance(guidance, list) else [str(guidance)])
        sections.append(
            _section(
                code="harvest",
                title="Harvest",
                status="documented",
                summary=instruction,
                instructions=details,
                traits=harvest_traits,
            )
        )
    elif harvest_guidance:
        guidance = harvest_guidance.normalized_value
        details = guidance if isinstance(guidance, list) else [str(guidance)]
        sections.append(
            _section(
                code="harvest",
                title="Harvest",
                status="documented",
                summary=details[0],
                instructions=details,
                traits=harvest_traits,
            )
        )
    else:
        sections.append(
            _section(
                code="harvest",
                title="Harvest",
                status="missing",
                summary="No reviewed maturity or harvest timing is available yet.",
                missing_evidence=["Days to maturity or harvest timing"],
            )
        )

    timeline.sort(key=lambda event: (event.start_date, event.code))
    return sections, timeline, assumptions


def _guide_action(
    section: GrowGuideSectionResponse,
    *,
    title: str,
    when: str,
    timeline: list[GrowGuideTimelineEventResponse] | None = None,
) -> GrowGuideActionResponse:
    action_timeline = timeline or []
    evidence = list(section.evidence)
    evidence_keys = {
        (
            item.field_name,
            item.source_document_id,
            item.source_locator,
            item.origin,
        )
        for item in evidence
    }
    for event in action_timeline:
        for item in event.evidence:
            key = (
                item.field_name,
                item.source_document_id,
                item.source_locator,
                item.origin,
            )
            if key not in evidence_keys:
                evidence.append(item)
                evidence_keys.add(key)
    return GrowGuideActionResponse(
        code=section.code,
        title=title,
        when=when,
        status=section.status,
        summary=section.summary,
        instructions=section.instructions,
        confidence=section.confidence,
        provenance=section.provenance,
        evidence=evidence,
        missing_evidence=section.missing_evidence,
        timeline=action_timeline,
    )


def _combined_action(
    sections: list[tuple[str, GrowGuideSectionResponse]],
    *,
    code: str,
    title: str,
    when: str,
    summary: str,
) -> GrowGuideActionResponse:
    statuses = {section.status for _, section in sections}
    if "conflict" in statuses:
        status = "conflict"
    elif statuses == {"missing"}:
        status = "missing"
    elif statuses & {"missing", "partial"}:
        status = "partial"
    else:
        status = "documented"

    confidence_values = [section.confidence for _, section in sections if section.confidence]
    confidence = None
    if confidence_values:
        rank = {"low": 0, "medium": 1, "high": 2}
        confidence = min(confidence_values, key=lambda item: rank.get(item, -1))

    provenances = {
        section.provenance for _, section in sections if section.provenance != "none"
    }
    provenance = "none"
    if "mixed" in provenances or len(provenances) > 1:
        provenance = "mixed"
    elif provenances:
        provenance = provenances.pop()

    evidence: list[SuitabilityEvidenceReference] = []
    evidence_keys: set[tuple[object, ...]] = set()
    for _, section in sections:
        for item in section.evidence:
            key = (
                item.field_name,
                item.source_document_id,
                item.source_locator,
                item.origin,
            )
            if key not in evidence_keys:
                evidence.append(item)
                evidence_keys.add(key)

    return GrowGuideActionResponse(
        code=code,
        title=title,
        when=when,
        status=status,
        summary=summary,
        instructions=[f"{label}: {section.summary}" for label, section in sections],
        confidence=confidence,
        provenance=provenance,
        evidence=evidence,
        missing_evidence=[
            f"{label}: {gap}"
            for label, section in sections
            for gap in section.missing_evidence
        ],
        timeline=[],
    )


def _build_phases(
    sections: list[GrowGuideSectionResponse],
    timeline: list[GrowGuideTimelineEventResponse],
) -> list[GrowGuidePhaseResponse]:
    section_by_code = {section.code: section for section in sections}
    event_by_code = {event.code: event for event in timeline}

    def action(
        code: str,
        title: str,
        when: str,
        event_code: str | None = None,
    ) -> GrowGuideActionResponse:
        event = event_by_code.get(event_code) if event_code else None
        return _guide_action(
            section_by_code[code],
            title=title,
            when=event.title if event else when,
            timeline=[event] if event else [],
        )

    preparation = _combined_action(
        [
            ("Soil", section_by_code["soil"]),
            ("Container", section_by_code["containers"]),
            ("Spacing", section_by_code["spacing"]),
            ("Support", section_by_code["trellising"]),
        ],
        code="prepare_space",
        title="Prepare the growing space",
        when="Before planting",
        summary="Prepare the soil and lay out the container, spacing, and support together.",
    )

    phases = [
        GrowGuidePhaseResponse(
            code="plan_and_plant",
            position=1,
            title="Plan and plant",
            summary=(
                "Choose the growing space, prepare it, and work through starting and planting "
                "in order."
            ),
            actions=[
                action("light", "Choose the growing location", "Before planting"),
                preparation,
                action(
                    "starting_method",
                    "Decide how to start the plants",
                    "Before outdoor planting",
                ),
                action(
                    "planting",
                    "Plant outdoors",
                    "At the supported planting stage",
                    "outdoor_planting_boundary",
                ),
            ],
        ),
        GrowGuidePhaseResponse(
            code="tend",
            position=2,
            title="Tend the plants",
            summary="Use the reviewed watering and maintenance guidance as the plants grow.",
            actions=[
                action("water", "Water with the crop's growth stages in mind", "During growth"),
                action("maintenance", "Maintain plant health", "Throughout the season"),
            ],
        ),
        GrowGuidePhaseResponse(
            code="harvest",
            position=3,
            title="Harvest",
            summary="Use the maturity basis and harvest guidance to decide when and how to pick.",
            actions=[
                action(
                    "harvest",
                    "Harvest at the right stage",
                    "At documented maturity",
                    "estimated_first_harvest",
                )
            ],
        ),
    ]

    fall_event = event_by_code.get("fall_frost_boundary")
    if fall_event:
        phases.append(
            GrowGuidePhaseResponse(
                code="finish_season",
                position=4,
                title="Finish the season",
                summary=(
                    "Use the local climate boundary for planning; cleanup and winterization "
                    "guidance still requires reviewed evidence."
                ),
                actions=[
                    GrowGuideActionResponse(
                        code="finish_season",
                        title="Watch the typical fall frost boundary",
                        when=fall_event.title,
                        status="partial",
                        summary=fall_event.summary,
                        instructions=[],
                        confidence=fall_event.confidence,
                        provenance="climate",
                        evidence=fall_event.evidence,
                        missing_evidence=[
                            "End-of-season cleanup or winterization guidance (follow-up #14)"
                        ],
                        timeline=[fall_event],
                    )
                ],
            )
        )

    return phases


def _fingerprint(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def get_grow_guide(
    session: Session,
    *,
    garden_profile_id: str,
    cultivar_slug: str,
) -> GrowGuideResponse:
    profile = session.scalar(
        select(GardenProfile)
        .where(GardenProfile.id == garden_profile_id)
        .options(
            selectinload(GardenProfile.location_dataset),
            selectinload(GardenProfile.location_evidence).selectinload(
                LocationEvidenceClaim.source_document
            ),
        )
    )
    if profile is None:
        raise GardenProfileNotFoundError(garden_profile_id)
    dataset = session.scalar(
        select(CultivarDatasetVersion).where(CultivarDatasetVersion.active.is_(True))
    )
    if dataset is None:
        raise SuitabilityUnavailableError("Load a cultivar catalog before generating grow guides.")
    catalog = list_cultivars(session)
    cultivar = next((item for item in catalog.cultivars if item.slug == cultivar_slug), None)
    if cultivar is None:
        raise CultivarNotFoundError(cultivar_slug)

    climate_claim = next(
        (
            claim
            for claim in profile.location_evidence
            if claim.field_name == "noaa_climate_normals"
        ),
        None,
    )
    sections, timeline, guide_assumptions = _build_sections(
        cultivar, climate_claim, profile.target_year
    )
    phases = _build_phases(sections, timeline)
    suitability = assess_cultivar(profile, cultivar, cultivar_dataset_id=dataset.id)
    missing_evidence = sorted(
        {item for section in sections for item in section.missing_evidence}, key=str.casefold
    )
    actions = [action for phase in phases for action in phase.actions]
    supported_count = sum(action.status in {"documented", "partial"} for action in actions)
    summary = (
        f"Follow {len(phases)} phases from planning through harvest"
        f"{' and the season boundary' if len(phases) == 4 else ''}. "
        f"{supported_count} of {len(actions)} actions include reviewed guidance; "
        "remaining gaps are called out rather than guessed."
    )
    fingerprint_payload = {
        "algorithm_version": GROW_GUIDE_ALGORITHM_VERSION,
        "garden_profile": {
            "id": profile.id,
            "target_year": profile.target_year,
            "growing_methods": profile.growing_methods,
            "support_available": profile.support_available,
        },
        "cultivar_dataset_id": dataset.id,
        "crop_dataset_id": dataset.crop_dataset_version_id,
        "cultivar": cultivar.model_dump(mode="json"),
        "climate_claim": (
            {
                "dataset_id": climate_claim.climate_dataset_version_id,
                "value": climate_claim.normalized_value,
                "source_document_id": climate_claim.source_document_id,
            }
            if climate_claim
            else None
        ),
    }
    return GrowGuideResponse(
        garden_profile_id=profile.id,
        garden_name=profile.name,
        target_year=profile.target_year,
        cultivar_slug=cultivar.slug,
        cultivar_name=cultivar.canonical_name,
        crop_slug=cultivar.crop_slug,
        crop_name=cultivar.crop_name,
        cultivar_dataset_id=dataset.id,
        crop_dataset_id=dataset.crop_dataset_version_id,
        algorithm_version=GROW_GUIDE_ALGORITHM_VERSION,
        input_fingerprint=_fingerprint(fingerprint_payload),
        summary=summary,
        phases=phases,
        sections=sections,
        timeline=timeline,
        conflicts=suitability.constraints,
        assumptions=[*suitability.assumptions, *guide_assumptions],
        missing_evidence=missing_evidence,
    )
