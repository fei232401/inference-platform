import type { ApiKeyOut, BackendOut } from "../../api/types";
import { REQUEST_STATUS_VALUES } from "../../api/types";
import { Field } from "../../components/Field";
import { requestStatusLabel } from "../../lib/format";
import type { RecordDraft } from "./record-draft";

export type RequestBasicFieldsProps = {
  draft: RecordDraft;
  onChange: (patch: Partial<RecordDraft>) => void;
  backends: BackendOut[];
  keys: ApiKeyOut[];
};

export function RequestBasicFields({ draft, onChange, backends, keys }: RequestBasicFieldsProps) {
  return (
    <>
      <div className="grid grid--2">
        <Field label="模型名">
          <input
            className="field__input"
            required
            value={draft.model_name}
            placeholder="qwen2.5:7b"
            onChange={(event) => onChange({ model_name: event.target.value })}
          />
        </Field>
        <Field label="状态">
          <select
            className="field__select"
            value={draft.status}
            onChange={(event) => onChange({ status: event.target.value })}
          >
            {REQUEST_STATUS_VALUES.map((value) => (
              <option key={value} value={value}>
                {requestStatusLabel(value)}
              </option>
            ))}
          </select>
        </Field>
        <Field label="开始时间">
          <input
            className="field__input"
            type="datetime-local"
            required
            value={draft.started_at}
            onChange={(event) => onChange({ started_at: event.target.value })}
          />
        </Field>
        <Field label="结束时间" hint="四种状态都要求已结束，所以这里是必填">
          <input
            className="field__input"
            type="datetime-local"
            required
            value={draft.finished_at}
            onChange={(event) => onChange({ finished_at: event.target.value })}
          />
        </Field>
        <Field label="后端">
          <select
            className="field__select"
            value={draft.backend_id}
            onChange={(event) => onChange({ backend_id: event.target.value })}
          >
            <option value="">不指定</option>
            {backends.map((item) => (
              <option key={item.id} value={String(item.id)}>
                #{item.id} {item.name}
              </option>
            ))}
          </select>
        </Field>
        <Field label="密钥">
          <select
            className="field__select"
            value={draft.api_key_id}
            onChange={(event) => onChange({ api_key_id: event.target.value })}
          >
            <option value="">不指定</option>
            {keys.map((item) => (
              <option key={item.id} value={String(item.id)}>
                #{item.id} {item.name}
              </option>
            ))}
          </select>
        </Field>
        <Field label="会话 ID" hint="同一会话链路的粘滞依据">
          <input
            className="field__input"
            value={draft.session_id}
            onChange={(event) => onChange({ session_id: event.target.value })}
          />
        </Field>
        <Field label="错误码" hint="success 时留空；失败状态必填">
          <input
            className="field__input"
            value={draft.error_code}
            placeholder="upstream_503 / deadline_exceeded"
            onChange={(event) => onChange({ error_code: event.target.value })}
          />
        </Field>
      </div>

      <div className="grid grid--4">
        <Field label="输入 token">
          <input
            className="field__input"
            type="number"
            min="0"
            value={draft.prompt_tokens}
            onChange={(event) => onChange({ prompt_tokens: event.target.value })}
          />
        </Field>
        <Field label="输出 token">
          <input
            className="field__input"
            type="number"
            min="0"
            value={draft.completion_tokens}
            onChange={(event) => onChange({ completion_tokens: event.target.value })}
          />
        </Field>
        <Field label="首字延迟（ms）">
          <input
            className="field__input"
            type="number"
            step="0.1"
            min="0"
            value={draft.ttft_ms}
            onChange={(event) => onChange({ ttft_ms: event.target.value })}
          />
        </Field>
        <Field label="总耗时（ms）">
          <input
            className="field__input"
            type="number"
            step="0.1"
            min="0"
            value={draft.total_ms}
            onChange={(event) => onChange({ total_ms: event.target.value })}
          />
        </Field>
      </div>
    </>
  );
}
