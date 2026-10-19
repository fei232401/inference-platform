export type MetricTone = "default" | "success" | "warning" | "danger";

export type MetricProps = {
  label: string;
  value: string;
  hint?: string;
  tone?: MetricTone;
};

const TONE_COLOR: Record<MetricTone, string | undefined> = {
  default: undefined,
  success: "var(--color-success)",
  warning: "var(--color-warning)",
  danger: "var(--color-danger)",
};

export function Metric({ label, value, hint, tone = "default" }: MetricProps) {
  const color = TONE_COLOR[tone];
  return (
    <div className="metric">
      <div className="metric__label">{label}</div>
      <div className="metric__value" style={color ? { color } : undefined}>
        {value}
      </div>
      {hint ? <div className="metric__hint">{hint}</div> : null}
    </div>
  );
}
