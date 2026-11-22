// Reusable controls: segmented buttons and the period picker (RF-03, HU-10, HU-28).

import type { ReactNode } from "react";

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
      <Segmented
        label="Año"
        wrap
        value={value.year}
        options={years.map((y) => ({ value: y, label: String(y) }))}
        onChange={(year) => onChange({ year })}
        hint="Solo se listan años con al menos una fuente que observa atropellos. 2018-2020 no tienen fuente."
      />
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

export function Notice({ children, tone = "info" }: { children: ReactNode; tone?: "info" | "warn" | "error" }) {
  return (
    <p className={`notice notice-${tone}`} role={tone === "error" ? "alert" : "status"}>
      {children}
    </p>
  );
}
