import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";

const garden = {
  id: "garden-1",
  name: "Test garden",
  location_input: "20910",
  postal_code: "20910",
  latitude: 39,
  longitude: -77,
  target_year: 2026,
  experience_level: "beginner",
  growing_methods: ["raised_bed"],
  support_available: null,
  max_plant_spread_inches: null,
  max_container_volume_gallons: null,
  intended_uses: [],
  disease_concerns: [],
  location_status: "resolved",
  coordinate_method: "test",
  location_source: null,
  hardiness: null,
  climate_normals: null,
  created_at: "2026-08-09T00:00:00Z",
  updated_at: "2026-08-09T00:00:00Z"
};

const tomato = {
  slug: "tomatoes",
  canonical_name: "Tomatoes",
  planning_category: "annual_crop",
  commodity_section_key: "tomatoes-source",
  commodity_section_title: "Tomatoes",
  commodity_section_position: 29,
  browse_category_key: "fruiting-crops",
  browse_category_title: "Tomatoes, peppers & other fruiting crops",
  browse_category_position: 5,
  documented_cultivar_count: 8,
  searchable_cultivar_count: 6,
  aliases: ["tomato", "tomatoes"],
  seasons: ["Early Summer"]
};

const emptyWishlist = {
  id: "wishlist-1",
  dataset_id: "crop-dataset-1",
  cultivar_dataset_id: "cultivar-dataset-1",
  garden_profile_id: garden.id,
  name: "Garden wishlist",
  entries: []
};

function jsonResponse(body: object): Response {
  return {
    ok: true,
    status: 200,
    json: async () => body,
    text: async () => JSON.stringify(body)
  } as Response;
}

const localValues = new Map<string, string>();
const testLocalStorage = {
  get length() {
    return localValues.size;
  },
  clear: () => localValues.clear(),
  getItem: (key: string) => localValues.get(key) ?? null,
  key: (index: number) => [...localValues.keys()][index] ?? null,
  removeItem: (key: string) => localValues.delete(key),
  setItem: (key: string, value: string) => localValues.set(key, value)
} as Storage;

beforeEach(() => {
  Object.defineProperty(window, "localStorage", {
    configurable: true,
    value: testLocalStorage
  });
});

afterEach(() => {
  cleanup();
  testLocalStorage.clear();
  vi.unstubAllGlobals();
});

describe("catalog browse workflow", () => {
  it("searches from browse, adds the crop, and returns to all crops when cleared", async () => {
    window.localStorage.setItem("kitchen-almanac-profile-id", garden.id);
    const updatedWishlist = {
      ...emptyWishlist,
      entries: [
        {
          id: "entry-1",
          position: 0,
          original_text: "Tomatoes",
          normalized_text: "tomatoes",
          status: "resolved",
          resolution_method: "catalog_selection",
          intent_kind: "crop",
          cultivar_intent_text: null,
          crop_type_intent: null,
          resolved_crop: {
            slug: "tomatoes",
            canonical_name: "Tomatoes",
            planning_category: "annual_crop"
          },
          resolved_cultivar: null,
          candidates: [],
          cultivar_candidates: []
        }
      ]
    };
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/garden-profiles") return jsonResponse({ profiles: [garden] });
      if (url === "/api/crops") {
        return jsonResponse({
          dataset_id: "crop-dataset-1",
          cultivar_dataset_id: "cultivar-dataset-1",
          crops: [tomato]
        });
      }
      if (url === `/api/garden-profiles/${garden.id}/wishlists/active`) {
        return jsonResponse(emptyWishlist);
      }
      if (url.startsWith("/api/catalog/search?")) {
        return jsonResponse({
          query: "Tomatoes",
          normalized_query: "tomatoes",
          crop_choices: [
            {
              crop: {
                slug: "tomatoes",
                canonical_name: "Tomatoes",
                planning_category: "annual_crop"
              },
              score: 100,
              matched_alias: "Tomatoes",
              match_method: "exact"
            }
          ],
          cultivars: [],
          can_add_custom: true
        });
      }
      if (
        url === `/api/wishlists/${emptyWishlist.id}/entries` &&
        init?.method === "POST"
      ) {
        return jsonResponse(updatedWishlist);
      }
      throw new Error(`Unexpected request: ${init?.method ?? "GET"} ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);

    await user.click(
      await screen.findByRole("button", { name: /Tomatoes, 8 documented · 6 listed/ })
    );
    expect(await screen.findByRole("heading", { name: "Results for “Tomatoes”" })).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Add crop" }));
    expect(await screen.findByText("Tomatoes added to your wishlist.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Remove Tomatoes" })).toBeTruthy();

    await user.click(screen.getByRole("button", { name: "Clear search" }));
    expect(
      await screen.findByRole("heading", { name: "Choose a crop to see its cultivars" })
    ).toBeTruthy();
    expect(screen.getByRole("button", { name: /All crops 1/ }).getAttribute("aria-pressed"))
      .toBe("true");
  });
});
