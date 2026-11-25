#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三组对照：64GB+est、64GB+affinity_tier、无限L1+affinity_tier。
无限 L1 + affinity_tier 固定为 KVcache 理论最高命中率对照组；八面板图叠加三条曲线。"""
import argparse
import json
import os
from dataclasses import asdict, replace

import sim as S


def load_cached(directory, cfg):
    """仅在完整配置一致时复用历史结果，避免误用不同负载或策略的数据。"""
    summary_path = os.path.join(directory, "summary.json")
    series_path = os.path.join(directory, "series.json")
    if not (os.path.isfile(summary_path) and os.path.isfile(series_path)):
        return None
    with open(summary_path, encoding="utf-8") as f:
        summary = json.load(f)
    expected = json.loads(json.dumps(asdict(cfg)))
    expected.pop("out", None)
    saved = summary.get("config", {})
    if any(saved.get(k) != v for k, v in expected.items()):
        return None
    with open(series_path, encoding="utf-8") as f:
        series = json.load(f)
    print("reusing", directory, flush=True)
    return summary, series


def main():
    p = argparse.ArgumentParser(description="64GB 调度策略对比及无限 L1 理论对照")
    p.add_argument("--agents", type=int, default=4000)
    p.add_argument("--hours", type=float, default=6.0)
    p.add_argument("--l1-gb-per-rank", type=float, default=64.0)
    p.add_argument("--write-policy", type=str, default="write_through")
    p.add_argument("--out", type=str, default="out_compare_inf")
    a = p.parse_args()

    base = S.Cfg(agents=a.agents, hours=a.hours, l1_gb_per_rank=a.l1_gb_per_rank,
                 write_policy=a.write_policy, sched_policy="est")
    affinity = replace(base, sched_policy="affinity_tier")
    inf_affinity = replace(affinity, l1_gb_per_rank=1e9)  # 理论对照：不淘汰且保持 L1 亲和
    groups = [
        ("baseline", base, "-", "L1=%gGB + est" % a.l1_gb_per_rank),
        ("affinity_tier", affinity, "-", "L1=%gGB + affinity_tier" % a.l1_gb_per_rank),
        ("infinite_l1_affinity_tier", inf_affinity, "--", "L1=inf + affinity_tier (upper bound)"),
    ]

    results = {}
    for name, cfg, _, _ in groups:
        d = os.path.join(a.out, name)
        cached = load_cached(d, cfg)
        if cached is None:
            print("running", name, flush=True)
            cached = S.Sim(cfg).run()
        results[name] = cached
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "summary.json"), "w", encoding="utf-8") as f:
            json.dump(cached[0], f, ensure_ascii=False, indent=2)
        with open(os.path.join(d, "series.json"), "w", encoding="utf-8") as f:
            json.dump(cached[1], f)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    panels = [
        ("hit_L1", "Prefill L1 hit rate (req mean)", (0, 1.02)),
        ("hit_L2", "Prefill L2 hit rate (req mean)", (0, 1.02)),
        ("hit_total", "Prefill TOTAL hit rate (req mean)", (0, 1.02)),
        ("decode_bs", "Decode avg batch size per rank", None),
        ("queued_prefill_tokens", "Cluster queued prefill tokens", None),
        ("ttft_s", "TTFT (s)", None),
        ("tpot_s", "TPOT (s)", None),
        ("te2e_s", "TE2E: arrival to decode end (s)", None),
    ]
    fig, axes = plt.subplots(2, 4, figsize=(20, 9))
    fig.suptitle("agents=%d | 64GB: est vs affinity_tier | upper bound: infinite L1 + affinity_tier | %s"
                 % (a.agents, a.write_policy))
    for ax, (key, title, ylim) in zip(axes.flat, panels):
        for name, _, style, label in groups:
            summary, series = results[name]
            t = series["t_min"]
            if key == "hit_total":
                v = [x + y + z for x, y, z in zip(series["hit_L1"], series["hit_L2"], series["hit_L3"])]
            else:
                v = series[key]
            ax.plot(t, v, style, label=label)
        ax.set_title(title, fontsize=10)
        ax.set_xlabel("time (min)")
        if ylim:
            ax.set_ylim(*ylim)
        ax.legend(fontsize=7)
        ax.grid(alpha=0.3)
        ax.tick_params(labelsize=8)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    os.makedirs(a.out, exist_ok=True)
    path = os.path.join(a.out, "metrics.png")
    fig.savefig(path, dpi=140)
    plt.close(fig)

    for name, _, _, _ in groups:
        s = results[name][0]
        print(name, "turn=%d rej=%d" % (s["turn_count"], s["rejects"]),
              "hit=", {k: round(v, 3) for k, v in s["hit_rate_token_weighted"].items()},
              "ttft_p50=%.2f" % s["ttft_s"]["p50"], "tpot=%.3f" % s["tpot_s"]["mean"])
    print("plot:", path)


if __name__ == "__main__":
    main()
