# Kitchen Almanac

Kitchen Almanac is a location-aware garden planning tool. See [PLAN.md](PLAN.md) for
the architecture and delivery roadmap.

## Repository layout

- `backend/`: FastAPI service, catalog tooling, persistence, and tests.
- `frontend/`: React and TypeScript application.
- `data/seed/`: reproducibly generated, reviewed seed datasets.
- `data/source/`: immutable snapshots of public source data.
- `Six Seasons Reference.md`: the original seasonal crop reference.

## Seed catalog quick start

With Python 3.12 and `uv` installed:

```shell
uv sync --project backend --extra dev
uv run --project backend kitchen-almanac catalog build
uv run --project backend kitchen-almanac catalog validate
uv run --project backend pytest
```

Unless `KITCHEN_ALMANAC_DATABASE_URL` is set, every command uses
`kitchen-almanac.db` in the repository root. This is independent of the current
working directory, so backend commands and the API share one local database.

The catalog builder reads `Six Seasons Reference.md` and writes
`data/seed/kitchen-almanac-catalog.v1.json`. The output is deterministic and records
all changes made to source labels.

## API

```shell
uv run --project backend kitchen-almanac db upgrade
uv run --project backend kitchen-almanac catalog load
uv run --project backend kitchen-almanac locations validate
uv run --project backend kitchen-almanac locations load
uv run --project backend kitchen-almanac climate validate-hardiness
uv run --project backend kitchen-almanac climate load-hardiness
uv run --project backend kitchen-almanac climate validate-noaa
uv run --project backend kitchen-almanac climate load-noaa
uv run --project backend kitchen-almanac cultivars fetch
uv run --project backend kitchen-almanac cultivars reconcile
uv run --project backend kitchen-almanac cultivars publish
uv run --project backend kitchen-almanac cultivars validate
uv run --project backend kitchen-almanac cultivars load
uv run --project backend kitchen-almanac rutgers fetch
uv run --project backend kitchen-almanac rutgers inventory
uv run --project backend kitchen-almanac rutgers extract
uv run --project backend kitchen-almanac rutgers validate
uv run --project backend uvicorn kitchen_almanac.main:app --reload
```

## Cultivar data workflow

Cultivar data is not maintained by editing database rows. The reproducible
publication workflow uses:

- `data/source/cultivars/reviewed-cultivars.v1.json` as the approved base.
- `data/source/cultivars/staged-mid-atlantic.v1.json` for normalized records
  extracted from pinned source documents.
- `data/source/cultivars/review-decisions.v1.json` for explicit create, link,
  enrich, or reject decisions tied to the exact staging checksum.
- `data/seed/cultivar-catalog.v1.json` as the deterministic published artifact
  loaded by the application.

`cultivars reconcile` reports exact and possible identity collisions.
`cultivars fetch` downloads source documents for local review and verifies their
approved checksums; copyrighted source binaries are intentionally not
redistributed in the repository. `cultivars publish` verifies the local source
snapshots and review coverage before building the artifact. `cultivars load`
then activates that immutable catalog version idempotently. The initial
expanded cohort contains 21 cultivars across tomatoes, cucumbers, string beans,
and summer squash. Its Mid-Atlantic source tables are commercial-production
recommendations; that scope is retained in the evidence rather than silently
presented as home-garden trial data. A research-depth cohort supplements five
cultivars with AAS cultivar data or observed 2025 Virginia home-garden trial
results. The app keeps those evidence contexts distinct.

Rutgers is the primary corpus for the next grow-guide evidence pass. Its
manifest pins the general production, soil and nutrient, irrigation, and four
initial commodity sections by URL and SHA-256 digest. `rutgers fetch` restores
the locally retained PDFs, `rutgers inventory` builds a deterministic page-level
coverage report, and `rutgers extract` reproduces structured candidates from
pinned source spans. Review decisions pin the exact candidate digest before
approved crop baselines enter `cultivars publish`; `rutgers validate` detects
changed PDFs, stale extraction, or stale review decisions. Chemical controls
remain quarantined, commercial rates remain context-only, and insect and disease
sections contribute only threat, resistance, and nonchemical-practice candidates
after review. The first reviewed irrigation pass publishes qualitative water
management and critical-growth-stage guidance for beans, cucumbers, summer
squash, and tomatoes; it deliberately does not turn commercial daily rates into
universal home-garden schedules.

The API includes:

- `GET /health` for service health.
- `GET /api/crops` for the active crop catalog.
- `GET /api/cultivars` for approved cultivar identities, effective traits,
  source identifiers, and separately modeled commercial listings.
- `GET /api/catalog/search` for deterministic one-at-a-time crop and cultivar
  discovery within a garden profile. Exact, prefix, commercial listing, and
  fuzzy matches are labeled in the response; generic crop results include a
  versioned, evidence-backed suitability assessment and a separate research-
  quality assessment. Results are grouped by garden fit and then prefer the
  better-documented cultivars within each group.
