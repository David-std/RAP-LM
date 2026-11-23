// Street corridors (D-09): the street-level view that Vision Zero programmes
// call a high-injury network. It ranks named streets of each district by
// recorded pedestrian collisions per km and shows how concentrated the record
// is. Recorded history, not a prediction (same caveat as those networks).

import L from "leaflet";
import { useEffect, useMemo, useRef, useState } from "react";

import { api } from "../api/client";
import type { CorridorCollection, CorridorProps, Meta, UnitCollection } from "../api/types";
import { useApi } from "../api/useApi";
import { LineChart } from "../components/charts";
import { FACTOR_LABEL } from "../components/ZonePanel";
import { Notice } from "../components/Controls";
import { addScopeMask, createBaseMap } from "../lib/basemap";
import { exportCsv, type ExportColumn } from "../lib/export";
import { BANDS, fmtCount } from "../lib/format";
import { colorFor, type ClassBand } from "../lib/levels";

const DENSITY_RAMP = ["#F8CBB8", "#F09A80", "#E0664D", "#BF3A2E", "#7E1F22"];
const VEHICLE_NAME: Record<string, string> = {
  auto: "auto",
  camioneta: "camioneta",
  combi_minibus: "combi o minibús",
  bus: "bus",
  carga: "carga",
  moto: "moto",
  mototaxi: "mototaxi",
  bicicleta: "bicicleta o triciclo",
  no_identificado: "no identificado",
};
const SUBPERIOD_LABEL = ["Lab 0-6", "Lab 6-12", "Lab 12-18", "Lab 18-24", "FdS 0-6", "FdS 6-12", "FdS 12-18", "FdS 18-24"];

interface Props {
  districts: UnitCollection;
  meta: Meta;
  bands: ClassBand[];
  initialDistrict: string | null;
}

