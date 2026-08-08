# Kitchen Almanac

Kitchen Almanac is a location-aware garden planning tool. See [PLAN.md](PLAN.md) for
the architecture and delivery roadmap.

## Repository layout

- `backend/`: FastAPI service, catalog tooling, persistence, and tests.
- `frontend/`: React and TypeScript application.
- `data/seed/`: reproducibly generated, reviewed seed datasets.
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
uv run --project backend uvicorn kitchen_almanac.main:app --reload
```

The initial endpoints are `GET /health` and `GET /api/crops`.

## Frontend

The frontend requires Node.js 22 or newer:

```shell
cd frontend
npm install
npm run dev
```
