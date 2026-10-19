import { useState } from "react";

import { api } from "../../api/endpoints";
import type { ApiKeyVerifyOut } from "../../api/types";
import { Field } from "../../components/Field";
import { useAsyncAction } from "../../hooks/useAsyncAction";
import { SCOPE_VALUES, formatDateTime } from "../../lib/format";

export function KeyVerifyForm() {
  const [probeKey, setProbeKey] = useState("");
  const [probeScope, setProbeScope] = useState("infer");
  const [result, setResult] = useState<ApiKeyVerifyOut | null>(null);
  const verify = useAsyncAction(api.keys.verify);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (probeKey.trim().length === 0) return;
    const response = await verify.run(probeKey.trim(), probeScope);
    if (response !== null) setResult(response);
  }

  const apiKey = result?.api_key ?? null;

  return (
    <form className="stack" onSubmit={handleSubmit}>
      <Field label="待校验密钥">
        <input
          className="field__input"
          value={probeKey}
          placeholder="aip_..."
          onChange={(event) => setProbeKey(event.target.value)}
        />
      </Field>
      <Field label="按哪个权限校验" hint="校验失败统一返回 valid=false，不区分具体原因">
        <select
          className="field__select"
          value={probeScope}
          onChange={(event) => setProbeScope(event.target.value)}
        >
          {SCOPE_VALUES.map((scope) => (
            <option key={scope} value={scope}>
              {scope}
            </option>
          ))}
        </select>
      </Field>
      <div>
        <button type="submit" className="btn" disabled={verify.pending || probeKey.length === 0}>
          {verify.pending ? "校验中" : "校验"}
        </button>
      </div>

      {verify.error ? (
        <div className="error-box">
          <span className="error-box__title">校验请求失败 · {verify.error.code}</span>
          <span>{verify.error.message}</span>
        </div>
      ) : null}

      {result && apiKey ? (
        <div className="kv">
          <span className="kv__key">结论</span>
          <span className="kv__value">
            <span className="badge badge--success">有效</span>
          </span>
          <span className="kv__key">密钥 ID</span>
          <span className="kv__value">{apiKey.id}</span>
          <span className="kv__key">名称</span>
          <span className="kv__value">{apiKey.name}</span>
          <span className="kv__key">权限</span>
          <span className="kv__value">{apiKey.scopes.join(" / ")}</span>
          <span className="kv__key">最后使用</span>
          <span className="kv__value">
            {apiKey.last_used_at ? formatDateTime(apiKey.last_used_at) : "刚被本次校验刷新"}
          </span>
        </div>
      ) : null}

      {result && !apiKey ? (
        <div className="error-box">
          <span className="error-box__title">结论：无效</span>
          <span>不存在 / 已吊销 / 已过期 / 权限不足，四选一，控制层刻意不区分。</span>
        </div>
      ) : null}
    </form>
  );
}
