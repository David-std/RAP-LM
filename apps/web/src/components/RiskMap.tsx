// Map and legend container (Figure 5C, RF-01, HU-01..HU-05).
// Leaflet is driven directly (not through react-leaflet) so that restyling
// ~2,900 polygons on a period change does not rebuild the layer.

import L from "leaflet";
import { useEffect, useRef } from "react";

import type { RiskResult, UnitCollection } from "../api/types";
import { addScopeMask, createBaseMap, LIMA_BOUNDS } from "../lib/basemap";
import { colorFor, type ClassBand } from "../lib/levels";

const HATCH_ID = "no-result-hatch";

export interface RiskMapProps {
  units: UnitCollection;
  outline?: UnitCollection; // district borders drawn over cells
  scope?: UnitCollection; // the 43 districts: everything outside is dimmed
  results: Map<string, RiskResult>;
  bands: ClassBand[];
  visible?: Set<string> | null; // units passing the filters (null = all)
  selected?: string[];
  labels?: Map<string, string>; // badge per unit (comparisons: A, B, C...)
  focus?: string | null; // unit to zoom to
  colorize?: (unitId: string) => string | null; // overrides the risk ramp (analysis maps)
  onSelect?: (unitId: string) => void;
  onHover?: (unitId: string | null, latlng: L.LatLng | null) => void;
  ariaLabel: string;
}

/** Inject the diagonal hatch used for "no result" units into the SVG renderer. */
function ensureHatch(renderer: L.SVG) {
  const svg = (renderer as unknown as { _container: SVGSVGElement })._container;
  if (!svg || svg.querySelector(`#${HATCH_ID}`)) return;
  const ns = "http://www.w3.org/2000/svg";
  const defs = document.createElementNS(ns, "defs");
  defs.innerHTML = `<pattern id="${HATCH_ID}" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
      <rect width="6" height="6" fill="#F4F4F1"/><line x1="0" y1="0" x2="0" y2="6" stroke="#A9A9A4" stroke-width="1.4"/></pattern>`;
  svg.insertBefore(defs, svg.firstChild);
}

export function RiskMap(props: RiskMapProps) {
  const host = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const layer = useRef<L.GeoJSON | null>(null);
  const outlineLayer = useRef<L.GeoJSON | null>(null);
  const labelLayer = useRef<L.LayerGroup | null>(null);
  const handlers = useRef(props);
  handlers.current = props;

  // Create the map once.
  useEffect(() => {
    if (!host.current) return;
    const renderer = L.svg({ padding: 0.3 });
    const m = createBaseMap(host.current, renderer);
    m.on("layeradd", () => ensureHatch(renderer));
    map.current = m;
    labelLayer.current = L.layerGroup().addTo(m);
    return () => {
      m.remove();
      map.current = null;
    };
  }, []);

  // (Re)build the unit layer when the geometry set changes (cell <-> district).
  useEffect(() => {
    const m = map.current;
    if (!m) return;
    layer.current?.remove();
    layer.current = L.geoJSON(props.units as GeoJSON.FeatureCollection, {
      style: () => ({ weight: 0.5, color: "#FFFFFF", fillOpacity: 0.9 }),
      onEachFeature: (feature, lyr) => {
        const id = (feature.properties as { unit_id: string }).unit_id;
        lyr.on("click", () => handlers.current.onSelect?.(id));
        lyr.on("mouseover", (e: L.LeafletMouseEvent) => handlers.current.onHover?.(id, e.latlng));
        lyr.on("mouseout", () => handlers.current.onHover?.(null, null));
      },
    }).addTo(m);
    outlineLayer.current?.bringToFront();
  }, [props.units]);

  // Dim everything outside the province of Lima (43 districts) so the scope is unambiguous.
  useEffect(() => {
    const m = map.current;
    if (!m || !props.scope) return;
    const mask = addScopeMask(m, props.scope);
    return () => {
      mask.remove();
    };
  }, [props.scope]);

  useEffect(() => {
    const m = map.current;
    if (!m) return;
    outlineLayer.current?.remove();
    outlineLayer.current = props.outline
      ? L.geoJSON(props.outline as GeoJSON.FeatureCollection, {
          interactive: false,
          style: { weight: 0.8, color: "#41444A", fill: false, opacity: 0.7 },
        }).addTo(m)
      : null;
  }, [props.outline]);

  // Restyle on every result / filter / selection change.
  useEffect(() => {
    const selected = new Set(props.selected ?? []);
    layer.current?.eachLayer((lyr) => {
      const path = lyr as L.Path & { feature: { properties: { unit_id: string } } };
      const id = path.feature.properties.unit_id;
      const result = props.results.get(id);
      const color = props.colorize ? props.colorize(id) : colorFor(result?.risk_index ?? null, props.bands);
      const inFilter = !props.visible || props.visible.has(id);
      const isSelected = selected.has(id);
      path.setStyle({
        fillColor: color ?? `url(#${HATCH_ID})`,
        fillOpacity: inFilter ? (color ? 0.82 : 0.9) : 0.1,
        color: isSelected ? "#16181D" : "#FFFFFF",
        weight: isSelected ? 2.4 : 0.4,
        opacity: inFilter || isSelected ? 1 : 0.3,
      });
      if (isSelected) path.bringToFront();
    });
    outlineLayer.current?.bringToFront();
  }, [props.results, props.bands, props.visible, props.selected, props.colorize]);

  // Badges for compared units.
  useEffect(() => {
    const group = labelLayer.current;
    if (!group || !layer.current) return;
    group.clearLayers();
    if (!props.labels) return;
    layer.current.eachLayer((lyr) => {
      const poly = lyr as L.Polygon & { feature: { properties: { unit_id: string } } };
      const label = props.labels!.get(poly.feature.properties.unit_id);
      if (!label) return;
      L.marker(poly.getBounds().getCenter(), {
        interactive: false,
        icon: L.divIcon({ className: "map-badge", html: label, iconSize: [20, 20] }),
      }).addTo(group);
    });
  }, [props.labels, props.units]);

  useEffect(() => {
    if (!props.focus || !layer.current || !map.current) return;
    layer.current.eachLayer((lyr) => {
      const poly = lyr as L.Polygon & { feature: { properties: { unit_id: string } } };
      if (poly.feature.properties.unit_id === props.focus) {
        map.current!.fitBounds(poly.getBounds(), { maxZoom: 13, padding: [40, 40] });
      }
    });
  }, [props.focus]);

  return <div ref={host} className="map" role="application" aria-label={props.ariaLabel} />;
}

export function resetView(m: L.Map) {
  m.fitBounds(LIMA_BOUNDS);
}
