# Rutgers home-garden source corpus

This corpus begins with Rutgers NJAES Cooperative Extension fact sheet FS129,
*Planning a Vegetable Garden*. It is intentionally separate from the
commercial-grower Mid-Atlantic manual because audience and geographic scope are
part of the evidence model.

The committed manifest pins the official HTML response by URL and SHA-256. The
HTML snapshot is excluded from version control and can be restored with:

```console
uv run --project backend kitchen-almanac rutgers fetch
```

`rutgers extract` reproduces the source-span-pinned candidates in
`structured-evidence.v1.json`. `review-decisions.v1.json` approves home-scale
light, spacing, row-spacing, starting-method, and average row-yield facts,
replaces commercial baselines where FS129 is more appropriate, and holds New
Jersey planting months until a location adapter exists.

The source table distinguishes bush and pole snap beans. Kitchen Almanac stores
those rows as contextual profiles and resolves them using each cultivar's
reviewed growth habit rather than publishing a misleading combined range.

The FS129 tomato light and in-row spacing candidates remain held because the
existing University of Maryland tomato guide provides more specific minimum,
preferred, habit, and support context. This is a field-specific precedence
decision, not a blanket preference for one publisher.
