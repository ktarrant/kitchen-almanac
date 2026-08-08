import { FormEvent, useMemo, useState } from "react";

type GrowingMethod = "in_ground" | "raised_bed" | "containers";

type GardenProfile = {
  id: string;
  name: string;
  location_input: string;
  postal_code: string | null;
  latitude: number | null;
  longitude: number | null;
  target_year: number;
  experience_level: "beginner" | "intermediate" | "advanced";
  growing_methods: GrowingMethod[];
  location_status: string;
  coordinate_method: string | null;
  location_source: {
    title: string;
    publisher: string | null;
  } | null;
  hardiness: {
    zone: string;
    mean_annual_extreme_minimum_f: number;
    confidence: string;
    source: {
      title: string;
      publisher: string | null;
      license: string | null;
    };
  } | null;
  climate_normals: {
    station_id: string;
    station_name: string;
    station_distance_km: number;
    growing_degree_days_base_50_f: number;
    last_spring_frost_50: string;
    first_fall_frost_50: string;
    growing_season_days_50: number;
    frost_probability: number;
    confidence: string;
    source: {
      title: string;
      publisher: string | null;
    };
  } | null;
};

type CropMatch = {
  slug: string;
  canonical_name: string;
  planning_category: string;
};

type Candidate = CropMatch & {
  score: number;
  matched_alias: string;
};

type CultivarMatch = {
  id: string;
  slug: string;
  canonical_name: string;
  crop_slug: string;
  crop_name: string;
  crop_type: string | null;
};

type CultivarCandidate = CultivarMatch & {
  score: number;
  matched_alias: string;
};

type CultivarTrait = {
  field_name: string;
  normalized_value: Record<string, unknown> | unknown[] | string | number | boolean;
  unit: string | null;
  inherited_from_crop: boolean;
  source: {
    title: string;
    publisher: string | null;
    scope: string | null;
  };
};

type CatalogCultivar = CultivarMatch & {
  description: string | null;
  aliases: string[];
  traits: CultivarTrait[];
  commercial_listings: {
    id: string;
    vendor: string;
    listing_name: string;
    source_identifier: string;
  }[];
};

type SuitabilityAssessment = {
  algorithm_version: string;
  input_fingerprint: string;
  status: "suitable" | "conditional" | "not_recommended" | "insufficient_evidence";
  score: number | null;
  evidence_quality: number;
  result_group:
    | "best_documented_fit"
    | "other_documented"
    | "conditional"
    | "constrained"
    | "insufficient_evidence";
  summary: string;
  factors: {
    code: string;
    effect: "positive" | "caution" | "constraint";
    points: number;
    explanation: string;
  }[];
  constraints: string[];
  assumptions: string[];
  missing_evidence: string[];
};

type CatalogSearchResults = {
  query: string;
  normalized_query: string;
  crop_choices: {
    crop: CropMatch;
    score: number;
    matched_alias: string;
    match_method: string;
  }[];
  cultivars: {
    cultivar: CatalogCultivar;
    score: number;
    matched_alias: string;
    match_method: string;
    suitability: SuitabilityAssessment;
  }[];
  can_add_custom: boolean;
};

type WishlistEntry = {
  id: string;
  position: number;
  original_text: string;
  normalized_text: string;
  status: "resolved" | "needs_confirmation" | "unresolved" | "custom";
  resolution_method: string | null;
  intent_kind: "crop" | "cultivar" | "crop_type";
  cultivar_intent_text: string | null;
  crop_type_intent: string | null;
  resolved_crop: CropMatch | null;
  resolved_cultivar: CultivarMatch | null;
  candidates: Candidate[];
  cultivar_candidates: CultivarCandidate[];
};

type Wishlist = {
  id: string;
  dataset_id: string;
  cultivar_dataset_id: string | null;
  garden_profile_id: string | null;
  name: string;
  entries: WishlistEntry[];
};

