import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api } from "../api/endpoints";
import { StateBadge } from "../components/Badges";
import { Field } from "../components/Field";
import { Metric } from "../components/Metric";
import { PageHeader } from "../components/PageHeader";
import { Panel } from "../components/Panel";
import { StateView } from "../components/StateView";
import { BackendEditForm } from "../features/backends/BackendEditForm";
import { BackendHealthForm } from "../features/backends/BackendHealthForm";
import { BackendModelBinder } from "../features/backends/BackendModelBinder";
import { useAsync } from "../hooks/useAsync";
import { useAsyncAction } from "../hooks/useAsyncAction";
import { BACKEND_STATE_VALUES } from "../api/types";
import {
  backendStateLabel,
  engineLabel,
  formatDateTime,
  formatMicros,
  formatMs,
  formatRelative,
} from "../lib/format";

export function BackendDetail() {
  const { backendId } = useParams<{ backendId: string }>();
  const parsed = Number(backendId);

  if (!Number.isInteger(parsed) || parsed <= 0) {
    return (
      <main className="page">
        <PageHeader title="实例详情" lead={`路由参数「${backendId ?? ""}」不是合法实例 ID。`} />
        <Panel title="返回">
          <Link to="/backends">回到实例列表</Link>
        </Panel>
      </main>
    );
  }

  return <BackendDetailView backendId={parsed} />;
}

