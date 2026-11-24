// Continuous scalar interpolation of the 1 km cell values. Colour and opacity
// are applied after interpolation to retain defined hotspots and readable maps.
import L from "leaflet";
import { useEffect, useMemo, useRef } from "react";

import type { UnitCollection } from "../api/types";
import { addScopeMask, createBaseMap } from "../lib/basemap";
import { heatPalette, sampleHeat } from "../lib/heatSurface";

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

const UPSCALE = 24;
const PALETTE_STEPS = 1024;

function boxes(cells: UnitCollection): CellBox[] {
  return cells.features.map((f) => {
    const b = L.geoJSON(f as unknown as GeoJSON.Feature).getBounds();
    return { id: f.properties.unit_id, south: b.getSouth(), west: b.getWest(), north: b.getNorth(), east: b.getEast() };
  });
}

const median = (v: number[]) => [...v].sort((a, b) => a - b)[Math.floor(v.length / 2)];

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
    const field = new Float32Array(grid.cols * grid.rows);
    for (const c of grid.pos) {
      const w = p.weight(c.id);
      if (Number.isFinite(w) && w > 0) field[c.y * grid.cols + c.x] = Math.min(1, w);
    }
    const palette = heatPalette(p.gradient, PALETTE_STEPS);
    const canvas = document.createElement("canvas");
    canvas.width = grid.cols * UPSCALE;
    canvas.height = grid.rows * UPSCALE;
    const ctx = canvas.getContext("2d")!;
    const img = ctx.createImageData(canvas.width, canvas.height);
    for (let y = 0; y < canvas.height; y++) {
      const gy = (y + 0.5) / UPSCALE - 0.5;
      for (let x = 0; x < canvas.width; x++) {
        const w = sampleHeat(field, grid.cols, grid.rows, (x + 0.5) / UPSCALE - 0.5, gy);
        const index = Math.round(w * PALETTE_STEPS) * 4;
        const pixel = (y * canvas.width + x) * 4;
        img.data[pixel] = palette[index];
        img.data[pixel + 1] = palette[index + 1];
        img.data[pixel + 2] = palette[index + 2];
        img.data[pixel + 3] = palette[index + 3];
      }
    }
    ctx.putImageData(img, 0, 0);
    ctx.globalCompositeOperation = "destination-in";
    ctx.beginPath();
    const bounds = grid.bounds;
    for (const feature of p.scope.features) {
      const polygons = feature.geometry.type === "Polygon" ? [feature.geometry.coordinates] : feature.geometry.coordinates;
      for (const polygon of polygons) {
        for (const ring of polygon) {
          ring.forEach(([lng, lat], i) => {
            const x = (lng - bounds.getWest()) / (bounds.getEast() - bounds.getWest()) * canvas.width;
            const y = (bounds.getNorth() - lat) / (bounds.getNorth() - bounds.getSouth()) * canvas.height;
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
          });
          ctx.closePath();
        }
      }
    }
    ctx.fillStyle = "#fff";
    ctx.fill("evenodd");
    overlay.current?.remove();
    overlay.current = L.imageOverlay(canvas.toDataURL("image/png"), grid.bounds, { opacity: 1, interactive: false }).addTo(m);
  }, [p.version, p.weight, p.gradient, p.scope, grid]);

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
