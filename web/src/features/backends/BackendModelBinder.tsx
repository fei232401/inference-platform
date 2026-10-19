import { useState } from "react";

import { api } from "../../api/endpoints";
import { Panel } from "../../components/Panel";
import { StateView } from "../../components/StateView";
import { useAsync } from "../../hooks/useAsync";
import { useAsyncAction } from "../../hooks/useAsyncAction";

export type BackendModelBinderProps = {
  backendId: number;
  boundIds: number[];
  onChanged: (message: string) => void;
};

export function BackendModelBinder({ backendId, boundIds, onChanged }: BackendModelBinderProps) {
  const [selected, setSelected] = useState<number[]>([]);
  const catalog = useAsync(() => api.models.list({ limit: 200 }), []);

  const bindModels = useAsyncAction(api.backends.bindModels);
  const replaceModels = useAsyncAction(api.backends.replaceModels);
  const unbindModels = useAsyncAction(api.backends.unbindModels);

  const items = catalog.data?.items ?? [];
  const selectedBound = selected.filter((id) => boundIds.includes(id)).length;

  function toggle(modelId: number) {
    setSelected((current) =>
      current.includes(modelId) ? current.filter((value) => value !== modelId) : [...current, modelId],
    );
  }

  async function handle(mode: "append" | "replace" | "unbind") {
    if (selected.length === 0) {
      onChanged("先在列表里勾选模型");
      return;
    }
    const result =
      mode === "append"
        ? await bindModels.run(backendId, selected)
        : mode === "replace"
          ? await replaceModels.run(backendId, selected)
          : await unbindModels.run(backendId, selected);

    if (result === null) return;
    const verb = mode === "append" ? "追加绑定" : mode === "replace" ? "替换绑定" : "解绑";
    setSelected([]);
    onChanged(`${verb}完成，当前共 ${result.model_ids.length} 个模型`);
  }

  const action = bindModels.error ?? replaceModels.error ?? unbindModels.error;

  return (
    <Panel
      title="选择模型"
      subtitle="决定该实例参与哪些模型的调度"
      actions={
        <span className="faint">
          已选 {selected.length} 个，其中 {selectedBound} 个已绑定
        </span>
      }
    >
      <StateView
        loading={catalog.loading}
        error={catalog.error}
        isEmpty={items.length === 0}
        emptyText="模型目录为空，先登记模型"
        onRetry={catalog.reload}
      >
        <div className="stack">
          {items.map((model) => (
            <label className="row" key={model.id}>
              <input
                type="checkbox"
                checked={selected.includes(model.id)}
                onChange={() => toggle(model.id)}
              />
              <span>{model.name}</span>
              <span className="faint">
                #{model.id} · {model.family ?? "无系列"}
                {model.parameter_billions ? ` · ${model.parameter_billions}B` : ""}
              </span>
              {boundIds.includes(model.id) ? <span className="badge badge--accent">已绑定</span> : null}
            </label>
          ))}
        </div>
      </StateView>

      <div className="row mt-4">
        <button
          type="button"
          className="btn btn--primary"
          disabled={bindModels.pending}
          onClick={() => {
            void handle("append");
          }}
        >
          追加绑定
        </button>
        <button
          type="button"
          className="btn"
          disabled={replaceModels.pending}
          onClick={() => {
            void handle("replace");
          }}
        >
          替换全部
        </button>
        <button
          type="button"
          className="btn btn--danger"
          disabled={unbindModels.pending}
          onClick={() => {
            void handle("unbind");
          }}
        >
          解绑选中
        </button>
      </div>

      {action ? (
        <div className="error-box mt-3">
          <span className="error-box__title">绑定操作失败 · {action.code}</span>
          <span>{action.message}</span>
        </div>
      ) : null}
    </Panel>
  );
}
