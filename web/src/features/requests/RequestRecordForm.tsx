import { useState } from "react";

import { api } from "../../api/endpoints";
import type { ApiKeyOut, BackendOut } from "../../api/types";
import { useAsyncAction } from "../../hooks/useAsyncAction";
import { RequestBasicFields } from "./RequestBasicFields";
import { RequestDecisionFields } from "./RequestDecisionFields";
import { buildRecordDraft, toRecordPayload } from "./record-draft";
import type { RecordDraft } from "./record-draft";

export type RequestRecordFormProps = {
  backends: BackendOut[];
  keys: ApiKeyOut[];
  onRecorded: (message: string) => void;
};

export function RequestRecordForm({ backends, keys, onRecorded }: RequestRecordFormProps) {
  const [draft, setDraft] = useState<RecordDraft>(() => buildRecordDraft());
  const [validation, setValidation] = useState<string | null>(null);
  const recordAction = useAsyncAction(api.requests.record);

  function patch(changes: Partial<RecordDraft>) {
    setDraft((current) => ({ ...current, ...changes }));
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setValidation(null);

    const built = toRecordPayload(draft);
    if (!built.ok) {
      setValidation(built.message);
      return;
    }

    const created = await recordAction.run(built.payload);
    if (created === null) return;
    onRecorded(
      `已写入请求 ${created.request_id}${created.decision ? "，含调度决策快照" : ""}`,
    );
    setDraft(buildRecordDraft());
  }

  return (
    <form className="stack" onSubmit={handleSubmit}>
      <RequestBasicFields draft={draft} onChange={patch} backends={backends} keys={keys} />
      <RequestDecisionFields draft={draft} onChange={patch} />

      <div className="row">
        <button type="submit" className="btn btn--primary" disabled={recordAction.pending}>
          {recordAction.pending ? "写入中" : "写入记录"}
        </button>
        <button type="button" className="btn" onClick={() => setDraft(buildRecordDraft())}>
          重置表单
        </button>
      </div>
      {validation ? <span className="muted">{validation}</span> : null}
      {recordAction.error ? (
        <div className="error-box">
          <span className="error-box__title">
            写入失败 · {recordAction.error.code}
            {recordAction.error.status > 0 ? ` · HTTP ${recordAction.error.status}` : ""}
          </span>
          <span>{recordAction.error.message}</span>
          {Object.keys(recordAction.error.detail).length > 0 ? (
            <pre className="code-block">{JSON.stringify(recordAction.error.detail, null, 2)}</pre>
          ) : null}
        </div>
      ) : null}
    </form>
  );
}
