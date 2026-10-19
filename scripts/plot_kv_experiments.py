from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402

for candidate in ("/mnt/c/Windows/Fonts/msyh.ttc", "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc", "/System/Library/Fonts/PingFang.ttc"):
    if Path(candidate).exists():
        font_manager.fontManager.addfont(candidate)
        plt.rcParams["font.sans-serif"] = [font_manager.FontProperties(fname=candidate).get_name(), "DejaVu Sans"]
        break
plt.rcParams["axes.unicode_minus"] = False

POLICY_LABEL = {"round_robin": "轮询", "least_inflight": "最少在途", "prefix_affinity": "前缀亲和"}


def spread(values: list[float]) -> dict[str, float]:
    return {"median": round(statistics.median(values), 2), "min": round(min(values), 2), "max": round(max(values), 2)}


def capacity(paths: list[Path], output: Path) -> dict:
    levels: dict[int, dict[str, list[float]]] = {}
    for path in paths:
        for level in json.loads(path.read_text())["levels"]:
            summary = level["summary"]
            bucket = levels.setdefault(summary["concurrency"], {"ttft_p50_ms": [], "ttft_p95_ms": [], "output_tokens_per_second": [], "success_e2e_p95_ms": []})
            for key in bucket:
                bucket[key].append(summary[key])
    table = {c: {key: spread(values) for key, values in metrics.items()} for c, metrics in sorted(levels.items())}
    xs = list(table)
    fig, left = plt.subplots(figsize=(8, 4.5))
    for key, label, style in (("ttft_p50_ms", "TTFT P50", "o-"), ("ttft_p95_ms", "TTFT P95", "s-")):
        medians = [table[c][key]["median"] for c in xs]
        low = [table[c][key]["median"] - table[c][key]["min"] for c in xs]
        high = [table[c][key]["max"] - table[c][key]["median"] for c in xs]
        left.errorbar(xs, medians, yerr=[low, high], fmt=style, capsize=3, label=label)
    left.set_xscale("log", base=2)
    left.set_xticks(xs, [str(c) for c in xs])
    left.set_yscale("log")
    left.set_xlabel("并发请求数（单实例，闭环）")
    left.set_ylabel("TTFT（毫秒，对数轴）")
    right = left.twinx()
    right.plot(xs, [table[c]["output_tokens_per_second"]["median"] for c in xs], "d--", color="tab:green", label="输出吞吐")
    right.set_ylabel("输出 token/秒")
    lines = left.get_legend_handles_labels()
    extra = right.get_legend_handles_labels()
    left.legend(lines[0] + extra[0], lines[1] + extra[1], loc="upper left")
    left.set_title("Qwen2.5-0.5B-AWQ 单实例：并发 → TTFT / 吞吐（3 轮中位数，误差线为最小~最大）")
    fig.tight_layout()
    fig.savefig(output / "capacity.png", dpi=150)
    plt.close(fig)
    return table


def affinity_table(path: Path) -> dict:
    by_policy: dict[str, dict[str, list[float]]] = {}
    for run in json.loads(path.read_text())["runs"]:
        summary = run["summary"]
        bucket = by_policy.setdefault(summary["policy"], {"prefix_cache_hit_rate": [], "ttft_p50_ms": [], "ttft_p95_ms": [], "elapsed_seconds": []})
        for key in bucket:
            bucket[key].append(summary[key])
    return {policy: {key: spread(values) for key, values in metrics.items()} for policy, metrics in by_policy.items()}


def affinity(sets: list[tuple[str, str]], output: Path) -> dict:
    tables = {label: affinity_table(Path(path)) for label, path in sets}
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.4))
    colors = {"round_robin": "tab:gray", "least_inflight": "tab:blue", "prefix_affinity": "tab:orange"}
    width = 0.26
    for column, (key, title, scale) in enumerate((
        ("prefix_cache_hit_rate", "前缀缓存命中率（%）", 100),
        ("ttft_p50_ms", "TTFT P50（毫秒）", 1),
        ("ttft_p95_ms", "TTFT P95（毫秒）", 1),
    )):
        axis = axes[column]
        for offset, policy in enumerate(POLICY_LABEL):
            xs, ys, low, high = [], [], [], []
            for index, label in enumerate(tables):
                if policy not in tables[label]:
                    continue
                cell = tables[label][policy][key]
                xs.append(index + (offset - 1) * width)
                ys.append(cell["median"] * scale)
                low.append((cell["median"] - cell["min"]) * scale)
                high.append((cell["max"] - cell["median"]) * scale)
            axis.bar(xs, ys, width, yerr=[low, high], capsize=3, color=colors[policy], label=POLICY_LABEL[policy])
        axis.set_xticks(range(len(tables)), list(tables))
        axis.set_title(title)
    axes[0].legend()
    fig.suptitle("两实例，每实例 KV 约 2.2 万 token；30 篇共享文档 × 300 请求 × 3 轮，并发 8（柱 = 中位数，误差线 = 最小~最大）")
    fig.tight_layout()
    fig.savefig(output / "affinity.png", dpi=150)
    plt.close(fig)
    return tables


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--capacity", nargs="+", type=Path, required=True)
    parser.add_argument("--affinity", nargs="+", required=True, help="label=path")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    summary = {"capacity": capacity(args.capacity, args.output), "affinity": affinity([tuple(item.rsplit("=", 1)) for item in args.affinity], args.output)}
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(summary, ensure_ascii=False))
