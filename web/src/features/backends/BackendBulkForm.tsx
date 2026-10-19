import { useState } from "react";

import { api } from "../../api/endpoints";
import type { BackendCreate } from "../../api/types";
import { Field } from "../../components/Field";
import { useAsyncAction } from "../../hooks/useAsyncAction";

const SAMPLE = `[
  { "name": "ollama-a", "url": "http://10.0.0.11:11434", "engine": "ollama", "weight": 1, "max_concurrency": 2, "cost_per_token": 0 },
  { "name": "vllm-b", "url": "http://10.0.0.12:8000", "engine": "openai", "weight": 3, "max_concurrency": 4, "cost_per_token": 0.000002 }
]`;

export function BackendBulkForm({ onCreated }: { onCreated: () => void }) {
  const [text, setText] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const bulkCreate = useAsyncAction(api.backends.bulkCreate);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage(null);

    let parsed: unknown;
    try {
      parsed = JSON.parse(text);
    } catch (cause) {
      setMessage(cause instanceof Error ? `JSON 解析失败：${cause.message}` : "JSON 解析失败");
      return;
    }
    if (!Array.isArray(parsed) || parsed.length === 0) {
      setMessage("顶层必须是长度大于 0 的数组");
      return;
    }

    const result = await bulkCreate.run(parsed as BackendCreate[]);
    if (result === null) return;
    setMessage(
      `提交 ${result.submitted} 条，新增 ${result.inserted} 条，跳过（名称已存在）${result.skipped} 条`,
    );
    onCreated();
  }

  return (
    <form className="stack" onSubmit={handleSubmit}>
      <Field label="JSON 数组" hint="每一项字段与单条登记一致">
        <textarea
          className="field__textarea"
          rows={10}
          value={text}
          placeholder={SAMPLE}
          onChange={(event) => setText(event.target.value)}
        />
      </Field>
      <div className="row">
        <button type="submit" className="btn btn--primary" disabled={bulkCreate.pending}>
          {bulkCreate.pending ? "提交中" : "批量登记"}
        </button>
        <button type="button" className="btn" onClick={() => setText(SAMPLE)}>
          填入示例
        </button>
      </div>
      {message ? <span className="muted">{message}</span> : null}
      {bulkCreate.error ? (
        <div className="error-box">
          <span className="error-box__title">批量登记失败 · {bulkCreate.error.code}</span>
          <span>{bulkCreate.error.message}</span>
        </div>
      ) : null}
    </form>
  );
}
