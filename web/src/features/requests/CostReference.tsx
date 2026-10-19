import type { BackendOut } from "../../api/types";
import { StateView } from "../../components/StateView";
import { formatMicros } from "../../lib/format";

export type CostReferenceProps = {
  backends: BackendOut[];
  loading: boolean;
  onRetry: () => void;
};

export function CostReference({ backends, loading, onRetry }: CostReferenceProps) {
  return (
    <StateView
      loading={loading}
      error={null}
      isEmpty={backends.length === 0}
      emptyText="还没有登记后端"
      onRetry={onRetry}
    >
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>后端</th>
              <th>引擎</th>
              <th className="num">每 token 单价</th>
              <th className="num">成本因子</th>
              <th>说明</th>
            </tr>
          </thead>
          <tbody>
            {backends.map((item) => (
              <tr key={item.id}>
                <td>{item.name}</td>
                <td className="faint">{item.engine}</td>
                <td className="num">{formatMicros(item.cost_per_token)}</td>
                <td className="num">
                  {item.cost_per_token <= 0
                    ? "1.0000"
                    : Math.min(0.000005 / item.cost_per_token, 1).toFixed(4)}
                </td>
                <td className="faint">
                  {item.cost_per_token <= 0
                    ? "本地零成本，成本维度不构成劣势"
                    : "单价越高，成本因子越低"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </StateView>
  );
}
