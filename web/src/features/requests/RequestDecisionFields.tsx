import { ROUTING_POLICIES } from "../../api/types";
import { Field } from "../../components/Field";
import { policyLabel } from "../../lib/format";
import type { RecordDraft } from "./record-draft";

export type RequestDecisionFieldsProps = {
  draft: RecordDraft;
  onChange: (patch: Partial<RecordDraft>) => void;
};

export function RequestDecisionFields({ draft, onChange }: RequestDecisionFieldsProps) {
  return (
    <>
      <Field label="同时写入调度决策快照" hint="不写快照时这一条只有结果、没有归因">
        <select
          className="field__select"
          value={draft.with_decision ? "yes" : "no"}
          onChange={(event) => onChange({ with_decision: event.target.value === "yes" })}
        >
          <option value="yes">写入</option>
          <option value="no">不写入</option>
        </select>
      </Field>

      {draft.with_decision ? (
        <div className="stack">
          <div className="grid grid--2">
            <Field label="策略">
              <select
                className="field__select"
                value={draft.policy}
                onChange={(event) => onChange({ policy: event.target.value })}
              >
                {ROUTING_POLICIES.map((value) => (
                  <option key={value} value={value}>
                    {policyLabel(value)}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="候选后端 ID" hint="逗号分隔，例如 1,2,3">
              <input
                className="field__input"
                value={draft.candidate_ids}
                onChange={(event) => onChange({ candidate_ids: event.target.value })}
              />
            </Field>
            <Field label="最终选中 ID" hint="必须来自候选列表，否则返回 422">
              <input
                className="field__input"
                type="number"
                min="1"
                value={draft.chosen_id}
                onChange={(event) => onChange({ chosen_id: event.target.value })}
              />
            </Field>
            <Field label="降级原因" hint="无可用候选时的兜底说明">
              <input
                className="field__input"
                value={draft.fallback_reason}
                onChange={(event) => onChange({ fallback_reason: event.target.value })}
              />
            </Field>
          </div>
          <Field label="打分明细（JSON 对象）" hint="留 {} 表示只记策略、不记明细">
            <textarea
              className="field__textarea"
              rows={4}
              value={draft.score_snapshot}
              onChange={(event) => onChange({ score_snapshot: event.target.value })}
            />
          </Field>
        </div>
      ) : null}
    </>
  );
}