const initialWishlist = "San Marzano tomatoes\npaste tomato\nCarrots\nZucchini";
const currentYear = new Date().getFullYear();
const methodOptions: { value: GrowingMethod; label: string; detail: string }[] = [
  { value: "in_ground", label: "In ground", detail: "Beds planted directly in your soil" },
  { value: "raised_bed", label: "Raised beds", detail: "Contained beds with added soil" },
  { value: "containers", label: "Containers", detail: "Pots, grow bags, and planters" }
];

async function responseMessage(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: string };
    return body.detail ?? "Something went wrong. Please try again.";
  } catch {
    return "Something went wrong. Please try again.";
  }
}

function humanize(value: string) {
  return value.replaceAll("_", " ");
}

function traitSummary(trait: CultivarTrait): string {
  const value = trait.normalized_value;
  if (Array.isArray(value)) return value.join(", ");
  if (typeof value !== "object") return `${humanize(String(value))}${trait.unit ? ` ${trait.unit}` : ""}`;

  const minimum = value.minimum;
  const maximum = value.maximum;
  if (typeof minimum === "number" && typeof maximum === "number") {
    return `${minimum}–${maximum}${trait.unit ? ` ${trait.unit}` : ""}`;
  }
  return Object.entries(value)
    .filter(([, item]) => typeof item === "string" || typeof item === "number")
    .map(([key, item]) => `${humanize(key)} ${item}`)
    .join(" · ");
}

function featuredTraits(cultivar: CatalogCultivar) {
  const preferred = ["days_to_maturity", "growth_habit", "plant_spacing", "fruit_weight"];
  return preferred
    .map((name) => cultivar.traits.find((trait) => trait.field_name === name))
    .filter((trait): trait is CultivarTrait => trait !== undefined)
    .slice(0, 3);
}

const suitabilityGroups = [
  {
    key: "best_documented_fit",
    title: "Best documented fits",
    description: "Strongest fit from the climate, setup, and regional evidence currently available."
  },
  {
    key: "other_documented",
    title: "Other suitable cultivars",
    description: "No hard conflict found, but the supporting evidence is less locally specific."
  },
  {
    key: "conditional",
    title: "Could fit with more information",
    description: "A key planning fact is still missing or needs confirmation."
  },
  {
    key: "constrained",
    title: "Documented constraints",
    description: "These cultivars conflict with the current season or growing setup."
  },
  {
    key: "insufficient_evidence",
    title: "Not enough evidence to rank",
    description: "Kitchen Almanac will not guess without the climate or cultivar facts it needs."
  }
] as const;

