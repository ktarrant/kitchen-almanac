import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

type GrowingMethod = "in_ground" | "raised_bed" | "containers" | "protected";
type IntendedUse = "fresh" | "snacking" | "sauce" | "canning" | "pickling" | "processing";
type DiseaseConcern =
  | "early_blight"
  | "fusarium_wilt"
  | "late_blight"
  | "root_knot_nematode"
  | "tomato_mosaic_virus"
  | "tomato_spotted_wilt_virus"
  | "verticillium_wilt";

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
  support_available: boolean | null;
  max_plant_spread_inches: number | null;
  max_container_volume_gallons: number | null;
  intended_uses: IntendedUse[];
  disease_concerns: DiseaseConcern[];
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
  created_at: string;
  updated_at: string;
};

type CropMatch = {
  slug: string;
  canonical_name: string;
  planning_category: string;
};

type BrowseCrop = CropMatch & {
  commodity_section_key: string;
  commodity_section_title: string;
  commodity_section_position: number;
  browse_category_key: string;
  browse_category_title: string;
  browse_category_position: number;
};

type CropListResponse = {
  dataset_id: string | null;
  crops: BrowseCrop[];
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
    availability_status: "in_stock" | "out_of_stock" | "unknown" | "retired";
    observed_at: string;
    identity_match_method: "exact_name" | "reviewed_alias";
    source: {
      source_url: string | null;
    };
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
  dimensions: {
    code: string;
    label: string;
    status: "fit" | "caution" | "constraint" | "unknown" | "not_applicable";
    explanation: string;
  }[];
  constraints: string[];
  assumptions: string[];
  missing_evidence: string[];
};

