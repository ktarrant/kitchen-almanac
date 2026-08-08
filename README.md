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
uv run --project backend kitchen-almanac climate validate-hardiness
uv run --project backend kitchen-almanac climate load-hardiness
uv run --project backend kitchen-almanac climate validate-noaa
uv run --project backend kitchen-almanac climate load-noaa
uv run --project backend kitchen-almanac cultivars validate
uv run --project backend kitchen-almanac cultivars load
uv run --project backend uvicorn kitchen_almanac.main:app --reload
```

The API includes:

- `GET /health` for service health.
- `GET /api/crops` for the active crop catalog.
- `GET /api/cultivars` for approved cultivar identities, effective traits,
  source identifiers, and separately modeled commercial listings.
- `GET /api/catalog/search` for deterministic one-at-a-time crop and cultivar
  discovery within a garden profile. Exact, prefix, commercial listing, and
  fuzzy matches are labeled in the response.
- `POST /api/garden-profiles` to save location and growing context.
- `GET /api/garden-profiles/{id}` to retrieve that context.
- `POST /api/wishlists/builder` to create an empty, catalog-pinned wishlist.
- `POST /api/wishlists/{id}/entries` to explicitly add a documented crop,
  documented cultivar, custom cultivar beneath a known crop, or custom crop.
- `POST /api/wishlists` to preserve and resolve a multiline Quick Import list
  for a garden profile, including cultivar and crop-type intent.
- `GET /api/wishlists/{id}` to retrieve its current resolution state.
- `PATCH /api/wishlists/{id}/entries/{entry_id}` to confirm a crop or keep a
  cultivar or crop, or keep a custom entry.

Only unique exact crop or cultivar aliases resolve automatically. Crop-qualified
custom cultivars remain linked to their crop, while fuzzy, crop-type, or
otherwise ambiguous results are returned as ranked candidates and require
explicit confirmation.

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
