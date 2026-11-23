// Continuous heat map of the selected layer (estimated risk, recorded density or
// Grad-CAM). The surface is drawn from the cell centroids weighted by the layer
// value; hovering any point identifies the 1 km cell under the cursor so the
// analyst reads the exact values, and a click opens that cell in the zone panel.

import L from "leaflet";
import "leaflet.heat";
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
  weight: (unitId: string) => number; // 0..1
  gradient: Record<number, string>;
  version: string; // changes when the weights change
  selected: string | null;
  onSelect: (unitId: string) => void;
  onHover: (unitId: string | null) => void;
}

function boxes(cells: UnitCollection): CellBox[] {
  return cells.features.map((f) => {
    const b = L.geoJSON(f as unknown as GeoJSON.Feature).getBounds();
    return { id: f.properties.unit_id, south: b.getSouth(), west: b.getWest(), north: b.getNorth(), east: b.getEast() };
  });
}

export function HeatMap(p: Props) {
  const host = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const heat = useRef<L.HeatLayer | null>(null);
  const marker = useRef<L.Rectangle | null>(null);
  const cellBoxes = useMemo(() => boxes(p.cells), [p.cells]);
  const handlers = useRef(p);
  handlers.current = p;

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
    heat.current?.remove();
    const points: L.HeatLatLngTuple[] = cellBoxes
      .map((c) => [(c.south + c.north) / 2, (c.west + c.east) / 2, p.weight(c.id)] as L.HeatLatLngTuple)
      .filter((pt) => pt[2] > 0);
    heat.current = L.heatLayer(points, { radius: 22, blur: 18, max: 1, minOpacity: 0.25, maxZoom: 13, gradient: p.gradient }).addTo(m);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [p.version, cellBoxes]);

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
