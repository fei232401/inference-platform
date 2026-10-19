import { useState } from "react";

import { api } from "../../api/endpoints";
import { Field } from "../../components/Field";
import { useAsyncAction } from "../../hooks/useAsyncAction";

function toLocalInput(date: Date): string {
  const pad = (value: number) => value.toString().padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export function RequestPurgeForm({ onPurged }: { onPurged: () => void }) {
  const [cutoff, setCutoff] = useState(() => toLocalInput(new Date()));
  const [batchSize, setBatchSize] = useState("5000");
  const [message, setMessage] = useState<string | null>(null);
  const purgeAction = useAsyncAction(api.requests.purge);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage(null);
    const result = await purgeAction.run({
      cutoff: new Date(cutoff).toISOString(),
      batch_size: Number(batchSize),
    });
    if (result === null) return;
    setMessage(
      `已删除 ${result.deleted} 条（截止 ${result.cutoff}，单批上限 ${result.batch_size}）`,
    );
    onPurged();
  }

  return (
    <form className="stack" onSubmit={handleSubmit}>
      <span className="muted">
        只删「已结束且结束时间早于截止点」的记录，按批删除，避免一次锁住太多行。决策快照随请求级联删除。
      </span>
      <Field label="截止时间" hint="finished_at 早于该时刻的记录会被删除">
        <input
          className="field__input"
          type="datetime-local"
          required
          value={cutoff}
          onChange={(event) => setCutoff(event.target.value)}
        />
      </Field>
      <Field label="单批上限" hint="1 ~ 50000">
        <input
          className="field__input"
          type="number"
          min="1"
          max="50000"
          value={batchSize}
          onChange={(event) => setBatchSize(event.target.value)}
        />
      </Field>
      <div>
        <button type="submit" className="btn btn--danger" disabled={purgeAction.pending}>
          {purgeAction.pending ? "删除中" : "执行清理"}
        </button>
      </div>
      {message ? <span className="muted">{message}</span> : null}
      {purgeAction.error ? (
        <div className="error-box">
          <span className="error-box__title">清理失败 · {purgeAction.error.code}</span>
          <span>{purgeAction.error.message}</span>
        </div>
      ) : null}
    </form>
  );
}
