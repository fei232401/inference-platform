import type { ReactNode } from "react";

export type PageHeaderProps = {
  title: string;
  lead?: string;
  actions?: ReactNode;
};

export function PageHeader({ title, lead, actions }: PageHeaderProps) {
  return (
    <div className="page__header">
      <div>
        <h1>{title}</h1>
        {lead ? <p className="page__lead">{lead}</p> : null}
      </div>
      {actions ? <div className="row">{actions}</div> : null}
    </div>
  );
}
