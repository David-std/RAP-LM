// Small SVG chart kit (no chart library): thin marks, recessive grid, one
// y-axis, legend for >= 2 series and a hover tooltip on every mark.

import { useMemo, useRef, useState, type ReactNode } from "react";

const W = 360;

function niceMax(v: number): number {
  if (v <= 0) return 1;
  const p = 10 ** Math.floor(Math.log10(v));
  const n = v / p;
  return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * p;
}

const fmt = (v: number) =>
  Math.abs(v) >= 100 ? v.toFixed(0) : Math.abs(v) >= 10 ? v.toFixed(1) : v.toFixed(2);

function Tip({ x, y, children }: { x: number | string; y: number; children: ReactNode }) {
  return (
    <div className="chart-tip" style={{ left: x, top: y }}>
      {children}
    </div>
  );
}

// ---------------------------------------------------------------- year series
export interface YearSeriesProps {
  years: number[];
  observed: number[];
  expected: number[];
  highlightYear?: number;
  observedLabel: string;
  expectedLabel: string;
  height?: number;
  onSelectYear?: (year: number) => void;
}

/** Observed record (bars) vs network estimate (line) per year; gaps where years are not consecutive. */
export function YearSeriesChart(p: YearSeriesProps) {
  const H = p.height ?? 150;
  const pad = { l: 34, r: 8, t: 10, b: 22 };
  const n = p.years.length;
  const max = niceMax(Math.max(...p.observed, ...p.expected, 0.01));
  const bw = (W - pad.l - pad.r) / n;
  const x = (i: number) => pad.l + bw * i + bw / 2;
  const y = (v: number) => pad.t + (H - pad.t - pad.b) * (1 - v / max);
  const [hover, setHover] = useState<number | null>(null);
  const segments: number[][] = [];
  p.years.forEach((yr, i) => {
    if (i === 0 || yr - p.years[i - 1] !== 1) segments.push([i]);
    else segments[segments.length - 1].push(i);
  });
  return (
    <div className="chart-wrap">
      <svg viewBox={`0 0 ${W} ${H}`} className="chart" role="img" aria-label={`${p.expectedLabel} y ${p.observedLabel} por año`}>
        {[0, 0.5, 1].map((f) => (
          <g key={f}>
            <line className="gridline" x1={pad.l} x2={W - pad.r} y1={y(max * f)} y2={y(max * f)} />
            <text x={pad.l - 4} y={y(max * f) + 3} textAnchor="end">
              {fmt(max * f)}
            </text>
          </g>
        ))}
        {p.years.map((yr, i) => (
          <g key={yr}>
            {yr === p.highlightYear && (
              <rect x={x(i) - bw / 2} y={pad.t} width={bw} height={H - pad.t - pad.b} fill="#e3f1ef" />
            )}
            <rect
              x={x(i) - bw * 0.3}
              y={y(p.observed[i])}
              width={bw * 0.6}
              height={Math.max(0, y(0) - y(p.observed[i]))}
              rx={2}
              fill="var(--chart-2)"
              opacity={0.75}
            />
            <text x={x(i)} y={H - 6} textAnchor="middle">
              {String(yr).slice(2)}
            </text>
            <rect
              x={x(i) - bw / 2}
              y={pad.t}
              width={bw}
              height={H - pad.t}
              fill="transparent"
              style={{ cursor: p.onSelectYear ? "pointer" : "default" }}
              onMouseEnter={() => setHover(i)}
              onMouseLeave={() => setHover(null)}
              onClick={() => p.onSelectYear?.(yr)}
            />
          </g>
        ))}
        {segments.map((seg) => (
          <polyline
            key={seg[0]}
            fill="none"
            stroke="var(--chart-1)"
            strokeWidth={2}
            points={seg.map((i) => `${x(i)},${y(p.expected[i])}`).join(" ")}
          />
        ))}
        {p.years.map((yr, i) => (
          <circle key={yr} cx={x(i)} cy={y(p.expected[i])} r={hover === i ? 4.5 : 3} fill="var(--chart-1)" stroke="#fff" strokeWidth={1.5} />
        ))}
      </svg>
      {hover !== null && (
        <Tip x={`${(x(hover) / W) * 100}%`} y={0}>
          <b>{p.years[hover]}</b>
          <br />
          {p.expectedLabel}: {fmt(p.expected[hover])}
          <br />
          {p.observedLabel}: {fmt(p.observed[hover])}
        </Tip>
      )}
      <div className="chart-legend">
        <span>
          <i style={{ background: "var(--chart-1)" }} /> {p.expectedLabel}
        </span>
        <span>
          <i className="box" style={{ background: "var(--chart-2)", opacity: 0.75 }} /> {p.observedLabel}
        </span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- diverging bars
export interface DivergingItem {
  label: string;
  value: number; // percent
  hint?: string;
}

/** Horizontal bars around zero: positive raises the estimate, negative lowers it. */
export function DivergingBars({ items, unit = "%" }: { items: DivergingItem[]; unit?: string }) {
  const max = niceMax(Math.max(...items.map((i) => Math.abs(i.value)), 1));
  return (
    <div role="list">
      {items.map((it) => {
        const w = (Math.abs(it.value) / max) * 50;
        const up = it.value >= 0;
        return (
          <div key={it.label} className="bar-row" role="listitem" title={it.hint}>
            <span>{it.label}</span>
            <span className="bar-track">
              <span style={{ position: "absolute", left: "50%", top: -2, bottom: -2, width: 1, background: "var(--line)" }} />
              <span
                className="bar-fill"
                style={{
                  left: up ? "50%" : `${50 - w}%`,
                  width: `${w}%`,
                  background: up ? "#bf3a2e" : "var(--chart-1)",
                }}
              />
            </span>
            <span className="num">
              {it.value > 0 ? "+" : ""}
              {it.value.toFixed(0)}
              {unit}
            </span>
          </div>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------- generic line chart
export interface LineSeries {
  name: string;
  color: string;
  points: [number, number][];
  dashed?: boolean;
}

export function LineChart({
  series,
  height = 170,
  xLabel,
  yLabel,
  xFormat = (v) => String(v),
  yFormat = fmt,
  marker,
}: {
  series: LineSeries[];
  height?: number;
  xLabel?: string;
  yLabel?: string;
  xFormat?: (v: number) => string;
  yFormat?: (v: number) => string;
  marker?: { x: number; label: string };
}) {
  const H = height;
  const pad = { l: 40, r: 10, t: 10, b: 30 };
  const all = series.flatMap((s) => s.points);
  const [x0, x1] = [Math.min(...all.map((p) => p[0])), Math.max(...all.map((p) => p[0]))];
  const ys = all.map((p) => p[1]);
  const y0 = Math.min(0, ...ys);
  const y1 = niceMax(Math.max(...ys, 0.0001));
  const sx = (v: number) => pad.l + ((v - x0) / Math.max(x1 - x0, 1e-9)) * (W - pad.l - pad.r);
  const sy = (v: number) => pad.t + (H - pad.t - pad.b) * (1 - (v - y0) / Math.max(y1 - y0, 1e-9));
  const ref = useRef<HTMLDivElement>(null);
  const [hx, setHx] = useState<number | null>(null);
  const xs = useMemo(() => [...new Set(all.map((p) => p[0]))].sort((a, b) => a - b), [all]);
  const onMove = (e: React.MouseEvent<SVGSVGElement>) => {
    const box = e.currentTarget.getBoundingClientRect();
    const vx = x0 + ((e.clientX - box.left) / box.width * W - pad.l) / (W - pad.l - pad.r) * (x1 - x0);
    let best = xs[0];
    for (const v of xs) if (Math.abs(v - vx) < Math.abs(best - vx)) best = v;
    setHx(best);
  };
  return (
    <div className="chart-wrap" ref={ref}>
      <svg viewBox={`0 0 ${W} ${H}`} className="chart" onMouseMove={onMove} onMouseLeave={() => setHx(null)} role="img" aria-label={yLabel}>
        {[0, 0.5, 1].map((f) => {
          const v = y0 + (y1 - y0) * f;
          return (
            <g key={f}>
              <line className="gridline" x1={pad.l} x2={W - pad.r} y1={sy(v)} y2={sy(v)} />
              <text x={pad.l - 4} y={sy(v) + 3} textAnchor="end">
                {yFormat(v)}
              </text>
            </g>
          );
        })}
        {y0 < 0 && <line className="axis" x1={pad.l} x2={W - pad.r} y1={sy(0)} y2={sy(0)} />}
        {[x0, (x0 + x1) / 2, x1].map((v) => (
          <text key={v} x={sx(v)} y={H - 14} textAnchor="middle">
            {xFormat(v)}
          </text>
        ))}
        {xLabel && (
          <text x={(W + pad.l) / 2} y={H - 2} textAnchor="middle">
            {xLabel}
          </text>
        )}
        {marker && (
          <g>
            <line x1={sx(marker.x)} x2={sx(marker.x)} y1={pad.t} y2={H - pad.b} stroke="var(--ink-2)" strokeDasharray="3 3" />
            <text x={sx(marker.x) + 4} y={pad.t + 9}>
              {marker.label}
            </text>
          </g>
        )}
        {series.map((s) => (
          <polyline
            key={s.name}
            fill="none"
            stroke={s.color}
            strokeWidth={2}
            strokeDasharray={s.dashed ? "4 3" : undefined}
            points={s.points.map(([a, b]) => `${sx(a)},${sy(b)}`).join(" ")}
          />
        ))}
        {hx !== null && <line x1={sx(hx)} x2={sx(hx)} y1={pad.t} y2={H - pad.b} stroke="var(--ink-2)" strokeWidth={1} />}
      </svg>
      {hx !== null && (
        <Tip x={`${(sx(hx) / W) * 100}%`} y={0}>
          <b>{xFormat(hx)}</b>
          {series.map((s) => {
            const pt = s.points.find((p) => p[0] === hx);
            return pt ? (
              <div key={s.name}>
                {s.name}: {yFormat(pt[1])}
              </div>
            ) : null;
          })}
        </Tip>
      )}
      {series.length > 1 && (
        <div className="chart-legend">
          {series.map((s) => (
            <span key={s.name}>
              <i style={{ background: s.color }} /> {s.name}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- horizontal comparison bars
export interface CompareBar {
  label: string;
  value: number;
  color: string;
  note?: string;
}

/** Horizontal bars on one scale; a reference value (baseline) is drawn as a dashed rule. */
export function CompareBars({ bars, reference, referenceLabel, format = fmt }: {
  bars: CompareBar[];
  reference?: number;
  referenceLabel?: string;
  format?: (v: number) => string;
}) {
  const max = niceMax(Math.max(...bars.map((b) => b.value), reference ?? 0));
  return (
    <div style={{ position: "relative" }}>
      {bars.map((b) => (
        <div key={b.label} className="bar-row" style={{ gridTemplateColumns: "170px 1fr 64px" }} title={b.note}>
          <span>{b.label}</span>
          <span className="bar-track">
            <span className="bar-fill" style={{ left: 0, width: `${(b.value / max) * 100}%`, background: b.color }} />
            {reference !== undefined && (
              <span style={{ position: "absolute", left: `${(reference / max) * 100}%`, top: -4, bottom: -4, borderLeft: "2px dashed var(--chart-3)" }} />
            )}
          </span>
          <span className="num">{format(b.value)}</span>
        </div>
      ))}
      {reference !== undefined && (
        <div className="chart-legend">
          <span>
            <i style={{ background: "var(--chart-3)" }} /> {referenceLabel} ({format(reference)})
          </span>
        </div>
      )}
    </div>
  );
}
