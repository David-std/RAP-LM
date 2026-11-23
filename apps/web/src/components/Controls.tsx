// Reusable controls (RF-03, RF-04, HU-10, HU-13..HU-16, HU-28).

import { useEffect, useId, useRef, useState, type ReactNode } from "react";

import type { DayType } from "../api/types";
import { BANDS, DAY_LABEL } from "../lib/format";
import type { PeriodKey } from "../state/QueryContext";

interface SegmentedProps<T extends string | number> {
  label: string;
  value: T;
  options: { value: T; label: string }[];
  onChange: (v: T) => void;
  hint?: string;
  wrap?: boolean;
}

/** Mutually exclusive options shown side by side (2 to 4 short labels). */
export function Segmented<T extends string | number>(p: SegmentedProps<T>) {
  return (
    <fieldset className={`seg${p.wrap ? " seg-wrap" : ""}`}>
      <legend className="field-label" title={p.hint}>
        {p.label}
      </legend>
      <div className="seg-row" role="radiogroup" aria-label={p.label}>
        {p.options.map((o) => (
          <button
            key={String(o.value)}
            type="button"
            role="radio"
            aria-checked={o.value === p.value}
            className={o.value === p.value ? "on" : ""}
            onClick={() => p.onChange(o.value)}
          >
            {o.label}
          </button>
        ))}
      </div>
    </fieldset>
  );
}

/** Year selector: dropdown with previous/next steps over the published years only. */
export function YearStepper({ years, value, onChange, label = "Año" }: { years: number[]; value: number; onChange: (y: number) => void; label?: string }) {
  const id = useId();
  const i = years.indexOf(value);
  return (
    <div>
      <label className="field-label" htmlFor={id}>
        {label}
      </label>
      <div className="stepper">
        <button type="button" className="step-btn" aria-label="Año anterior" disabled={i <= 0} onClick={() => onChange(years[i - 1])}>
          ‹
        </button>
        <select id={id} className="select" value={value} onChange={(e) => onChange(Number(e.target.value))}>
          {years.map((y, k) => (
            <option key={y} value={y}>
              {y}
              {k > 0 && y - years[k - 1] > 1 ? " (sin datos 2018-2020 antes)" : ""}
            </option>
          ))}
        </select>
        <button type="button" className="step-btn" aria-label="Año siguiente" disabled={i >= years.length - 1} onClick={() => onChange(years[i + 1])}>
          ›
        </button>
      </div>
    </div>
  );
}

export function PeriodPicker({
  years,
  value,
  onChange,
  title,
}: {
  years: number[];
  value: PeriodKey;
  onChange: (patch: Partial<PeriodKey>) => void;
  title?: ReactNode;
}) {
  return (
    <div className="period-picker">
      {title}
      <YearStepper years={years} value={value.year} onChange={(year) => onChange({ year })} />
      <Segmented<DayType>
        label="Tipo de día"
        value={value.dayType}
        options={[
          { value: "weekday", label: DAY_LABEL.weekday },
          { value: "weekend", label: DAY_LABEL.weekend },
        ]}
        onChange={(dayType) => onChange({ dayType })}
      />
      <Segmented
        label="Franja horaria"
        value={value.band}
        options={BANDS.map((b, i) => ({ value: i, label: b }))}
        onChange={(band) => onChange({ band })}
      />
    </div>
  );
}

/** Toggleable filter chips with a count, the usual pattern for faceted filters. */
export function FilterChips<T extends string>({
  label,
  items,
  selected,
  onToggle,
}: {
  label: string;
  items: { value: T; label: string; count?: number; swatch?: ReactNode }[];
  selected: T[];
  onToggle: (v: T) => void;
}) {
  return (
    <fieldset>
      <legend className="field-label">{label}</legend>
      <div className="chips" role="group" aria-label={label}>
        {items.map((it) => {
          const on = selected.includes(it.value);
          return (
            <button key={it.value} type="button" className={`filter-chip${on ? " on" : ""}`} aria-pressed={on} onClick={() => onToggle(it.value)}>
              {it.swatch}
              <span>{it.label}</span>
              {it.count !== undefined && <span className="chip-count">{it.count.toLocaleString("es-PE")}</span>}
            </button>
          );
        })}
      </div>
    </fieldset>
  );
}

/** Searchable single choice (input + suggestions) with a clear button. */
export function SearchSelect({
  label,
  options,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  options: { id: string; name: string }[];
  value: string | null;
  onChange: (id: string | null) => void;
  placeholder: string;
}) {
  const id = useId();
  const current = options.find((o) => o.id === value)?.name ?? "";
  const [text, setText] = useState(current);
  // Clearing the filter from outside (for example "Quitar filtros") must also clear the
  // typed text; clearing because the user is typing must not.
  const typing = useRef(false);
  useEffect(() => {
    if (value === null && !typing.current) setText("");
    typing.current = false;
  }, [value]);
  const commit = (t: string) => {
    const match = options.find((o) => o.name.toLowerCase() === t.trim().toLowerCase());
    if (match) onChange(match.id);
  };
  return (
    <div>
      <label className="field-label" htmlFor={id}>
        {label}
      </label>
      <div className="search-select">
        <input
          id={id}
          list={`${id}-list`}
          className="input"
          value={value ? current : text}
          placeholder={placeholder}
          onChange={(e) => {
            setText(e.target.value);
            typing.current = true;
            if (value) onChange(null);
            commit(e.target.value);
          }}
        />
        {value && (
          <button type="button" className="icon-btn" aria-label={`Quitar ${label.toLowerCase()}`} onClick={() => { setText(""); onChange(null); }}>
            ×
          </button>
        )}
        <datalist id={`${id}-list`}>
          {options.map((o) => (
            <option key={o.id} value={o.name} />
          ))}
        </datalist>
      </div>
    </div>
  );
}

/** Vertical list of choices with a short description each. */
export function OptionList<T extends string>({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: { value: T; label: string; description: string }[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <fieldset>
      <legend className="field-label">{label}</legend>
      <div className="option-list" role="radiogroup" aria-label={label}>
        {options.map((o) => (
          <button key={o.value} type="button" role="radio" aria-checked={o.value === value} className={`option${o.value === value ? " on" : ""}`} onClick={() => onChange(o.value)}>
            <span className="option-dot" aria-hidden="true" />
            <span>
              <span className="option-label">{o.label}</span>
              <span className="option-desc">{o.description}</span>
            </span>
          </button>
        ))}
      </div>
    </fieldset>
  );
}

export function Notice({ children, tone = "info" }: { children: ReactNode; tone?: "info" | "warn" | "error" }) {
  return (
    <p className={`notice notice-${tone}`} role={tone === "error" ? "alert" : "status"}>
      {children}
    </p>
  );
}
