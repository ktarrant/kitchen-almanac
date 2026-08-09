# Rutgers Mid-Atlantic source corpus

This directory retains selected sections from the **2026/2027 Mid-Atlantic
Commercial Vegetable Production Recommendations**, published by Rutgers NJAES
Cooperative Extension with cooperating land-grant universities and USDA.

Source landing page:
https://njaes.rutgers.edu/pubs/publication.php?pid=E001

The checksum-pinned corpus currently includes general production, soil and
nutrient management, irrigation management, beans, cucumbers, summer squash,
and tomatoes. The PDF binaries are excluded from version control. Restore them
and reproduce the inventory from the repository root with:

```console
uv run --project backend kitchen-almanac rutgers fetch
uv run --project backend kitchen-almanac rutgers inventory
uv run --project backend kitchen-almanac rutgers extract
uv run --project backend kitchen-almanac rutgers validate
```

Exact source URLs, retrieval metadata, and checksums are recorded in
`corpus-manifest.v1.json`. `coverage-report.v1.json` is a deterministic,
page-level map of potential evidence fields. It records where review should
start; it does not extract facts into the application database.

`structured-evidence.v1.json` is reproduced from deterministic regular-expression
matches against pinned PDF pages. It stores normalized candidates, concise
source summaries, locators, and source-span hashes without copying whole source
passages. `structured-review-decisions.v1.json` pins the complete staging digest
and records an approval, corroboration, hold, or rejection rationale for every
candidate. Only approved home-garden candidates are merged into the generated
cultivar catalog; held commercial or location-dependent candidates cannot pass
the publication gate.

The publication states that its recommendations are for commercial vegetable
growers rather than specifically for home gardeners. Kitchen Almanac retains
that scope and applies these boundaries:

- Cultivar identities, pH, spacing, planting, irrigation, and harvest material
  are candidates that still require review and home-garden adaptation.
- Per-acre nutrient and production rates are commercial context only.
- Insect and disease material may supply threat names, resistance information,
  and nonchemical practices after review.
- Pesticide, herbicide, fungicide, fumigant, and commercial chemical-control
  programs are quarantined from beginner guidance.

Existing reviewed cultivar records continue to use
`../staged-mid-atlantic.v1.json` and `../review-decisions.v1.json`. A cultivar's
appearance in a regional table is evidence of identity and regional inclusion;
it is not, by itself, a personalized home-garden recommendation.
