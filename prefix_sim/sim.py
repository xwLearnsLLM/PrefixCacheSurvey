#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多级前缀缓存仿真器（HiCache L1+L2+L3 write-through 风格，PD 共部，多机 EP 域）

抽象与简化（与需求文档对齐，均为可配置项）：
  - 仿真粒度到 model.forward 步进；L1/L2/L3 之间 promote/demote 瞬时完成（忽略传输时延）。
  - 每机 1 个 EP 域（机内 DP rank 的 forward 同步），机器之间完全异步。
  - prefill：TP8EP8，整机推一条请求；KV 落在指定 DP rank，之后该请求在该 rank 上 decode。
  - decode：DP8EP8，每 rank 独立 batch（<=32）；机内同步，步长 = ITL(机内最大 rank bs)。
  - 不开启 continuous batching：prefill 期间 decode 暂停。
  - 缓存键 = (agent_id, chunk_index)，chunk=256 tokens；只缓存完整 chunk。
  - 连续前缀命中用各层 per-agent chunk 计数近似（L1 段 → L2 续段 → L3 续段）。
  - write-through：新 chunk 立即写 L1/L2/L3（去重）；各层独立 LRU 淘汰。
  - 全局调度：估计 TTFT = (排队 prefill tokens + 本请求 miss tokens) / prefill_tps，取最小。