export default function App() {
  const [profile, setProfile] = useState<GardenProfile | null>(null);
  const [postalCode, setPostalCode] = useState("");
  const [targetYear, setTargetYear] = useState(currentYear);
  const [experienceLevel, setExperienceLevel] = useState("beginner");
  const [growingMethods, setGrowingMethods] = useState<GrowingMethod[]>(["raised_bed"]);
  const [text, setText] = useState(initialWishlist);
  const [wishlist, setWishlist] = useState<Wishlist | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<CatalogSearchResults | null>(null);
  const [savingProfile, setSavingProfile] = useState(false);
  const [searching, setSearching] = useState(false);
  const [addingSelection, setAddingSelection] = useState<string | null>(null);
  const [matchingWishlist, setMatchingWishlist] = useState(false);
  const [updatingEntry, setUpdatingEntry] = useState<string | null>(null);
  const [addedNotice, setAddedNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const reviewCount = useMemo(
    () =>
      wishlist?.entries.filter(
        (entry) => entry.status === "needs_confirmation" || entry.status === "unresolved"
      ).length ?? 0,
    [wishlist]
  );
  const groupedCultivars = suitabilityGroups
    .map((group) => ({
      ...group,
      results:
        searchResults?.cultivars.filter(
          (result) => result.suitability.result_group === group.key
        ) ?? []
    }))
    .filter((group) => group.results.length > 0);

  function toggleGrowingMethod(method: GrowingMethod) {
    setGrowingMethods((selected) =>
      selected.includes(method)
        ? selected.filter((item) => item !== method)
        : [...selected, method]
    );
  }

  async function submitGardenProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSavingProfile(true);
    setError(null);
    try {
      const response = await fetch("/api/garden-profiles", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          postal_code: postalCode,
          target_year: targetYear,
          experience_level: experienceLevel,
          growing_methods: growingMethods
        })
      });
      if (!response.ok) {
        throw new Error(await responseMessage(response));
      }
      setProfile((await response.json()) as GardenProfile);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not save your garden.");
    } finally {
      setSavingProfile(false);
    }
  }

  async function submitWishlist(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!profile) return;
    setMatchingWishlist(true);
    setError(null);
    try {
      const response = await fetch("/api/wishlists", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, garden_profile_id: profile.id })
      });
      if (!response.ok) {
        throw new Error(await responseMessage(response));
      }
      setWishlist((await response.json()) as Wishlist);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not resolve this wishlist.");
    } finally {
      setMatchingWishlist(false);
    }
  }

  async function submitCatalogSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!profile || !searchQuery.trim()) return;
    setSearching(true);
    setError(null);
    setAddedNotice(null);
    try {
      const parameters = new URLSearchParams({
        q: searchQuery.trim(),
        garden_profile_id: profile.id
      });
      const response = await fetch(`/api/catalog/search?${parameters}`);
      if (!response.ok) {
        throw new Error(await responseMessage(response));
      }
      setSearchResults((await response.json()) as CatalogSearchResults);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not search the catalog.");
    } finally {
      setSearching(false);
    }
  }

  async function wishlistForSelection(): Promise<Wishlist> {
    if (wishlist) return wishlist;
    if (!profile) throw new Error("Save your garden before adding plants.");
    const response = await fetch("/api/wishlists/builder", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ garden_profile_id: profile.id })
    });
    if (!response.ok) throw new Error(await responseMessage(response));
    return (await response.json()) as Wishlist;
  }

  async function addSearchSelection(key: string, body: object, label: string) {
    setAddingSelection(key);
    setError(null);
    setAddedNotice(null);
    try {
      const currentWishlist = await wishlistForSelection();
      const response = await fetch(`/api/wishlists/${currentWishlist.id}/entries`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      });
      if (!response.ok) throw new Error(await responseMessage(response));
      setWishlist((await response.json()) as Wishlist);
      setAddedNotice(`${label} added to your wishlist.`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not add this plant.");
    } finally {
      setAddingSelection(null);
    }
  }

  async function updateEntry(entryId: string, body: object) {
    if (!wishlist) return;
    setUpdatingEntry(entryId);
    setError(null);
    try {
      const response = await fetch(`/api/wishlists/${wishlist.id}/entries/${entryId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      });
      if (!response.ok) {
        throw new Error(await responseMessage(response));
      }
      setWishlist((await response.json()) as Wishlist);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not update this crop.");
    } finally {
      setUpdatingEntry(null);
    }
  }

  return (
    <main>
      <header className="site-header">
        <p className="eyebrow">Kitchen Almanac</p>
        <p className="step-marker">
          {profile ? "02 / Find plants" : "01 / Garden context"}
        </p>
      </header>

      {!profile ? (
        <>
          <section className="hero">
            <h1>Start with where you grow.</h1>
            <p>
              A good garden plan begins with place. Tell us your location and setup so later
              recommendations can account for your season, space, and experience.
            </p>
          </section>

          <form className="profile-form" onSubmit={submitGardenProfile}>
            <div className="field-grid">
              <label className="field" htmlFor="postal-code">
                <span>US ZIP code</span>
                <input
                  id="postal-code"
                  inputMode="numeric"
                  maxLength={10}
                  pattern="[0-9]{5}(-[0-9]{4})?"
                  placeholder="20910"
                  required
                  value={postalCode}
                  onChange={(event) => setPostalCode(event.target.value)}
                />
              </label>
              <label className="field" htmlFor="target-year">
                <span>Planning year</span>
                <select
                  id="target-year"
                  value={targetYear}
                  onChange={(event) => setTargetYear(Number(event.target.value))}
                >
                  {[0, 1, 2].map((offset) => (
                    <option key={offset} value={currentYear + offset}>
                      {currentYear + offset}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field" htmlFor="experience-level">
                <span>Gardening experience</span>
                <select
                  id="experience-level"
                  value={experienceLevel}
                  onChange={(event) => setExperienceLevel(event.target.value)}
                >
                  <option value="beginner">Just getting started</option>
                  <option value="intermediate">A few seasons in</option>
                  <option value="advanced">Experienced grower</option>
                </select>
              </label>
            </div>

            <fieldset>
              <legend>How will you grow?</legend>
              <p className="field-help">Choose every setup you expect to use.</p>
              <div className="method-options">
                {methodOptions.map((method) => (
                  <label
                    className={
                      growingMethods.includes(method.value) ? "method-option selected" : "method-option"
                    }
                    key={method.value}
                  >
                    <input
                      type="checkbox"
                      checked={growingMethods.includes(method.value)}
                      onChange={() => toggleGrowingMethod(method.value)}
                    />
                    <strong>{method.label}</strong>
                    <span>{method.detail}</span>
                  </label>
                ))}
              </div>
            </fieldset>

            <div className="profile-footer">
              <p>
                ZIP codes are matched to an approximate Census ZCTA representative point,
                never treated as an exact address.
              </p>
              <button
                className="primary-button"
                disabled={savingProfile || !postalCode.trim() || growingMethods.length === 0}
                type="submit"
              >
                {savingProfile ? "Saving…" : "Save garden & continue"}
              </button>
            </div>
          </form>
        </>
      ) : (
        <>
          <section className="profile-summary" aria-label="Garden context">
            <div>
              <p className="section-kicker">Garden saved</p>
              <h2>{profile.location_input}</h2>
              {profile.location_source && (
                <p className="source-note">
                  Approximate ZCTA point from{" "}
                  {profile.location_source.publisher ?? profile.location_source.title}
                  .
                </p>
              )}
              {profile.hardiness && (
                <p className="source-note">
                  Hardiness evidence from{" "}
                  {profile.hardiness.source.publisher ?? profile.hardiness.source.title}.
                </p>
              )}
              {profile.climate_normals && (
                <p className="source-note">
                  Climate normals from {profile.climate_normals.station_name} (
                  {profile.climate_normals.station_distance_km.toFixed(1)} km away), published by{" "}
                  {profile.climate_normals.source.publisher ?? profile.climate_normals.source.title}.
                </p>
              )}
            </div>
            <dl>
              <div>
                <dt>Season</dt>
                <dd>{profile.target_year}</dd>
              </div>
              <div>
                <dt>Setup</dt>
                <dd>{profile.growing_methods.map((method) => method.replace("_", " ")).join(", ")}</dd>
              </div>
              <div>
                <dt>USDA zone</dt>
                <dd>
                  {profile.hardiness
                    ? `${profile.hardiness.zone} · ${profile.hardiness.mean_annual_extreme_minimum_f.toFixed(1)}°F`
                    : "Not available"}
                </dd>
              </div>
              <div>
                <dt>Typical frost window</dt>
                <dd>
                  {profile.climate_normals
                    ? `${profile.climate_normals.last_spring_frost_50} – ${profile.climate_normals.first_fall_frost_50}`
                    : "Not available"}
                </dd>
              </div>
              <div>
                <dt>Growing season</dt>
                <dd>
                  {profile.climate_normals
                    ? `${profile.climate_normals.growing_season_days_50} days · ${profile.climate_normals.growing_degree_days_base_50_f.toFixed(0)} GDD₅₀`
                    : "Not available"}
                </dd>
              </div>
            </dl>
          </section>

          <section className="hero compact-hero">
            <h1>What do you want to grow?</h1>
            <p>
              Search one plant at a time. Choose a documented cultivar, keep the variety
              undecided, or save your own wording for later research.
            </p>
          </section>

          <form className="catalog-search" onSubmit={submitCatalogSearch}>
            <label htmlFor="catalog-query">Crop or cultivar</label>
            <div className="search-row">
              <input
                id="catalog-query"
                type="search"
                maxLength={120}
                placeholder="Try tomatoes or San Marzano"
                autoComplete="off"
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
              />
              <button
                className="primary-button"
                disabled={searching || !searchQuery.trim()}
                type="submit"
              >
                {searching ? "Searching…" : "Search catalog"}
              </button>
            </div>
            <p>Names, aliases, types, and spelling variations are supported.</p>
          </form>

          {searchResults && (
            <section className="search-results" aria-live="polite">
              <div className="search-results-heading">
                <div>
                  <p className="section-kicker">Catalog matches</p>
                  <h2>Results for “{searchResults.query}”</h2>
                </div>
                <p>
                  {searchResults.crop_choices.length + searchResults.cultivars.length} documented
                  choices
                </p>
              </div>

              {searchResults.crop_choices.length > 0 && (
                <div className="result-group">
                  <div className="result-group-heading">
                    <h3>Crop choices</h3>
                    <p>Add the crop now and choose a cultivar later.</p>
                  </div>
                  <div className="crop-result-list">
                    {searchResults.crop_choices.map((result) => (
                      <article className="crop-result-card" key={result.crop.slug}>
                        <div>
                          <p className="result-kind">Crop · {humanize(result.match_method)}</p>
                          <h3>{result.crop.canonical_name}</h3>
                          <p>{humanize(result.crop.planning_category)}</p>
                        </div>
                        <button
                          className="secondary-button"
                          type="button"
                          disabled={addingSelection !== null}
                          onClick={() =>
                            addSearchSelection(
                              `crop-${result.crop.slug}`,
                              {
                                original_text: searchResults.query,
                                selection_kind: "crop",
                                crop_slug: result.crop.slug
                              },
                              result.crop.canonical_name
                            )
                          }
                        >
                          {addingSelection === `crop-${result.crop.slug}`
                            ? "Adding…"
                            : "Add crop"}
                        </button>
                      </article>
                    ))}
                  </div>
                </div>
              )}

              {groupedCultivars.map((group) => (
                <div className="result-group" key={group.key}>
                  <div className="result-group-heading">
                    <h3>{group.title}</h3>
                    <p>{group.description}</p>
                  </div>
                  <div className="cultivar-result-list">
                    {group.results.map((result) => {
                      const traits = featuredTraits(result.cultivar);
                      const evidence =
                        result.cultivar.traits.find((trait) => trait.source.scope)?.source ??
                        traits[0]?.source;
                      return (
                        <article className="cultivar-result-card" key={result.cultivar.id}>
                          <div className="cultivar-card-heading">
                            <div>
                              <p className="result-kind">
                                {result.cultivar.crop_type
                                  ? humanize(result.cultivar.crop_type)
                                  : result.cultivar.crop_name}
                                {` · ${humanize(result.match_method)}`}
                              </p>
                              <h3>{result.cultivar.canonical_name}</h3>
                            </div>
                            <span className={`suitability-badge ${result.suitability.status}`}>
                              {result.suitability.score === null
                                ? "Needs climate"
                                : `${result.suitability.score}/100 fit`}
                            </span>
                          </div>
                          {result.cultivar.description && <p>{result.cultivar.description}</p>}
                          {traits.length > 0 && (
                            <dl className="trait-list">
                              {traits.map((trait) => (
                                <div key={trait.field_name}>
                                  <dt>{humanize(trait.field_name)}</dt>
                                  <dd>
                                    {traitSummary(trait)}
                                    {trait.inherited_from_crop ? " · crop baseline" : ""}
                                  </dd>
                                </div>
                              ))}
                            </dl>
                          )}
                          <div className="suitability-summary">
                            <p>{result.suitability.summary}</p>
                            {result.suitability.factors.length > 0 && (
                              <ul>
                                {result.suitability.factors.slice(0, 2).map((factor) => (
                                  <li className={factor.effect} key={factor.code}>
                                    {factor.explanation}
                                  </li>
                                ))}
                              </ul>
                            )}
                            {result.suitability.constraints.map((constraint) => (
                              <p className="constraint-note" key={constraint}>
                                Constraint: {constraint}
                              </p>
                            ))}
                            {result.suitability.missing_evidence.length > 0 && (
                              <p className="missing-note">
                                Missing: {result.suitability.missing_evidence.join("; ")}
                              </p>
                            )}
                          </div>
                          {evidence && (
                            <p className="evidence-note">
                              Evidence: {evidence.publisher ?? evidence.title}
                              {evidence.scope ? ` · ${evidence.scope}` : ""}
                            </p>
                          )}
                          <button
                            className="secondary-button"
                            type="button"
                            disabled={addingSelection !== null}
                            onClick={() =>
                              addSearchSelection(
                                `cultivar-${result.cultivar.slug}`,
                                {
                                  original_text: searchResults.query,
                                  selection_kind: "cultivar",
                                  cultivar_slug: result.cultivar.slug
                                },
                                result.cultivar.canonical_name
                              )
                            }
                          >
                            {addingSelection === `cultivar-${result.cultivar.slug}`
                              ? "Adding…"
                              : "Add cultivar"}
                          </button>
                        </article>
                      );
                    })}
                  </div>
                </div>
              ))}

              {searchResults.crop_choices.length === 0 &&
                searchResults.cultivars.length === 0 && (
                  <p className="empty-results">
                    No documented match was close enough. You can still keep your wording.
                  </p>
                )}

              {searchResults.can_add_custom && (
                <div className="custom-actions">
                  <div>
                    <h3>Don’t see the right one?</h3>
                    <p>Custom entries stay clearly marked until supporting evidence is added.</p>
                  </div>
                  <div>
                    {searchResults.crop_choices[0] && (
                      <button
                        className="text-button"
                        type="button"
                        disabled={addingSelection !== null}
                        onClick={() =>
                          addSearchSelection(
                            "custom-cultivar",
                            {
                              original_text: searchResults.query,
                              selection_kind: "custom_cultivar",
                              crop_slug: searchResults.crop_choices[0].crop.slug
                            },
                            searchResults.query
                          )
                        }
                      >
                        Keep as a custom cultivar under{" "}
                        {searchResults.crop_choices[0].crop.canonical_name}
                      </button>
                    )}
                    <button
                      className="text-button"
                      type="button"
                      disabled={addingSelection !== null}
                      onClick={() =>
                        addSearchSelection(
                          "custom-crop",
                          {
                            original_text: searchResults.query,
                            selection_kind: "custom_crop"
                          },
                          searchResults.query
                        )
                      }
                    >
                      Keep as a completely custom crop
                    </button>
                  </div>
                </div>
              )}
            </section>
          )}

          {addedNotice && (
            <p className="success-message" role="status">
              {addedNotice}
            </p>
          )}

          <details className="quick-import">
            <summary>Have a list already? Use Quick Import</summary>
            <form className="wishlist-form" onSubmit={submitWishlist}>
              <label htmlFor="wishlist">One crop or cultivar per line</label>
              <textarea
                id="wishlist"
                value={text}
                onChange={(event) => setText(event.target.value)}
                rows={8}
                maxLength={12_000}
                placeholder={"Tomatoes\nSnap peas\nZucchini"}
              />
              <div className="form-footer">
                <span>Up to 100 entries · uncertain matches require confirmation</span>
                <button
                  className="primary-button"
                  disabled={matchingWishlist || !text.trim()}
                  type="submit"
                >
                  {matchingWishlist ? "Matching…" : "Match my list"}
                </button>
              </div>
            </form>
          </details>
        </>
      )}

      {error && (
        <p className="error-message" role="alert">
          {error}
        </p>
      )}

      {profile && wishlist && (
        <section className="results" aria-live="polite">
          <div className="results-heading">
            <div>
              <p className="section-kicker">Wishlist review</p>
              <h2>
                {wishlist.entries.length}{" "}
                {wishlist.entries.length === 1 ? "plant" : "plants"} on your list
              </h2>
            </div>
            <p className={reviewCount ? "review-count attention" : "review-count"}>
              {reviewCount ? `${reviewCount} need your input` : "Everything is settled"}
            </p>
          </div>

          <div className="entry-list">
            {wishlist.entries.map((entry) => (
              <article className={`entry-card ${entry.status}`} key={entry.id}>
                <div className="entry-number">{String(entry.position).padStart(2, "0")}</div>
                <div className="entry-content">
                  <div className="entry-title-row">
                    <h3>{entry.original_text}</h3>
                    <span className="status-label">{entry.status.replace("_", " ")}</span>
                  </div>

                  {entry.status === "resolved" && entry.resolved_cultivar && (
                    <p className="match-copy">
                      Matched cultivar <strong>{entry.resolved_cultivar.canonical_name}</strong>
                      {` under ${entry.resolved_cultivar.crop_name}`}
                      {entry.resolution_method === "user_confirmed" ? " by you" : ""}.
                    </p>
                  )}

                  {entry.status === "resolved" && !entry.resolved_cultivar && entry.resolved_crop && (
                    <p className="match-copy">
                      Matched to <strong>{entry.resolved_crop.canonical_name}</strong>
                      {entry.resolution_method === "user_confirmed" ? " by you" : ""}.
                    </p>
                  )}

                  {entry.status === "needs_confirmation" && (
                    <div className="candidate-panel">
                      <p>
                        {entry.cultivar_candidates.length
                          ? "Which cultivar did you mean?"
                          : "Which crop did you mean?"}
                      </p>
                      <div className="candidate-actions">
                        {entry.cultivar_candidates.map((candidate) => (
                          <button
                            type="button"
                            className="candidate-button"
                            disabled={updatingEntry === entry.id}
                            key={candidate.id}
                            onClick={() =>
                              updateEntry(entry.id, { cultivar_slug: candidate.slug })
                            }
                          >
                            <strong>{candidate.canonical_name}</strong>
                            <span>
                              {candidate.crop_type?.replace("_", " ") ?? candidate.crop_name} ·
                              matched “{candidate.matched_alias}”
                            </span>
                          </button>
                        ))}
                        {entry.candidates.map((candidate) => (
                          <button
                            type="button"
                            className="candidate-button"
                            disabled={updatingEntry === entry.id}
                            key={candidate.slug}
                            onClick={() => updateEntry(entry.id, { crop_slug: candidate.slug })}
                          >
                            <strong>{candidate.canonical_name}</strong>
                            <span>Matched “{candidate.matched_alias}”</span>
                          </button>
                        ))}
                      </div>
                      <button
                        className="text-button"
                        type="button"
                        disabled={updatingEntry === entry.id}
                        onClick={() => updateEntry(entry.id, { keep_custom: true })}
                      >
                        None of these—keep my wording
                      </button>
                    </div>
                  )}

                  {entry.status === "unresolved" && (
                    <div className="unresolved-panel">
                      <p>
                        {entry.resolved_crop && entry.cultivar_intent_text
                          ? `We recognized ${entry.resolved_crop.canonical_name}, but “${entry.cultivar_intent_text}” is not a documented cultivar yet.`
                          : "We couldn’t confidently match this to the current crop catalog."}
                      </p>
                      <button
                        className="text-button"
                        type="button"
                        disabled={updatingEntry === entry.id}
                        onClick={() => updateEntry(entry.id, { keep_custom: true })}
                      >
                        {entry.resolved_crop ? "Keep as a custom cultivar" : "Keep as a custom crop"}
                      </button>
                    </div>
                  )}

                  {entry.status === "custom" && (
                    <p className="match-copy">
                      Saved with your original wording
                      {entry.resolved_crop ? ` under ${entry.resolved_crop.canonical_name}` : ""} for
                      later research.
                    </p>
                  )}
                </div>
              </article>
            ))}
          </div>
        </section>
      )}
    </main>
  );
}
