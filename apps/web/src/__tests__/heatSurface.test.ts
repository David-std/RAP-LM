import { describe, expect, it } from "vitest";
import { heatAlpha, heatLegend, heatPalette, sampleHeat } from "../lib/heatSurface";

describe("continuous heat surface", () => {
  it("preserves peaks and zero values at cell centres without adding intensity", () => {
    const field = new Float32Array([0, 1, 0.25, 0.5]);
    expect(sampleHeat(field, 2, 2, 0, 0)).toBe(0);
    expect(sampleHeat(field, 2, 2, 1, 0)).toBe(1);
    expect(sampleHeat(field, 2, 2, 0, 1)).toBe(0.25);
    expect(sampleHeat(field, 2, 2, 0.5, 0)).toBe(0.5);
    expect(sampleHeat(field, 2, 2, -1, 0)).toBe(0);
    for (let y = -1; y < 3; y += 0.1) for (let x = -1; x < 3; x += 0.1) {
      expect(sampleHeat(field, 2, 2, x, y)).toBeGreaterThanOrEqual(0);
      expect(sampleHeat(field, 2, 2, x, y)).toBeLessThanOrEqual(1);
    }
  });
  it("fades low weights and keeps higher values visible", () => {
    expect(heatAlpha(0)).toBe(0);
    expect(heatAlpha(0.1)).toBeLessThan(5);
    expect(heatAlpha(0.5)).toBeGreaterThan(150);
    expect(heatAlpha(1)).toBeGreaterThan(245);
  });
  it("uses identical sorted gradient stops in the raster and legend", () => {
    const ramp = { 0: "#0000FF", 1: "#FF0000", 0.5: "#00FF00" };
    const p = heatPalette(ramp, 100);
    expect([...p.slice(200, 203)]).toEqual([0, 255, 0]);
    expect([...p.slice(400, 403)]).toEqual([255, 0, 0]);
    expect(heatLegend(ramp)).toBe("linear-gradient(90deg, #0000FF 0%, #00FF00 50%, #FF0000 100%)");
  });
});
