// Continuous heat map of the selected layer (estimated risk, recorded density or
// Grad-CAM). Each 1 km cell becomes one pixel of a small raster coloured with
// the layer ramp; the raster is upsampled with bilinear smoothing and a light
// blur, so the surface is continuous but every colour still maps to the
// legend (no kernel sums that saturate dense areas). Hovering any point
// identifies the cell under the cursor; a click opens it in the zone panel.

import L from "leaflet";
import { useEffect, useMemo, useRef } from "react";

import type { UnitCollection } from "../api/types";
import { addScopeMask, createBaseMap } from "../lib/basemap";

interface CellBox {
  id: string;
  south: number;
  west: number;
  north: number;
  east: number;
}

interface Props {
  cells: UnitCollection;
  scope: UnitCollection;
  weight: (unitId: string) => number; // 0..1, 0 = transparent
  gradient: Record<number, string>; // stop (0..1) -> colour
  version: string; // changes when the weights change
  selected: string | null;
  onSelect: (unitId: string) => void;
  onHover: (unitId: string | null) => void;
}

const UPSCALE = 12;

function boxes(cells: UnitCollection): CellBox[] {
  return cells.features.map((f) => {
    const b = L.geoJSON(f as unknown as GeoJSON.Feature).getBounds();
    return { id: f.properties.unit_id, south: b.getSouth(), west: b.getWest(), north: b.getNorth(), east: b.getEast() };
  });
}

const median = (v: number[]) => [...v].sort((a, b) => a - b)[Math.floor(v.length / 2)];

function hexToRgb(hex: string): [number, number, number] {
  const n = parseInt(hex.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

/** Linear interpolation over the gradient stops. */
function rampColor(stops: [number, [number, number, number]][], w: number): [number, number, number] {
  if (w <= stops[0][0]) return stops[0][1];
  for (let i = 1; i < stops.length; i++) {
    const [p1, c1] = stops[i];
    const [p0, c0] = stops[i - 1];
    if (w <= p1) {
      const t = (w - p0) / (p1 - p0);
      return [0, 1, 2].map((k) => Math.round(c0[k] + t * (c1[k] - c0[k]))) as [number, number, number];
    }
  }
  return stops[stops.length - 1][1];
}

export function HeatMap(p: Props) {
  const host = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const overlay = useRef<L.ImageOverlay | null>(null);
  const marker = useRef<L.Rectangle | null>(null);
  const cellBoxes = useMemo(() => boxes(p.cells), [p.cells]);
  const handlers = useRef(p);
  handlers.current = p;

  // Raster geometry: grid step and extent from the cell bounds.
  const grid = useMemo(() => {
    const dx = median(cellBoxes.map((c) => c.east - c.west));
    const dy = median(cellBoxes.map((c) => c.north - c.south));
    const west = Math.min(...cellBoxes.map((c) => c.west));
    const north = Math.max(...cellBoxes.map((c) => c.north));
    const cols = Math.round((Math.max(...cellBoxes.map((c) => c.east)) - west) / dx) + 1;
    const rows = Math.round((north - Math.min(...cellBoxes.map((c) => c.south))) / dy) + 1;
    const pos = cellBoxes.map((c) => ({
      id: c.id,
      x: Math.min(cols - 1, Math.floor(((c.west + c.east) / 2 - west) / dx)),
      y: Math.min(rows - 1, Math.floor((north - (c.north + c.south) / 2) / dy)),
    }));
    const bounds = L.latLngBounds([north - rows * dy, west], [north, west + cols * dx]);
    return { cols, rows, pos, bounds };
  }, [cellBoxes]);

  useEffect(() => {
    if (!host.current) return;
    const m = createBaseMap(host.current, L.canvas());
    const mask = addScopeMask(m, p.scope);
    const find = (ll: L.LatLng) =>
      cellBoxes.find((c) => ll.lat >= c.south && ll.lat <= c.north && ll.lng >= c.west && ll.lng <= c.east)?.id ?? null;
    m.on("mousemove", (e: L.LeafletMouseEvent) => handlers.current.onHover(find(e.latlng)));
    m.on("mouseout", () => handlers.current.onHover(null));
    m.on("click", (e: L.LeafletMouseEvent) => {
      const id = find(e.latlng);
      if (id) handlers.current.onSelect(id);
    });
    map.current = m;
    return () => {
      mask.remove();
      m.remove();
      map.current = null;
    };
  }, [cellBoxes, p.scope]);

  useEffect(() => {
    const m = map.current;
    if (!m) return;
    const stops = Object.entries(p.gradient)
      .map(([k, v]) => [Number(k), hexToRgb(v)] as [number, [number, number, number]])
      .sort((a, b) => a[0] - b[0]);
    const small = document.createElement("canvas");
    small.width = grid.cols;
    small.height = grid.rows;
    const sctx = small.getContext("2d")!;
    const img = sctx.createImageData(grid.cols, grid.rows);
    for (const c of grid.pos) {
      const w = p.weight(c.id);
      if (!(w > 0)) continue;
      const [r, g, b] = rampColor(stops, Math.min(1, w));
      // Low values fade out so the base map stays readable; high values stay opaque.
      img.data.set([r, g, b, Math.round(40 + 200 * Math.min(1, w))], (c.y * grid.cols + c.x) * 4);
    }
    sctx.putImageData(img, 0, 0);
    const big = document.createElement("canvas");
    big.width = grid.cols * UPSCALE;
    big.height = grid.rows * UPSCALE;
    const bctx = big.getContext("2d")!;
    bctx.imageSmoothingEnabled = true;
    bctx.imageSmoothingQuality = "high";
    bctx.filter = `blur(${UPSCALE * 0.25}px)`;
    bctx.drawImage(small, 0, 0, big.width, big.height);
    overlay.current?.remove();
    overlay.current = L.imageOverlay(big.toDataURL("image/png"), grid.bounds, { opacity: 0.9, interactive: false }).addTo(m);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [p.version, grid]);

  useEffect(() => {
    const m = map.current;
    if (!m) return;
    marker.current?.remove();
    const c = cellBoxes.find((b) => b.id === p.selected);
    if (c) {
      marker.current = L.rectangle([[c.south, c.west], [c.north, c.east]], { color: "#16181d", weight: 2.4, fill: false }).addTo(m);
    }
  }, [p.selected, cellBoxes]);

  return <div ref={host} className="map" role="application" aria-label="Mapa de calor continuo" />;
}
