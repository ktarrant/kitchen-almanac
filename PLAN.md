# Kitchen Almanac Implementation Plan

## Product vision

Build a location-aware gardening application that turns a user's vegetable
wishlist into suitable varieties, evidence-backed grow guides, an optimized
garden layout and calendar, yield forecasts, and meal or preservation plans.

The primary workflow is:

`garden context -> catalog search -> cultivar selection -> wishlist -> grow guides -> garden plan -> yield forecast -> food plan`

Users add crops one at a time from a searchable cultivar catalog. A secondary
Quick Import workflow accepts a multiline list and uses the crop resolver to
prepare entries for confirmation.

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
- Verification: pytest for backend and data pipelines, Vitest and Testing
  Library for focused frontend workflows, and Playwright for later end-to-end
  browser coverage.

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

- `GardenProfile`: location, target year, experience level, growing methods,
  and links to versioned climate facts.
- `LocationProfile`: ZIP, coordinates, elevation, hardiness zone, climate
  station, frost dates, and growing degree days derived for a garden profile.
- `Crop`: canonical name, aliases, botanical family, crop category, and annual
  or perennial lifecycle.
- `Cultivar`: canonical cultivated variety linked to a crop, with aliases,
  maturity, growth habit, disease resistance, and other distinguishing traits.
- `CultivarListing`: a source- or vendor-specific listing linked to a canonical
  cultivar when identity can be established.
- `WishlistItem`: a selected cultivar, a crop whose cultivar is undecided, or a
  custom cultivar/crop linked to its garden profile.
- `SuitabilityAssessment`: versioned cultivar-by-location constraints, score,
  explanations, and evidence quality.
- `CultivarResearchQuality`: versioned breadth score for reviewed,
  cultivar-specific sources and facts, kept separate from garden suitability.
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
- Retain this workflow as Quick Import after catalog search becomes the primary
  wishlist interface.

Acceptance criteria:

- Common aliases resolve consistently.
- Ambiguous terms are never silently assigned.

### Step 3: Garden context and location profile

Status: **Completed 2026-08-08**

Implemented garden-context collection, persistence, validation, wishlist
association, and versioned ZIP-area coordinate resolution. The application now
derives USDA hardiness from the pinned 2023 CONUS raster and selects the nearest
qualifying station from a pinned NOAA 1991–2020 normals archive for probable
freeze dates, growing-season length, temperature, precipitation, and GDD50.
Every derived value carries an immutable dataset ID, source checksum, locator,
extraction method, extractor version, distance or raster cell, and confidence.
Saved profiles are listed newest-first on the home page, can be selected without
creating another record, and the last explicit selection is remembered in the
local browser. Users can switch gardens or deliberately create another profile
in an accessible dialog connected to the creation action. A confirmed delete
flow atomically removes the selected garden and its owned planning data without
affecting shared catalog evidence; deleting the last garden returns the user to
the initial creation state.

- Collect a US ZIP code or coordinate pair before personalized catalog search.
- Collect the target growing year, experience level, and expected growing
  methods such as in-ground beds, raised beds, and containers.
- Persist garden profiles and associate every wishlist with one profile.
- Resolve ZIP codes to coordinates and retain both the original and normalized
  location input.
- Import USDA 2023 hardiness-zone data while retaining required attribution.
- Import or query NOAA climate normals for probable first and last freeze,
  growing-season length, temperatures, precipitation, and growing degree days.
- Store climate values as versioned evidence rather than mutable profile fields.

Acceptance criteria:

- A user cannot request personalized suitability without a garden profile.
- The same location source snapshot produces the same normalized climate
  profile.
- Every derived location or climate value is traceable to its source.

### Step 4: Cultivar identity and evidence catalog (Goal B)

Status: **In progress**

Current progress: the reviewed catalog now contains 46 canonical cultivars
across 12 crop identities, with 336 loaded field-level evidence claims. Six current 2026–2027 Mid-Atlantic
Extension commodity PDFs retain explicit commercial-production scope. A depth
cohort adds cultivar-specific AAS evidence for Mountain Merit
and a 2025 Virginia home-garden trial for Provider, Marketmore 76, Dunja, and
Sun Gold. Trial observations, regional awards, and catalog claims remain
separate facts with their own context and confidence.