export function CorridorsPage({ districts, meta, bands, initialDistrict }: Props) {
  const [district, setDistrict] = useState<string>(initialDistrict ?? "");
  const [limit, setLimit] = useState(300);
  const [selected, setSelected] = useState<string | null>(null);
  const data = useApi(
    (s) => api.corridors({ districtIds: district ? [district] : undefined, limit, minEvents: 1 }, s),
    [district, limit],
  );
  const all = useApi((s) => api.model(s), []);
  const features = data.data?.features ?? [];
  const sorted = useMemo(() => [...features].sort((a, b) => b.properties.events_per_km - a.properties.events_per_km), [features]);
  const current = features.find((f) => f.id === selected)?.properties ?? null;
  const summary = all.data?.corridor_summary;
  const options = useMemo(
    () => districts.features.map((f) => ({ id: f.properties.unit_id, name: f.properties.display_name })).sort((a, b) => a.name.localeCompare(b.name, "es")),
    [districts],
  );
  const columns: ExportColumn<CorridorProps>[] = [
    { header: "corridor_id", value: (r) => r.corridor_id },
    { header: "district", value: (r) => r.district_name },
    { header: "street", value: (r) => r.street },
    { header: "length_km", value: (r) => r.length_km },
    { header: "events", value: (r) => r.events },
    { header: "events_per_km", value: (r) => r.events_per_km },
    { header: "injured", value: (r) => r.injured },
    { header: "deceased", value: (r) => r.deceased },
    { header: "mean_risk_index", value: (r) => r.mean_risk_index },
  ];

  return (
    <div className="workspace">
      <aside className="rail" aria-label="Filtros de vías críticas">
        <div>
          <p className="eyebrow">Calles</p>
          <h2 className="rail-title">Vías críticas: calles con más atropellos registrados</h2>
          <p className="muted small" style={{ marginTop: 6 }}>
            Calles con nombre dentro de cada distrito, con los atropellos registrados ubicados sobre ellas (2011-2017 y
            2021-2024). Útil para priorizar dónde mirar con más detalle.
          </p>
        </div>
        {summary && (
          <div className="card" style={{ boxShadow: "none" }}>
            <p className="kpi-label">Concentración en Lima</p>
            <p className="kpi-value">{Math.round((summary.concentration["10%_length"] ?? 0) * 100)} %</p>
            <p className="kpi-foot">de los atropellos ubicados ocurre en el 10 % de la longitud de calles con mayor densidad</p>
          </div>
        )}
        <div className="rail-section">
          <label className="field-label" htmlFor="corr-district">Distrito</label>
          <select id="corr-district" className="select" value={district} onChange={(e) => { setDistrict(e.target.value); setSelected(null); }}>
            <option value="">Los 43 distritos (los más críticos)</option>
            {options.map((o) => (
              <option key={o.id} value={o.id}>{o.name}</option>
            ))}
          </select>
          <label className="field-label" htmlFor="corr-limit">Tramos de calle mostrados: {limit}</label>
          <input id="corr-limit" type="range" min={50} max={1000} step={50} value={limit} onChange={(e) => setLimit(Number(e.target.value))} />
          <button type="button" className="btn" disabled={!features.length} onClick={() => exportCsv(`rap-lm-vias-criticas${district ? `-${district}` : ""}`, sorted.map((f) => f.properties), columns, meta, `corridors ${district || "all"}`)}>
            Exportar CSV
          </button>
        </div>
        <p className="muted small">
          Un cruce reparte medio evento a cada calle. Las avenidas de doble calzada suman ambas vías en la longitud, lo que
          reduce sus eventos por km. Eventos sin calle identificable quedan fuera ({summary ? fmtCount(summary.events_not_on_corridor) : "…"}).
        </p>
      </aside>

      <main className="map-area">
        {data.error && <Notice tone="error">{data.error.message}</Notice>}
        <CorridorMap data={data.data} scope={districts} selected={selected} onSelect={setSelected} />
        {data.loading && <div className="map-loading">Cargando…</div>}
        <div className="legend-dock">
          <section className="legend">
            <strong>Atropellos por km</strong>
            <p className="legend-sub">Grosor y color según densidad de eventos registrados</p>
            <ul className="legend-classes">
              {["< p20", "p20-p40", "p40-p60", "p60-p80", "> p80"].map((l, i) => (
                <li key={l}>
                  <span className="swatch" style={{ background: DENSITY_RAMP[i], height: 4 + i, width: 18 }} /> {l}
                </li>
              ))}
            </ul>
          </section>
        </div>
        <div className="map-scope">Provincia de Lima, 43 distritos</div>
      </main>

      <aside className="zone-panel" aria-label="Detalle de vías críticas">
        {current ? (
          <CorridorDetail c={current} bands={bands} onBack={() => setSelected(null)} />
        ) : (
          <section className="card">
            <header>
              <h3>Ranking por atropellos por km</h3>
              <span className="card-sub">{features.length} tramos de calle</span>
            </header>
            <ol className="ranked-list">
              {sorted.slice(0, 40).map((f, i) => (
                <li key={f.id}>
                  <button type="button" className="link-btn" onClick={() => setSelected(f.id)}>
                    {i + 1}. {f.properties.street}
                  </button>
                  <span className="num small">
                    {f.properties.events_per_km.toFixed(1)}/km, {fmtCount(f.properties.events)}
                    <span className="muted"> {f.properties.district_name}</span>
                  </span>
                </li>
              ))}
            </ol>
          </section>
        )}
        {summary && !current && (
          <section className="card">
            <header>
              <h3>Curva de concentración</h3>
            </header>
            <p className="muted small">Qué parte de los atropellos ubicados se acumula al recorrer las calles de mayor a menor densidad.</p>
            <LineChart
              height={140}
              series={[
                {
                  name: "Atropellos acumulados",
                  color: "#bf3a2e",
                  points: [[0, 0], [5, Math.round(summary.concentration["5%_length"] * 100)], [10, Math.round(summary.concentration["10%_length"] * 100)], [20, Math.round(summary.concentration["20%_length"] * 100)], [100, 100]],
                },
                { name: "Distribución uniforme", color: "#b9b6ae", dashed: true, points: [[0, 0], [100, 100]] },
              ]}
              xLabel="% de la longitud de calles"
              xFormat={(v) => `${v.toFixed(0)} %`}
              yFormat={(v) => `${v.toFixed(0)} %`}
            />
          </section>
        )}
      </aside>
    </div>
  );
}

