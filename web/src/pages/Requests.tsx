import { useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api/endpoints";
import type { RequestListQuery } from "../api/types";
import { StatusBadge } from "../components/Badges";
import { PageHeader } from "../components/PageHeader";
import { Pager } from "../components/Pager";
import { Panel } from "../components/Panel";
import { StateView } from "../components/StateView";
import { CostReference } from "../features/requests/CostReference";
import { RequestFilterBar } from "../features/requests/RequestFilterBar";
import { RequestPurgeForm } from "../features/requests/RequestPurgeForm";
import { RequestRecordForm } from "../features/requests/RequestRecordForm";
import { useAsync } from "../hooks/useAsync";
import { usePager } from "../hooks/usePager";
import { formatDateTime, formatInt, formatMs, shortId } from "../lib/format";

export function Requests() {
  const pager = usePager(20);
  const [applied, setApplied] = useState<RequestListQuery>({});
  const [notice, setNotice] = useState<string | null>(null);

  const requests = useAsync(
    (signal) => api.requests.list({ ...applied, limit: pager.limit, offset: pager.offset }, signal),
    [applied, pager.limit, pager.offset],
  );
  const backends = useAsync(() => api.backends.list({ limit: 200 }), []);
  const keys = useAsync(() => api.keys.list({ limit: 200 }), []);

  const items = requests.data?.items ?? [];
  const backendItems = backends.data?.items ?? [];
  const keyItems = keys.data?.items ?? [];

  function handleApply(query: RequestListQuery) {
    pager.reset();
    setApplied(query);
  }

  return (
    <main className="page">
      <PageHeader
        title="请求流水"
        lead="每次推理调用的完整台账 + 当时的调度决策快照。快照是事后归因的唯一证据：为什么选中它、为什么排除别人，全部落库留存。"
        actions={
          <button type="button" className="btn" onClick={requests.reload} disabled={requests.loading}>
            刷新
          </button>
        }
      />

      {notice ? <div className="notice">{notice}</div> : null}

      <Panel title="筛选" subtitle="时间区间按 started_at 过滤">
        <RequestFilterBar onApply={handleApply} />
      </Panel>

      <Panel
        title="流水列表"
        subtitle={requests.data ? `共 ${requests.data.meta.total} 条` : undefined}
        flush
      >
        <StateView
          loading={requests.loading}
          error={requests.error}
          isEmpty={items.length === 0}
          emptyText="没有符合条件的请求"
          onRetry={requests.reload}
        >
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>请求 ID</th>
                  <th>模型</th>
                  <th>后端</th>
                  <th>会话</th>
                  <th>状态</th>
                  <th className="num">首字</th>
                  <th className="num">总耗时</th>
                  <th className="num">输入 / 输出 token</th>
                  <th>起始时间</th>
                  <th>错误码</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.request_id}>
                    <td className="mono" title={item.request_id}>
                      {shortId(item.request_id, 8)}…
                    </td>
                    <td>{item.model_name}</td>
                    <td>
                      {item.backend_id === null || item.backend_id === undefined ? (
                        <span className="faint">未归属</span>
                      ) : (
                        <Link to={`/backends/${item.backend_id}`}>#{item.backend_id}</Link>
                      )}
                    </td>
                    <td className="faint">{item.session_id ?? "—"}</td>
                    <td>
                      <StatusBadge status={item.status} />
                    </td>
                    <td className="num">{formatMs(item.ttft_ms, 0)}</td>
                    <td className="num">{formatMs(item.total_ms, 0)}</td>
                    <td className="num">
                      {formatInt(item.prompt_tokens)} / {formatInt(item.completion_tokens)}
                    </td>
                    <td className="faint">{formatDateTime(item.started_at)}</td>
                    <td className="faint">{item.error_code ?? "—"}</td>
                    <td>
                      <Link className="btn btn--sm btn--ghost" to={`/requests/${item.request_id}`}>
                        详情
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </StateView>
        {requests.data ? (
          <Pager
            meta={requests.data.meta}
            busy={requests.loading}
            onPrev={pager.prev}
            onNext={pager.next}
          />
        ) : null}
      </Panel>

      <div className="split">
        <Panel title="补录请求记录" subtitle="POST /api/v1/requests">
          <RequestRecordForm
            backends={backendItems}
            keys={keyItems}
            onRecorded={(message) => {
              setNotice(message);
              requests.reload();
            }}
          />
        </Panel>
        <Panel title="清理历史" subtitle="POST /api/v1/requests/purge">
          <RequestPurgeForm onPurged={requests.reload} />
        </Panel>
      </div>

      <Panel title="成本参考" subtitle="按各实例单价折算出的成本因子">
        <CostReference
          backends={backendItems}
          loading={backends.loading}
          onRetry={backends.reload}
        />
      </Panel>
    </main>
  );
}
