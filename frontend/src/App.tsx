import { FormEvent, useMemo, useState } from "react";

type CropMatch = {
  slug: string;
  canonical_name: string;
  planning_category: string;
};

type Candidate = CropMatch & {
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
  resolved_crop: CropMatch | null;
  candidates: Candidate[];
};

type Wishlist = {
  id: string;
  dataset_id: string;
  name: string;
  entries: WishlistEntry[];
};

const initialWishlist = "Tomatoes\nGreen beans\nCarrots\nZucchini";

async function responseMessage(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: string };
    return body.detail ?? "Something went wrong. Please try again.";
  } catch {
    return "Something went wrong. Please try again.";
  }
}

export default function App() {
  const [text, setText] = useState(initialWishlist);
  const [wishlist, setWishlist] = useState<Wishlist | null>(null);
  const [busy, setBusy] = useState(false);
  const [updatingEntry, setUpdatingEntry] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const reviewCount = useMemo(
    () => wishlist?.entries.filter((entry) => entry.status === "needs_confirmation").length ?? 0,
    [wishlist]
  );

  async function submitWishlist(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const response = await fetch("/api/wishlists", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text })
      });
      if (!response.ok) {
        throw new Error(await responseMessage(response));
      }
      setWishlist((await response.json()) as Wishlist);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not resolve this wishlist.");
    } finally {
      setBusy(false);
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
        <p className="step-marker">01 / Choose crops</p>
      </header>

      <section className="hero">
        <h1>What would you love to harvest?</h1>
        <p>
          Start with the vegetables you actually want to eat. Add one crop per line—we’ll
          match familiar names and ask whenever there’s room for doubt.
        </p>
      </section>

      <form className="wishlist-form" onSubmit={submitWishlist}>
        <label htmlFor="wishlist">Your vegetable wishlist</label>
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
          <button className="primary-button" disabled={busy || !text.trim()} type="submit">
            {busy ? "Matching…" : "Match my crops"}
          </button>
        </div>
      </form>

      {error && (
        <p className="error-message" role="alert">
          {error}
        </p>
      )}

      {wishlist && (
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

                  {entry.status === "resolved" && entry.resolved_crop && (
                    <p className="match-copy">
                      Matched to <strong>{entry.resolved_crop.canonical_name}</strong>
                      {entry.resolution_method === "user_confirmed" ? " by you" : ""}.
                    </p>
                  )}

                  {entry.status === "needs_confirmation" && (
                    <div className="candidate-panel">
                      <p>Which crop did you mean?</p>
                      <div className="candidate-actions">
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
                      <p>We couldn’t confidently match this to the current crop catalog.</p>
                      <button
                        className="text-button"
                        type="button"
                        disabled={updatingEntry === entry.id}
                        onClick={() => updateEntry(entry.id, { keep_custom: true })}
                      >
                        Keep as a custom crop
                      </button>
                    </div>
                  )}

                  {entry.status === "custom" && (
                    <p className="match-copy">Saved with your original wording for later research.</p>
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