Acquisition tooling separates staged source records, immutable review
decisions, identity reconciliation, enrichment of existing cultivars, and
deterministic publication. The publisher refuses stale review files, changed
source snapshots, duplicate identities, unsupported enrichment targets,
unreviewed candidates, and unsupported attributes. The versioned loader and
read API expose effective traits with explicit inheritance and keep commercial
seed listings separate. Quick Import extracts exact, fuzzy, crop-qualified,
and crop-type cultivar intent while preserving the original wording; unknown
cultivars remain linked to their recognized crop as custom intent.

Rutgers-to-retail intersections are published for beets and the bundled cole
crop section. Commercial listings are a separate, observation-dated source: 38 cultivars have an
identity-reviewed Reimer listing and are eligible for user-facing search,
including temporarily out-of-stock listings. Retired listings and cultivars
without a reviewed listing remain hidden from search. The next catalog cohorts
should repeat this intersection for additional Rutgers commodity tables using
the now-canonical Rutgers crop identities. Additional home-garden and trial
evidence should supplement regional commercial recommendations before
suitability scoring treats them as directly equivalent.

The complete 512-page Rutgers manual is now the reproducible corpus anchor. A
reviewed taxonomy crosswalk covers all 31 commodity sections and publishes all
47 extracted crop concepts as canonical identities. The former 9 broad catalog
groups and 12 missing identities have been resolved. A
deterministic minimum-useful coverage matrix measures identity, cultivar,
commercial listing, soil, water, spacing, container, planting, harvest, and
threat coverage before each new crop cohort is published. The cole-crop chapter
now validates this model with 16 reviewed cultivar identities across seven crop
types. Its embedded Chinese cabbage and pak choi table now maps to the separate
Chinese Cabbage identity rather than being attached to head cabbage.

- Add canonical cultivars beneath each crop and keep cultivar identity separate
  from commercial seed listings.
- Support cultivar aliases, crop types such as paste or cherry tomato, and
  source-specific identifiers.
- Extract optional cultivar or type intent from imported wishlist wording
  without discarding the original text.
- Ingest maturity basis, growth habit, size, spacing, support, container use,
  harvest pattern, culinary use, disease resistance, and climate traits.
- Represent crop-level requirements as defaults and cultivar facts as
  evidence-backed, field-specific overrides.
- Snapshot sources and require review before cultivar identities or traits are
  published.

Acceptance criteria:

- `Tomatoes`, `San Marzano tomatoes`, and a vendor's `San Marzano 2` listing
  remain three distinguishable concepts.
- No commercial listing is silently treated as a canonical cultivar.
- Every cultivar-specific requirement is sourced, while missing traits visibly
  fall back to the crop baseline.

### Step 5: Searchable catalog and wishlist builder (Goal A/B)

Status: **Complete**

Completed: the primary frontend workflow searches crops and
cultivars one at a time. A deterministic API ranks canonical names, aliases,
crop types, approved commercial listing names and identifiers, and spelling
variations. Results remain suggestions until the user explicitly adds a
documented cultivar, a crop with its cultivar undecided, a custom cultivar
linked to a known crop, or a custom crop. The wishlist builder pins both active
catalog versions, and Quick Import remains available as a secondary workflow.
Result cards expose concise effective traits, inherited crop baselines, and an
evidence publisher. The Step 6 model now supplies location-specific result
groups, suitability reasons, constraints, and evidence gaps rather than
implying recommendation from text matching alone.

When search is empty, the catalog defaults to all 47 crops alphabetically and
offers seven versioned gardener-oriented category filters. Each crop shows its
documented cultivar count separately from cultivars eligible for catalog search,
so crops with no documented cultivars remain useful crop-level choices without
appearing to promise cultivar results. The crop API pins these counts to the
active compatible crop and cultivar dataset versions.

The active wishlist is restored when a saved garden is selected, using the
most recently updated wishlist without merging separate lists. Selected crops,
cultivars, and custom entries remain visible in the top garden card, where they
can be removed. Entry removal atomically deletes dependent match candidates,
compacts positions, and preserves the empty wishlist for later additions.

