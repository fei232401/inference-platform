import { RefreshCw } from "lucide-react";
import { useLocation } from "react-router-dom";

import { api } from "../api/endpoints";
import { useAsync } from "../hooks/useAsync";
import { resolveTitle } from "../lib/navigation";

function describe(
  loading: boolean,
  error: string | null,
  status: string | undefined,
  schemaVersion: number | null | undefined,
  failed: string[],
): string {
  if (loading) return "探测中";
  if (error) return "控制层不可达";
  if (status === "ok") return `schema v${schemaVersion ?? "?"}`;
  return `降级：${failed.length > 0 ? failed.join(" / ") : "未知原因"}`;
}

export function Topbar() {
  const { pathname } = useLocation();
  const health = useAsync((signal) => api.readyz(signal), []);

  const dotClass = health.error
    ? "health-dot health-dot--down"
    : health.data?.status === "ok"
      ? "health-dot health-dot--up"
      : "health-dot";

  return (
    <header className="topbar">
      <div className="topbar__crumb">
        <span className="faint">控制层</span>
        <span className="faint">/</span>
        <span>{resolveTitle(pathname)}</span>
      </div>

      <div className="topbar__right">
        <span className="row">
          <span className={dotClass} />
          <span className="muted">
            {describe(
              health.loading,
              health.error?.message ?? null,
              health.data?.status,
              health.data?.schema_version,
              health.data?.failed ?? [],
            )}
          </span>
        </span>
        <span className="faint" title="构建期注入的版本号（git short sha）">
          {__BUILD_VERSION__}
        </span>
        <button
          type="button"
          className="btn btn--sm"
          onClick={health.reload}
          disabled={health.loading}
        >
          <RefreshCw size={14} strokeWidth={1.75} aria-hidden />
          重新探测
        </button>
      </div>
    </header>
  );
}