type CultivarResearchQuality = {
  algorithm_version: string;
  score: number;
  tier: "well_researched" | "documented" | "limited";
  source_count: number;
  cultivar_specific_trait_count: number;
  strengths: string[];
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
    research_quality: CultivarResearchQuality;
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

type GuideEvidence = {
  field_name: string;
  value: object | unknown[] | string | number | boolean;
  origin: "cultivar_catalog" | "crop_baseline" | "climate_normal" | "garden_profile";
  source_document_id: string | null;
  title: string | null;
  publisher: string | null;
  source_url: string | null;
  source_locator: string | null;
  source_scope: string | null;
  inherited_from_crop: boolean;
};

type GrowGuide = {
  garden_profile_id: string;
  garden_name: string;
  target_year: number;
  cultivar_slug: string;
  cultivar_name: string;
  crop_slug: string;
  crop_name: string;
  cultivar_dataset_id: string;
  crop_dataset_id: string;
  algorithm_version: string;
  input_fingerprint: string;
  summary: string;
  sections: {
    code: string;
    title: string;
    status: "documented" | "partial" | "missing" | "conflict";
    summary: string;
    instructions: string[];
    confidence: string | null;
    provenance: "cultivar" | "crop_baseline" | "mixed" | "none";
    evidence: GuideEvidence[];
    missing_evidence: string[];
  }[];
  timeline: {
    code: string;
    title: string;
    start_date: string;
    end_date: string | null;
    summary: string;
    confidence: string;
    evidence: GuideEvidence[];
  }[];
  conflicts: string[];
  assumptions: string[];
  missing_evidence: string[];
};

const initialWishlist = "San Marzano tomatoes\npaste tomato\nCarrots\nZucchini";
const currentYear = new Date().getFullYear();
const methodOptions: { value: GrowingMethod; label: string; detail: string }[] = [
  { value: "in_ground", label: "In ground", detail: "Beds planted directly in your soil" },
  { value: "raised_bed", label: "Raised beds", detail: "Contained beds with added soil" },
  { value: "containers", label: "Containers", detail: "Pots, grow bags, and planters" },
  {
    value: "protected",
    label: "Protected culture",
    detail: "A greenhouse or high tunnel"
  }
];
const intendedUseOptions: { value: IntendedUse; label: string }[] = [
  { value: "fresh", label: "Fresh eating" },
  { value: "snacking", label: "Snacking" },
  { value: "sauce", label: "Sauce" },
  { value: "canning", label: "Canning" },
  { value: "pickling", label: "Pickling" },
  { value: "processing", label: "General processing" }
];
const diseaseOptions: { value: DiseaseConcern; label: string }[] = [
  { value: "early_blight", label: "Early blight" },
  { value: "late_blight", label: "Late blight" },
  { value: "fusarium_wilt", label: "Fusarium wilt" },
  { value: "verticillium_wilt", label: "Verticillium wilt" },
  { value: "root_knot_nematode", label: "Root-knot nematode" },
  { value: "tomato_mosaic_virus", label: "Tomato mosaic virus" },
  { value: "tomato_spotted_wilt_virus", label: "Tomato spotted wilt virus" }
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

function formatGuideDate(value: string) {
  return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" }).format(
    new Date(`${value}T12:00:00`)
  );
}

function wishlistEntryName(entry: WishlistEntry) {
  return (
    entry.resolved_cultivar?.canonical_name ??
    entry.resolved_crop?.canonical_name ??
    entry.original_text
  );
}

function wishlistEntryKind(entry: WishlistEntry) {
  if (entry.status === "custom") {
    return entry.resolved_crop ? "Custom cultivar" : "Custom crop";
  }
  if (entry.resolved_cultivar) return "Cultivar";
  if (entry.resolved_crop) return "Crop · cultivar undecided";
  return humanize(entry.status);
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
  const [savedProfiles, setSavedProfiles] = useState<GardenProfile[]>([]);
  const [loadingProfiles, setLoadingProfiles] = useState(true);
  const [profileToDelete, setProfileToDelete] = useState<GardenProfile | null>(null);
  const [deletingProfile, setDeletingProfile] = useState(false);
  const [deleteGardenError, setDeleteGardenError] = useState<string | null>(null);
  const [profileName, setProfileName] = useState("My garden");
  const [postalCode, setPostalCode] = useState("");
  const [targetYear, setTargetYear] = useState(currentYear);
  const [experienceLevel, setExperienceLevel] = useState("beginner");
  const [growingMethods, setGrowingMethods] = useState<GrowingMethod[]>(["raised_bed"]);
  const [supportChoice, setSupportChoice] = useState<"unknown" | "yes" | "no">("unknown");
  const [maxPlantSpread, setMaxPlantSpread] = useState("");
  const [maxContainerVolume, setMaxContainerVolume] = useState("");
  const [intendedUses, setIntendedUses] = useState<IntendedUse[]>([]);
  const [diseaseConcerns, setDiseaseConcerns] = useState<DiseaseConcern[]>([]);
  const [text, setText] = useState(initialWishlist);
  const [wishlist, setWishlist] = useState<Wishlist | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<CatalogSearchResults | null>(null);
  const [browseCrops, setBrowseCrops] = useState<BrowseCrop[]>([]);
  const [browseCategoryKey, setBrowseCategoryKey] = useState("all");
  const [loadingBrowseCrops, setLoadingBrowseCrops] = useState(true);
  const [browseCropsError, setBrowseCropsError] = useState<string | null>(null);
  const [savingProfile, setSavingProfile] = useState(false);
  const [searching, setSearching] = useState(false);
  const [addingSelection, setAddingSelection] = useState<string | null>(null);
  const [matchingWishlist, setMatchingWishlist] = useState(false);
  const [loadingWishlist, setLoadingWishlist] = useState(false);
  const [updatingEntry, setUpdatingEntry] = useState<string | null>(null);
  const [removingEntry, setRemovingEntry] = useState<string | null>(null);
  const [guideCultivarSlug, setGuideCultivarSlug] = useState<string | null>(null);
  const [growGuide, setGrowGuide] = useState<GrowGuide | null>(null);
  const [loadingGrowGuide, setLoadingGrowGuide] = useState(false);
  const [addedNotice, setAddedNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const wishlistRequestId = useRef(0);
  const catalogSearchRequestId = useRef(0);
  const growGuideRequestId = useRef(0);
  const createGardenDialogRef = useRef<HTMLDialogElement>(null);
  const deleteGardenDialogRef = useRef<HTMLDialogElement>(null);
  const growGuideRef = useRef<HTMLElement>(null);
  const catalogQueryRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const controller = new AbortController();
    async function loadProfiles() {
      try {
        const response = await fetch("/api/garden-profiles", { signal: controller.signal });
        if (!response.ok) throw new Error(await responseMessage(response));
        const profiles = ((await response.json()) as { profiles: GardenProfile[] }).profiles;
        setSavedProfiles(profiles);
        const rememberedId = window.localStorage.getItem("kitchen-almanac-profile-id");
        const remembered = profiles.find((item) => item.id === rememberedId);
        if (remembered) void chooseGardenProfile(remembered);
      } catch (caught) {
        if (caught instanceof DOMException && caught.name === "AbortError") return;
        setError(caught instanceof Error ? caught.message : "Could not load saved gardens.");
      } finally {
        if (!controller.signal.aborted) setLoadingProfiles(false);
      }
    }
    void loadProfiles();
    return () => {
      controller.abort();
      wishlistRequestId.current += 1;
    };
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    async function loadBrowseCrops() {
      try {
        const response = await fetch("/api/crops", { signal: controller.signal });
        if (!response.ok) throw new Error(await responseMessage(response));
        const payload = (await response.json()) as CropListResponse;
        setBrowseCrops(
          [...payload.crops].sort((left, right) =>
            left.canonical_name.localeCompare(right.canonical_name)
          )
        );
      } catch (caught) {
        if (caught instanceof DOMException && caught.name === "AbortError") return;
        setBrowseCropsError(
          caught instanceof Error ? caught.message : "Could not load crop choices."
        );
      } finally {
        if (!controller.signal.aborted) setLoadingBrowseCrops(false);
      }
    }
    void loadBrowseCrops();
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (profileToDelete && !deleteGardenDialogRef.current?.open) {
      deleteGardenDialogRef.current?.showModal();
    }
  }, [profileToDelete]);

  const reviewCount = useMemo(
    () =>
      wishlist?.entries.filter(
        (entry) => entry.status === "needs_confirmation" || entry.status === "unresolved"
      ).length ?? 0,
    [wishlist]
  );
  const browseCategories = useMemo(() => {
    const categories = new Map<
      string,
      { key: string; title: string; position: number; crops: BrowseCrop[] }
    >();
    for (const crop of browseCrops) {
      const category = categories.get(crop.browse_category_key) ?? {
        key: crop.browse_category_key,
        title: crop.browse_category_title,
        position: crop.browse_category_position,
        crops: []
      };
      category.crops.push(crop);
      categories.set(category.key, category);
    }
    return [...categories.values()]
      .sort((left, right) => left.position - right.position)
      .map((category) => ({
        ...category,
        crops: category.crops.sort((left, right) =>
          left.canonical_name.localeCompare(right.canonical_name)
        )
      }));
  }, [browseCrops]);
  const selectedBrowseCategory = browseCategories.find(
    (category) => category.key === browseCategoryKey
  );
  const visibleBrowseCrops = useMemo(
    () =>
      browseCategoryKey === "all"
        ? [...browseCrops].sort((left, right) =>
            left.canonical_name.localeCompare(right.canonical_name)
          )
        : (selectedBrowseCategory?.crops ?? []),
    [browseCategoryKey, browseCrops, selectedBrowseCategory]
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

  function toggleIntendedUse(use: IntendedUse) {
    setIntendedUses((selected) =>
      selected.includes(use) ? selected.filter((item) => item !== use) : [...selected, use]
    );
  }

  function toggleDiseaseConcern(concern: DiseaseConcern) {
    setDiseaseConcerns((selected) =>
      selected.includes(concern)
        ? selected.filter((item) => item !== concern)
        : [...selected, concern]
    );
  }

  async function chooseGardenProfile(selected: GardenProfile) {
    const requestId = ++wishlistRequestId.current;
    growGuideRequestId.current += 1;
    setProfile(selected);
    setWishlist(null);
    setLoadingWishlist(true);
    catalogSearchRequestId.current += 1;
    setSearching(false);
    setSearchResults(null);
    setSearchQuery("");
    setGuideCultivarSlug(null);
    setGrowGuide(null);
    setAddedNotice(null);
    setError(null);
    window.localStorage.setItem("kitchen-almanac-profile-id", selected.id);
    try {
      const response = await fetch(`/api/garden-profiles/${selected.id}/wishlists/active`);
      if (!response.ok) throw new Error(await responseMessage(response));
      const restored = (await response.json()) as Wishlist | null;
      if (wishlistRequestId.current === requestId) setWishlist(restored);
    } catch (caught) {
      if (wishlistRequestId.current !== requestId) return;
      setError(caught instanceof Error ? caught.message : "Could not load saved plants.");
    } finally {
      if (wishlistRequestId.current === requestId) setLoadingWishlist(false);
    }
  }

  function switchGardenProfile() {
    wishlistRequestId.current += 1;
    growGuideRequestId.current += 1;
    setProfile(null);
    setWishlist(null);
    setLoadingWishlist(false);
    catalogSearchRequestId.current += 1;
    setSearching(false);
    setSearchResults(null);
    setSearchQuery("");
    setGuideCultivarSlug(null);
    setGrowGuide(null);
    setAddedNotice(null);
    window.localStorage.removeItem("kitchen-almanac-profile-id");
  }

  function openCreateGardenDialog() {
    setError(null);
    if (!createGardenDialogRef.current?.open) {
      createGardenDialogRef.current?.showModal();
    }
  }

  function closeCreateGardenDialog() {
    createGardenDialogRef.current?.close();
  }

  function requestGardenDeletion(saved: GardenProfile) {
    setDeleteGardenError(null);
    setProfileToDelete(saved);
  }

  function cancelGardenDeletion() {
    if (deletingProfile) return;
    deleteGardenDialogRef.current?.close();
    setProfileToDelete(null);
    setDeleteGardenError(null);
  }

  async function confirmGardenDeletion() {
    if (!profileToDelete) return;
    const deletedProfile = profileToDelete;
    setDeletingProfile(true);
    setDeleteGardenError(null);
    try {
      const response = await fetch(`/api/garden-profiles/${deletedProfile.id}`, {
        method: "DELETE"
      });
      if (!response.ok) throw new Error(await responseMessage(response));

      setSavedProfiles((profiles) =>
        profiles.filter((saved) => saved.id !== deletedProfile.id)
      );
      if (window.localStorage.getItem("kitchen-almanac-profile-id") === deletedProfile.id) {
        window.localStorage.removeItem("kitchen-almanac-profile-id");
      }
      if (profile?.id === deletedProfile.id) switchGardenProfile();
      deleteGardenDialogRef.current?.close();
      setProfileToDelete(null);
    } catch (caught) {
      setDeleteGardenError(
        caught instanceof Error ? caught.message : "Could not delete this garden."
      );
    } finally {
      setDeletingProfile(false);
    }
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
          name: profileName,
          postal_code: postalCode,
          target_year: targetYear,
          experience_level: experienceLevel,
          growing_methods: growingMethods,
          support_available:
            supportChoice === "unknown" ? null : supportChoice === "yes",
          max_plant_spread_inches: maxPlantSpread ? Number(maxPlantSpread) : null,
          max_container_volume_gallons: maxContainerVolume
            ? Number(maxContainerVolume)
            : null,
          intended_uses: intendedUses,
          disease_concerns: diseaseConcerns
        })
      });
      if (!response.ok) {
        throw new Error(await responseMessage(response));
      }
      const created = (await response.json()) as GardenProfile;
      setSavedProfiles((profiles) => [created, ...profiles]);
      createGardenDialogRef.current?.close();
      void chooseGardenProfile(created);
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

  async function searchCatalog(query: string) {
    const normalizedQuery = query.trim();
    if (!profile || !normalizedQuery) return;
    const requestId = ++catalogSearchRequestId.current;
    setSearchQuery(normalizedQuery);
    setSearchResults(null);
    setSearching(true);
    setError(null);
    setAddedNotice(null);
    try {
      const parameters = new URLSearchParams({
        q: normalizedQuery,
        garden_profile_id: profile.id
      });
      const response = await fetch(`/api/catalog/search?${parameters}`);
      if (!response.ok) {
        throw new Error(await responseMessage(response));
      }
      const results = (await response.json()) as CatalogSearchResults;
      if (catalogSearchRequestId.current === requestId) setSearchResults(results);
    } catch (caught) {
      if (catalogSearchRequestId.current !== requestId) return;
      setError(caught instanceof Error ? caught.message : "Could not search the catalog.");
    } finally {
      if (catalogSearchRequestId.current === requestId) setSearching(false);
    }
  }

  async function submitCatalogSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await searchCatalog(searchQuery);
  }

  function updateCatalogQuery(query: string) {
    catalogSearchRequestId.current += 1;
    setSearchQuery(query);
    setSearchResults(null);
    setSearching(false);
  }

  function clearCatalogSearch() {
    updateCatalogQuery("");
    catalogQueryRef.current?.focus();
  }

  async function wishlistForSelection(): Promise<Wishlist> {
    if (wishlist) return wishlist;
    if (!profile) throw new Error("Save your garden before adding plants.");
    if (loadingWishlist) throw new Error("Your saved plants are still loading.");
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

  async function removeEntry(entry: WishlistEntry) {
    if (!wishlist) return;
    setRemovingEntry(entry.id);
    setError(null);
    setAddedNotice(null);
    try {
      const response = await fetch(`/api/wishlists/${wishlist.id}/entries/${entry.id}`, {
        method: "DELETE"
      });
      if (!response.ok) throw new Error(await responseMessage(response));
      setWishlist((await response.json()) as Wishlist);
      if (entry.resolved_cultivar?.slug === guideCultivarSlug) {
        growGuideRequestId.current += 1;
        setGuideCultivarSlug(null);
        setGrowGuide(null);
        setLoadingGrowGuide(false);
      }
      setAddedNotice(`${wishlistEntryName(entry)} removed from your selected plants.`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not remove this plant.");
    } finally {
      setRemovingEntry(null);
    }
  }

  async function showGrowGuide(cultivar: CultivarMatch) {
    if (!profile) return;
    const requestId = ++growGuideRequestId.current;
    setGuideCultivarSlug(cultivar.slug);
    setGrowGuide(null);
    setLoadingGrowGuide(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        garden_profile_id: profile.id,
        cultivar_slug: cultivar.slug
      });
      const response = await fetch(`/api/grow-guides?${params}`);
      if (!response.ok) throw new Error(await responseMessage(response));
      const guide = (await response.json()) as GrowGuide;
      if (growGuideRequestId.current !== requestId) return;
      setGrowGuide(guide);
      window.requestAnimationFrame(() => {
        growGuideRef.current?.focus();
        growGuideRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    } catch (caught) {
      if (growGuideRequestId.current !== requestId) return;
      setError(caught instanceof Error ? caught.message : "Could not generate this grow guide.");
    } finally {
      if (growGuideRequestId.current === requestId) setLoadingGrowGuide(false);
    }
  }

  function closeGrowGuide() {
    growGuideRequestId.current += 1;
    setGuideCultivarSlug(null);
    setGrowGuide(null);
    setLoadingGrowGuide(false);
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
            <h1>{savedProfiles.length > 0 ? "Continue your garden." : "Start with where you grow."}</h1>
            <p>
              {savedProfiles.length > 0
                ? "Choose a saved garden to continue, or create a new context for a different place or setup."
                : "A good garden plan begins with place. Tell us your location and setup so later recommendations can account for your season, space, and experience."}
            </p>
          </section>

          {loadingProfiles && <p className="profile-loading">Loading saved gardens…</p>}

          {!loadingProfiles && savedProfiles.length > 0 && (
            <section className="saved-profiles" aria-labelledby="saved-gardens-heading">
              <div className="saved-profiles-heading">
                <div>
                  <p className="section-kicker">Saved gardens</p>
                  <h2 id="saved-gardens-heading">Pick up where you left off</h2>
                </div>
                <button
                  className="secondary-button"
                  type="button"
                  onClick={openCreateGardenDialog}
                >
                  Create another garden
                </button>
              </div>
              <div className="saved-profile-list">
                {savedProfiles.map((saved) => (
                  <article className="saved-profile-card" key={saved.id}>
                    <div>
                      <p className="result-kind">{saved.location_input}</p>
                      <h3>{saved.name}</h3>
                      <p>
                        {saved.target_year} · {saved.growing_methods.map(humanize).join(", ")}
                        {saved.hardiness ? ` · USDA ${saved.hardiness.zone}` : ""}
                      </p>
                    </div>
                    <div className="saved-profile-actions">
                      <button
                        className="secondary-button"
                        type="button"
                        onClick={() => chooseGardenProfile(saved)}
                      >
                        Use this garden
                      </button>
                      <button
                        className="text-button danger-text-button"
                        type="button"
                        onClick={() => requestGardenDeletion(saved)}
                      >
                        Delete
                      </button>
                    </div>
                  </article>
                ))}
              </div>
            </section>
          )}

          {!loadingProfiles && (
          <dialog
            aria-labelledby="create-garden-heading"
            className={
              savedProfiles.length === 0
                ? "create-garden-dialog inline"
                : "create-garden-dialog"
            }
            open={savedProfiles.length === 0 ? true : undefined}
            ref={createGardenDialogRef}
            onCancel={(event) => {
              if (savedProfiles.length === 0) event.preventDefault();
            }}
          >
          <form className="profile-form" onSubmit={submitGardenProfile}>
            <div className="create-garden-heading">
              <div>
                <p className="section-kicker">New garden</p>
                <h2 id="create-garden-heading">Create a garden context</h2>
              </div>
              {savedProfiles.length > 0 && (
                <button
                  aria-label="Close new garden form"
                  className="dialog-close-button"
                  type="button"
                  onClick={closeCreateGardenDialog}
                >
                  Close
                </button>
              )}
            </div>
            {error && (
              <p className="error-message" role="alert">
                {error}
              </p>
            )}
            <div className="field-grid">
              <label className="field" htmlFor="profile-name">
                <span>Garden name</span>
                <input
                  id="profile-name"
                  maxLength={120}
                  placeholder="Backyard garden"
                  required
                  value={profileName}
                  autoFocus={savedProfiles.length > 0}
                  onChange={(event) => setProfileName(event.target.value)}
                />
              </label>
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

            <fieldset>
              <legend>What can your space support?</legend>
              <p className="field-help">
                Optional details turn possible physical conflicts into explicit checks.
              </p>
              <div className="field-grid">
                <label className="field" htmlFor="support-available">
                  <span>Cages, stakes, or trellises</span>
                  <select
                    id="support-available"
                    value={supportChoice}
                    onChange={(event) =>
                      setSupportChoice(event.target.value as "unknown" | "yes" | "no")
                    }
                  >
                    <option value="unknown">Not sure yet</option>
                    <option value="yes">I can provide support</option>
                    <option value="no">No support available</option>
                  </select>
                </label>
                <label className="field" htmlFor="plant-spread">
                  <span>Maximum width per plant</span>
                  <select
                    id="plant-spread"
                    value={maxPlantSpread}
                    onChange={(event) => setMaxPlantSpread(event.target.value)}
                  >
                    <option value="">Not specified</option>
                    <option value="12">12 inches</option>
                    <option value="18">18 inches</option>
                    <option value="24">24 inches</option>
                    <option value="36">36 inches</option>
                    <option value="60">60 inches or more</option>
                  </select>
                </label>
                {growingMethods.includes("containers") && (
                  <label className="field" htmlFor="container-volume">
                    <span>Largest available container</span>
                    <select
                      id="container-volume"
                      value={maxContainerVolume}
                      onChange={(event) => setMaxContainerVolume(event.target.value)}
                    >
                      <option value="">Not specified</option>
                      <option value="3">3 gallons</option>
                      <option value="5">5 gallons</option>
                      <option value="10">10 gallons</option>
                      <option value="15">15 gallons</option>
                      <option value="20">20 gallons or more</option>
                    </select>
                  </label>
                )}
              </div>
            </fieldset>

            <fieldset>
              <legend>What matters for this garden?</legend>
              <p className="field-help">
                Optional culinary goals and recurring disease concerns refine cultivar rankings.
              </p>
              <div className="preference-options">
                {intendedUseOptions.map((option) => (
                  <label key={option.value}>
                    <input
                      type="checkbox"
                      checked={intendedUses.includes(option.value)}
                      onChange={() => toggleIntendedUse(option.value)}
                    />
                    <span>{option.label}</span>
                  </label>
                ))}
              </div>
              <details className="disease-options">
                <summary>Add recurring tomato disease concerns</summary>
                <div className="preference-options">
                  {diseaseOptions.map((option) => (
                    <label key={option.value}>
                      <input
                        type="checkbox"
                        checked={diseaseConcerns.includes(option.value)}
                        onChange={() => toggleDiseaseConcern(option.value)}
                      />
                      <span>{option.label}</span>
                    </label>
                  ))}
                </div>
              </details>
            </fieldset>

            <div className="profile-footer">
              <p>
                ZIP codes are matched to an approximate Census ZCTA representative point,
                never treated as an exact address.
              </p>
              <div className="profile-footer-actions">
                {savedProfiles.length > 0 && (
                  <button
                    className="secondary-button"
                    disabled={savingProfile}
                    type="button"
                    onClick={closeCreateGardenDialog}
                  >
                    Cancel
                  </button>
                )}
                <button
                  className="primary-button"
                  disabled={
                    savingProfile ||
                    !profileName.trim() ||
                    !postalCode.trim() ||
                    growingMethods.length === 0
                  }
                  type="submit"
                >
                  {savingProfile ? "Saving…" : "Save garden & continue"}
                </button>
              </div>
            </div>
          </form>
          </dialog>
          )}

          <dialog
            aria-labelledby="delete-garden-heading"
            className="confirmation-dialog"
            ref={deleteGardenDialogRef}
            onCancel={(event) => {
              event.preventDefault();
              cancelGardenDeletion();
            }}
          >
            {profileToDelete && (
              <div>
                <p className="section-kicker">Delete garden</p>
                <h2 id="delete-garden-heading">Delete “{profileToDelete.name}”?</h2>
                <p>
                  This permanently removes the garden context, its location evidence, and all
                  saved wishlist entries. Catalog and cultivar research will not be affected.
                </p>
                {deleteGardenError && (
                  <p className="dialog-error" role="alert">
                    {deleteGardenError}
                  </p>
                )}
                <div className="confirmation-actions">
                  <button
                    className="secondary-button"
                    disabled={deletingProfile}
                    type="button"
                    onClick={cancelGardenDeletion}
                  >
                    Keep garden
                  </button>
                  <button
                    className="danger-button"
                    disabled={deletingProfile}
                    type="button"
                    onClick={() => void confirmGardenDeletion()}
                  >
                    {deletingProfile ? "Deleting…" : "Delete garden"}
                  </button>
                </div>
              </div>
            )}
          </dialog>
        </>
      ) : (
        <>
          <section className="hero compact-hero">
            <h1>What do you want to grow?</h1>
            <p>
              Search one plant at a time. Choose a documented cultivar, keep the variety
              undecided, or save your own wording for later research.
            </p>
          </section>

          <section className="profile-summary" aria-label="Garden context">
            <div>
              <p className="section-kicker">Garden saved</p>
              <h2>{profile.name}</h2>
              <p className="profile-location">{profile.location_input}</p>
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
                <dt>Physical limits</dt>
                <dd>
                  {profile.support_available === null
                    ? "Support not specified"
                    : profile.support_available
                      ? "Support available"
                      : "No support"}
                  {profile.max_plant_spread_inches
                    ? ` · ${profile.max_plant_spread_inches} in per plant`
                    : ""}
                </dd>
              </div>
              <div>
                <dt>Priorities</dt>
                <dd>
                  {[...profile.intended_uses, ...profile.disease_concerns]
                    .map(humanize)
                    .join(", ") || "None selected"}
                </dd>
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
            <section className="selected-plants" aria-labelledby="selected-plants-heading">
              <div className="selected-plants-heading">
                <div>
                  <p className="section-kicker">Current wishlist</p>
                  <h3 id="selected-plants-heading">Selected plants</h3>
                </div>
                {!loadingWishlist && wishlist && (
                  <span>
                    {wishlist.entries.length} {wishlist.entries.length === 1 ? "plant" : "plants"}
                  </span>
                )}
              </div>
              {loadingWishlist ? (
                <p className="selected-plants-empty">Loading saved plants…</p>
              ) : wishlist?.entries.length ? (
                <ul className="selected-plant-list">
                  {wishlist.entries.map((entry) => (
                    <li key={entry.id}>
                      <div>
                        <strong>{wishlistEntryName(entry)}</strong>
                        <span>{wishlistEntryKind(entry)}</span>
                      </div>
                      <div className="selected-plant-actions">
                        {entry.resolved_cultivar && (
                          <button
                            className="guide-link-button"
                            type="button"
                            disabled={loadingGrowGuide && guideCultivarSlug === entry.resolved_cultivar.slug}
                            onClick={() => void showGrowGuide(entry.resolved_cultivar!)}
                          >
                            {loadingGrowGuide && guideCultivarSlug === entry.resolved_cultivar.slug
                              ? "Loading guide…"
                              : "Grow guide"}
                          </button>
                        )}
                        <button
                          type="button"
                          disabled={removingEntry !== null}
                          onClick={() => void removeEntry(entry)}
                          aria-label={`Remove ${wishlistEntryName(entry)}`}
                        >
                          {removingEntry === entry.id ? "Removing…" : "Remove"}
                        </button>
                      </div>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="selected-plants-empty">
                  No plants selected yet. Search the catalog to start this garden’s wishlist.
                </p>
              )}
              {reviewCount > 0 && (
                <a className="review-link" href="#wishlist-review">
                  Review {reviewCount} uncertain {reviewCount === 1 ? "entry" : "entries"} below
                </a>
              )}
              {addedNotice && (
                <p className="selection-notice" role="status">
                  {addedNotice}
                </p>
              )}
            </section>
            <button className="text-button" type="button" onClick={switchGardenProfile}>
              Switch garden
            </button>
          </section>

          {guideCultivarSlug && (
            <section
              aria-busy={loadingGrowGuide}
              aria-live="polite"
              className="grow-guide"
              ref={growGuideRef}
              tabIndex={-1}
            >
              <div className="grow-guide-heading">
                <div>
                  <p className="section-kicker">Cultivar-aware grow guide</p>
                  <h2>{growGuide?.cultivar_name ?? "Building your guide…"}</h2>
                  {growGuide && (
                    <p>
                      {growGuide.crop_name} · {growGuide.garden_name} · {growGuide.target_year}
                    </p>
                  )}
                </div>
                <button className="text-button" type="button" onClick={closeGrowGuide}>
                  Close guide
                </button>
              </div>

              {loadingGrowGuide && <p className="guide-loading">Combining reviewed evidence…</p>}

              {growGuide && (
                <>
                  <p className="guide-summary">{growGuide.summary}</p>

                  {growGuide.conflicts.length > 0 && (
                    <div className="guide-conflicts" role="note">
                      <strong>Garden conflicts</strong>
                      <ul>
                        {growGuide.conflicts.map((conflict) => (
                          <li key={conflict}>{conflict}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  <section className="guide-timeline" aria-labelledby="guide-timeline-heading">
                    <div>
                      <p className="section-kicker">Local timeline</p>
                      <h3 id="guide-timeline-heading">Planning dates</h3>
                    </div>
                    {growGuide.timeline.length > 0 ? (
                      <ol>
                        {growGuide.timeline.map((event) => (
                          <li key={event.code}>
                            <time dateTime={event.start_date}>
                              {formatGuideDate(event.start_date)}
                              {event.end_date && event.end_date !== event.start_date
                                ? ` – ${formatGuideDate(event.end_date)}`
                                : ""}
                            </time>
                            <div>
                              <strong>{event.title}</strong>
                              <p>{event.summary}</p>
                              <details className="guide-sources">
                                <summary>
                                  {event.evidence.length} evidence {event.evidence.length === 1 ? "record" : "records"}
                                </summary>
                                <ul>
                                  {event.evidence.map((evidence, index) => (
                                    <li key={`${event.code}-${evidence.field_name}-${index}`}>
                                      {evidence.source_url ? (
                                        <a href={evidence.source_url} target="_blank" rel="noreferrer">
                                          {evidence.publisher ?? evidence.title ?? humanize(evidence.origin)}
                                        </a>
                                      ) : (
                                        <strong>
                                          {evidence.publisher ?? evidence.title ?? humanize(evidence.origin)}
                                        </strong>
                                      )}
                                      {evidence.source_locator && <span>{evidence.source_locator}</span>}
                                    </li>
                                  ))}
                                </ul>
                              </details>
                            </div>
                          </li>
                        ))}
                      </ol>
                    ) : (
                      <p className="guide-empty">
                        A local timeline needs both a reviewed relative planting rule and climate
                        normals for this garden.
                      </p>
                    )}
                  </section>

                  <div className="guide-section-grid">
                    {growGuide.sections.map((section) => (
                      <article className={`guide-section ${section.status}`} key={section.code}>
                        <div className="guide-section-heading">
                          <h3>{section.title}</h3>
                          <span>{humanize(section.status)}</span>
                        </div>
                        <p>{section.summary}</p>
                        {section.instructions.length > 1 && (
                          <ul>
                            {section.instructions.map((instruction) => (
                              <li key={instruction}>{instruction}</li>
                            ))}
                          </ul>
                        )}
                        <p className="guide-provenance">
                          {section.provenance === "crop_baseline"
                            ? "Inherited crop guidance"
                            : section.provenance === "cultivar"
                              ? "Cultivar-specific guidance"
                              : section.provenance === "mixed"
                                ? "Crop and cultivar evidence"
                                : "Evidence needed"}
                          {section.confidence ? ` · ${humanize(section.confidence)} confidence` : ""}
                        </p>
                        {section.missing_evidence.length > 0 && (
                          <p className="guide-gap">
                            Missing: {section.missing_evidence.join("; ")}
                          </p>
                        )}
                        {section.evidence.length > 0 && (
                          <details className="guide-sources">
                            <summary>
                              {section.evidence.length} evidence {section.evidence.length === 1 ? "record" : "records"}
                            </summary>
                            <ul>
                              {section.evidence.map((evidence, index) => (
                                <li key={`${evidence.field_name}-${evidence.source_document_id}-${index}`}>
                                  {evidence.source_url ? (
                                    <a href={evidence.source_url} target="_blank" rel="noreferrer">
                                      {evidence.publisher ?? evidence.title ?? humanize(evidence.origin)}
                                    </a>
                                  ) : (
                                    <strong>
                                      {evidence.publisher ?? evidence.title ?? humanize(evidence.origin)}
                                    </strong>
                                  )}
                                  {evidence.source_locator && <span>{evidence.source_locator}</span>}
                                  {evidence.inherited_from_crop && <span>Inherited from crop baseline</span>}
                                </li>
                              ))}
                            </ul>
                          </details>
                        )}
                      </article>
                    ))}
                  </div>

                  <details className="guide-audit">
                    <summary>Guide assumptions and reproducibility</summary>
                    {growGuide.assumptions.length > 0 && (
                      <ul>
                        {growGuide.assumptions.map((assumption) => (
                          <li key={assumption}>{assumption}</li>
                        ))}
                      </ul>
                    )}
                    <dl>
                      <div>
                        <dt>Guide algorithm</dt>
                        <dd>{growGuide.algorithm_version}</dd>
                      </div>
                      <div>
                        <dt>Cultivar dataset</dt>
                        <dd>{growGuide.cultivar_dataset_id}</dd>
                      </div>
                      <div>
                        <dt>Input fingerprint</dt>
                        <dd>{growGuide.input_fingerprint}</dd>
                      </div>
                    </dl>
                  </details>
                </>
              )}
            </section>
          )}

          <section className="catalog-panel" aria-label="Catalog search">
            <form className="catalog-search" onSubmit={submitCatalogSearch}>
              <label htmlFor="catalog-query">Crop or cultivar</label>
              <div className="search-row">
                <input
                  id="catalog-query"
                  ref={catalogQueryRef}
                  type="search"
                  maxLength={120}
                  placeholder="Try tomatoes or San Marzano"
                  autoComplete="off"
                  value={searchQuery}
                  onChange={(event) => updateCatalogQuery(event.target.value)}
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

            {!searchQuery.trim() && (
              <section className="crop-browser" aria-labelledby="crop-browser-heading">
                <div className="crop-browser-heading">
                  <div>
                    <p className="section-kicker">Browse the catalog</p>
                    <h2 id="crop-browser-heading">Choose a crop to see its cultivars</h2>
                  </div>
                  {!loadingBrowseCrops && !browseCropsError && (
                    <p>{browseCrops.length} crops</p>
                  )}
                </div>
                {loadingBrowseCrops && <p className="crop-browser-status">Loading crops…</p>}
                {browseCropsError && (
                  <p className="crop-browser-status" role="alert">
                    {browseCropsError} You can still search by name above.
                  </p>
                )}
                {!loadingBrowseCrops && !browseCropsError && (
                  <>
                    <div
                      className="crop-browser-filters"
                      role="group"
                      aria-label="Filter crops by category"
                    >
                      <button
                        className="crop-browser-filter"
                        type="button"
                        aria-pressed={browseCategoryKey === "all"}
                        onClick={() => setBrowseCategoryKey("all")}
                      >
                        All crops <span>{browseCrops.length}</span>
                      </button>
                      {browseCategories.map((category) => (
                        <button
                          className="crop-browser-filter"
                          type="button"
                          key={category.key}
                          aria-pressed={browseCategoryKey === category.key}
                          onClick={() => setBrowseCategoryKey(category.key)}
                        >
                          {category.title} <span>{category.crops.length}</span>
                        </button>
                      ))}
                    </div>
                    <div className="crop-browser-list-heading">
                      <h3>{selectedBrowseCategory?.title ?? "All crops"}</h3>
                      <p>Alphabetical · {visibleBrowseCrops.length} crops</p>
                    </div>
                    <div className="crop-browser-list">
                      {visibleBrowseCrops.map((crop) => (
                        <button
                          className="crop-browser-button"
                          type="button"
                          key={crop.slug}
                          disabled={searching}
                          onClick={() => void searchCatalog(crop.canonical_name)}
                        >
                          {crop.canonical_name}
                        </button>
                      ))}
                    </div>
                  </>
                )}
              </section>
            )}

            {searchQuery.trim() && searchResults && (
              <div className="search-results" aria-live="polite">
                <div className="search-results-heading">
                  <div>
                    <p className="section-kicker">Catalog matches</p>
                    <h2>Results for “{searchResults.query}”</h2>
                  </div>
                  <div className="search-results-summary">
                    <p>
                      {searchResults.crop_choices.length + searchResults.cultivars.length}{" "}
                      documented choices
                    </p>
                    <button
                      className="secondary-button"
                      type="button"
                      onClick={clearCatalogSearch}
                    >
                      Clear search
                    </button>
                  </div>
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
                          disabled={addingSelection !== null || loadingWishlist}
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
                      const seedListing = result.cultivar.commercial_listings[0];
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
                          <p className={`research-quality ${result.research_quality.tier}`}>
                            Research: {humanize(result.research_quality.tier)} ·{" "}
                            {result.research_quality.score}/100 ·{" "}
                            {result.research_quality.source_count}{" "}
                            {result.research_quality.source_count === 1 ? "source" : "sources"}
                          </p>
                          {seedListing && (
                            <p className="evidence-note">
                              Seed listing: {seedListing.vendor} ·{" "}
                              {seedListing.availability_status === "in_stock"
                                ? "in stock"
                                : seedListing.availability_status === "out_of_stock"
                                  ? "currently out of stock"
                                  : "availability not confirmed"}
                              {seedListing.source.source_url && (
                                <>
                                  {" · "}
                                  <a
                                    href={seedListing.source.source_url}
                                    rel="noreferrer"
                                    target="_blank"
                                  >
                                    View listing
                                  </a>
                                </>
                              )}
                            </p>
                          )}
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
                            <details className="suitability-details">
                              <summary>
                                Review all {result.suitability.dimensions.length} checks ·{" "}
                                {result.suitability.evidence_quality}% evidence coverage
                              </summary>
                              <dl>
                                {result.suitability.dimensions.map((dimension) => (
                                  <div key={dimension.code}>
                                    <dt>
                                      {dimension.label} · {humanize(dimension.status)}
                                    </dt>
                                    <dd>{dimension.explanation}</dd>
                                  </div>
                                ))}
                              </dl>
                            </details>
                            <details className="suitability-details">
                              <summary>Why this research rating?</summary>
                              <p>{result.research_quality.strengths.join(" ")}</p>
                              {result.research_quality.missing_evidence.length > 0 && (
                                <p className="missing-note">
                                  Research gaps: {result.research_quality.missing_evidence.join("; ")}
                                </p>
                              )}
                            </details>
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
                            disabled={addingSelection !== null || loadingWishlist}
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
                        disabled={addingSelection !== null || loadingWishlist}
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
                      disabled={addingSelection !== null || loadingWishlist}
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
              </div>
            )}
          </section>

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
                  disabled={matchingWishlist || loadingWishlist || !text.trim()}
                  type="submit"
                >
                  {matchingWishlist ? "Matching…" : "Match my list"}
                </button>
              </div>
            </form>
          </details>
        </>
      )}

      {error && profile && (
        <p className="error-message" role="alert">
          {error}
        </p>
      )}

      {profile && wishlist && wishlist.entries.length > 0 && (
        <section className="results" id="wishlist-review" aria-live="polite">
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
                    <div className="entry-actions">
                      <span className="status-label">{entry.status.replace("_", " ")}</span>
                      <button
                        className="text-button"
                        type="button"
                        disabled={removingEntry !== null}
                        onClick={() => void removeEntry(entry)}
                      >
                        {removingEntry === entry.id ? "Removing…" : "Remove"}
                      </button>
                    </div>
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