"""
from __future__ import annotations

import argparse
import heapq
import json
import os
from collections import Counter, OrderedDict, deque
from dataclasses import dataclass, asdict

import numpy as np

# ---------------- decode ITL 拟合（分段线性插值，bs=1..32） ----------------
ITL_POINTS = [(1, 40.6), (4, 44.5), (8, 53.2), (12, 59.1), (16, 66.7),
              (20, 73.1), (24, 83.2), (28, 88.6), (32, 97.9)]


def _make_itl():
    xs = [p[0] for p in ITL_POINTS]
    ys = [p[1] for p in ITL_POINTS]

    def itl(bs: float) -> float:
        if bs <= 1:
            return ys[0]
        if bs >= xs[-1]:
            return ys[-1]
        for i in range(len(xs) - 1):
            if xs[i] <= bs <= xs[i + 1]:
                return ys[i] + (ys[i + 1] - ys[i]) * (bs - xs[i]) / (xs[i + 1] - xs[i])
        return ys[-1]

    return itl


ITL_MS = _make_itl()


@dataclass
class Cfg:
    machines: int = 4
    ranks: int = 8                       # 每机 DP rank 数
    l1_gb_per_rank: float = 4096.0       # "每机 32TB" / 8 卡（字面默认，可调）
    l2_gb_per_machine: float = 2048.0    # 每机 2TB
    l3_gb: float = 262144.0              # 全局 256TB
    kv_bytes_per_token: float = 105 * 1024   # K3.1 Pro MLA 量级
    chunk_tokens: int = 256
    max_batched_tokens: int = 8192
    prefill_tps: float = 10000.0         # 每机 prefill tokens/s
    max_decode_bs: int = 32
    mtp_probs: tuple = (0.5, 0.25, 0.15, 0.10)   # P(吐1/2/3/4 token)
    agents: int = 4500
    hours: float = 3.0
    turns_mean: float = 8.0
    turns_max: int = 128
    prefill_len_mean: float = 4096.0
    decode_len_mean: float = 512.0
    think_mean_s: float = 600.0
    think_dist: str = "exponential"    # poisson | exponential（指数分布去同步效应更真实）
    bucket_s: float = 60.0
    seed: int = 42
    out: str = "out"
    sched_decode_weight: float = 1.0   # 调度 decode 感知权重：est += w * rank积压tok/rank解码速率
    decode_tps_est: float = 604.5      # 每 rank decode 满 batch 吞吐估计 (32 seq * 1.85 tok / 97.9ms)
    write_policy: str = "write_through"  # write_through: 新chunk立即写L1/L2/L3 | write_back: 仅写L1，L1淘汰时才级联写L2→L3 | write_selective: 仅写L1，被再次命中时才写穿L2/L3


# ---------------- 缓存层（LRU + per-agent chunk 计数） ----------------
class Tier:
    __slots__ = ("cap", "od", "achunks")

    def __init__(self, cap_chunks: int):
        self.cap = cap_chunks
        self.od = OrderedDict()          # (aid, cno) -> None, LRU 顺序
        self.achunks = Counter()         # aid -> 该层持有该 agent 的 chunk 数

    def has(self, k):
        return k in self.od

    def count(self, aid):
        return self.achunks.get(aid, 0)

    def add(self, k):
        if k in self.od:
            self.od.move_to_end(k)
            return False
        self.od[k] = None
        self.achunks[k[0]] += 1
        return True

    def evict_to(self, budget_chunks: int):
        evicted = []
        od = self.od
        while len(od) > budget_chunks:
            (a, cno), _ = od.popitem(last=False)
            self.achunks[a] -= 1
            if self.achunks[a] <= 0:
                del self.achunks[a]
            evicted.append((a, cno))
        return evicted


class Rank:
    __slots__ = ("l1", "active_tokens", "decode", "dwait", "dec_left")

    def __init__(self, l1_cap_chunks: int):
        self.l1 = Tier(l1_cap_chunks)
        self.active_tokens = 0           # 在 rank 上驻留的请求 KV（prompt+out，准入时预留）
        self.decode = []                 # 正在 decode 的请求（<= max_decode_bs）
        self.dwait = deque()             # 等 decode 位置的请求
        self.dec_left = 0.0              # 该 rank decode 积压（剩余 token 总数）


class Machine:
    __slots__ = ("mid", "ranks", "l2", "q", "queued_tokens", "prefilling", "cur", "idle", "busy_s", "dec_tokens_left")

    def __init__(self, mid, cfg, l1_cap_chunks, l2_cap_chunks):
        self.mid = mid
        self.ranks = [Rank(l1_cap_chunks) for _ in range(cfg.ranks)]
        self.l2 = Tier(l2_cap_chunks)
        self.q = deque()                 # prefill 等待队列
        self.queued_tokens = 0
        self.prefilling = None           # 正在 prefill 的请求（chunked prefill 跨步保持）
        self.cur = None                  # (kind, dur, req, chunk) 当前步
        self.idle = True
        self.busy_s = 0.0
        self.dec_tokens_left = 0         # decode 积压（驻留请求剩余 token 总数）


class Req:
    __slots__ = ("aid", "prompt", "out", "hist_chunks", "arrival", "m", "r",
                 "h1", "h2", "h3", "miss_left", "out_left", "prefill_end")

    def __init__(self, aid, prompt, out, hist_chunks, arrival):
        self.aid = aid
        self.prompt = prompt
        self.out = out
        self.hist_chunks = hist_chunks
        self.arrival = arrival
        self.m = -1
        self.r = -1
        self.h1 = self.h2 = self.h3 = 0
        self.miss_left = prompt
        self.out_left = out
        self.prefill_end = 0.0


class Agent:
    __slots__ = ("aid", "turns", "done", "hist")

    def __init__(self, aid, turns):
        self.aid = aid
        self.turns = turns
        self.done = 0
        self.hist = 0                    # 历史总长度（tokens）


# ---------------- 仿真器 ----------------
class Sim:
    def __init__(self, cfg: Cfg):
        self.cfg = cfg
        c = cfg
        self.CT = c.chunk_tokens
        self.l1_cap_tokens = int(c.l1_gb_per_rank * 1e9 / c.kv_bytes_per_token)
        self.l1_cap_chunks = self.l1_cap_tokens // self.CT
        self.l2_cap_chunks = int(c.l2_gb_per_machine * 1e9 / c.kv_bytes_per_token) // self.CT
        self.l3_cap_chunks = int(c.l3_gb * 1e9 / c.kv_bytes_per_token) // self.CT
        self.L3 = Tier(self.l3_cap_chunks)
        self.machines = [Machine(i, cfg, self.l1_cap_chunks, self.l2_cap_chunks)
                         for i in range(c.machines)]
        self.rng = np.random.default_rng(c.seed)
        self.T = c.hours * 3600.0
        self.events = []                 # (t, seq, kind, payload)
        self.eseq = 0
        # MTP 采样 CDF
        p = np.asarray(c.mtp_probs, dtype=float)
        p = p / p.sum()
        self.mtp_cdf = np.cumsum(p)
        # agents
        self.agents = []
        for aid in range(c.agents):
            turns = min(int(self.rng.geometric(1.0 / c.turns_mean)), c.turns_max)
            self.agents.append(Agent(aid, max(1, turns)))
        # 指标
        self.prefill_rec = []            # (t_end, ttft, h1t, h2t, h3t, prompt)
        self.turn_rec = []               # (t_end, tpot, e2e)
        self.decstep_rec = []            # (t, avg_rank_bs, dur)
        self.queue_rec = []              # (t, cluster_queued_prefill)
        self.rejects = 0
        self.writes = {"L1": 0, "L2": 0, "L3": 0}   # 各层实际插入的 chunk 数（写操作量）
        self.stalls = 0                  # 机器空闲但有活未干的停摆次数

    # ---------- 工具 ----------
    def push(self, t, kind, payload):
        self.eseq += 1
        heapq.heappush(self.events, (t, self.eseq, kind, payload))

    def mtp_sample(self):
        r = self.rng.random()
        cdf = self.mtp_cdf
        if r < cdf[0]:
            return 1
        if r < cdf[1]:
            return 2
        if r < cdf[2]:
            return 3
        return 4

    def think_time(self):
        if self.cfg.think_dist == "poisson":
            return float(self.rng.poisson(self.cfg.think_mean_s))
        return float(self.rng.exponential(self.cfg.think_mean_s))

    def probe(self, m, r, aid, hc):
        """连续前缀命中近似：返回 (L1_chunks, L2_chunks, L3_chunks)。"""
        l1 = min(m.ranks[r].l1.count(aid), hc)
        c2 = min(m.l2.count(aid), hc)
        add2 = max(c2 - l1, 0)
        c3 = min(self.L3.count(aid), hc)
        add3 = max(c3 - l1 - add2, 0)
        return l1, add2, add3

    def l1_evict(self, m, rk):
        budget = max(0, (self.l1_cap_tokens - rk.active_tokens)) // self.CT
        ev = rk.l1.evict_to(budget)
        if self.cfg.write_policy == "write_back" and ev:
            # L1 淘汰 → 级联写 L2；L2 溢出 → 级联写 L3
            for k in ev:
                if m.l2.add(k):
                    self.writes["L2"] += 1
                if self.L3.add(k):
                    self.writes["L3"] += 1
            ev2 = m.l2.evict_to(self.l2_cap_chunks)
            for k in ev2:
                if self.L3.add(k):
                    self.writes["L3"] += 1
            self.L3.evict_to(self.l3_cap_chunks)

    def write_through(self, m, rk, aid, cno_from, cno_to):
        """新 chunk 落盘：write_through=立即写全层；write_back/write_selective=仅写 L1。"""
        l1, l2, L3 = rk.l1, m.l2, self.L3
        wt = self.cfg.write_policy == "write_through"
        for cno in range(cno_from, cno_to):
            k = (aid, cno)
            if l1.add(k):
                self.writes["L1"] += 1
            if wt:
                if l2.add(k):
                    self.writes["L2"] += 1
                if L3.add(k):
                    self.writes["L3"] += 1
        if wt:
            l2.evict_to(self.l2_cap_chunks)
            L3.evict_to(self.l3_cap_chunks)
        self.l1_evict(m, rk)

    # ---------- 全局调度器 ----------
    def assign(self, req):
        best = None
        hc = req.hist_chunks
        c = self.cfg
        tps = c.prefill_tps
        w = c.sched_decode_weight
        for m in self.machines:
            qt = m.queued_tokens
            if m.prefilling is not None:
                qt += m.prefilling.miss_left
            for r in range(c.ranks):
                h1, h2, h3 = self.probe(m, r, req.aid, hc)
                miss = req.prompt - (h1 + h2 + h3) * self.CT
                dec_pen = w * m.ranks[r].dec_left / c.decode_tps_est
                est = (qt + miss) / tps + dec_pen   # 预估 TTFT：排队 + miss 计算 + rank decode 积压
                key = (est, m.ranks[r].dec_left, len(m.q), m.mid, r)  # 并列时打散到空闲 rank
                if best is None or key < best[0]:
                    best = (key, m, r)
        _, m, r = best
        req.m, req.r = m.mid, r
        return m

    # ---------- 请求生命周期 ----------
    def on_arrival(self, t, aid):
        ag = self.agents[aid]
        c = self.cfg
        prompt = ag.hist + int(self.rng.poisson(c.prefill_len_mean))
        out = max(1, int(self.rng.poisson(c.decode_len_mean)))
        req = Req(aid, prompt, out, ag.hist // self.CT, t)
        if prompt + out > self.l1_cap_tokens:
            self.rejects += 1
            ag.done += 1                  # 拒服：本轮作废，进入下一轮等待
            if ag.done < ag.turns:
                self.push(t + self.think_time(), "A", aid)
            return
        m = self.assign(req)
        m.q.append(req)
        m.queued_tokens += req.prompt
        self.kick(m, t)

    def kick(self, m, t):
        """若机器空闲则立即决策并启动下一个 forward 步。"""
        if not m.idle:
            return
        nxt = self.machine_decide(m)
        if nxt is None:
            return
        m.idle = False
        m.cur = nxt
        self.push(t + nxt[1], "S", m)

    def machine_decide(self, m):
        c = self.cfg
        if m.prefilling is not None:                      # 继续 chunked prefill
            req = m.prefilling
            chunk = min(req.miss_left, c.max_batched_tokens)
            return ("p", chunk / c.prefill_tps, req, chunk)
        if m.q:                                           # prefill 优先
            req = m.q[0]
            rk = m.ranks[req.r]
            if rk.active_tokens + req.prompt + req.out <= self.l1_cap_tokens:
                m.q.popleft()
                m.queued_tokens -= req.prompt
                self.start_prefill(m, rk, req)
                m.prefilling = req
                chunk = min(req.miss_left, c.max_batched_tokens)
                return ("p", chunk / c.prefill_tps, req, chunk)
        total = 0
        bmax = 0
        for rk in m.ranks:
            n = len(rk.decode)
            total += n
            if n > bmax:
                bmax = n
        if total:                                         # 纯 decode 步
            return ("d", ITL_MS(min(bmax, c.max_decode_bs)) / 1000.0, None, 0)
        return None

    def start_prefill(self, m, rk, req):
        h1, h2, h3 = self.probe(m, req.r, req.aid, req.hist_chunks)
        req.h1, req.h2, req.h3 = h1, h2, h3
        hit = (h1 + h2 + h3) * self.CT
        req.miss_left = req.prompt - hit
        rk.active_tokens += req.prompt + req.out          # 准入即预留全长
        # promote：命中 chunk 立即进入/触及各层
        l1, l2, L3 = rk.l1, m.l2, self.L3
        sel = self.cfg.write_policy == "write_selective"
        for cno in range(h1 + h2 + h3):
            k = (req.aid, cno)
            if l1.add(k):
                self.writes["L1"] += 1
            if sel:                       # write_selective：被命中（证明会复用）才写穿到 L2/L3
                if l2.add(k):
                    self.writes["L2"] += 1
                if L3.add(k):
                    self.writes["L3"] += 1
            else:
                l2.add(k)
                L3.add(k)
        if sel:
            l2.evict_to(self.l2_cap_chunks)
            L3.evict_to(self.l3_cap_chunks)
        self.l1_evict(m, rk)

    def finish_prefill(self, m, req, t):
        rk = m.ranks[req.r]
        req.prefill_end = t
        self.prefill_rec.append((t, t - req.arrival,
                                 req.h1 * self.CT, req.h2 * self.CT,
                                 req.h3 * self.CT, req.prompt))
        # write-through：prompt 的完整 chunk 写入各层（去重）
        self.write_through(m, rk, req.aid, 0, req.prompt // self.CT)
        if len(rk.decode) < self.cfg.max_decode_bs:
            rk.decode.append(req)
        else:
            rk.dwait.append(req)
        rk.dec_left += req.out
        m.dec_tokens_left += req.out

    def finish_turn(self, m, rk, req, t):
        rk.decode.remove(req)
        rk.active_tokens -= req.prompt + req.out
        # decode 产生的新 chunk write-through
        pc = req.prompt // self.CT
        tc = (req.prompt + req.out) // self.CT
        if tc > pc:
            self.write_through(m, rk, req.aid, pc, tc)
        self.l1_evict(m, rk)
        self.turn_rec.append((t, (t - req.prefill_end) / req.out, t - req.arrival))
        ag = self.agents[req.aid]
        ag.hist = req.prompt + req.out
        ag.done += 1
        if ag.done < ag.turns:
            self.push(t + self.think_time(), "A", req.aid)
        while rk.dwait and len(rk.decode) < self.cfg.max_decode_bs:
            rk.decode.append(rk.dwait.popleft())

    def apply_step(self, m, t):
        kind, dur, req, chunk = m.cur
        if kind == "noop":               # 停摆自愈探针，不计忙时、不进指标
            return
        m.busy_s += dur
        if kind == "p":
            req.miss_left -= chunk
            if req.miss_left <= 0:
                m.prefilling = None
                self.finish_prefill(m, req, t)
        else:
            total = 0
            for rk in m.ranks:
                n = len(rk.decode)
                total += n
                if n:
                    for req in list(rk.decode):
                        k = self.mtp_sample()
                        d = min(k, max(req.out_left, 0))
                        rk.dec_left -= d
                        m.dec_tokens_left -= d
                        req.out_left -= k
                        if req.out_left <= 0:
                            self.finish_turn(m, rk, req, t)
            self.decstep_rec.append((t, total / self.cfg.ranks, dur))

    # ---------- 主循环 ----------
    def run(self):
        for aid in range(self.cfg.agents):
            self.push(self.think_time(), "A", aid)   # 首轮与后续轮一致：think time 后到达
        ev = self.events
        while ev:
            t, _, kind, payload = heapq.heappop(ev)
            if t > self.T:
                break
            if kind == "A":
                self.on_arrival(t, payload)
                self.queue_rec.append((t, sum(m.queued_tokens for m in self.machines)))
            else:  # "S"：machine 完成一个 forward 步
                m = payload
                self.apply_step(m, t)
                nxt = self.machine_decide(m)
                if nxt is None:
                    has_work = m.q or m.prefilling is not None or any(
                        rk.decode or rk.dwait for rk in m.ranks)
                    if has_work:
                        self.stalls += 1
                        self.push(t + 1.0, "S", m)   # 自愈：1s 后重探
                        m.cur = ("noop", 1.0, None, 0)
                    else:
                        m.idle = True
                        m.cur = None
                else:
                    m.cur = nxt
                    self.push(t + nxt[1], "S", m)
        return self.report()

    # ---------- 指标 ----------
    def report(self):
        c = self.cfg
        nb = int(self.T // c.bucket_s) + 1
        bt = [(i + 0.5) * c.bucket_s / 60.0 for i in range(nb)]   # 分钟

        def bucketize(rec, val_fn, weight_fn=None):
            num = [0.0] * nb
            den = [0.0] * nb
            for r in rec:
                b = min(int(r[0] // c.bucket_s), nb - 1)
                w = weight_fn(r) if weight_fn else 1.0
                num[b] += val_fn(r) * w
                den[b] += w
            return [v / d if d > 0 else float("nan") for v, d in zip(num, den)]

        hit = {
            "L1": bucketize(self.prefill_rec, lambda r: r[2] / r[5]),
            "L2": bucketize(self.prefill_rec, lambda r: r[3] / r[5]),
            "L3": bucketize(self.prefill_rec, lambda r: r[4] / r[5]),
        }
        ttft_s = bucketize(self.prefill_rec, lambda r: r[1])
        tpot_s = bucketize(self.turn_rec, lambda r: r[1])
        te2e_s = bucketize(self.turn_rec, lambda r: r[2])
        decbs_s = bucketize(self.decstep_rec, lambda r: r[1], weight_fn=lambda r: r[2])
        queue_s = bucketize(self.queue_rec, lambda r: r[1])

        tot_p = sum(r[5] for r in self.prefill_rec) or 1
        summary = {
            "config": asdict(c),
            "l1_cap_tokens_per_rank": self.l1_cap_tokens,
            "l2_cap_tokens_per_machine": self.l2_cap_chunks * self.CT,
            "l3_cap_tokens_global": self.l3_cap_chunks * self.CT,
            "prefill_count": len(self.prefill_rec),
            "turn_count": len(self.turn_rec),
            "rejects": self.rejects,
            "stall_events": self.stalls,
            "tier_writes_chunks": dict(self.writes),
            "tier_writes_gb": {k: round(v * self.CT * c.kv_bytes_per_token / 1e9, 1)
                               for k, v in self.writes.items()},
            "hit_rate_token_weighted": {
                "L1": sum(r[2] for r in self.prefill_rec) / tot_p,
                "L2": sum(r[3] for r in self.prefill_rec) / tot_p,
                "L3": sum(r[4] for r in self.prefill_rec) / tot_p,
            },
            "hit_rate_req_mean": {
                k: float(np.nanmean(v)) for k, v in hit.items()
            },
            "decode_avg_bs": float(np.average(
                [r[1] for r in self.decstep_rec],
                weights=[r[2] for r in self.decstep_rec])) if self.decstep_rec else 0.0,
            "ttft_s": self._stats([r[1] for r in self.prefill_rec]),
            "tpot_s": self._stats([r[1] for r in self.turn_rec]),
            "te2e_s": self._stats([r[2] for r in self.turn_rec]),
            "machine_busy_ratio": [round(m.busy_s / self.T, 4) for m in self.machines],
        }
        series = {"t_min": bt, "hit_L1": hit["L1"], "hit_L2": hit["L2"], "hit_L3": hit["L3"],
                  "ttft_s": ttft_s, "tpot_s": tpot_s, "te2e_s": te2e_s,
                  "decode_bs": decbs_s, "queued_prefill_tokens": queue_s}
        return summary, series

    @staticmethod
    def _stats(xs):
        if not xs:
            return {}
        a = np.asarray(xs)
        return {"mean": float(a.mean()), "p50": float(np.percentile(a, 50)),
                "p90": float(np.percentile(a, 90)), "p99": float(np.percentile(a, 99))}


def plot(series, summary, outdir):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    t = series["t_min"]
    fig, axes = plt.subplots(2, 3, figsize=(16, 8))
    fig.suptitle("Prefix Cache Simulation (%s, PD-colocated)" % summary["config"]["write_policy"])

    ax = axes[0][0]
    ax.plot(t, series["hit_L1"], label="L1 HBM")
    ax.plot(t, series["hit_L2"], label="L2 DRAM")
    ax.plot(t, series["hit_L3"], label="L3 SSD")
    ax.set_title("Prefill hit rate (per-request mean)")
    ax.set_xlabel("time (min)")
    ax.set_ylim(0, 1.02)
    ax.legend()
    ax.grid(alpha=0.3)

    ax = axes[0][1]
    ax.plot(t, series["decode_bs"], color="tab:red")
    ax.set_title("Decode avg batch size per rank")
    ax.set_xlabel("time (min)")
    ax.grid(alpha=0.3)

    ax = axes[0][2]
    ax.plot(t, series["queued_prefill_tokens"], color="tab:purple")
    ax.set_title("Cluster queued prefill tokens")
    ax.set_xlabel("time (min)")
    ax.grid(alpha=0.3)

    ax = axes[1][0]
    ax.plot(t, series["ttft_s"], color="tab:green")
    ax.set_title("TTFT (s)")
    ax.set_xlabel("time (min)")
    ax.grid(alpha=0.3)

    ax = axes[1][1]
    ax.plot(t, series["tpot_s"], color="tab:orange")
    ax.set_title("TPOT (s)")
    ax.set_xlabel("time (min)")
    ax.grid(alpha=0.3)

    ax = axes[1][2]
    ax.plot(t, series["te2e_s"], color="tab:brown")
    ax.set_title("TE2E (s)")
    ax.set_xlabel("time (min)")
    ax.grid(alpha=0.3)

    for a in axes.flat:
        a.tick_params(labelsize=8)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    path = os.path.join(outdir, "metrics.png")
    fig.savefig(path, dpi=140)
    return path


def main():
    p = argparse.ArgumentParser(description="多级前缀缓存仿真器")
    p.add_argument("--machines", type=int, default=4)
    p.add_argument("--ranks", type=int, default=8)
    p.add_argument("--l1-gb-per-rank", type=float, default=4096.0)
    p.add_argument("--l2-gb-per-machine", type=float, default=2048.0)
    p.add_argument("--l3-gb", type=float, default=262144.0)
    p.add_argument("--kv-bytes-per-token", type=float, default=105 * 1024)
    p.add_argument("--chunk-tokens", type=int, default=256)
    p.add_argument("--max-batched-tokens", type=int, default=8192)
    p.add_argument("--prefill-tps", type=float, default=10000.0)
    p.add_argument("--max-decode-bs", type=int, default=32)
    p.add_argument("--mtp-probs", type=str, default="0.5,0.25,0.15,0.10")
    p.add_argument("--agents", type=int, default=7000)
    p.add_argument("--hours", type=float, default=3.0)
    p.add_argument("--turns-mean", type=float, default=8.0)
    p.add_argument("--turns-max", type=int, default=128)
    p.add_argument("--prefill-len-mean", type=float, default=4096.0)
    p.add_argument("--decode-len-mean", type=float, default=512.0)
    p.add_argument("--think-mean-s", type=float, default=600.0)
    p.add_argument("--think-dist", type=str, default="exponential", choices=["poisson", "exponential"])
    p.add_argument("--write-policy", type=str, default="write_through",
                   choices=["write_through", "write_back", "write_selective"],
                   help="write_through=新chunk立即写全层；write_back=仅写L1淘汰时级联下沉；write_selective=仅写L1，再次被命中时才写穿L2/L3")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--sched-decode-weight", type=float, default=1.0,
                   help="调度器感知 decode 积压的强度：est += w * rank积压tok/rank解码速率；0=纯规格书基线")
    p.add_argument("--out", type=str, default="out")
    a = p.parse_args()

    cfg = Cfg(
        machines=a.machines, ranks=a.ranks,
        l1_gb_per_rank=a.l1_gb_per_rank, l2_gb_per_machine=a.l2_gb_per_machine,
        l3_gb=a.l3_gb, kv_bytes_per_token=a.kv_bytes_per_token,
        chunk_tokens=a.chunk_tokens, max_batched_tokens=a.max_batched_tokens,
        prefill_tps=a.prefill_tps, max_decode_bs=a.max_decode_bs,
        mtp_probs=tuple(float(x) for x in a.mtp_probs.split(",")),
        agents=a.agents, hours=a.hours, turns_mean=a.turns_mean, turns_max=a.turns_max,
        prefill_len_mean=a.prefill_len_mean, decode_len_mean=a.decode_len_mean,
        think_mean_s=a.think_mean_s, think_dist=a.think_dist, seed=a.seed, out=a.out,
        sched_decode_weight=a.sched_decode_weight, write_policy=a.write_policy,
    )
    os.makedirs(cfg.out, exist_ok=True)
    sim = Sim(cfg)
    summary, series = sim.run()

    with open(os.path.join(cfg.out, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    with open(os.path.join(cfg.out, "series.json"), "w", encoding="utf-8") as f:
        json.dump(series, f)
    png = plot(series, summary, cfg.out)

    print(json.dumps({k: v for k, v in summary.items() if k != "config"},
                     ensure_ascii=False, indent=2))
    print("plot:", png)


if __name__ == "__main__":
    main()
