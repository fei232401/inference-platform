import { useState } from "react";

import { api } from "../api/endpoints";
import type { CandidateListOut } from "../api/types";
import { ROUTING_POLICIES } from "../api/types";
import { BarRow } from "../components/BarRow";
import { Field } from "../components/Field";
import { PageHeader } from "../components/PageHeader";
import { Panel } from "../components/Panel";
import { StateView } from "../components/StateView";
import { useAsync } from "../hooks/useAsync";
import { useAsyncAction } from "../hooks/useAsyncAction";
import { formatMicros, formatMs, formatScore, policyLabel } from "../lib/format";
import { policyExpression, policyFactors, reasonLabel } from "../lib/scoring";

type FactorKey = "health" | "latency" | "cost";

const FACTOR_LABEL: Record<FactorKey, string> = {
  health: "健康因子",
  latency: "延迟因子",
  cost: "成本因子",
};

export function Routing() {
  const names = useAsync(() => api.models.names(), []);
  const [modelName, setModelName] = useState("");
  const [policy, setPolicy] = useState<string>("weighted_random");
  const [result, setResult] = useState<CandidateListOut | null>(null);

  const query = useAsyncAction(api.routing.candidates);

  const ranked = result?.ranked ?? [];
  const eligible = ranked.filter((candidate) => !candidate.excluded);
  const maxScore = ranked.reduce((accumulator, candidate) => Math.max(accumulator, candidate.score), 0);
  const totalEligibleScore = eligible.reduce((accumulator, candidate) => accumulator + candidate.score, 0);
  const factors = policyFactors(policy);

  const modelOptions = names.data ?? [];

  async function handleQuery(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (modelName.length === 0) return;
    const response = await query.run({ model_name: modelName, policy });
    if (response !== null) setResult(response);
  }

  return (
    <main className="page">
      <PageHeader
        title="候选打分"
        lead="查看模型的健康与评分候选。此页面不含实时并发占用；实际准入和后端选择发生在发送推理请求时。"
      />

      <Panel title="查询条件" subtitle="GET /api/v1/routing/candidates">
        <form className="toolbar" onSubmit={handleQuery}>
          <Field label="模型" hint={modelOptions.length === 0 ? "模型目录为空" : `${modelOptions.length} 个可选`}>
            <select
              className="field__select"
              value={modelName}
              onChange={(event) => setModelName(event.target.value)}
            >
              <option value="">请选择</option>
              {modelOptions.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="策略">
            <select
              className="field__select"
              value={policy}
              onChange={(event) => setPolicy(event.target.value)}
            >
              {ROUTING_POLICIES.map((value) => (
                <option key={value} value={value}>
                  {policyLabel(value)}
                </option>
              ))}
            </select>
          </Field>
          <button
            type="submit"
            className="btn btn--primary"
            disabled={query.pending || modelName.length === 0}
          >
            {query.pending ? "计算中" : "计算打分"}
          </button>
        </form>
        {query.error ? (
          <div className="error-box mt-3">
            <span className="error-box__title">计算失败 · {query.error.code}</span>
            <span>{query.error.message}</span>
          </div>
        ) : null}
      </Panel>

      <div className="split">
        <Panel title="打分公式" subtitle="与数据面权重表同源">
          <div className="stack">
            <code className="code-block">{policyExpression(policy)}</code>
            <span className="muted">
              最终分数 = 权重 × 健康因子^a × 延迟因子^b × 成本因子^c，指数即下表系数。系数为 0
              表示该维度不参与本策略。
            </span>
            {factors ? (
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>维度</th>
                      <th className="num">指数</th>
                      <th>取值规则</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td>{FACTOR_LABEL.health}</td>
                      <td className="num">{factors.health}</td>
                      <td className="faint">通过 1.0 · 无数据 0.5 · 失败 0.0（直接排除）</td>
                    </tr>
                    <tr>
                      <td>{FACTOR_LABEL.latency}</td>
                      <td className="num">{factors.latency}</td>
                      <td className="faint">1 − 0.6 × min(延迟 / 2000ms, 1) · 无样本 0.5</td>
                    </tr>
                    <tr>
                      <td>{FACTOR_LABEL.cost}</td>
                      <td className="num">{factors.cost}</td>
                      <td className="faint">min(5e-6 / 单价, 1) · 单价为 0 视为 1.0</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            ) : null}
          </div>
        </Panel>

        <Panel title="选点规则" subtitle="实际请求还会检查并发容量">
          <div className="stack">
            <span className="muted">
              候选先按分数降序排列，再累加分数得到权重区间：分数越高，占的区间越宽，被抽中的概率越大。
              随机数落在哪个区间，就选哪个后端。
            </span>
            <code className="code-block">
              {"cursor = clamp(fraction, 0, 1) × Σscore\n" +
                "running += score\n" +
                "if cursor <= running: 命中"}
            </code>
            <span className="muted">
              加权随机使用随机抽样，不保证重放选择相同后端。最少进行中请求策略使用当前路由实例的请求计数，相同计数随机选择；此处的分数不能推导该策略的选择概率。
            </span>
            {result ? (
              <div className="kv">
                <span className="kv__key">模型</span>
                <span className="kv__value">{result.model_name}</span>
                <span className="kv__key">策略</span>
                <span className="kv__value">
                  {policyLabel(result.policy)}（{result.policy}）
                </span>
                <span className="kv__key">候选总数</span>
                <span className="kv__value">{ranked.length}</span>
                <span className="kv__key">可参与</span>
                <span className="kv__value">{eligible.length}</span>
                <span className="kv__key">分数总和</span>
                <span className="kv__value">{formatScore(totalEligibleScore, 4)}</span>
              </div>
            ) : null}
          </div>
        </Panel>
      </div>

      <Panel
        title="排序结果"
        subtitle={result ? `${result.model_name} · ${policyLabel(result.policy)}` : "尚未查询"}
        flush
      >
        <StateView
          loading={query.pending}
          error={query.error}
          isEmpty={result === null}
          emptyText="选好模型与策略后点击「计算打分」"
        >
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>名次</th>
                  <th>后端</th>
                  <th>得分</th>
                  <th>得分对比</th>
                  <th className="num">权重</th>
                  <th className="num">延迟</th>
                  <th className="num">单价</th>
                  <th>命中概率</th>
                  <th>依据</th>
                </tr>
              </thead>
              <tbody>
                {ranked.map((candidate, index) => (
                  <tr key={candidate.backend_id}>
                    <td className="num">{index + 1}</td>
                    <td>
                      <span className="row">
                        <span>{candidate.name}</span>
                        <span className="faint">#{candidate.backend_id}</span>
                        {candidate.excluded ? (
                          <span className="badge badge--danger">已排除</span>
                        ) : candidate.healthy === true ? (
                          <span className="badge badge--success">健康</span>
                        ) : candidate.healthy === false ? (
                          <span className="badge badge--danger">异常</span>
                        ) : (
                          <span className="badge">无数据</span>
                        )}
                      </span>
                    </td>
                    <td className="mono">{formatScore(candidate.score)}</td>
                    <td>
                      <BarRow
                        label=""
                        value={candidate.excluded ? 0 : candidate.score}
                        max={maxScore}
                        display={candidate.excluded ? "排除" : ""}
                        tone={candidate.excluded ? "muted" : "accent"}
                      />
                    </td>
                    <td className="num">{candidate.weight}</td>
                    <td className="num">{formatMs(candidate.latency_ms, 0)}</td>
                    <td className="num">{formatMicros(candidate.cost_per_token)}</td>
                    <td className="mono">
                      {result?.policy !== "weighted_random" || candidate.excluded || totalEligibleScore <= 0
                        ? "—"
                        : `${((candidate.score / totalEligibleScore) * 100).toFixed(1)}%`}
                    </td>
                    <td className="faint">
                      <span className="stack">
                        {candidate.reasons.length > 0 ? (
                          candidate.reasons.map((reason) => (
                            <span key={reason}>{reasonLabel(reason)}</span>
                          ))
                        ) : (
                          <span>无</span>
                        )}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </StateView>
      </Panel>
    </main>
  );
}
