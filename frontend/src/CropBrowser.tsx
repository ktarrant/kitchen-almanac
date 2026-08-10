import { useMemo, useState } from "react";

export type BrowseCrop = {
  slug: string;
  canonical_name: string;
  planning_category: string;
  commodity_section_key: string;
  commodity_section_title: string;
  commodity_section_position: number;
  browse_category_key: string;
  browse_category_title: string;
  browse_category_position: number;
  documented_cultivar_count: number;
  searchable_cultivar_count: number;
};

type CropBrowserProps = {
  crops: BrowseCrop[];
  loading: boolean;
  error: string | null;
  searching: boolean;
  onSelectCrop: (cropName: string) => void;
};

function cultivarAvailability(crop: BrowseCrop): string {
  if (crop.documented_cultivar_count === 0) return "No documented cultivars";
  const listed =
    crop.searchable_cultivar_count === 0
      ? "none listed"
      : `${crop.searchable_cultivar_count} listed`;
  return `${crop.documented_cultivar_count} documented · ${listed}`;
}

export default function CropBrowser({
  crops,
  loading,
  error,
  searching,
  onSelectCrop
}: CropBrowserProps) {
  const [categoryKey, setCategoryKey] = useState("all");
  const categories = useMemo(() => {
    const grouped = new Map<
      string,
      { key: string; title: string; position: number; crops: BrowseCrop[] }
    >();
    for (const crop of crops) {
      const category = grouped.get(crop.browse_category_key) ?? {
        key: crop.browse_category_key,
        title: crop.browse_category_title,
        position: crop.browse_category_position,
        crops: []
      };
      category.crops.push(crop);
      grouped.set(category.key, category);
    }
    return [...grouped.values()]
      .sort((left, right) => left.position - right.position)
      .map((category) => ({
        ...category,
        crops: category.crops.sort((left, right) =>
          left.canonical_name.localeCompare(right.canonical_name)
        )
      }));
  }, [crops]);
  const selectedCategory = categories.find((category) => category.key === categoryKey);
  const visibleCrops = useMemo(
    () =>
      categoryKey === "all"
        ? [...crops].sort((left, right) =>
            left.canonical_name.localeCompare(right.canonical_name)
          )
        : (selectedCategory?.crops ?? []),
    [categoryKey, crops, selectedCategory]
  );

  return (
    <section className="crop-browser" aria-labelledby="crop-browser-heading">
      <div className="crop-browser-heading">
        <div>
          <p className="section-kicker">Browse the catalog</p>
          <h2 id="crop-browser-heading">Choose a crop to see its cultivars</h2>
        </div>
        {!loading && !error && <p>{crops.length} crops</p>}
      </div>
      {loading && <p className="crop-browser-status">Loading crops…</p>}
      {error && (
        <p className="crop-browser-status" role="alert">
          {error} You can still search by name above.
        </p>
      )}
      {!loading && !error && (
        <>
          <div
            className="crop-browser-filters"
            role="group"
            aria-label="Filter crops by category"
          >
            <button
              className="crop-browser-filter"
              type="button"
              aria-pressed={categoryKey === "all"}
              onClick={() => setCategoryKey("all")}
            >
              All crops <span>{crops.length}</span>
            </button>
            {categories.map((category) => (
              <button
                className="crop-browser-filter"
                type="button"
                key={category.key}
                aria-pressed={categoryKey === category.key}
                onClick={() => setCategoryKey(category.key)}
              >
                {category.title} <span>{category.crops.length}</span>
              </button>
            ))}
          </div>
          <div className="crop-browser-list-heading">
            <h3>{selectedCategory?.title ?? "All crops"}</h3>
            <p>Alphabetical · {visibleCrops.length} crops</p>
          </div>
          <div className="crop-browser-list">
            {visibleCrops.map((crop) => (
              <button
                className="crop-browser-button"
                type="button"
                key={crop.slug}
                disabled={searching}
                aria-label={`${crop.canonical_name}, ${cultivarAvailability(crop)}`}
                onClick={() => onSelectCrop(crop.canonical_name)}
              >
                <span className="crop-browser-button-name">{crop.canonical_name}</span>
                <span
                  className={`crop-browser-availability${
                    crop.documented_cultivar_count === 0 ? " empty" : ""
                  }`}
                >
                  {cultivarAvailability(crop)}
                </span>
              </button>
            ))}
          </div>
        </>
      )}
    </section>
  );
}
