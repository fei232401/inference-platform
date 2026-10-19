import { Cpu } from "lucide-react";
import { NavLink } from "react-router-dom";

import { NAV_GROUPS } from "../lib/navigation";

export function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="sidebar__brand">
        <span className="sidebar__brand-mark">
          <Cpu size={18} strokeWidth={1.75} aria-hidden />
        </span>
        <span className="sidebar__brand-text">
          <span className="sidebar__brand-title">AI Infra 控制台</span>
          <span className="sidebar__brand-sub">调度依据可视化</span>
        </span>
      </div>

      {NAV_GROUPS.map((group) => (
        <div className="sidebar__group" key={group.label}>
          <span className="sidebar__group-label">{group.label}</span>
          {group.items.map((item) => {
            const LinkIcon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) => (isActive ? "nav-item nav-item--active" : "nav-item")}
              >
                <LinkIcon size={16} strokeWidth={1.75} aria-hidden />
                <span>{item.label}</span>
              </NavLink>
            );
          })}
        </div>
      ))}

      <div className="sidebar__footer">
        <span>策略：加权 / 延迟 / 轮询</span>
        <span>契约：openapi.json</span>
      </div>
    </aside>
  );
}