Broad crop searches also expose a versioned research-quality score based on
independent reviewed sources and coverage of maturity, habit, space, harvest,
disease, regional, and home-garden trial facts. Within each suitability group,
well-researched cultivars are preferred over thinly documented ones. This
quality score describes the evidence record only; it never substitutes for
garden fit.

- Make one-at-a-time catalog search the primary wishlist workflow.
- Search crop names, cultivar names, crop types, aliases, and approved source
  listings using deterministic exact, prefix, and fuzzy ranking.
- Group results into crop-level choices, locally recommended cultivars, other
  documented cultivars, and custom-entry actions.
- Let users add a confirmed cultivar, a crop with cultivar undecided, a custom
  cultivar linked to a known crop, or a completely custom crop.
- Show concise maturity, habit, space, disease, use, suitability, and evidence
  information on result cards.
- Retain multiline resolution as a secondary Quick Import path that prepares
  entries for the same confirmation flow.

Acceptance criteria:

- Searching `tomato` can add generic tomatoes or a documented cultivar.
- Searching `San Marzano` preserves the cultivar selection rather than reducing
  it to generic tomatoes.
- Searching `San Marzano tomatoes` returns both documented San Marzano
  cultivars in deterministic order and never silently chooses one.
- Misspellings such as `san marzno` and `tomatos` produce explicit fuzzy
  suggestions rather than automatic assignments.
- Custom cultivars inherit only known crop-level facts and clearly display
  cultivar-specific unknowns.

### Step 6: Regional cultivar suitability (Goal B)

Status: **Complete**

Completed: the garden profile now captures protected culture, support
availability, per-plant width, container volume, intended culinary uses, and
recurring tomato disease concerns. The versioned deterministic assessment
evaluates frost-free maturity, temperature/GDD, photoperiod, disease pressure,
growing method, support, space, container fit, intended use, regional evidence,
and weighted evidence coverage. Supported comparisons create cited score factors;
season, support, space, container, and protected-culture conflicts become hard
constraints. Missing cultivar requirements remain explicit `unknown`
dimensions and never receive hidden points. Crop-type-to-use mappings are
declared assumptions rather than silent facts.

Generic crop searches rank and group cultivars by the assessment, while
cultivar-specific searches continue to rank by name relevance. The frontend
collects the garden constraints, shows leading reasons and constraints, and
provides an expandable audit of every dimension. A direct endpoint returns the
complete assessment with algorithm version, catalog/climate provenance,
evidence quality, and a deterministic fingerprint of all inputs. Temperature,
GDD, and photoperiod comparisons are wired for future comparable cultivar
claims; the current baseline truthfully reports those catalog gaps.

- Evaluate cultivar candidates against the garden's frost-free window,
  temperature and growing-degree-day needs, photoperiod, disease pressure,
  growing methods, support, space, intended use, and evidence quality.
- Treat incompatible maturity windows and physical requirements as explicit
  constraints rather than soft recommendations.
- Rank generic-crop search results using the deterministic suitability model.
- Explain positive rankings, disqualifying constraints, assumptions, and
  missing evidence.

Acceptance criteria:

- Each recommendation explains why that cultivar fits the selected garden and
  cites every fact used.
- Identical garden, catalog, climate, and algorithm versions produce identical
  rankings.

### Step 7: Cultivar-aware, evidence-backed grow guides (Goal C)

Status: **In progress**

Current progress: `grow-guide-v1.3.0` provides a structured API and chronological
frontend walkthrough for every selected documented cultivar. It deterministically
merges approved cultivar overrides with crop baselines and organizes the retained
atomic evidence sections into Plan and plant, Tend the plants, Harvest, and a
conditional Finish the season phase. Contextual **When** labels use an exact
date or range when supported and honest relative or recurring labels otherwise.
The existing outdoor planting, first-harvest, and fall-frost events now appear
beside the actions they inform; the standalone frontend timeline is gone, while
the underlying event API remains available for reproducibility and the future
task calendar. Evidence, confidence, inheritance, missing fields, and suitability
conflicts remain visible without dominating the walkthrough.

