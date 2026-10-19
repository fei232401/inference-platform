import type { ReactNode } from "react";

import { backendStateLabel, requestStatusLabel, stateTone, statusTone } from "../lib/format";

export function StateBadge({ state }: { state: string }) {
  return <span className={`badge badge--${stateTone(state)}`}>{backendStateLabel(state)}</span>;
}

export function StatusBadge({ status }: { status: string }) {
  return <span className={`badge badge--${statusTone(status)}`}>{requestStatusLabel(status)}</span>;
}

export function ToneBadge({
  tone,
  children,
}: {
  tone: "neutral" | "accent" | "success" | "warning" | "danger";
  children: ReactNode;
}) {
  return (
    <span className={tone === "neutral" ? "badge" : `badge badge--${tone}`}>{children}</span>
  );
}
