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

The catalog builder reads `Six Seasons Reference.md` and writes
`data/seed/kitchen-almanac-catalog.v1.json`. The output is deterministic and records
all changes made to source labels.

## API

```shell
uv run --project backend kitchen-almanac db upgrade
uv run --project backend kitchen-almanac catalog load
uv run --project backend kitchen-almanac locations validate
uv run --project backend kitchen-almanac locations load
uv run --project backend uvicorn kitchen_almanac.main:app --reload
```

The API includes:

- `GET /health` for service health.
- `GET /api/crops` for the active crop catalog.
- `POST /api/garden-profiles` to save location and growing context.
- `GET /api/garden-profiles/{id}` to retrieve that context.
- `POST /api/wishlists` to preserve and resolve a multiline Quick Import list
  for a garden profile.
- `GET /api/wishlists/{id}` to retrieve its current resolution state.
- `PATCH /api/wishlists/{id}/entries/{entry_id}` to confirm a crop or keep a
  custom entry.

Only unique exact aliases resolve automatically. Fuzzy or ambiguous results are
returned as ranked candidates and require explicit confirmation.

## Location data

ZIP-area coordinates come from the [2025 U.S. Census Bureau ZCTA
Gazetteer](https://www.census.gov/geographies/reference-files/time-series/geo/gazetteer-files.2025.html).
The original archive is retained with its checksum and retrieval metadata, and
each resolved coordinate exposes its source row through the API. A ZIP Code
Tabulation Area is a Census geography rather than a USPS delivery ZIP; its
representative point is therefore an approximation, not an address or property
location. This product is not endorsed or certified by the Census Bureau.

## Frontend

The frontend requires Node.js 22 or newer:

```shell
cd frontend
npm install
npm run dev
```
