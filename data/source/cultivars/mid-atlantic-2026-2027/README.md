# Rutgers Mid-Atlantic source corpus

This directory retains selected sections from the **2026/2027 Mid-Atlantic
Commercial Vegetable Production Recommendations**, published by Rutgers NJAES
Cooperative Extension with cooperating land-grant universities and USDA.

Source landing page:
https://njaes.rutgers.edu/pubs/publication.php?pid=E001

The checksum-pinned corpus includes the complete 512-page manual, general
production, soil and nutrient management, irrigation management, beans, beets,
cucumbers, summer squash, and tomatoes. The PDF binaries are excluded from
version control. Restore them and reproduce the inventories from the repository
root with:

```console
uv run --project backend kitchen-almanac rutgers fetch
uv run --project backend kitchen-almanac rutgers inventory
uv run --project backend kitchen-almanac rutgers taxonomy
uv run --project backend kitchen-almanac rutgers extract
uv run --project backend kitchen-almanac rutgers validate
```

Exact source URLs, retrieval metadata, and checksums are recorded in
`corpus-manifest.v1.json`. `coverage-report.v1.json` is a deterministic,
page-level map of potential evidence fields. It records where review should
start; it does not extract facts into the application database.

`commodity-crosswalk.v1.json` is the reviewed mapping from all 31 commodity
sections in the full manual to 46 individual Rutgers crop concepts and the
current canonical crop catalog. `taxonomy-coverage-report.v1.json` verifies the
table-of-contents page ranges, inventories potential evidence across the full
commodity chapter, identifies exact, overly broad, and missing crop identities,
and measures each crop against the minimum-useful evidence fields. It is a
planning and review artifact, not an automatic publication source.

`structured-evidence.v1.json` is reproduced from deterministic regular-expression
matches against pinned PDF pages. It stores normalized candidates, concise
source summaries, locators, and source-span hashes without copying whole source
passages. `structured-review-decisions.v1.json` pins the complete staging digest
and records an approval, corroboration, hold, or rejection rationale for every
candidate. Only approved home-garden candidates are merged into the generated
cultivar catalog; held commercial or location-dependent candidates cannot pass
the publication gate.

The current review publishes qualitative water-management guidance and critical
watering stages for the four initial crops. Commercial field-capacity targets
and peak daily rates remain staged as explicit holds, and the app does not infer
a weekly watering quantity from them.

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