function CorridorDetail({ c, bands, onBack }: { c: CorridorProps; bands: ClassBand[]; onBack: () => void }) {
  const years = Object.keys(c.by_year).sort();
  const peak = c.by_subperiod.indexOf(Math.max(...c.by_subperiod));
  const riskColor = colorFor(c.mean_risk_index, bands);
  return (
    <>
      <section className="card">
        <div className="zone-head">
          <div>
            <h2>{c.street}</h2>
            <p className="muted">{c.district_name}, {c.length_km.toFixed(1)} km de vía mapeada</p>
          </div>
          <button type="button" className="icon-btn" onClick={onBack} aria-label="Volver al ranking">×</button>
        </div>
        <div className="kpi-row" style={{ marginTop: 12 }}>
          <div className="kpi"><span className="kpi-label">Atropellos</span><span className="kpi-value">{fmtCount(c.events)}</span><span className="kpi-foot">registrados</span></div>
          <div className="kpi"><span className="kpi-label">Por km</span><span className="kpi-value">{c.events_per_km.toFixed(1)}</span><span className="kpi-foot">puesto {c.rank}</span></div>
          <div className="kpi">
            <span className="kpi-label">Riesgo modelado</span>
            <span className="kpi-value">{c.mean_risk_index === null ? "–" : Math.round(c.mean_risk_index)}</span>
            <span className="kpi-foot"><span className="swatch" style={{ background: riskColor ?? undefined }} /> índice medio de sus celdas</span>
          </div>
        </div>
      </section>
      <section className="card">
        <header><h3>Atropellos por año</h3></header>
        <LineChart
          height={130}
          series={[{ name: "Atropellos", color: "var(--chart-2)", points: years.map((y) => [Number(y), c.by_year[y]]) }]}
          xFormat={(v) => String(Math.round(v))}
          yFormat={(v) => v.toFixed(0)}
        />
        <p className="card-note">2018-2020 sin fuente. Desde 2021 solo se registran siniestros con fallecido (ONSV).</p>
      </section>
      <section className="card">
        <header><h3>Cuándo ocurren</h3><span className="card-sub">pico: {SUBPERIOD_LABEL[peak]}</span></header>
        {c.by_subperiod.map((v, i) => (
          <div key={i} className="bar-row" style={{ gridTemplateColumns: "80px 1fr 36px" }}>
            <span className="small">{SUBPERIOD_LABEL[i]}</span>
            <span className="bar-track"><span className="bar-fill" style={{ left: 0, width: `${(v / Math.max(...c.by_subperiod, 1)) * 100}%`, background: "var(--chart-2)" }} /></span>
            <span className="num small">{fmtCount(v)}</span>
          </div>
        ))}
        <p className="card-note">Lab: laborable; FdS: fin de semana. Franjas de {BANDS.join(", ")}.</p>
      </section>
      <section className="card">
        <dl className="kv">
          <dt>Lesionados</dt><dd>{fmtCount(c.injured)}</dd>
          <dt>Fallecidos</dt><dd>{fmtCount(c.deceased)}</dd>
          <dt>Fuentes</dt><dd>{Object.entries(c.by_family).map(([k, v]) => `${k === "cenacom" ? "CENACOM" : "ONSV"} ${fmtCount(v)}`).join(", ")}</dd>
          <dt>Ubicación</dt><dd>{Object.entries(c.located_via).map(([k, v]) => `${k === "street" ? "tramo" : k === "intersection" ? "cruce" : "punto"} ${fmtCount(v)}`).join(", ")}</dd>
          {c.by_vehicle && (
            <>
              <dt>Vehículos</dt>
              <dd>
                {Object.entries(c.by_vehicle)
                  .filter(([, v]) => v > 0)
                  .sort((a, b) => b[1] - a[1])
                  .map(([k, v]) => `${VEHICLE_NAME[k] ?? k} ${fmtCount(v)}`)
                  .join(", ")}
              </dd>
            </>
          )}
          {c.by_factor && (
            <>
              <dt>Factores</dt>
              <dd>
                {Object.entries(c.by_factor)
                  .filter(([k, v]) => v > 0 && k !== "sin_causa")
                  .sort((a, b) => b[1] - a[1])
                  .slice(0, 5)
                  .map(([k, v]) => `${(FACTOR_LABEL as Record<string, string>)[k]?.toLowerCase() ?? k} ${fmtCount(v)}`)
                  .join(", ") || "sin causa registrada"}
              </dd>
            </>
          )}
        </dl>
      </section>
    </>
  );
}

function CorridorMap({ data, scope, selected, onSelect }: { data: CorridorCollection | null; scope: UnitCollection; selected: string | null; onSelect: (id: string) => void }) {
  const host = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const layer = useRef<L.GeoJSON | null>(null);
  const select = useRef(onSelect);
  select.current = onSelect;

  useEffect(() => {
    if (!host.current) return;
    const m = createBaseMap(host.current, L.canvas({ padding: 0.3 }));
    const mask = addScopeMask(m, scope);
    map.current = m;
    return () => {
      mask.remove();
      m.remove();
      map.current = null;
    };
  }, [scope]);

  useEffect(() => {
    const m = map.current;
    if (!m) return;
    layer.current?.remove();
    if (!data) return;
    const dens = data.features.map((f) => f.properties.events_per_km).sort((a, b) => a - b);
    const q = (p: number) => dens[Math.min(dens.length - 1, Math.floor(p * dens.length))] ?? 0;
    const cuts = [q(0.2), q(0.4), q(0.6), q(0.8)];
    layer.current = L.geoJSON(data as unknown as GeoJSON.FeatureCollection, {
      style: (f) => {
        const p = f!.properties as CorridorProps;
        const k = cuts.filter((c) => p.events_per_km > c).length;
        const isSel = f!.id === selected || p.corridor_id === selected;
        return { color: isSel ? "#16181d" : DENSITY_RAMP[k], weight: isSel ? 7 : 2 + k, opacity: 0.95 };
      },
      onEachFeature: (f, lyr) => {
        const p = f.properties as CorridorProps;
        lyr.bindTooltip(`<b>${p.street}</b><br>${p.district_name}<br>${p.events} atropellos, ${p.events_per_km.toFixed(1)} por km`, { sticky: true });
        lyr.on("click", () => select.current(p.corridor_id));
      },
    }).addTo(m);
    if (selected) {
      layer.current.eachLayer((l) => {
        const pl = l as L.Polyline & { feature: { properties: CorridorProps } };
        if (pl.feature.properties.corridor_id === selected) m.fitBounds(pl.getBounds(), { maxZoom: 15, padding: [60, 60] });
      });
    }
  }, [data, selected]);

  return <div ref={host} className="map" role="application" aria-label="Mapa de vías críticas" />;
}
