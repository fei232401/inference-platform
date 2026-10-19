import { relativeBarWidth } from "../lib/format";

export type BarTone = "accent" | "muted" | "warning" | "danger";

export type BarRowProps = {
  label: string;
  value: number;
  max: number;
  display: string;
  tone?: BarTone;
};

export function BarRow({ label, value, max, display, tone = "accent" }: BarRowProps) {
  const fillClass =
    tone === "muted"
      ? "bar-row__fill bar-row__fill--muted"
      : tone === "warning"
        ? "bar-row__fill bar-row__fill--warning"
        : tone === "danger"
          ? "bar-row__fill bar-row__fill--danger"
          : "bar-row__fill";

  return (
    <div className="bar-row">
      <span className="bar-row__label" title={label}>
        {label}
      </span>
      <span className="bar-row__track">
        <span className={fillClass} style={{ width: `${relativeBarWidth(value, max)}%` }} />
      </span>
      <span className="bar-row__value">{display}</span>
    </div>
  );
}
