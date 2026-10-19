import type { ReactNode } from "react";

export type PanelProps = {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
  flush?: boolean;
  children: ReactNode;
};

export function Panel({ title, subtitle, actions, flush = false, children }: PanelProps) {
  return (
    <section className="panel">
      <div className="panel__head">
        <div className="panel__title">
          <span>{title}</span>
          {subtitle ? <span className="panel__subtitle">{subtitle}</span> : null}
        </div>
        {actions ? <div className="panel__actions">{actions}</div> : null}
      </div>
      <div className={flush ? "panel__body panel__body--flush" : "panel__body"}>{children}</div>
    </section>
  );
}
