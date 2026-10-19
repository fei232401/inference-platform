import { useMemo, useState } from "react";

import { api } from "../api/endpoints";
import { BarRow } from "../components/BarRow";
import { Field } from "../components/Field";
import { Metric } from "../components/Metric";
import { PageHeader } from "../components/PageHeader";
import { Panel } from "../components/Panel";
import { StateView } from "../components/StateView";
import { useAsync } from "../hooks/useAsync";
import {
  backendStateLabel,
  engineLabel,
  formatInt,
  formatMs,
  formatPercent,
  requestStatusLabel,
  statusTone,
} from "../lib/format";

type RangeOption = {
  value: string;
  label: string;
  hours: number;
};

const RANGE_OPTIONS: readonly RangeOption[] = [
  { value: "1", label: "近 1 小时", hours: 1 },
  { value: "24", label: "近 24 小时", hours: 24 },
  { value: "168", label: "近 7 天", hours: 168 },
  { value: "0", label: "全部", hours: 0 },
];

function isoHoursAgo(hours: number): string {
  return new Date(Date.now() - hours * 3_600_000).toISOString();
}

export function Overview() {
  const [range, setRange] = useState("24");
  const hours = Number(range);
  const startedAfter = useMemo(() => (hours > 0 ? isoHoursAgo(hours) : undefined), [hours]);

  const summary = useAsync(
    (signal) => api.requests.summary({ started_after: startedAfter }, signal),
    [startedAfter],
  );
  const backends = useAsync((signal) => api.backends.list({ limit: 200 }, signal), []);
  const ready = useAsync((signal) => api.readyz(signal), []);

  const statusRows = summary.data?.by_status ?? [];
  const total = statusRows.reduce((accumulator, row) => accumulator + row.total, 0);
  const successCount = statusRows.reduce(
    (accumulator, row) => (row.status === "success" ? accumulator + row.total : accumulator),
    0,
  );
  const latency = summary.data?.latency;
  const backendItems = backends.data?.items ?? [];
  const activeCount = backendItems.reduce(
    (accumulator, item) => (item.state === "active" ? accumulator + 1 : accumulator),
    0,
  );

  const backendStats = summary.data?.by_backend ?? [];
  const maxBackendTotal = backendStats.reduce(
    (accumulator, row) => Math.max(accumulator, row.total),
    0,
  );
  const maxStatusTotal = statusRows.reduce(
    (accumulator, row) => Math.max(accumulator, row.total),
    0,
  );

  const pool = ready.data?.pool;

  return (
    <main className="page">
      <PageHeader
        title="总览"
        lead="这一页只读聚合视图：请求量、成功率、延迟分位、后端分布与数据库依赖探测，全部来自控制层公开的只读端点。"
        actions={
          <button type="button" className="btn" onClick={summary.reload} disabled={summary.loading}>
            刷新聚合
          </button>
        }
      />

      <Panel title="统计窗口" subtitle="时间窗口只影响聚合与状态分布，不影响后端列表">
        <div className="toolbar">
          <Field label="时间范围" hint="以 started_at 为过滤口径">
            <select
              className="field__select"
              value={range}
              onChange={(event) => setRange(event.target.value)}
            >
              {RANGE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </Field>
          <span className="muted">
            起点：{startedAfter ? startedAfter : "不限"} · 无记录时各项指标显示为 —
          </span>
        </div>
      </Panel>

      <StateView
        loading={summary.loading}
        error={summary.error}
        onRetry={summary.reload}
      >
        <div className="grid grid--4">
          <Metric label="请求总量" value={formatInt(total)} hint={`窗口内 ${statusRows.length} 种状态`} />
          <Metric
            label="成功率"
            value={formatPercent(successCount, total)}
            hint={`成功 ${formatInt(successCount)} / 总计 ${formatInt(total)}`}
            tone={total > 0 && successCount === total ? "success" : "default"}
          />
          <Metric label="P50 总耗时" value={formatMs(latency?.p50_ms)} hint={`样本 ${formatInt(latency?.samples ?? 0)}`} />
          <Metric label="P95 总耗时" value={formatMs(latency?.p95_ms)} hint="尾延迟看这一项" />
          <Metric label="P99 总耗时" value={formatMs(latency?.p99_ms)} hint={`最慢 ${formatMs(latency?.max_ms)}`} />
          <Metric
            label="运行中后端"
            value={`${activeCount} / ${backendItems.length}`}
            hint="active 实例数 / 已登记总数"
            tone={activeCount === 0 && backendItems.length > 0 ? "danger" : "default"}
          />
        </div>
      </StateView>

      <div className="split">
        <Panel title="按后端分布" subtitle="请求量 / 成功率 / 平均耗时">
          <StateView
            loading={summary.loading}
            error={summary.error}
            isEmpty={backendStats.length === 0}
            emptyText="窗口内没有请求记录"
            onRetry={summary.reload}
          >
            <div className="stack">
              {backendStats.map((row) => {
                const key = row.backend_id ?? -1;
                const owner = backendItems.find((item) => item.id === row.backend_id);
                return (
                  <div key={key} className="stack">
                    <BarRow
                      label={owner ? owner.name : `未归属 #${row.backend_id ?? "?"}`}
                      value={row.total}
                      max={maxBackendTotal}
                      display={formatInt(row.total)}
                      tone={row.failures > 0 ? "warning" : "accent"}
                    />
                    <span className="faint">
                      成功 {formatInt(row.successes)} · 失败 {formatInt(row.failures)} · 成功率{" "}
                      {formatPercent(row.successes, row.total)} · 平均总耗时 {formatMs(row.avg_total_ms)} ·
                      平均首字 {formatMs(row.avg_ttft_ms)}
                    </span>
                  </div>
                );
              })}
            </div>
          </StateView>
        </Panel>

        <Panel title="按状态分布" subtitle="写入时即固定的终态">
          <StateView
            loading={summary.loading}
            error={summary.error}
            isEmpty={statusRows.length === 0}
            emptyText="窗口内没有请求记录"
            onRetry={summary.reload}
          >
            <div className="stack">
              {statusRows.map((row) => (
                <BarRow
                  key={row.status}
                  label={requestStatusLabel(row.status)}
                  value={row.total}
                  max={maxStatusTotal}
                  display={formatInt(row.total)}
                  tone={
                    statusTone(row.status) === "success"
                      ? "accent"
                      : statusTone(row.status) === "warning"
                        ? "warning"
                        : "danger"
                  }
                />
              ))}
            </div>
          </StateView>
        </Panel>
      </div>

      <div className="split">
        <Panel
          title="依赖探测"
          subtitle="/readyz"
          actions={
            <button type="button" className="btn btn--sm" onClick={ready.reload} disabled={ready.loading}>
              重新探测
            </button>
          }
        >
          <StateView loading={ready.loading} error={ready.error} onRetry={ready.reload}>
            <div className="kv">
              <span className="kv__key">整体状态</span>
              <span className="kv__value">{ready.data?.status ?? "—"}</span>
              <span className="kv__key">数据库</span>
              <span className="kv__value">{ready.data?.database ?? "—"}</span>
              <span className="kv__key">结构版本</span>
              <span className="kv__value">v{ready.data?.schema_version ?? "?"}</span>
              <span className="kv__key">连接池</span>
              <span className="kv__value">
                {pool
                  ? `size ${pool.size} · 空闲 ${pool.checked_in} · 占用 ${pool.checked_out} · 溢出 ${pool.overflow}`
                  : "—"}
              </span>
              <span className="kv__key">失败项</span>
              <span className="kv__value">
                {ready.data?.failed && ready.data.failed.length > 0 ? ready.data.failed.join(" / ") : "无"}
              </span>
            </div>
          </StateView>
        </Panel>

        <Panel
          title="后端实例"
          subtitle={`${backendItems.length} 条`}
          actions={
            <button type="button" className="btn btn--sm" onClick={backends.reload} disabled={backends.loading}>
              刷新列表
            </button>
          }
        >
          <StateView
            loading={backends.loading}
            error={backends.error}
            isEmpty={backendItems.length === 0}
            emptyText="还没有登记任何后端"
            onRetry={backends.reload}
          >
            <div className="stack">
              {backendItems.map((item) => (
                <div className="row" key={item.id}>
                  <span
                    className={`badge badge--${item.state === "active" ? "success" : item.state === "draining" ? "warning" : "danger"}`}
                  >
                    {backendStateLabel(item.state)}
                  </span>
                  <span>{item.name}</span>
                  <span className="faint">
                    {engineLabel(item.engine)} · 权重 {item.weight} · 并发 {item.max_concurrency}
                  </span>
                </div>
              ))}
            </div>
          </StateView>
        </Panel>
      </div>
    </main>
  );
}
