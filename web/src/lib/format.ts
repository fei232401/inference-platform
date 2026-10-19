const BACKEND_STATE_LABEL: Record<string, string> = {
  active: "运行中",
  draining: "排空中",
  disabled: "已下线",
};

const REQUEST_STATUS_LABEL: Record<string, string> = {
  success: "成功",
  error: "失败",
  timeout: "超时",
  rejected: "被拒",
};

const POLICY_LABEL: Record<string, string> = {
  weighted_random: "加权随机",
  least_latency: "探测延迟优先",
  least_inflight: "最少进行中请求",
  round_robin: "轮询",
  session_sticky: "会话粘滞",
};

const ENGINE_LABEL: Record<string, string> = {
  ollama: "Ollama",
  openai: "OpenAI 兼容",
};

export const ENGINE_VALUES: readonly string[] = ["ollama", "openai"];

export const SCOPE_VALUES: readonly string[] = ["infer", "admin"];

export function backendStateLabel(state: string): string {
  return BACKEND_STATE_LABEL[state] ?? state;
}

export function requestStatusLabel(status: string): string {
  return REQUEST_STATUS_LABEL[status] ?? status;
}

export function policyLabel(policy: string): string {
  return POLICY_LABEL[policy] ?? policy;
}

export function engineLabel(engine: string): string {
  return ENGINE_LABEL[engine] ?? engine;
}

export function stateTone(state: string): "success" | "warning" | "danger" {
  if (state === "active") return "success";
  if (state === "draining") return "warning";
  return "danger";
}

export function statusTone(status: string): "success" | "warning" | "danger" {
  if (status === "success") return "success";
  if (status === "timeout") return "warning";
  return "danger";
}

function pad(value: number): string {
  return value.toString().padStart(2, "0");
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return `${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

export function formatClock(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

export function formatRelative(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const seconds = Math.round((Date.now() - date.getTime()) / 1000);
  if (seconds < 0) return "刚刚";
  if (seconds < 60) return `${seconds} 秒前`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)} 分钟前`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} 小时前`;
  return `${Math.floor(seconds / 86400)} 天前`;
}

export function formatInt(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return value.toLocaleString("zh-CN");
}

export function formatMs(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined) return "—";
  return `${value.toFixed(digits)} ms`;
}

export function formatMicros(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  if (value <= 0) return "免费";
  return value.toExponential(2);
}

export function formatScore(value: number | null | undefined, digits = 4): string {
  if (value === null || value === undefined) return "—";
  return value.toFixed(digits);
}

export function formatPercent(part: number, total: number, digits = 1): string {
  if (total <= 0) return "—";
  return `${((part / total) * 100).toFixed(digits)}%`;
}

export function formatBytes(value: number): string {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

export function shortId(value: string | null | undefined, head = 8): string {
  if (!value) return "—";
  return value.length <= head ? value : value.slice(0, head);
}

export function truncate(value: string, max = 48): string {
  return value.length <= max ? value : `${value.slice(0, max - 1)}…`;
}

export function relativeBarWidth(value: number, max: number): number {
  if (max <= 0) return 0;
  return Math.max(2, Math.round((value / max) * 100));
}
