// Shared Leaflet base map: Esri World Light Gray (no API key), labels in a
// pane above the analytical layers, scale, "full Lima" button and a mask that
// dims everything outside the 43 districts of the province of Lima (RG-01).

import L from "leaflet";

import type { UnitCollection } from "../api/types";

export const LIMA_BOUNDS = L.latLngBounds([-12.52, -77.2], [-11.57, -76.62]);
const ESRI = "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas";
const ATTRIBUTION = "Mapa base &copy; Esri, HERE, Garmin, &copy; colaboradores de OpenStreetMap";

export function createBaseMap(host: HTMLElement, renderer: L.Renderer): L.Map {
  const m = L.map(host, { renderer, zoomSnap: 0.25, minZoom: 9, maxZoom: 17, maxBounds: LIMA_BOUNDS.pad(0.5) });
  L.tileLayer(`${ESRI}/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}`, {
    attribution: ATTRIBUTION,
    maxNativeZoom: 16,
    maxZoom: 18,
  }).addTo(m);
  m.createPane("scope-mask").style.zIndex = "390";
  const labels = m.createPane("labels");
  labels.style.zIndex = "650";
  labels.style.pointerEvents = "none";
  L.tileLayer(`${ESRI}/World_Light_Gray_Reference/MapServer/tile/{z}/{y}/{x}`, {
    maxNativeZoom: 16,
    maxZoom: 18,
    pane: "labels",
  }).addTo(m);
  L.control.scale({ imperial: false, position: "bottomleft" }).addTo(m);
  const Home = L.Control.extend({
    onAdd: () => {
      const button = L.DomUtil.create("button", "map-home");
      button.type = "button";
      button.title = "Volver a la vista completa de Lima";
      button.setAttribute("aria-label", "Volver a la vista completa de Lima");
      button.innerHTML = "⤢";
      L.DomEvent.disableClickPropagation(button);
      button.onclick = () => m.fitBounds(LIMA_BOUNDS);
      return button;
    },
  });
  new Home({ position: "topright" }).addTo(m);
  m.fitBounds(LIMA_BOUNDS);
  return m;
}

/** Grey veil over everything outside the given districts. Returns the layer (remove to clear). */
export function addScopeMask(m: L.Map, scope: UnitCollection): L.Polygon {
  const holes: L.LatLngTuple[][] = [];
  for (const f of scope.features) {
    const polys = f.geometry.type === "Polygon" ? [f.geometry.coordinates] : f.geometry.coordinates;
    for (const poly of polys) holes.push(poly[0].map(([lng, lat]) => [lat, lng] as L.LatLngTuple));
  }
  const world: L.LatLngTuple[] = [[-14.5, -79.5], [-14.5, -74.5], [-9.5, -74.5], [-9.5, -79.5]];
  return L.polygon([world, ...holes], {
    pane: "scope-mask",
    interactive: false,
    stroke: false,
    fillColor: "#2b2e35",
    fillOpacity: 0.28,
  }).addTo(m);
}
