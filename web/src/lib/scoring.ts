export type FactorKey = "health" | "latency" | "cost";

export const POLICY_FACTORS: Record<string, Record<FactorKey, number>> = {
  weighted_random: { health: 1, latency: 1, cost: 1 },
  least_latency: { health: 1, latency: 3, cost: 0 },
  least_inflight: { health: 1, latency: 0, cost: 0 },
  round_robin: { health: 1, latency: 0, cost: 0 },
  session_sticky: { health: 1, latency: 0.5, cost: 0.5 },
  prefix_affinity: { health: 1, latency: 0, cost: 0 },
};

export const LATENCY_BASELINE_MS = 2000;
export const COST_BASELINE = 0.000005;

const REASON_LABEL: Record<string, string> = {
  health_ok: "健康探测通过，因子 1.0",
  health_unknown: "无健康数据，因子 0.5",
  health_failed: "健康探测失败，因子 0.0 并直接排除",
  latency_measured: "有延迟样本，1 − 0.6 × min(延迟 / 2000, 1)",
  latency_unknown: "无延迟样本，因子 0.5",
  cost_free: "零单价，因子 1.0",
  cost_measured: "按单价折算，min(5e-6 / 单价, 1)",
};

export function reasonLabel(reason: string): string {
  return REASON_LABEL[reason] ?? reason;
}

export function policyFactors(policy: string): Record<FactorKey, number> | null {
  return POLICY_FACTORS[policy] ?? null;
}

export function policyExpression(policy: string): string {
  if (policy === "least_inflight") return "过滤健康与容量后，选择本进程进行中请求最少的后端；相同数量随机选择";
  if (policy === "prefix_affinity") return "按提示词前缀哈希做 rendezvous 排序，优先命中同一后端的 KV 前缀缓存；超过有界负载上限时顺延到下一个";
  const factors = POLICY_FACTORS[policy];
  if (factors === undefined) return "未知策略";
  const terms: string[] = ["权重"];
  if (factors.health > 0) terms.push(`健康^${factors.health}`);
  if (factors.latency > 0) terms.push(`延迟^${factors.latency}`);
  if (factors.cost > 0) terms.push(`成本^${factors.cost}`);
  return terms.join(" × ");
}
