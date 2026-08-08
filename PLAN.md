# Kitchen Almanac Implementation Plan

## Product vision

Build a location-aware gardening application that turns a user's vegetable
wishlist into suitable varieties, evidence-backed grow guides, an optimized
garden layout and calendar, yield forecasts, and meal or preservation plans.

The primary workflow is:

`wishlist -> varieties -> grow guides -> garden plan -> yield forecast -> food plan`

The first release is a local, single-household web application. It will accept
a US ZIP code or coordinates rather than assuming a particular climate.

## Architecture

- Frontend: React, TypeScript, and Vite.
- Backend: Python, FastAPI, Pydantic, and SQLAlchemy.
- Persistence: SQLite for local development and PostgreSQL in deployed
  environments.
- Data tooling: a Typer CLI for source ingestion, validation, publishing, and
  maintenance.
- Optimization: OR-Tools CP-SAT with fixed seeds, stable candidate ordering,
  and deterministic tie-breaking.
- Verification: pytest for backend and data pipelines; Playwright for browser
  workflows.

The repository is organized as a small monorepo:

```text
backend/      API, domain model, ingestion CLI, migrations, and tests
frontend/     React application
data/seed/    reviewed, reproducible seed datasets
PLAN.md       implementation roadmap and decisions
```

## Engineering principles

1. Every agricultural fact retains its source, retrieval metadata, evidence,
   units, and confidence.
2. Remote inputs are snapshotted so a published dataset can be reproduced.
3. LLMs may extract or reconcile facts into a validated schema, but they may
   not publish unsupported facts or invent citations.
4. Generated garden plans are deterministic for identical user inputs,
   algorithm versions, and data versions.
5. Planting dates and yields are represented as ranges with uncertainty rather
   than as falsely precise predictions.
6. USDA hardiness zone is only one regional signal. Frost dates, growing-season
   length, temperature, growing degree days, and cultivar maturity drive annual
   vegetable suitability.
7. Preservation instructions must come from an approved, tested source. An LLM
   may not invent processing time, acidity, pressure, or altitude adjustments.

## Core domain model

- `LocationProfile`: ZIP, coordinates, elevation, hardiness zone, climate
  station, frost dates, and growing degree days.
- `Crop`: canonical name, aliases, botanical family, crop category, and annual
  or perennial lifecycle.
- `Variety`: cultivar, crop, maturity, temperature traits, disease resistance,
  growth habit, and seed source.
- `SourceDocument` and `EvidenceClaim`: immutable provenance and extraction
  history.
- `GrowProfile`: light, soil, water, spacing, container, trellis, sowing,
  temperature, and harvest requirements.
- `PlantingRule`: an event expressed relative to frost, soil temperature,
  growing degree days, or another event.
- `GardenSpace`: bed or container geometry, depth, sun, trellis capacity, and
  usable area.
- `CropPreference`: priority, desired amount, cultivar preference, and intended
  fresh or preservation use.
- `GardenPlan`, `PlantingCohort`, `SpaceAssignment`, and `GardenTask`.
- `YieldModel` and `HarvestForecast`.
- `Recipe`, `PreservationProcess`, `IngredientRequirement`, and
  `HarvestAllocation`.

Every derived record references the source-data version and algorithm version
that produced it.

## Delivery plan

### Step 1: Foundation and seed catalog

Status: **Completed on 2026-08-08**

- Scaffold the backend, frontend, database migrations, CLI, tests, and local
  development configuration.
- Import `Six Seasons Reference.md` into a versioned seed dataset.
- Preserve each source label and record every correction or normalization.
- Correct `Rutabage` to `Rutabaga` through an explicit correction record.
- Represent `Onion Family`, `Lettuces and Early Greens`, and similar entries as
  groups rather than pretending they are individual cultivars.
- Mark asparagus and artichokes as perennial special cases.
- Mark mushrooms as a specialty growing system outside the first vegetable
  planner.
- Create units, provenance, confidence, and data-versioning infrastructure.

Acceptance criteria:

- The source reference imports reproducibly into a validated catalog.
- Identical input produces byte-identical generated JSON.
- No source-label change can occur without a corresponding correction record.
- The generated catalog can be loaded idempotently into the development
  database.

### Step 2: Wishlist resolution (Goal A)

Status: **Completed on 2026-08-08**

- Add a multiline wishlist editor.
- Resolve canonical aliases before applying conservative fuzzy matching.
- Require confirmation for ambiguous matches.
- Preserve the user's original wording and allow unresolved custom entries.

Acceptance criteria:

- Common aliases resolve consistently.
- Ambiguous terms are never silently assigned.

### Step 3: Location and regional suitability (Goal B)

