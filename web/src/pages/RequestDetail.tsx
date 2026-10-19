import { Link, useParams } from "react-router-dom";

import { api } from "../api/endpoints";
import { StatusBadge, ToneBadge } from "../components/Badges";
import { Metric } from "../components/Metric";
import { PageHeader } from "../components/PageHeader";
import { Panel } from "../components/Panel";
import { StateView } from "../components/StateView";
import { useAsync } from "../hooks/useAsync";
import {
  formatDateTime,
  formatInt,
  formatMs,
  formatRelative,
  policyLabel,
  shortId,
} from "../lib/format";

export function RequestDetail() {
  const { requestId } = useParams<{ requestId: string }>();

  if (requestId === undefined || requestId.length === 0) {
    return (
      <main className="page">
        <PageHeader title="请求详情" lead="路由参数缺少 request_id。" />
        <Panel title="返回">
          <Link to="/requests">回到请求流水</Link>
        </Panel>
      </main>
    );
  }

  return <RequestDetailView requestId={requestId} />;
}

function RequestDetailView({ requestId }: { requestId: string }) {
  const detail = useAsync((signal) => api.requests.detail(requestId, signal), [requestId]);
  const backends = useAsync(() => api.backends.list({ limit: 200 }), []);

  const log = detail.data;
  const decision = log?.decision ?? null;
  const backendItems = backends.data?.items ?? [];

  function backendName(backendId: number | null | undefined): string {
    if (backendId === null || backendId === undefined) return "未归属";
    const owner = backendItems.find((item) => item.id === backendId);
    return owner ? `${owner.name}（#${backendId}）` : `#${backendId}`;
  }

  return (
    <main className="page">
      <PageHeader
        title="请求详情"
        lead="一条请求的完整证据链：时延分解、token 用量、终态与错误码，以及当时参与打分的所有候选与最终选点。"
        actions={
          <>
            <Link className="btn" to="/requests">
              返回列表
            </Link>
            <button type="button" className="btn" onClick={detail.reload} disabled={detail.loading}>
              刷新
            </button>
          </>
        }
      />

      <StateView loading={detail.loading} error={detail.error} onRetry={detail.reload}>
        {log ? (
          <>
            <div className="grid grid--4">
              <Metric label="状态" value={log.status} hint={log.error_code ?? "无错误码"} />
              <Metric label="首字延迟" value={formatMs(log.ttft_ms, 0)} hint="TTFT，体感流畅度的关键项" />
              <Metric label="总耗时" value={formatMs(log.total_ms, 0)} hint="端到端 wall clock" />
              <Metric
                label="输出 token"
                value={formatInt(log.completion_tokens)}
                hint={`输入 ${formatInt(log.prompt_tokens)}`}
              />
            </div>

            <Panel
              title="基础信息"
              subtitle={requestId}
              actions={<StatusBadge status={log.status} />}
            >
              <div className="kv">
                <span className="kv__key">请求 ID</span>
                <span className="kv__value">{log.request_id}</span>
                <span className="kv__key">短标识</span>
                <span className="kv__value">{shortId(log.request_id, 12)}…</span>
                <span className="kv__key">模型</span>
                <span className="kv__value">{log.model_name}</span>
                <span className="kv__key">后端</span>
                <span className="kv__value">
                  {log.backend_id === null || log.backend_id === undefined ? (
                    backendName(null)
                  ) : (
                    <Link to={`/backends/${log.backend_id}`}>{backendName(log.backend_id)}</Link>
                  )}
                </span>
                <span className="kv__key">会话 ID</span>
                <span className="kv__value">{log.session_id ?? "—"}</span>
                <span className="kv__key">密钥 ID</span>
                <span className="kv__value">{log.api_key_id ?? "—"}</span>
                <span className="kv__key">输入 token</span>
                <span className="kv__value">{formatInt(log.prompt_tokens)}</span>
                <span className="kv__key">输出 token</span>
                <span className="kv__value">{formatInt(log.completion_tokens)}</span>
                <span className="kv__key">首字延迟</span>
                <span className="kv__value">{formatMs(log.ttft_ms, 0)}</span>
                <span className="kv__key">总耗时</span>
                <span className="kv__value">{formatMs(log.total_ms, 0)}</span>
                <span className="kv__key">错误码</span>
                <span className="kv__value">{log.error_code ?? "—"}</span>
                <span className="kv__key">开始时间</span>
                <span className="kv__value">
                  {formatDateTime(log.started_at)}（{formatRelative(log.started_at)}）
                </span>
                <span className="kv__key">结束时间</span>
                <span className="kv__value">
                  {log.finished_at
                    ? `${formatDateTime(log.finished_at)}（${formatRelative(log.finished_at)}）`
                    : "未结束"}
                </span>
              </div>
            </Panel>

            {decision ? (
              <>
                <Panel
                  title="调度决策快照"
                  subtitle={`决策时间 ${formatDateTime(decision.decided_at)}`}
                  actions={
                    <ToneBadge tone={decision.fallback_reason ? "warning" : "accent"}>
                      {policyLabel(decision.policy)}
                    </ToneBadge>
                  }
                >
                  <div className="stack">
                    <div className="kv">
                      <span className="kv__key">策略</span>
                      <span className="kv__value">
                        {policyLabel(decision.policy)}（{decision.policy}）
                      </span>
                      <span className="kv__key">候选数</span>
                      <span className="kv__value">{decision.candidate_ids.length}</span>
                      <span className="kv__key">最终选中</span>
                      <span className="kv__value">
                        {decision.chosen_id === null || decision.chosen_id === undefined
                          ? "未选点"
                          : backendName(decision.chosen_id)}
                      </span>
                      <span className="kv__key">降级原因</span>
                      <span className="kv__value">
                        {decision.fallback_reason ? (
                          <span className="badge badge--warning">{decision.fallback_reason}</span>
                        ) : (
                          "无，正常选点"
                        )}
                      </span>
                    </div>

                    <div className="table-wrap">
                      <table className="table">
                        <thead>
                          <tr>
                            <th>序位</th>
                            <th>候选后端</th>
                            <th>是否被选中</th>
                          </tr>
                        </thead>
                        <tbody>
                          {decision.candidate_ids.map((candidateId, index) => (
                            <tr key={candidateId}>
                              <td className="num">{index + 1}</td>
                              <td>
                                <Link to={`/backends/${candidateId}`}>{backendName(candidateId)}</Link>
                              </td>
                              <td>
                                {decision.chosen_id === candidateId ? (
                                  <span className="badge badge--accent">已选中</span>
                                ) : (
                                  <span className="faint">落选</span>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </Panel>

                <Panel title="打分明细" subtitle="写入时刻的原始快照">
                  <pre className="code-block">{JSON.stringify(decision.score_snapshot, null, 2)}</pre>
                </Panel>
              </>
            ) : (
              <Panel title="调度决策快照" subtitle="这条记录没有快照">
                <span className="muted">
                  只写结果不写快照的请求，事后无法归因：既说不清为什么选它，也说不清为什么排除别人。
                  补录时把「同时写入调度决策快照」打开即可。
                </span>
              </Panel>
            )}
          </>
        ) : null}
      </StateView>
    </main>
  );
}