function BackendDetailView({ backendId }: { backendId: number }) {
  const [notice, setNotice] = useState<string | null>(null);
  const [historyNonce, setHistoryNonce] = useState(0);

  const detail = useAsync((signal) => api.backends.detail(backendId, true, signal), [backendId]);
  const history = useAsync(
    (signal) => api.backends.healthHistory(backendId, 20, signal),
    [backendId, historyNonce],
  );

  const changeState = useAsyncAction(api.backends.changeState);
  const disable = useAsyncAction(api.backends.disable);

  const backend = detail.data;
  const boundModels = backend?.models ?? [];
  const boundIds = boundModels.map((model) => model.id);
  const stateError = changeState.error ?? disable.error;

  async function handleStateChange(state: string) {
    const updated = await changeState.run(backendId, state);
    if (updated === null) return;
    setNotice(`状态已切换为「${backendStateLabel(state)}」`);
    detail.reload();
  }

  async function handleDisable() {
    const updated = await disable.run(backendId);
    if (updated === null) return;
    setNotice("已下线：记录保留，状态置为 disabled");
    detail.reload();
  }

  return (
    <main className="page">
      <PageHeader
        title={backend ? `实例详情 · ${backend.name}` : "实例详情"}
        lead="单个实例的完整台账：调度参数、模型绑定、健康探测历史。所有写操作都经控制层 API 落库，前端不持有业务状态。"
        actions={
          <>
            <Link className="btn" to="/backends">
              返回列表
            </Link>
            <button type="button" className="btn" onClick={detail.reload} disabled={detail.loading}>
              刷新
            </button>
          </>
        }
      />

      {notice ? <div className="notice">{notice}</div> : null}

      <StateView loading={detail.loading} error={detail.error} onRetry={detail.reload}>
        {backend ? (
          <>
            <div className="grid grid--4">
              <Metric label="实例 ID" value={String(backend.id)} hint={engineLabel(backend.engine)} />
              <Metric label="权重" value={String(backend.weight)} hint="打分公式的比例因子" />
              <Metric label="最大并发" value={String(backend.max_concurrency)} hint="仅登记，不做限流" />
              <Metric
                label="每 token 单价"
                value={formatMicros(backend.cost_per_token)}
                hint="0 视为本地免费"
              />
              <Metric label="绑定模型" value={String(boundModels.length)} hint="决定参与哪些模型的调度" />
              <Metric label="状态" value={backendStateLabel(backend.state)} hint="active / draining / disabled" />
              <Metric
                label="创建时间"
                value={formatDateTime(backend.created_at)}
                hint={formatRelative(backend.created_at)}
              />
              <Metric
                label="更新时间"
                value={formatDateTime(backend.updated_at)}
                hint={formatRelative(backend.updated_at)}
              />
            </div>

            <Panel
              title="状态与地址"
              subtitle={`${backend.url} · ${engineLabel(backend.engine)}`}
              actions={<StateBadge state={backend.state} />}
            >
              <div className="toolbar">
                <Field label="切换状态" hint="排空：不再接收新流量；下线：终态，记录保留">
                  <select
                    className="field__select"
                    value={backend.state}
                    disabled={changeState.pending}
                    onChange={(event) => {
                      void handleStateChange(event.target.value);
                    }}
                  >
                    {BACKEND_STATE_VALUES.map((value) => (
                      <option key={value} value={value}>
                        {backendStateLabel(value)}
                      </option>
                    ))}
                  </select>
                </Field>
                <button
                  type="button"
                  className="btn btn--danger"
                  disabled={disable.pending || backend.state === "disabled"}
                  onClick={() => {
                    void handleDisable();
                  }}
                >
                  下线实例
                </button>
              </div>
              {stateError ? (
                <div className="error-box mt-3">
                  <span className="error-box__title">状态操作失败 · {stateError.code}</span>
                  <span>{stateError.message}</span>
                </div>
              ) : null}
            </Panel>

            <Panel title="编辑调度参数" subtitle="PATCH /api/v1/backends/{id}">
              <BackendEditForm
                backend={backend}
                onSaved={() => {
                  setNotice("调度参数已更新");
                  detail.reload();
                }}
              />
            </Panel>

            <div className="split">
              <Panel title="已绑定模型" subtitle={`${boundModels.length} 个`} flush>
                <StateView
                  loading={false}
                  error={null}
                  isEmpty={boundModels.length === 0}
                  emptyText="还没绑定任何模型"
                >
                  <div className="table-wrap">
                    <table className="table">
                      <thead>
                        <tr>
                          <th>ID</th>
                          <th>名称</th>
                          <th>系列</th>
                          <th>参数量</th>
                          <th>量化</th>
                        </tr>
                      </thead>
                      <tbody>
                        {boundModels.map((model) => (
                          <tr key={model.id}>
                            <td className="num">{model.id}</td>
                            <td>{model.name}</td>
                            <td>{model.family ?? "—"}</td>
                            <td className="num">
                              {model.parameter_billions ? `${model.parameter_billions}B` : "—"}
                            </td>
                            <td>{model.quantization ?? "—"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </StateView>
              </Panel>

              <BackendModelBinder
                backendId={backendId}
                boundIds={boundIds}
                onChanged={(message) => {
                  setNotice(message);
                  detail.reload();
                }}
              />
            </div>

            <div className="split">
              <Panel title="上报健康探测" subtitle="POST /api/v1/backends/{id}/health">
                <BackendHealthForm
                  backendId={backendId}
                  onRecorded={(recordId) => {
                    setNotice(`已写入健康探测记录 #${recordId}`);
                    setHistoryNonce((current) => current + 1);
                  }}
                />
              </Panel>

              <Panel
                title="健康探测历史"
                subtitle="最近 20 条"
                actions={
                  <button
                    type="button"
                    className="btn btn--sm"
                    onClick={() => setHistoryNonce((current) => current + 1)}
                    disabled={history.loading}
                  >
                    刷新
                  </button>
                }
                flush
              >
                <StateView
                  loading={history.loading}
                  error={history.error}
                  isEmpty={(history.data?.length ?? 0) === 0}
                  emptyText="还没有探测记录"
                  onRetry={() => setHistoryNonce((current) => current + 1)}
                >
                  <div className="table-wrap">
                    <table className="table">
                      <thead>
                        <tr>
                          <th>ID</th>
                          <th>探测时间</th>
                          <th>结果</th>
                          <th className="num">延迟</th>
                          <th>错误</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(history.data ?? []).map((record) => (
                          <tr key={record.id}>
                            <td className="num">{record.id}</td>
                            <td className="faint">{formatDateTime(record.checked_at)}</td>
                            <td>
                              <span className={`badge badge--${record.healthy ? "success" : "danger"}`}>
                                {record.healthy ? "通过" : "失败"}
                              </span>
                            </td>
                            <td className="num">{formatMs(record.latency_ms, 0)}</td>
                            <td className="faint">{record.error ?? "—"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </StateView>
              </Panel>
            </div>
          </>
        ) : null}
      </StateView>
    </main>
  );
}
