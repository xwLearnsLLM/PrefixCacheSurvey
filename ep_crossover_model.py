# -*- coding: utf-8 -*-
"""
机制1重算：EPLB（冗余专家均衡）下 EP8 vs EP64 的交叉点
模型: K3.1 Pro, 896 routed experts, top-16, expert = 3584x3072 MXFP4
硬件: Ascend 950DT, 486 TFLOPS (MFU 0.4), HBM 3.2 TB/s, MTP3 -> 每卡 query = 4B
参照: DeepInfer 实测 moe_lb (decode EP64=1.090, 冗余 1 expert/卡; EP8 冗余 4/卡)
"""
import numpy as np

rng = np.random.default_rng(42)

# ---- 模型/硬件常量 ----
N_EXP   = 896          # routed experts
TOPK    = 16
LAYERS  = 92
W_BYTES = 16.5e6       # 每 expert 16.5 MB (MXFP4)
FLOPS_E = 66e6         # 每 expert-eval FLOPs
BW_HBM  = 3.2e12
BW_HBF  = 0.8e12       # HBF 读带宽
TFLOPS  = 486e12 * 0.4 # 有效算力
Q_PER_B = 4            # MTP3: 每请求 4 个 query
TAU     = 3.25         # 每步接受 token 数 (DeepInfer 口径)

T_W = W_BYTES / BW_HBM        # 单 expert 权重读取 5.16us
T_C = FLOPS_E / TFLOPS        # 单 eval 计算 0.34us

def zipf_probs(n, s):
    r = np.arange(1, n + 1)
    p = 1.0 / r ** s
    return p / p.sum()

PROBS = {s: zipf_probs(N_EXP, s) for s in (0.0, 0.5, 1.0)}

def mc_load(B, G, s, trials=100):
    """每卡 64B 个 expert-eval 按 Zipf(s) 分布, 分成 G 组, 返回 max/mean 负载比"""
    evals = 64 * B
    if evals == 0:
        return 1.0
    cnt = rng.multinomial(evals, PROBS[s], size=trials)      # trials x 896
    grp = cnt.reshape(trials, G, N_EXP // G).sum(axis=2)     # trials x G
    return float((grp.max(axis=1) / grp.mean(axis=1)).mean())

def t_moe_ms(B, G, L):
    """单步 MoE 耗时 (ms): max(权重读取地板, 计算) — 通信/attention 两方案相同, 略"""
    e_local = N_EXP // G
    t_w = e_local * T_W
    t_c = L * (64 * B / G) * T_C
    return LAYERS * max(t_w, t_c) * 1e3

def t_moe_hbf_ms(B, G, L):
    """若权重从 HBF (800GB/s) 读取"""
    e_local = N_EXP // G
    t_w = e_local * (W_BYTES / BW_HBF)
    t_c = L * (64 * B / G) * T_C
    return LAYERS * max(t_w, t_c) * 1e3

# ---- 1) 无 EPLB 的 Monte Carlo 负载因子 ----
print("== Monte Carlo 负载因子 L(B,G,s) [无冗余均衡] ==")
LMC = {}
for B in range(1, 513):
    for s in (0.0, 0.5, 1.0):
        LMC[(B, 8, s)] = mc_load(B, 8, s)
        LMC[(B, 64, s)] = mc_load(B, 64, s)
Bs = [4, 8, 16, 32, 64, 128, 256]
print("B      " + "".join(f"G=8,s={s:<4} G=64,s={s:<4}" for s in (0.0, 0.5, 1.0)))
for B in Bs:
    row = f"{B:<7}"
    for s in (0.0, 0.5, 1.0):
        row += f"{LMC[(B,8,s)]:<10.3f} {LMC[(B,64,s)]:<10.3f}"
    print(row)

# ---- 2) EPLB cap: 冗余专家把 L 压到上限 (DeepInfer 实测口径) ----
CAP8, CAP64 = 1.05, 1.09
def L_eff(B, G, s, eplb):
    l = LMC[(B, G, s)]
    return min(l, CAP8 if G == 8 else CAP64) if eplb else l

# ---- 3) 交叉点: EP8 胜出 <=> T(B,8) < T(B,64) ----
print("\n== EP8 反超 EP64 的交叉点 (每卡 batch B*) ==")
print("skew s | 无EPLB | 有EPLB(cap 1.05/1.09)")
for s in (0.0, 0.5, 1.0):
    line = f"s={s:<4}| "
    for eplb in (False, True):
        cross = None
        for B in range(1, 513):
            if t_moe_ms(B, 8, L_eff(B, 8, s, eplb)) < t_moe_ms(B, 64, L_eff(B, 64, s, eplb)):
                cross = B
                break
        line += ("永不反超" if cross is None else f"B*={cross}") + "      | "
    print(line)

# ---- 4) 有 EPLB 时吞吐-时延曲线 (s=0.5 中性偏斜) ----
print("\n== 有 EPLB, s=0.5: 单步耗时 / 每卡吞吐 / 单用户速率 ==")
print("B    | EP8 T(ms)  tok/s/卡  tok/s/用户 | EP64 T(ms) tok/s/卡  tok/s/用户")
for B in (8, 16, 32, 64, 128, 256):
    t8  = t_moe_ms(B, 8,  L_eff(B, 8, 0.5, True))
    t64 = t_moe_ms(B, 64, L_eff(B, 64, 0.5, True))
    print(f"{B:<4} | {t8:8.1f} {B*TAU/t8*1e3:8.0f} {TAU/t8*1e3:9.1f} | "
          f"{t64:8.1f} {B*TAU/t64*1e3:8.0f} {TAU/t64*1e3:9.1f}")

# ---- 5) SLO 下最大 batch (单用户 >= 50 tok/s => T<=65ms; >=30 => T<=108ms) ----
print("\n== 有 EPLB, s=0.5: SLO 约束下最大每卡 batch ==")
for slo, tmax in ((50, TAU/50*1e3), (30, TAU/30*1e3)):
    r = {}
    for G in (8, 64):
        ok = [B for B in range(1, 513) if t_moe_ms(B, G, L_eff(B, G, 0.5, True)) <= tmax]
        r[G] = max(ok) if ok else 0
    print(f"单用户>={slo} tok/s (T<={tmax:.0f}ms): EP8 Bmax={r[8]}, EP64 Bmax={r[64]}")

# ---- 6) HBF 带宽口径: 权重读取地板 ----
print("\n== 权重读取地板 (HBM vs HBF) ==")
for G in (8, 64):
    gb = LAYERS * (N_EXP // G) * W_BYTES / 1e9
    print(f"EP{G}: 每步权重 {gb:6.1f} GB | HBM {LAYERS*(N_EXP//G)*T_W*1e3:6.1f} ms"
          f" | HBF {LAYERS*(N_EXP//G)*(W_BYTES/BW_HBF)*1e3:7.1f} ms")
