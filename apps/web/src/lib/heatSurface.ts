export type HeatGradient = Record<number, string>;

const clamp01 = (v: number) => Math.max(0, Math.min(1, v));

export function sortedStops(gradient: HeatGradient) {
  return Object.entries(gradient).map(([position, color]) => ({
    position: Number(position), color,
  })).sort((a, b) => a.position - b.position);
}

export function heatLegend(gradient: HeatGradient): string {
  return "linear-gradient(90deg, " + sortedStops(gradient)
    .map(({ position, color }) => color + " " + position * 100 + "%").join(", ") + ")";
}

export function heatAlpha(weight: number): number {
  const w = clamp01(weight);
  const knots = [[0, 0], [0.12, 0.015], [0.25, 0.25], [0.4, 0.62],
    [0.55, 0.83], [0.7, 0.93], [1, 0.98]];
  for (let i = 1; i < knots.length; i++) {
    const [b, y] = knots[i];
    const [a, x] = knots[i - 1];
    if (w <= b) return Math.round(255 * (x + (y - x) * (w - a) / (b - a)));
  }
  return 250;
}

export function sampleHeat(field: Float32Array, cols: number, rows: number, x: number, y: number): number {
  const ix = Math.floor(x), iy = Math.floor(y);
  const tx = x - ix, ty = y - iy;
  const sx = tx * tx * (3 - 2 * tx), sy = ty * ty * (3 - 2 * ty);
  const at = (cx: number, cy: number) =>
    cx < 0 || cy < 0 || cx >= cols || cy >= rows ? 0 : field[cy * cols + cx];
  const top = at(ix, iy) * (1 - sx) + at(ix + 1, iy) * sx;
  const bottom = at(ix, iy + 1) * (1 - sx) + at(ix + 1, iy + 1) * sx;
  return clamp01(top * (1 - sy) + bottom * sy);
}

export function heatPalette(gradient: HeatGradient, steps = 1024): Uint8ClampedArray {
  const stops = sortedStops(gradient).map(({ position, color }) => {
    const n = Number.parseInt(color.slice(1), 16);
    return { position, rgb: [(n >> 16) & 255, (n >> 8) & 255, n & 255] };
  });
  const palette = new Uint8ClampedArray((steps + 1) * 4);
  let j = 0;
  for (let i = 0; i <= steps; i++) {
    const w = i / steps;
    while (j < stops.length - 1 && w > stops[j + 1].position) j++;
    const a = stops[j], b = stops[Math.min(j + 1, stops.length - 1)];
    const t = a.position === b.position ? 0 : clamp01((w - a.position) / (b.position - a.position));
    for (let k = 0; k < 3; k++) palette[i * 4 + k] = a.rgb[k] + (b.rgb[k] - a.rgb[k]) * t;
    palette[i * 4 + 3] = heatAlpha(w);
  }
  return palette;
}
