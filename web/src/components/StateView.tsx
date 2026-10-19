import type { ReactNode } from "react";

import type { ApiError } from "../api/client";

export type StateViewProps = {
  loading: boolean;
  error: ApiError | null;
  isEmpty?: boolean;
  emptyText?: string;
  onRetry?: () => void;
  children: ReactNode;
};

export function StateView({
  loading,
  error,
  isEmpty = false,
  emptyText = "暂无数据",
  onRetry,
  children,
}: StateViewProps) {
  if (loading) {
    return (
      <div className="loading">
        <span className="spinner" />
        <span>加载中</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="error-box">
        <span className="error-box__title">
          {error.code}
          {error.status > 0 ? ` · HTTP ${error.status}` : ""}
        </span>
        <span>{error.message}</span>
        {Object.keys(error.detail).length > 0 ? (
          <pre className="code-block">{JSON.stringify(error.detail, null, 2)}</pre>
        ) : null}
        {onRetry ? (
          <button type="button" className="btn btn--sm" onClick={onRetry}>
            重试
          </button>
        ) : null}
      </div>
    );
  }

  if (isEmpty) {
    return <div className="empty">{emptyText}</div>;
  }

  return <>{children}</>;
}
