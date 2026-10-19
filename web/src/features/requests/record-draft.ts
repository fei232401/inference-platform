import type { RequestLogIn } from "../../api/types";

export type RecordDraft = {
  model_name: string;
  status: string;
  started_at: string;
  finished_at: string;
  backend_id: string;
  api_key_id: string;
  session_id: string;
  prompt_tokens: string;
  completion_tokens: string;
  ttft_ms: string;
  total_ms: string;
  error_code: string;
  with_decision: boolean;
  policy: string;
  candidate_ids: string;
  chosen_id: string;
  fallback_reason: string;
  score_snapshot: string;
};

function toLocalInput(date: Date): string {
  const pad = (value: number) => value.toString().padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export function buildRecordDraft(): RecordDraft {
  const now = new Date();
  const before = new Date(now.getTime() - 60_000);
  return {
    model_name: "",
    status: "success",
    started_at: toLocalInput(before),
    finished_at: toLocalInput(now),
    backend_id: "",
    api_key_id: "",
    session_id: "",
    prompt_tokens: "",
    completion_tokens: "",
    ttft_ms: "",
    total_ms: "",
    error_code: "",
    with_decision: true,
    policy: "weighted_random",
    candidate_ids: "",
    chosen_id: "",
    fallback_reason: "",
    score_snapshot: "{}",
  };
}

export function optionalInt(value: string): number | null {
  return value.trim().length > 0 ? Number(value) : null;
}

export function optionalText(value: string): string | null {
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

export type BuildResult =
  | { ok: true; payload: RequestLogIn }
  | { ok: false; message: string };

export function toRecordPayload(draft: RecordDraft): BuildResult {
  let snapshot: Record<string, unknown> | null = null;

  if (draft.with_decision) {
    let parsed: unknown;
    try {
      parsed = JSON.parse(draft.score_snapshot);
    } catch (cause) {
      return {
        ok: false,
        message:
          cause instanceof Error
            ? `打分明细不是合法 JSON：${cause.message}`
            : "打分明细不是合法 JSON",
      };
    }
    if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
      return { ok: false, message: "打分明细必须是 JSON 对象，例如 {}" };
    }
    snapshot = parsed as Record<string, unknown>;
  }

  const candidateIds = draft.candidate_ids
    .split(",")
    .map((value) => value.trim())
    .filter((value) => value.length > 0)
    .map((value) => Number(value));

  return {
    ok: true,
    payload: {
      model_name: draft.model_name.trim(),
      status: draft.status,
      started_at: new Date(draft.started_at).toISOString(),
      finished_at: new Date(draft.finished_at).toISOString(),
      backend_id: optionalInt(draft.backend_id),
      api_key_id: optionalInt(draft.api_key_id),
      session_id: optionalText(draft.session_id),
      prompt_tokens: optionalInt(draft.prompt_tokens),
      completion_tokens: optionalInt(draft.completion_tokens),
      ttft_ms: optionalText(draft.ttft_ms),
      total_ms: optionalText(draft.total_ms),
      error_code: optionalText(draft.error_code),
      decision:
        snapshot === null
          ? null
          : {
              policy: draft.policy,
              candidate_ids: candidateIds,
              chosen_id: optionalInt(draft.chosen_id),
              score_snapshot: snapshot,
              fallback_reason: optionalText(draft.fallback_reason),
            },
    },
  };
}
