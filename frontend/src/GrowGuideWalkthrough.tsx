type GuideEvidence = {
  field_name: string;
  origin: "cultivar_catalog" | "crop_baseline" | "climate_normal" | "garden_profile";
  source_document_id: string | null;
  title: string | null;
  publisher: string | null;
  source_url: string | null;
  source_locator: string | null;
  inherited_from_crop: boolean;
};

type GuideTimelineEvent = {
  code: string;
  title: string;
  start_date: string;
  end_date: string | null;
  summary: string;
  confidence: string;
  evidence: GuideEvidence[];
};

export type GuidePhase = {
  code: "plan_and_plant" | "tend" | "harvest" | "finish_season";
  position: number;
  title: string;
  summary: string;
  actions: {
    code: string;
    title: string;
    when: string;
    status: "documented" | "partial" | "missing" | "conflict";
    summary: string;
    instructions: string[];
    confidence: string | null;
    provenance: "cultivar" | "crop_baseline" | "mixed" | "climate" | "none";
    evidence: GuideEvidence[];
    missing_evidence: string[];
    timeline: GuideTimelineEvent[];
  }[];
};

type GrowGuideWalkthroughProps = {
  phases: GuidePhase[];
};

function humanize(value: string) {
  return value.replaceAll("_", " ");
}

function formatGuideDate(value: string) {
  return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" }).format(
    new Date(`${value}T12:00:00`)
  );
}

function provenanceLabel(provenance: GuidePhase["actions"][number]["provenance"]) {
  if (provenance === "crop_baseline") return "Inherited crop guidance";
  if (provenance === "cultivar") return "Cultivar-specific guidance";
  if (provenance === "mixed") return "Crop and cultivar evidence";
  if (provenance === "climate") return "Local climate normal";
  return "Evidence needed";
}

export default function GrowGuideWalkthrough({ phases }: GrowGuideWalkthroughProps) {
  return (
    <div className="guide-walkthrough" aria-label="Chronological grow guide">
      {phases.map((phase) => (
        <section
          className={`guide-phase ${phase.code}`}
          aria-labelledby={`guide-phase-${phase.code}`}
          key={phase.code}
        >
          <header className="guide-phase-heading">
            <span aria-hidden="true">{phase.position}</span>
            <div>
              <p className="section-kicker">Step {phase.position}</p>
              <h3 id={`guide-phase-${phase.code}`}>{phase.title}</h3>
              <p>{phase.summary}</p>
            </div>
          </header>
          <ol className="guide-action-list">
            {phase.actions.map((action) => {
              const additionalInstructions = action.instructions.filter(
                (instruction) => instruction !== action.summary
              );
              return (
                <li className={`guide-action ${action.status}`} key={action.code}>
                  <div className="guide-action-when">
                    <span>When</span>
                    {action.timeline.length > 0 ? (
                      action.timeline.map((event) => (
                        <div key={event.code}>
                          <time dateTime={event.start_date}>
                            {formatGuideDate(event.start_date)}
                            {event.end_date && event.end_date !== event.start_date
                              ? ` – ${formatGuideDate(event.end_date)}`
                              : ""}
                          </time>
                          <small>{action.when}</small>
                          <p>{event.summary}</p>
                        </div>
                      ))
                    ) : (
                      <strong>{action.when}</strong>
                    )}
                  </div>
                  <div className="guide-action-body">
                    <div className="guide-action-heading">
                      <h4>{action.title}</h4>
                      <span>{humanize(action.status)}</span>
                    </div>
                    <p>{action.summary}</p>
                    {additionalInstructions.length > 0 && (
                      <ul>
                        {additionalInstructions.map((instruction) => (
                          <li key={instruction}>{instruction}</li>
                        ))}
                      </ul>
                    )}
                    <p className="guide-provenance">
                      {provenanceLabel(action.provenance)}
                      {action.confidence
                        ? ` · ${humanize(action.confidence)} confidence`
                        : ""}
                    </p>
                    {action.missing_evidence.length > 0 && (
                      <p className="guide-gap">
                        Still needed: {action.missing_evidence.join("; ")}
                      </p>
                    )}
                    {action.evidence.length > 0 && (
                      <details className="guide-sources">
                        <summary>Sources and evidence ({action.evidence.length})</summary>
                        <ul>
                          {action.evidence.map((evidence, index) => (
                            <li
                              key={`${action.code}-${evidence.field_name}-${evidence.source_document_id}-${index}`}
                            >
                              {evidence.source_url ? (
                                <a href={evidence.source_url} target="_blank" rel="noreferrer">
                                  {evidence.publisher ?? evidence.title ?? humanize(evidence.origin)}
                                </a>
                              ) : (
                                <strong>
                                  {evidence.publisher ?? evidence.title ?? humanize(evidence.origin)}
                                </strong>
                              )}
                              {evidence.source_locator && <span>{evidence.source_locator}</span>}
                              {evidence.inherited_from_crop && (
                                <span>Inherited from crop baseline</span>
                              )}
                            </li>
                          ))}
                        </ul>
                      </details>
                    )}
                  </div>
                </li>
              );
            })}
          </ol>
        </section>
      ))}
    </div>
  );
}
