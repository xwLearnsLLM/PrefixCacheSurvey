#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""汇总五档用户规模、三组配置的 overall 与最后 1 小时指标。"""
import csv
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent / "out_user_sweep"
USERS = [2000, 3000, 4000, 4500, 5000]
GROUPS = [
    ("baseline", "64GB+est"),
    ("affinity_tier", "64GB+affinity_tier"),
    ("infinite_l1_affinity_tier", "infL1+affinity_tier"),
]

rows = []
for users in USERS:
    for group, label in GROUPS:
        directory = ROOT / f"users_{users}" / group
        with (directory / "summary.json").open(encoding="utf-8") as f:
            s = json.load(f)
        with (directory / "series.json").open(encoding="utf-8") as f:
            series = json.load(f)
        hit = s["hit_rate_token_weighted"]
        late = np.asarray(series["t_min"]) >= 300.0
        row = {
            "users": users,
            "group": label,
            "turns": s["turn_count"],
            "rejects": s["rejects"],
            "hit_L1_pct": 100 * hit["L1"],
            "hit_L2_pct": 100 * hit["L2"],
            "hit_L3_pct": 100 * hit["L3"],
            "hit_total_pct": 100 * sum(hit.values()),
            "decode_bs": s["decode_avg_bs"],
            "ttft_mean_s": s["ttft_s"]["mean"],
            "ttft_p50_s": s["ttft_s"]["p50"],
            "ttft_p90_s": s["ttft_s"]["p90"],
            "ttft_p99_s": s["ttft_s"]["p99"],
            "tpot_mean_s": s["tpot_s"]["mean"],
            "tpot_p99_s": s["tpot_s"]["p99"],
            "late_ttft_mean_s": float(np.nanmean(np.asarray(series["ttft_s"])[late])),
            "late_tpot_mean_s": float(np.nanmean(np.asarray(series["tpot_s"])[late])),
            "late_decode_bs": float(np.nanmean(np.asarray(series["decode_bs"])[late])),
            "late_queued_tokens": float(np.nanmean(np.asarray(series["queued_prefill_tokens"])[late])),
        }
        rows.append(row)

out = ROOT / "metrics_summary.csv"
with out.open("w", encoding="utf-8-sig", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)

print("OVERALL")
print("| 用户 | 配置 | 完成轮数 | L1/L2/L3 命中 | 总命中 | decode bs | TTFT p50/p90 (s) | TPOT mean (s) |")
print("|---:|---|---:|---:|---:|---:|---:|---:|")
for r in rows:
    print("| {users} | {group} | {turns} | {hit_L1_pct:.1f}/{hit_L2_pct:.1f}/{hit_L3_pct:.1f}% | {hit_total_pct:.1f}% | {decode_bs:.2f} | {ttft_p50_s:.2f}/{ttft_p90_s:.2f} | {tpot_mean_s:.3f} |".format(**r))

print("\nLAST HOUR (minute-bucket means)")
print("| 用户 | 配置 | TTFT mean (s) | TPOT mean (s) | decode bs | queued tokens |")
print("|---:|---|---:|---:|---:|---:|")
for r in rows:
    print("| {users} | {group} | {late_ttft_mean_s:.2f} | {late_tpot_mean_s:.3f} | {late_decode_bs:.2f} | {late_queued_tokens:.0f} |".format(**r))
print("\nCSV:", out)
