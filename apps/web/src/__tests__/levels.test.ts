// Legend and colour logic (RF-01, RF-07, HU-02, HU-21, HU-27).
import { describe, expect, it } from "vitest";

import type { Legend } from "../api/types";
import { classBands, colorFor, inkOn, RAMP } from "../lib/levels";

const legend: Legend = {
  threshold_set_id: "levels-v1",
  version: "levels-v1",
  method: "fixed",
  bands: [
    { level: "low", min_index: 0, max_index: 40, label: "Low" },
    { level: "medium", min_index: 40, max_index: 70, label: "Medium" },
    { level: "high", min_index: 70, max_index: 100, label: "High" },
  ],
  no_result_label: "No result",
};

describe("classBands", () => {
  const bands = classBands(legend);
  it("splits the three API levels into six ordered classes", () => {
    expect(bands.map((b) => [b.min, b.max])).toEqual([
      [0, 20], [20, 40], [40, 55], [55, 70], [70, 85], [85, 100],
    ]);
    expect(bands.map((b) => b.level)).toEqual(["low", "low", "medium", "medium", "high", "high"]);
  });
  it("colours by the level cut points of the API, not hard-coded ones", () => {
    expect(colorFor(39.9, bands)).toBe(RAMP[1]);
    expect(colorFor(40, bands)).toBe(RAMP[2]);
    expect(colorFor(70, bands)).toBe(RAMP[4]);
    expect(colorFor(100, bands)).toBe(RAMP[5]);
  });
  it("never colours a missing result as low risk", () => {
    expect(colorFor(null, bands)).toBeNull();
  });
});

describe("inkOn", () => {
  it("uses white text on the dark half of the ramp for contrast", () => {
    expect(inkOn(RAMP[5])).toBe("#FFFFFF");
    expect(inkOn(RAMP[0])).toBe("#18191B");
  });
});