- `GET /api/suitability` for the complete cited assessment of one cultivar
  against one garden profile, including its algorithm version, input
  fingerprint, constraints, assumptions, and missing evidence.
- `GET /api/grow-guides` to combine reviewed crop baselines, cultivar
  overrides, and local climate normals into a cited, reproducible guide and
  planting timeline.
- `POST /api/garden-profiles` to save location and growing context.
- `GET /api/garden-profiles` to list saved garden contexts newest-first.
- `GET /api/garden-profiles/{id}` to retrieve that context.
- `DELETE /api/garden-profiles/{id}` to atomically remove a garden and its
  location evidence, wishlists, entries, and match candidates while preserving
  shared catalog and source data.
- `GET /api/garden-profiles/{id}/wishlists/active` to restore its most recently
  updated wishlist without creating or merging records.
- `POST /api/wishlists/builder` to create an empty, catalog-pinned wishlist.
- `POST /api/wishlists/{id}/entries` to explicitly add a documented crop,
  documented cultivar, custom cultivar beneath a known crop, or custom crop.
- `POST /api/wishlists` to preserve and resolve a multiline Quick Import list
  for a garden profile, including cultivar and crop-type intent.
- `DELETE /api/wishlists/{id}/entries/{entry_id}` to remove one selection and
  deterministically compact the remaining positions.
- `GET /api/wishlists/{id}` to retrieve its current resolution state.
- `PATCH /api/wishlists/{id}/entries/{entry_id}` to confirm a crop or keep a
  cultivar or crop, or keep a custom entry.

Only unique exact crop or cultivar aliases resolve automatically. Crop-qualified
custom cultivars remain linked to their crop, while fuzzy, crop-type, or
otherwise ambiguous results are returned as ranked candidates and require
explicit confirmation.

## Suitability model

Garden profiles can record support availability, maximum per-plant width,
container volume, intended culinary uses, recurring disease concerns, and
protected-culture access. The current disease choices are explicitly scoped to
tomatoes, the crop for which the catalog has comparable resistance evidence.
The `suitability-v1.1.0` algorithm audits maturity,
temperature/GDD, photoperiod, disease pressure, growing method, support, space,
container fit, intended use, regional evidence, and evidence coverage. Every
score-changing factor includes the catalog, climate, or garden-profile facts
that produced it. Unsupported dimensions are returned as `unknown` and do not
receive points; incompatible documented physical requirements are returned as
constraints. Identical versioned inputs produce the same SHA-256 assessment
fingerprint and ranking.

## Grow guides

Documented cultivars on a garden wishlist expose a grow guide in the saved
garden card. The `grow-guide-v1.2.0` generator renders light, soil, water,
spacing, containers, support, starting, planting, maintenance, companions, and
harvest as separate evidence states. Cultivar claims override crop baselines
field by field; each instruction identifies its origin, confidence, source, and
source locator. Unsupported guidance remains visible as missing evidence rather
than being filled with generic advice. Water guidance includes reviewed
management practices and critical growth stages while continuing to show
numeric quantity as missing unless a suitable reviewed source supports it.

When reviewed frost sensitivity, transplant-based maturity, and NOAA freeze
normals are all available, the guide generates a target-year outdoor planting
boundary and first-harvest range. These dates are planning calculations from
50-percent-probability climate normals, not weather forecasts. The response
retains the guide, crop catalog, cultivar catalog, climate evidence, algorithm
version, and a deterministic SHA-256 input fingerprint needed to reproduce it.

## Location data

ZIP-area coordinates come from the [2025 U.S. Census Bureau ZCTA
Gazetteer](https://www.census.gov/geographies/reference-files/time-series/geo/gazetteer-files.2025.html).
The original archive is retained with its checksum and retrieval metadata, and
each resolved coordinate exposes its source row through the API. A ZIP Code
Tabulation Area is a Census geography rather than a USPS delivery ZIP; its
representative point is therefore an approximation, not an address or property
location. This product is not endorsed or certified by the Census Bureau.

Hardiness evidence comes from the [2023 USDA Plant Hardiness Zone Map mean
annual extreme-low-temperature
rasters](https://catalog.data.gov/dataset/2023-usda-plant-hardiness-zone-map-mean-annual-extreme-low-temperature-rasters),
created by USDA ARS and Oregon State University's PRISM Climate Group and
licensed under CC BY 4.0. The application retains the original CONUS raster and
records the exact raster cell and extraction version behind each derived zone.

Freeze dates, growing-season length, growing-degree days, temperature, and
precipitation come from NOAA NCEI's [U.S. Climate Normals
1991–2020](https://www.ncei.noaa.gov/access/metadata/landing-page/bin/iso?id=gov.noaa.ncdc%3AC01619)
(version 1.0.1; DOI 10.25921/4ek7-fk11). The pinned national station archive is
processed locally. Garden profiles use the nearest qualifying station within
200 km, record its distance and completeness class, and label 32°F freeze dates
as 50-percent-probability values rather than guarantees.

## Frontend

The frontend requires Node.js 22 or newer:

```shell
cd frontend
npm install
npm run dev
```
