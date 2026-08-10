import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import CropBrowser, { type BrowseCrop } from "./CropBrowser";

const crops: BrowseCrop[] = [
  {
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
    searchable_cultivar_count: 6
  },
  {
    slug: "carrots",
    canonical_name: "Carrots",
    planning_category: "annual_crop",
    commodity_section_key: "carrots-source",
    commodity_section_title: "Carrots",
    commodity_section_position: 4,
    browse_category_key: "roots-tubers-alliums",
    browse_category_title: "Roots, tubers & alliums",
    browse_category_position: 1,
    documented_cultivar_count: 0,
    searchable_cultivar_count: 0
  },
  {
    slug: "beets",
    canonical_name: "Beets",
    planning_category: "annual_crop",
    commodity_section_key: "beets-source",
    commodity_section_title: "Beets",
    commodity_section_position: 3,
    browse_category_key: "roots-tubers-alliums",
    browse_category_title: "Roots, tubers & alliums",
    browse_category_position: 1,
    documented_cultivar_count: 9,
    searchable_cultivar_count: 9
  },
  {
    slug: "asparagus",
    canonical_name: "Asparagus",
    planning_category: "perennial",
    commodity_section_key: "asparagus-source",
    commodity_section_title: "Asparagus",
    commodity_section_position: 1,
    browse_category_key: "perennial-crops",
    browse_category_title: "Perennial crops",
    browse_category_position: 7,
    documented_cultivar_count: 0,
    searchable_cultivar_count: 0
  }
];

afterEach(cleanup);

describe("CropBrowser", () => {
  it("starts alphabetically and labels documented and missing cultivar coverage", () => {
    const { container } = render(
      <CropBrowser
        crops={crops}
        loading={false}
        error={null}
        searching={false}
        onSelectCrop={() => undefined}
      />
    );

    const names = [...container.querySelectorAll(".crop-browser-button-name")].map(
      (element) => element.textContent
    );
    expect(names).toEqual(["Asparagus", "Beets", "Carrots", "Tomatoes"]);
    expect(screen.getAllByText("No documented cultivars")).toHaveLength(2);
    expect(screen.getByText("8 documented · 6 listed")).toBeTruthy();
    expect(screen.getByText("9 documented · 9 listed")).toBeTruthy();
  });

  it("filters categories and passes the precise crop selection to search", async () => {
    const user = userEvent.setup();
    const onSelectCrop = vi.fn();
    render(
      <CropBrowser
        crops={crops}
        loading={false}
        error={null}
        searching={false}
        onSelectCrop={onSelectCrop}
      />
    );

    await user.click(screen.getByRole("button", { name: /Roots, tubers & alliums 2/ }));
    expect(screen.queryByText("Tomatoes")).toBeNull();
    await user.click(screen.getByRole("button", { name: /Beets, 9 documented/ }));
    expect(onSelectCrop).toHaveBeenCalledWith("Beets");
  });
});
