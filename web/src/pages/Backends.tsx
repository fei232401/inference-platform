import { useState } from "react";

import { api } from "../api/endpoints";
import type { BackendListQuery } from "../api/types";
import { StateBadge } from "../components/Badges";
import { PageHeader } from "../components/PageHeader";
import { Pager } from "../components/Pager";
import { Panel } from "../components/Panel";
import { StateView } from "../components/StateView";
import { BackendBulkForm } from "../features/backends/BackendBulkForm";
import { BackendCreateForm } from "../features/backends/BackendCreateForm";
import { BackendFilterBar } from "../features/backends/BackendFilterBar";
import { BackendRowActions } from "../features/backends/BackendRowActions";
import { toBackendQuery } from "../features/backends/filters";
import type { BackendFilters } from "../features/backends/filters";
import { useAsync } from "../hooks/useAsync";
import { usePager } from "../hooks/usePager";
import { engineLabel, formatDateTime, formatMicros } from "../lib/format";

export function Backends() {
  const pager = usePager(20);
  const [applied, setApplied] = useState<BackendListQuery>({});

  const backends = useAsync(
    (signal) => api.backends.list({ ...applied, limit: pager.limit, offset: pager.offset }, signal),
    [applied, pager.limit, pager.offset],
  );

  const items = backends.data?.items ?? [];

  function handleApply(filters: BackendFilters) {
    pager.reset();
    setApplied(toBackendQuery(filters));
  }

  return (
    <main className="page">
      <PageHeader
        title="后端实例"
        lead="登记真实推理进程的地址与调度参数。权重与单价是打分公式的输入；最大并发只做登记，限流属于数据面职责。"
        actions={
          <button type="button" className="btn" onClick={backends.reload} disabled={backends.loading}>
            刷新
          </button>
        }
      />

      <Panel title="筛选" subtitle="名称模糊匹配走 ILIKE，留空表示不过滤">
        <BackendFilterBar onApply={handleApply} />
      </Panel>

      <Panel
        title="实例列表"
        subtitle={backends.data ? `共 ${backends.data.meta.total} 条` : undefined}
        flush
      >
        <StateView
          loading={backends.loading}
          error={backends.error}
          isEmpty={items.length === 0}
          emptyText="没有符合条件的实例"
          onRetry={backends.reload}
        >
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>名称</th>
                  <th>引擎</th>
                  <th>地址</th>
                  <th className="num">权重</th>
                  <th className="num">并发</th>
                  <th className="num">单价</th>
                  <th>状态</th>
                  <th>模型</th>
                  <th>更新时间</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id}>
                    <td className="num">{item.id}</td>
                    <td>{item.name}</td>
                    <td>{engineLabel(item.engine)}</td>
                    <td className="mono">{item.url}</td>
                    <td className="num">{item.weight}</td>
                    <td className="num">{item.max_concurrency}</td>
                    <td className="num">{formatMicros(item.cost_per_token)}</td>
                    <td>
                      <StateBadge state={item.state} />
                    </td>
                    <td>
                      {item.models ? (
                        item.models.length > 0 ? (
                          <span className="row">
                            {item.models.slice(0, 2).map((model) => (
                              <span className="tag" key={model.id}>
                                {model.name}
                              </span>
                            ))}
                            {item.models.length > 2 ? (
                              <span className="faint">+{item.models.length - 2}</span>
                            ) : null}
                          </span>
                        ) : (
                          <span className="faint">未绑定</span>
                        )
                      ) : (
                        <span className="faint">未加载</span>
                      )}
                    </td>
                    <td className="faint">{formatDateTime(item.updated_at)}</td>
                    <td>
                      <BackendRowActions backend={item} onChanged={backends.reload} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </StateView>
        {backends.data ? (
          <Pager
            meta={backends.data.meta}
            busy={backends.loading}
            onPrev={pager.prev}
            onNext={pager.next}
          />
        ) : null}
      </Panel>

      <div className="split">
        <Panel title="登记新实例" subtitle="POST /api/v1/backends">
          <BackendCreateForm onCreated={backends.reload} />
        </Panel>
        <Panel title="批量登记" subtitle="POST /api/v1/backends/bulk，同名自动跳过">
          <BackendBulkForm onCreated={backends.reload} />
        </Panel>
      </div>
    </main>
  );
}