- Collect ZIP code or coordinates and a target growing year.
- Import USDA 2023 hardiness-zone data while retaining required attribution.
- Import or query NOAA climate normals for probable first and last freeze,
  growing-season length, temperatures, precipitation, and growing degree days.
- Build provider adapters for regional Cooperative Extension recommendations
  and cultivar sources whose terms permit ingestion.
- Rank cultivars using explicit maturity, temperature, photoperiod, disease,
  space, and evidence-quality rules.
- Explain both positive rankings and disqualifying constraints.

Acceptance criteria:

- Each recommendation explains why it fits the location and cites the facts it
  uses.

### Step 4: Evidence-backed grow guides (Goal C)

- Define a structured grow-guide schema covering light, soil, water, spacing,
  container size, trellising, starting method, planting, maintenance, companion
  considerations, and harvest.
- Store source snapshots and implement provider-specific parsers.
- Constrain any LLM extraction to schema-validated output with cited source
  spans, prompt version, and model version.
- Require review before extracted facts are published.
- Generate local timelines from relative planting rules.
- Render beginner-friendly instructions, conflicts, confidence, and citations.

Acceptance criteria:

- A guide can be regenerated from stored inputs.
- Every numeric recommendation is traceable to evidence.

### Step 5: Garden configuration and optimization (Goal D)

- Model beds, containers, soil depth, usable area, sun, trellises, paths, and
  inaccessible margins.
- Collect user priorities, desired amounts, cultivar preferences, succession
  preferences, and exclusions.
- Generate feasible crop, cultivar, location, and date candidates.
- Use CP-SAT constraints for spacing, container capacity, sunlight, trellising,
  seasonal occupancy, succession, and planting windows.
- Optimize preference satisfaction, useful yield, diversity, harvest spread,
  and space utilization with a documented objective.
- Explain infeasible requests.
- Merge crop events into one deduplicated task calendar.

Acceptance criteria:

- Identical inputs produce identical assignments.
- No assignment violates a declared constraint.

### Step 6: Yield forecasting (Goal E)

- Store low, base, and high yield ranges by crop, cultivar, and growing method.
- Model single, concentrated, repeated, and indeterminate harvest curves.
- Adjust forecasts for plant count, survival, spacing, shade, and succession.
- Display weekly and seasonal ranges.
- Capture actual germination, plant loss, and harvest weights for calibration.

Acceptance criteria:

- Every forecast is reproducible from cohorts and documented assumptions.

### Step 7: Meals and preservation (Goal F)

- Normalize recipe ingredients into crop identities and consistent units.
- Allocate forecast harvest to fresh eating, recipes, freezing, fermentation,
  pickling, and canning.
- Model servings, preferences, jar and freezer capacity, shelf life, and batch
  sizes.
- Use USDA FoodData Central when nutrition or food identity data is needed.
- Limit preservation workflows to approved sources such as the National Center
  for Home Food Preservation.
- Begin with user-entered or explicitly licensed recipes.

Acceptance criteria:

- Every preservation recommendation links to an approved tested process.
- Safety-affecting substitutions are never made silently.

### Step 8: Product hardening

- Add end-to-end browser tests and contrasting climate fixtures.
- Detect upstream source changes and stale datasets.
- Add graceful provider-failure behavior and data freshness indicators.
- Add authentication, backups, privacy controls for location data, monitoring,
  and deployment automation when the local workflow is stable.

## Initial release scope

The first complete vertical slice covers Goals A through D for approximately
ten to twelve annual crops: tomatoes, peppers, cucumbers, beans, lettuce,
carrots, radishes, kale, broccoli, peas, beets, and squash. It should initially
use one well-supported region while retaining a location-agnostic data model.
Yield forecasting follows once the planner is validated; food utilization is
the final major feature area.

## Known risks and mitigations

- **Heterogeneous sources:** use provider adapters, snapshot inputs, validate
  schemas, and require evidence for published facts.
- **Cultivar availability changes:** separate horticultural suitability from
  current commercial availability and timestamp the latter.
- **Licensing and copyright:** retain source terms and attribution; do not scrape
  or republish content without permission.
- **False precision:** expose ranges, confidence, and the assumptions behind
  dates and yields.
- **Optimizer complexity:** begin with bed blocks and individual containers,
  then add detailed two-dimensional layouts only after the constraint model is
  validated.
- **Food safety:** use allowlisted preservation sources and prohibit generated
  processing parameters.

## Decisions to confirm before broader implementation

- First fully supported geographic region.
- Local-only versus hosted multi-user deployment after the MVP.
- Pilot crop list and the first approved regional sources.
- LLM provider and review process for source extraction.
