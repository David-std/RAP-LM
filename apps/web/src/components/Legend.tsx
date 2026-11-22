// Legend (RF-01, RF-07, HU-02, HU-27). Classes carry numeric ranges and the
// level name, so reading it does not depend on colour alone.

import { useState } from "react";

import type { Legend as LegendDto } from "../api/types";
import { LEVEL_LABEL, type ClassBand } from "../lib/levels";

interface Props {
  legend: LegendDto;
  bands: ClassBand[];
  title: string;
  subtitle: string;
}

export function Legend({ legend, bands, title, subtitle }: Props) {
  const [open, setOpen] = useState(true);
  const levels = legend.bands;
  return (
    <section className="legend" aria-label="Leyenda del mapa">
      <button type="button" className="legend-toggle" aria-expanded={open} onClick={() => setOpen(!open)}>
        <span aria-hidden="true">{open ? "▾" : "▸"}</span> {title}
      </button>
      {open && (
        <>
          <p className="legend-sub">{subtitle}</p>
          <div className="legend-grid">
            <ul className="legend-classes">
              {[...bands].reverse().map((b) => (
                <li key={b.min}>
                  <span className="swatch" style={{ background: b.color }} aria-hidden="true" />
                  {Math.round(b.min)} a {b.max >= 100 ? 100 : Math.round(b.max) - 1}
                </li>
              ))}
            </ul>
            <ul className="legend-levels">
              {[...levels].reverse().map((l) => (
                <li key={l.level}>{LEVEL_LABEL[l.level]}</li>
              ))}
            </ul>
          </div>
          <p className="legend-nodata">
            <span className="swatch hatch" aria-hidden="true" /> Sin resultado, no equivale a bajo
          </p>
          <p className="legend-method">
            Umbrales {legend.version}: bajo &lt; {levels[0].max_index}, medio &lt; {levels[1].max_index}, alto ≥{" "}
            {levels[2].min_index}
          </p>
        </>
      )}
    </section>
  );
}
