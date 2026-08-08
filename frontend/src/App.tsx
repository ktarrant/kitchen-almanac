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

export default function App() {
  const [profile, setProfile] = useState<GardenProfile | null>(null);
  const [postalCode, setPostalCode] = useState("");
  const [targetYear, setTargetYear] = useState(currentYear);
  const [experienceLevel, setExperienceLevel] = useState("beginner");
  const [growingMethods, setGrowingMethods] = useState<GrowingMethod[]>(["raised_bed"]);
  const [text, setText] = useState(initialWishlist);
  const [wishlist, setWishlist] = useState<Wishlist | null>(null);
  const [savingProfile, setSavingProfile] = useState(false);
  const [matchingWishlist, setMatchingWishlist] = useState(false);
  const [updatingEntry, setUpdatingEntry] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const reviewCount = useMemo(
    () =>
      wishlist?.entries.filter(
        (entry) => entry.status === "needs_confirmation" || entry.status === "unresolved"
      ).length ?? 0,
    [wishlist]
  );

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
          {profile ? "02 / Quick import" : "01 / Garden context"}
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
            <h1>Bring over your crop list.</h1>
            <p>
              Search-and-select cultivar discovery is the next workflow slice. For now, quick
              import keeps the earlier crop resolver available as a secondary path.
            </p>
          </section>

          <form className="wishlist-form" onSubmit={submitWishlist}>
            <label htmlFor="wishlist">Quick-import wishlist</label>
            <textarea
              id="wishlist"
              value={text}
              onChange={(event) => setText(event.target.value)}
              rows={8}
              maxLength={12_000}
              placeholder={"Tomatoes\nSnap peas\nZucchini"}
            />
            <div className="form-footer">
              <span>One crop per line · up to 100 entries</span>
              <button
                className="primary-button"
                disabled={matchingWishlist || !text.trim()}
                type="submit"
              >
                {matchingWishlist ? "Matching…" : "Match my crops"}
              </button>
            </div>
          </form>
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
              <h2>{wishlist.entries.length} crops on your list</h2>
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
