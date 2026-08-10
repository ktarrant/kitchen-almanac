import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import GrowGuideWalkthrough, { type GuidePhase } from "./GrowGuideWalkthrough";

const evidence = {
  field_name: "frost_tender",
  origin: "crop_baseline" as const,
  source_document_id: "source-1",
  title: "Reviewed crop guidance",
  publisher: "University Extension",
  source_url: "https://example.com/guidance",
  source_locator: "page 1",
  inherited_from_crop: true
};

function action(
  code: string,
  title: string,
  when: string,
  timeline: GuidePhase["actions"][number]["timeline"] = []
): GuidePhase["actions"][number] {
  return {
    code,
    title,
    when,
    status: "documented",
    summary: `Reviewed guidance for ${title.toLowerCase()}.`,
    instructions: [],
    confidence: "high",
    provenance: "crop_baseline",
    evidence: [evidence],
    missing_evidence: [],
    timeline
  };
}

const plantingEvent = {
  code: "outdoor_planting_boundary",
  title: "Typical outdoor planting boundary",
  start_date: "2026-03-24",
  end_date: null,
  summary: "This is a climate normal, not a weather forecast.",
  confidence: "high",
  evidence: [evidence]
};

const phases: GuidePhase[] = [
  {
    code: "plan_and_plant",
    position: 1,
    title: "Plan and plant",
    summary: "Prepare the growing space and plant in order.",
    actions: [
      action("light", "Choose the growing location", "Before planting"),
      action("planting", "Plant outdoors", plantingEvent.title, [plantingEvent])
    ]
  },
  {
    code: "tend",
    position: 2,
    title: "Tend the plants",
    summary: "Care for the crop as it grows.",
    actions: [action("water", "Water consistently", "During growth")]
  },
  {
    code: "harvest",
    position: 3,
    title: "Harvest",
    summary: "Pick at the documented stage.",
    actions: [action("harvest", "Harvest at the right stage", "At maturity")]
  },
  {
    code: "finish_season",
    position: 4,
    title: "Finish the season",
    summary: "Use the fall boundary for planning.",
    actions: [action("finish_season", "Watch the fall frost boundary", "Around first frost")]
  }
];

afterEach(cleanup);

describe("GrowGuideWalkthrough", () => {
  it("renders actions chronologically with dates beside the action they inform", () => {
    const { container } = render(<GrowGuideWalkthrough phases={phases} />);

    expect(
      [...container.querySelectorAll(".guide-phase-heading h3")].map(
        (heading) => heading.textContent
      )
    ).toEqual(["Plan and plant", "Tend the plants", "Harvest", "Finish the season"]);
    expect(screen.getByText("Before planting")).toBeTruthy();
    expect(screen.getByText("Mar 24")).toBeTruthy();
    expect(screen.getByText("Typical outdoor planting boundary")).toBeTruthy();
    expect(screen.getByText("This is a climate normal, not a weather forecast.")).toBeTruthy();
    expect(screen.queryByText("Planning dates")).toBeNull();
    expect(screen.getAllByText("Sources and evidence (1)").length).toBeGreaterThan(0);
  });

  it("omits the finish phase when the API has no useful end-of-season action", () => {
    render(<GrowGuideWalkthrough phases={phases.slice(0, 3)} />);

    expect(screen.queryByRole("heading", { name: "Finish the season" })).toBeNull();
  });
});