For frost-tender crops with reviewed transplant maturity and NOAA normals, the
guide calculates a target-year planting boundary and first-harvest range while
labeling climate normals as planning inputs rather than forecasts. A transplant
recommendation now explicitly reports that producing starts from seed still
needs evidence rather than pretending the starting-method fact is a complete
procedure. Identical catalog, garden, climate, and algorithm inputs produce the
same SHA-256 fingerprint. The reviewed-catalog pipeline supplies immutable source
snapshots, checksums, extraction metadata, and approval gates; no unreviewed or
LLM-made instruction enters a guide.

The first evidence-expansion pass establishes the 2026/2027 Rutgers Mid-Atlantic
manual as the primary corpus. A checksum-pinned manifest now covers its general
production, soil and nutrient, irrigation, beans, cucumbers, summer squash, and
tomatoes sections, plus the beets commodity table and complete 512-page manual.
A deterministic page-level inventory maps the corpus to grow-
guide evidence fields while quarantining chemical controls, retaining commercial
rates as context only, and prohibiting database publication without review.
The inventory is the review queue foundation, not itself gardening advice. The
first provider adapter now extracts 34 source-span-pinned candidates for crop pH,
lime thresholds, starting methods, spacing, harvest guidance, irrigation, and
broad regional planting windows. Review admits 26 home-scale facts into four
crop baselines, including qualitative water-management practices and critical
watering stages. It retains UMD as the primary corroborated tomato-spacing
source and holds regional calendar windows, commercial density, and commercial
daily water targets until suitable location and home-scale adapters exist.

Remaining work is primarily evidence expansion: reviewed soil-condition,
container, support, starting, and maintenance rules for the initial crop cohort,
plus additional relative planting rules and provider-specific ingestion
automation. Companion considerations are explicitly deferred to GitHub issue
#12 because they require a separate, stricter evidence review and do not block
the core grow-guide work. Producing recommended transplants from seed is tracked
in issue #13, and end-of-season cleanup and winterization evidence is tracked in
issue #14.

- Define a structured grow-guide schema covering light, soil, water, spacing,
  container size, trellising, starting method, planting, maintenance, companion
  considerations, and harvest.
- Store source snapshots and implement provider-specific parsers.
- Constrain any LLM extraction to schema-validated output with cited source
  spans, prompt version, and model version.
- Require review before extracted facts are published.
- Generate local timelines from relative planting rules.
- Render beginner-friendly instructions, conflicts, confidence, and citations.
- Generate effective instructions by combining the crop baseline with the
  selected cultivar's field-specific overrides.

Acceptance criteria:

- A guide can be regenerated from stored inputs.
- Every numeric recommendation is traceable to evidence.
- The guide identifies which advice is cultivar-specific and which is inherited
  from the crop baseline.

### Step 8: Garden configuration and optimization (Goal D)

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

### Step 9: Yield forecasting (Goal E)

- Store low, base, and high yield ranges by crop, cultivar, and growing method.
- Model single, concentrated, repeated, and indeterminate harvest curves.
- Adjust forecasts for plant count, survival, spacing, shade, and succession.
- Display weekly and seasonal ranges.
- Capture actual germination, plant loss, and harvest weights for calibration.

Acceptance criteria:

- Every forecast is reproducible from cohorts and documented assumptions.

### Step 10: Meals and preservation (Goal F)

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

### Step 11: Product hardening

- Add end-to-end browser tests and contrasting climate fixtures.
- Detect upstream source changes and stale datasets.
- Add graceful provider-failure behavior and data freshness indicators.
- Add authentication, backups, privacy controls for location data, monitoring,
  and deployment automation when the local workflow is stable.

## Initial release scope

The first complete vertical slice covers garden context, catalog search,
cultivar selection, suitability, grow guides, and planning for approximately
ten to twelve annual crops: tomatoes, peppers, cucumbers, beans, lettuce,
carrots, radishes, kale, broccoli, peas, beets, and squash. It should initially
use one well-supported region while retaining a location-agnostic data model.
Quick Import remains available but is not the primary onboarding path. Yield
forecasting follows once the planner is validated; food utilization is the
final major feature area.

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
