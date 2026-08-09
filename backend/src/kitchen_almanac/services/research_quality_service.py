from __future__ import annotations

from kitchen_almanac.schemas import CultivarResearchQualityResponse, CultivarResponse

RESEARCH_QUALITY_VERSION = "research-quality-v1.0.0"


def assess_research_quality(cultivar: CultivarResponse) -> CultivarResearchQualityResponse:
    """Score breadth of reviewed cultivar-specific evidence, not garden suitability."""

    direct_traits = [trait for trait in cultivar.traits if not trait.inherited_from_crop]
    fields = {trait.field_name for trait in direct_traits}
    sources = {
        identifier.source.source_document_id for identifier in cultivar.source_identifiers
    } | {trait.source.source_document_id for trait in direct_traits}
    sources.discard(None)

    components: list[tuple[bool, int, str]] = [
        (True, 5, "The cultivar identity has been reviewed."),
        (
            len(sources) >= 1,
            10,
            "At least one reviewed source documents this cultivar.",
        ),
        (
            len(sources) >= 2,
            10,
            "Two or more independent reviewed sources document this cultivar.",
        ),
        (
            bool(fields & {"days_to_maturity", "trial_days_to_harvest"}),
            15,
            "Cultivar-specific maturity evidence is available.",
        ),
        (
            bool(fields & {"growth_habit", "flowering_habit"}),
            10,
            "Growth or flowering habit is documented.",
        ),
        (
            bool(fields & {"plant_height", "plant_spacing", "plant_spread"}),
            10,
            "Plant size or spacing is documented.",
        ),
        (
            bool(
                fields
                & {
                    "fruit_dimensions",
                    "fruit_length",
                    "fruit_weight",
                    "harvest_pattern",
                    "uses",
                }
            ),
            10,
            "Harvest characteristics or uses are documented.",
        ),
        (
            bool(
                fields
                & {
                    "disease_resistance",
                    "source_reported_disease_resistance",
                    "trial_disease_resistance",
                }
            ),
            15,
            "Disease-resistance evidence is documented.",
        ),
        (
            bool(fields & {"regional_award", "regional_recommendation", "regional_trial"}),
            10,
            "Regional recommendation, award, or trial evidence is available.",
        ),
        (
            bool(fields & {"trial_overall_rating", "trial_recommendation_rate"}),
            5,
            "Home-garden trial ratings are available.",
        ),
    ]
    score = sum(points for present, points, _ in components if present)
    strengths = [explanation for present, _, explanation in components if present][1:]

    if score >= 80:
        tier = "well_researched"
    elif score >= 55:
        tier = "documented"
    else:
        tier = "limited"

    missing: list[str] = []
    if len(sources) < 2:
        missing.append("a second independent cultivar source")
    if not fields & {"days_to_maturity", "trial_days_to_harvest"}:
        missing.append("cultivar-specific maturity")
    if not fields & {"plant_height", "plant_spacing", "plant_spread"}:
        missing.append("plant size or spacing")
    if not fields & {
        "disease_resistance",
        "source_reported_disease_resistance",
        "trial_disease_resistance",
    }:
        missing.append("disease-resistance evidence")
    if not fields & {"regional_award", "regional_recommendation", "regional_trial"}:
        missing.append("regional evidence")

    return CultivarResearchQualityResponse(
        algorithm_version=RESEARCH_QUALITY_VERSION,
        score=score,
        tier=tier,
        source_count=len(sources),
        cultivar_specific_trait_count=len(direct_traits),
        strengths=strengths,
        missing_evidence=missing,
    )
