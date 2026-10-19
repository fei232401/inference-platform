import { KeyRound } from "lucide-react";
import { useState } from "react";

import { clearApiKey, maskApiKey, setApiKey } from "../api/apiKey";
import { useApiKey } from "../hooks/useApiKey";

export function ApiKeyBar() {
  const apiKey = useApiKey();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");

  const masked = maskApiKey(apiKey);

  if (apiKey.length > 0 && !editing) {
    return (
      <div className="apikeybar">
        <KeyRound size={14} strokeWidth={1.75} aria-hidden />
        <span className="muted">已配置 API Key</span>
        <code className="faint">{masked}</code>
        <span className="faint">仅本次会话有效（关闭标签页即失效）</span>
        <button
          type="button"
          className="btn btn--sm btn--ghost"
          onClick={() => {
            setDraft("");
            setEditing(true);
          }}
        >
          更换
        </button>
        <button
          type="button"
          className="btn btn--sm btn--ghost btn--danger"
          onClick={() => {
            clearApiKey();
            setDraft("");
            setEditing(false);
          }}
        >
          清除
        </button>
      </div>
    );
  }

  return (
    <form
      className="apikeybar apikeybar--unset"
      onSubmit={(event) => {
        event.preventDefault();
        setApiKey(draft);
        setDraft("");
        setEditing(false);
      }}
    >
      <KeyRound size={14} strokeWidth={1.75} aria-hidden />
      <span>控制台需要一把 API Key 才能读取数据</span>
      <input
        className="field__input"
        type="password"
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        placeholder="aip_..."
        aria-label="API Key"
        autoComplete="off"
        spellCheck={false}
      />
      <button type="submit" className="btn btn--sm btn--primary" disabled={draft.trim().length === 0}>
        保存
      </button>
      {apiKey.length > 0 ? (
        <button
          type="button"
          className="btn btn--sm btn--ghost"
          onClick={() => {
            setDraft("");
            setEditing(false);
          }}
        >
          取消
        </button>
      ) : null}
      <span className="field__hint">
        只存在 sessionStorage，且必须带 admin 或 infer 权限；请求会带上 X-API-Key 头
      </span>
    </form>
  );
}
