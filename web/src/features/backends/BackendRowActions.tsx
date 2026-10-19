import { Link } from "react-router-dom";

import { api } from "../../api/endpoints";
import type { BackendOut } from "../../api/types";
import { BACKEND_STATE_VALUES } from "../../api/types";
import { useAsyncAction } from "../../hooks/useAsyncAction";
import { backendStateLabel } from "../../lib/format";

export type BackendRowActionsProps = {
  backend: BackendOut;
  onChanged: () => void;
};

export function BackendRowActions({ backend, onChanged }: BackendRowActionsProps) {
  const changeState = useAsyncAction(api.backends.changeState);
  const disable = useAsyncAction(api.backends.disable);

  async function handleState(state: string) {
    const updated = await changeState.run(backend.id, state);
    if (updated !== null) onChanged();
  }

  async function handleDisable() {
    const updated = await disable.run(backend.id);
    if (updated !== null) onChanged();
  }

  return (
    <span className="row">
      <Link className="btn btn--sm btn--ghost" to={`/backends/${backend.id}`}>
        详情
      </Link>
      <select
        className="field__select"
        value={backend.state}
        aria-label={`切换 ${backend.name} 状态`}
        disabled={changeState.pending}
        onChange={(event) => {
          void handleState(event.target.value);
        }}
      >
        {BACKEND_STATE_VALUES.map((value) => (
          <option key={value} value={value}>
            {backendStateLabel(value)}
          </option>
        ))}
      </select>
      <button
        type="button"
        className="btn btn--sm btn--danger"
        disabled={disable.pending || backend.state === "disabled"}
        onClick={() => {
          void handleDisable();
        }}
      >
        下线
      </button>
    </span>
  );
}
