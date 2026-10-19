import { useState } from "react";

import { api } from "../api/endpoints";
import type { ApiKeyCreatedOut } from "../api/types";
import { Field } from "../components/Field";
import { PageHeader } from "../components/PageHeader";
import { Pager } from "../components/Pager";
import { Panel } from "../components/Panel";
import { StateView } from "../components/StateView";
import { KeyIssueForm } from "../features/keys/KeyIssueForm";
import { KeyVerifyForm } from "../features/keys/KeyVerifyForm";
import { useAsync } from "../hooks/useAsync";
import { useAsyncAction } from "../hooks/useAsyncAction";
import { usePager } from "../hooks/usePager";
import { formatDateTime, formatRelative, shortId } from "../lib/format";

function keyStatus(key: { revoked_at?: string | null; expires_at?: string | null }): {
  label: string;
  tone: string;
} {
  if (key.revoked_at) return { label: "已吊销", tone: "danger" };
  if (key.expires_at && new Date(key.expires_at).getTime() <= Date.now()) {
    return { label: "已过期", tone: "warning" };
  }
  return { label: "有效", tone: "success" };
}

export function Keys() {
  const pager = usePager(20);
  const [nameLike, setNameLike] = useState("");
  const [activeOnly, setActiveOnly] = useState(false);
  const [applied, setApplied] = useState({ active_only: false, name_like: "" });
  const [issued, setIssued] = useState<ApiKeyCreatedOut | null>(null);
  const [copied, setCopied] = useState(false);

  const keys = useAsync(
    (signal) => api.keys.list({ ...applied, limit: pager.limit, offset: pager.offset }, signal),
    [applied, pager.limit, pager.offset],
  );
  const revoke = useAsyncAction(api.keys.revoke);

  const items = keys.data?.items ?? [];

  function applyFilters() {
    pager.reset();
    setApplied({ active_only: activeOnly, name_like: nameLike });
  }

  async function handleRevoke(keyId: number) {
    const updated = await revoke.run(keyId);
    if (updated !== null) keys.reload();
  }

  async function handleCopy() {
    if (issued === null) return;
    try {
      await navigator.clipboard.writeText(issued.key);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }

  function handleIssued(created: ApiKeyCreatedOut) {
    setIssued(created);
    setCopied(false);
    keys.reload();
  }

  return (
    <main className="page">
      <PageHeader
        title="访问密钥"
        lead="库里只存 SHA-256 摘要，明文仅在签发那一刻返回一次。last_used_at 带 60 秒节流，避免每次校验都写库。"
        actions={
          <button type="button" className="btn" onClick={keys.reload} disabled={keys.loading}>
            刷新
          </button>
        }
      />

      {issued ? (
        <Panel
          title="明文密钥（只显示这一次）"
          subtitle={`${issued.name} · #${issued.id}`}
          actions={
            <button type="button" className="btn btn--sm" onClick={() => setIssued(null)}>
              我已保存
            </button>
          }
        >
          <div className="stack">
            <code className="code-block">{issued.key}</code>
            <div className="row">
              <button type="button" className="btn btn--primary" onClick={() => void handleCopy()}>
                {copied ? "已复制" : "复制到剪贴板"}
              </button>
              <span className="faint">
                前缀 {issued.key_prefix} · 权限 {issued.scopes.join(" / ")} · 过期{" "}
                {issued.expires_at ? formatDateTime(issued.expires_at) : "永不"}
              </span>
            </div>
          </div>
        </Panel>
      ) : null}

      <Panel title="筛选">
        <form
          className="toolbar"
          onSubmit={(event) => {
            event.preventDefault();
            applyFilters();
          }}
        >
          <Field label="名称包含">
            <input
              className="field__input"
              value={nameLike}
              onChange={(event) => setNameLike(event.target.value)}
            />
          </Field>
          <Field label="只看有效" hint="同时排除已吊销与已过期">
            <select
              className="field__select"
              value={activeOnly ? "yes" : "no"}
              onChange={(event) => setActiveOnly(event.target.value === "yes")}
            >
              <option value="no">全部</option>
              <option value="yes">仅未吊销未过期</option>
            </select>
          </Field>
          <button type="submit" className="btn btn--primary">
            查询
          </button>
          <button
            type="button"
            className="btn"
            onClick={() => {
              setNameLike("");
              setActiveOnly(false);
              pager.reset();
              setApplied({ active_only: false, name_like: "" });
            }}
          >
            重置
          </button>
        </form>
      </Panel>

      <Panel title="密钥列表" subtitle={keys.data ? `共 ${keys.data.meta.total} 条` : undefined} flush>
        <StateView
          loading={keys.loading}
          error={keys.error}
          isEmpty={items.length === 0}
          emptyText="还没有签发过密钥"
          onRetry={keys.reload}
        >
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>名称</th>
                  <th>前缀</th>
                  <th>权限</th>
                  <th className="num">限速</th>
                  <th>创建时间</th>
                  <th>最后使用</th>
                  <th>过期时间</th>
                  <th>状态</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => {
                  const status = keyStatus(item);
                  return (
                    <tr key={item.id}>
                      <td className="num">{item.id}</td>
                      <td>{item.name}</td>
                      <td className="mono">{shortId(item.key_prefix, 12)}…</td>
                      <td>
                        <span className="row">
                          {item.scopes.map((scope) => (
                            <span className="tag" key={scope}>
                              {scope}
                            </span>
                          ))}
                        </span>
                      </td>
                      <td className="num">{item.rate_limit_per_second ?? "不限"}</td>
                      <td className="faint">{formatDateTime(item.created_at)}</td>
                      <td className="faint">
                        {item.last_used_at ? formatRelative(item.last_used_at) : "从未"}
                      </td>
                      <td className="faint">
                        {item.expires_at ? formatDateTime(item.expires_at) : "永不"}
                      </td>
                      <td>
                        <span className={`badge badge--${status.tone}`}>{status.label}</span>
                      </td>
                      <td>
                        <button
                          type="button"
                          className="btn btn--sm btn--danger"
                          disabled={revoke.pending || Boolean(item.revoked_at)}
                          onClick={() => {
                            void handleRevoke(item.id);
                          }}
                        >
                          吊销
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </StateView>
        {keys.data ? (
          <Pager meta={keys.data.meta} busy={keys.loading} onPrev={pager.prev} onNext={pager.next} />
        ) : null}
      </Panel>

      {revoke.error ? (
        <div className="error-box">
          <span className="error-box__title">吊销失败 · {revoke.error.code}</span>
          <span>{revoke.error.message}</span>
        </div>
      ) : null}

      <div className="split">
        <Panel title="签发新密钥" subtitle="POST /api/v1/keys">
          <KeyIssueForm onIssued={handleIssued} />
        </Panel>
        <Panel title="校验工具" subtitle="POST /api/v1/keys/verify">
          <KeyVerifyForm />
        </Panel>
      </div>
    </main>
  );
}
