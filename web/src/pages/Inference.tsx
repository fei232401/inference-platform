import { useState } from "react";

import { api } from "../api/endpoints";
import type { RouteOut } from "../api/types";
import { ROUTING_POLICIES } from "../api/types";
import { ToneBadge } from "../components/Badges";
import { Field } from "../components/Field";
import { Metric } from "../components/Metric";
import { PageHeader } from "../components/PageHeader";
import { Panel } from "../components/Panel";
import { StateView } from "../components/StateView";
import { useAsync } from "../hooks/useAsync";
import { useAsyncAction } from "../hooks/useAsyncAction";
import { formatMs, policyLabel } from "../lib/format";

const DEFAULT_PROMPT = "用一句话解释什么是路由。";
const DEFAULT_MAX_TOKENS = "64";

export function Inference() {
  const models = useAsync(() => api.models.names(), []);
  const backends = useAsync(() => api.backends.list({ limit: 50, offset: 0 }), []);

  const [modelName, setModelName] = useState("");
  const [policy, setPolicy] = useState<string>("least_inflight");
  const [prompt, setPrompt] = useState(DEFAULT_PROMPT);
  const [maxTokens, setMaxTokens] = useState(DEFAULT_MAX_TOKENS);
  const [engineModels, setEngineModels] = useState<Record<string, string>>({});
  const [result, setResult] = useState<RouteOut | null>(null);

  const route = useAsyncAction(api.inference.route);

  const modelOptions = models.data ?? [];
  const backendItems = backends.data?.items ?? [];
  const selectedModel = modelName || modelOptions[0] || "";

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (selectedModel.length === 0 || prompt.trim().length === 0) return;
    setResult(null);

    const mapping: Record<string, string> = {};
    for (const item of backendItems) {
      const value = (engineModels[item.name] ?? "").trim();
      if (value.length > 0) mapping[item.name] = value;
    }

    const parsedMax = Number.parseInt(maxTokens, 10);
    const response = await route.run({
      model_name: selectedModel,
      prompt,
      policy,
      max_tokens: Number.isFinite(parsedMax) && parsedMax > 0 ? parsedMax : undefined,
      engine_models: mapping,
    });
    if (response !== null) setResult(response);
  }

  const ranked = result?.decision.score_snapshot.ranked ?? [];

  return (
    <main className="page">
      <PageHeader
        title="发起推理"
        lead="选择模型并发送问题。平台会过滤不可用和满载的后端，再选择实例生成回答。"
      />

      <Panel title="请求" subtitle="POST /v1/route（经 nginx 反代到 router）">
        <form className="stack" onSubmit={handleSubmit}>
          <div className="toolbar">
            <Field
              label="模型（控制层的逻辑名）"
              hint={modelOptions.length === 0 ? "模型目录为空" : `${modelOptions.length} 个可选`}
            >
              <select
                className="field__select"
                value={selectedModel}
                onChange={(event) => setModelName(event.target.value)}
              >
                {modelOptions.length === 0 ? <option value="">（无）</option> : null}
                {modelOptions.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </select>
            </Field>

            <Field label="调度策略" hint="最少进行中请求按当前路由实例计数；满载时拒绝，不排队">
              <select
                className="field__select"
                value={policy}
                onChange={(event) => setPolicy(event.target.value)}
              >
                {ROUTING_POLICIES.map((name) => (
                  <option key={name} value={name}>
                    {policyLabel(name)}
                  </option>
                ))}
              </select>
            </Field>

            <Field label="max_tokens" hint="上限 2048">
              <input
                className="field__input"
                type="number"
                min={1}
                max={2048}
                value={maxTokens}
                onChange={(event) => setMaxTokens(event.target.value)}
              />
            </Field>
          </div>

          <Field label="提示词">
            <textarea
              className="field__textarea"
              rows={3}
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
            />
          </Field>

          <Panel
            title="引擎侧模型名映射"
            subtitle="选填。控制层的 model 表存的是逻辑名，而 ollama 要 qwen2.5:3b、vLLM 要 /models/qwen2.5-3b-awq —— 这个「后端怎么称呼这个模型」目前没有进 schema，所以由调用方带。留空则直接用逻辑名。"
          >
            <div className="stack">
              {backendItems.length === 0 ? (
                <span className="faint">还没有登记任何后端实例</span>
              ) : (
                backendItems.map((item) => (
                  <div className="toolbar" key={item.id}>
                    <Field label={item.name} hint={`engine=${item.engine}`}>
                      <input
                        className="field__input"
                        value={engineModels[item.name] ?? ""}
                        placeholder={selectedModel}
                        onChange={(event) =>
                          setEngineModels((current) => ({
                            ...current,
                            [item.name]: event.target.value,
                          }))
                        }
                      />
                    </Field>
                  </div>
                ))
              )}
            </div>
          </Panel>

          <div className="row">
            <button
              type="submit"
              className="btn btn--primary"
              disabled={route.pending || selectedModel.length === 0 || prompt.trim().length === 0}
            >
              {route.pending ? "生成中…" : "发送"}
            </button>
            <span className="faint">慢后端可能要几秒到几十秒，请等</span>
          </div>
        </form>
      </Panel>

      <StateView
        loading={false}
        error={route.error}
        isEmpty={result === null}
        emptyText="还没有发起过请求。点上面的「发送」。"
      >
        {result === null ? null : (
          <div className="stack">
            <Panel title="生成结果" subtitle={`request_id=${result.request_id ?? "（未记录）"}`}>
              <div className="stack">
                <div className="row">
                  <Metric label="选中后端" value={result.backend.name} hint={`engine=${result.backend.engine}`} tone="success" />
                  <Metric label="总耗时" value={formatMs(result.timings.total_ms)} />
                  <Metric label="prompt tokens" value={String(result.usage.prompt_tokens ?? "—")} />
                  <Metric label="completion tokens" value={String(result.usage.completion_tokens ?? "—")} />
                </div>
                <div>
                  <span className="faint">模型输出</span>
                  <pre className="code-block">{result.output || "（空）"}</pre>
                </div>
                <div className="row">
                  <ToneBadge tone={result.recorded ? "success" : "warning"}>
                    {result.recorded ? "决策已写回 PostgreSQL" : "决策未能写回（生成结果仍有效）"}
                  </ToneBadge>
                  <span className="faint">引擎侧模型名 = {result.timings.engine_model}</span>
                  <span className="faint">后端地址 = {result.backend.url}</span>
                </div>
              </div>
            </Panel>

            <Panel
              title="这次的路由决策"
              subtitle={`policy=${policyLabel(result.decision.policy)}　chosen=${result.decision.chosen_id ?? "—"}`}
            >
              <div className="stack">
                <span className="faint">
                  决策时的候选快照。最少进行中请求策略使用请求数选择，分数仅为控制面参考。
                </span>
                <div className="table-wrap">
                  <table className="table">
                    <thead>
                      <tr>
                        <th>后端</th>
                        <th>分数</th>
                        <th>排除</th>
                        <th>健康</th>
                        <th>探测延迟</th>
                        <th>进行中 / 上限</th>
                        <th>原因</th>
                      </tr>
                    </thead>
                    <tbody>
                      {ranked.map((candidate) => (
                        <tr key={candidate.backend_id}>
                          <td>{candidate.name}</td>
                          <td className="mono">{candidate.score}</td>
                          <td>
                            <ToneBadge tone={candidate.excluded ? "danger" : "success"}>
                              {candidate.excluded ? "是" : "否"}
                            </ToneBadge>
                          </td>
                          <td>{candidate.healthy === null ? "未知" : candidate.healthy ? "健康" : "不健康"}</td>
                          <td>{candidate.latency_ms === null ? "—" : formatMs(candidate.latency_ms)}</td>
                          <td>{candidate.inflight ?? "—"} / {candidate.max_inflight ?? "—"}</td>
                          <td className="faint">{candidate.reasons.join(" / ")}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div>
                  <span className="faint">决策快照（原样来自后端）</span>
                  <pre className="code-block">{JSON.stringify(result.decision, null, 2)}</pre>
                </div>
              </div>
            </Panel>
          </div>
        )}
      </StateView>
    </main>
  );
}
