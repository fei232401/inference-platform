import type { PageMeta } from "../api/types";

export type PagerProps = {
  meta: PageMeta;
  onPrev: () => void;
  onNext: () => void;
  busy?: boolean;
};

export function Pager({ meta, onPrev, onNext, busy = false }: PagerProps) {
  const first = meta.total === 0 ? 0 : meta.offset + 1;
  const last = meta.offset + meta.count;

  return (
    <div className="pager">
      <span>
        第 {first}–{last} 条，共 {meta.total} 条
      </span>
      <span className="pager__buttons">
        <button
          type="button"
          className="btn btn--sm"
          onClick={onPrev}
          disabled={busy || meta.offset === 0}
        >
          上一页
        </button>
        <button
          type="button"
          className="btn btn--sm"
          onClick={onNext}
          disabled={busy || !meta.has_more}
        >
          下一页
        </button>
      </span>
    </div>
  );
}
