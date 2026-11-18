# Ascend950-HBF 推理系统竞争力分析：对话技术简报

> 用途：作为后续 agent 开展 HBF 推理系统竞争力分析的背景材料与计算底稿。
>
> 目标模型：**GLM-5.2-w4a8c8**；Decode 使用 **MTP3**，即每个请求每步包含 4 个 query。
>
> 注意：本文混合了用户给定规格、论文锚点、解析估算与 Monte Carlo 仿真。除明确标为“实测/论文”的内容外，不应将数值当作硬件或系统的官方承诺。

## 1. 核心问题与结论摘要

本对话围绕以下问题展开：

1. 设想一种新的NPU形态：Ascend950-HBF，它是把 Ascend950DT 的 HBM 换成堆叠的 DRAM 和 HBF。在这种硬件形态下，围绕"高性价比推理"命题设想一种推理架构。
2. 用 **Ascend950-HBF** 替代 **Ascend950DT**，在 PD 分离的中心化推理中部署 GLM-5.2-w4a8c8，能否在尽量不影响性能的前提下提高吞吐与性价比。
3. HBF 的大容量能否支持权重、KV cache 分层卸载，并通过 DRAM/HBF 流水掩盖加载开销。
4. 能否把 Prefill/Decode 的 EP、TP 通信限制在 8 卡刀片内，以省去大规模超节点，仅保留廉价 scale-out 网络。
5. 在 A5 上比较 **DP8EP8** 与 **DP64EP64**：大 batch、MTP3 和专家路由偏斜如何改变 ITL、单用户吞吐和单 NPU 吞吐。

目前得到的方向性结论：

- **容量是 HBF 的主要优势，带宽与随机访问粒度是主要约束。** 权重可以驻留 HBF 并滚动预取，KV cache 可以采用 DRAM 热缓存 + HBF 冷容量，但必须用足够大的 batch 和预取窗口掩盖 HBF 读开销。
- 在设定的 64K、EP8、IndexShare 工作点，解析估算得到 **BS=12 左右刚好掩盖 MoE 与 KV 加载**；工程上建议 BS=13～16 或更高，以保留调度、抖动和路由偏斜裕量。
- 8 卡形态在容量和带宽上具有可行性，主要风险不只是裸通信，而是 **prefix cache 组亲和、连续 batch 调度碎片、冷热 KV 命中率和 HBF 尾延迟**。
- EP8 与 EP64 的优劣取决于 batch 和路由偏斜：均匀路由时 EP64 通常占优；偏斜和大 batch 会放大 EP64 的全组同步拖尾，EP8 的交叉点提前。
- 当前仿真交叉点约为：**s=0 时 B≈96；s=0.25 时 B≈56；s=0.5 时 B≈32**。B 是每卡 batch，不是全 EP 组 batch。B>48 属于对实测 ITL 拟合式的外推。

## 2. 模型与推理前提

### 2.1 GLM-5.2-w4a8c8

本对话采用的结构参数：

| 项目 | 数值 |
|---|---:|
| 总层数 | 78 |
| Dense 层 / MoE 层 | 3 / 75 |
| Hidden size | 6144 |
| Routed experts | 256 |
| Shared expert | 1 |
| 每 token routed top-k | 8 |
| MoE intermediate size | 2048 |
| Dense FFN intermediate size | 12288 |
| MLA latent 维度 | 576 |
| 权重精度 | W4 |
| 激活、KV 假设 | A8、C8 |
| Decode 推测机制 | MTP3，每请求每步 4 query |

单个 routed expert 的 W4 权重近似为：

```text
3 × 6144 × 2048 × 0.5 Byte = 18.9 MB
```

因此：

```text
每个 MoE 层 257 个 expert 约 4.85 GB
全模型 W4 权重约 372 GB
```

KV cache 采用论文中 GLM-5.2-w4a8c16 的实测值 190.6 KB/token 作锚点，再按 C16→C8 减半：

```text
C8 KV ≈ 95.3 KB/token
```

这是估算锚点，实际部署还需确认 IndexShare、层类型、对齐、元数据和分页开销。

### 2.2 MTP3 对计算与通信的影响

MTP3 不是把每请求只按 1 个 query 计算，而是：

```text
Q = 4
每卡 query 数 = 4B
全 EP 组 query 数 = 4B × G
```

其中 G 为 EP 组大小。MoE 激活率、专家计算量和 all-to-all 流量都必须使用 query 数，而不能直接使用请求数 B。

每步接受约 3 个输出 token，因此：

```text
TPOT = ITL / 3
单用户输出吞吐 = 3 / ITL
若 ITL 使用 ms，则单用户输出吞吐 = 3000 / ITL(ms)  tokens/s
单 NPU 输出吞吐 = B × 3000 / ITL(ms)  tokens/s
```

## 3. 硬件与拓扑前提

### 3.1 Ascend950DT 与 Ascend950-HBF

术语：**HHM（High Bandwidth Hybrid Memory）** 即 950-HBF 这张 NPU 采用的存储方案——3 个 DRAM die + 1 个 HBF die 堆叠（用户 2026-11-10 确认）。下文"36GB DRAM + 320GB HBF"即 HHM 封装内的两级。

本对话使用的用户给定规格：

| 项目 | Ascend950DT | Ascend950-HBF |
|---|---:|---:|
| 近端高带宽内存 | 96 GB HBM | 36 GB DRAM |
| DRAM 可用划分 | — | 12 GB 写缓冲 + 24 GB 可见 |
| DRAM/HBM 带宽 | 3.2 TB/s | 3.2 TB/s |
| 大容量介质 | — | 320 GB HBF |
| HBF 读带宽 | — | 800 GB/s |
| HBF 写带宽 | — | 40 GB/s |
| HBF IOPS | — | 48M IOPS |
| HBF 最小访问粒度 | — | 4 KB |
| HBF 访问特征 | — | 读时延较高，适合流水预取，不适合无掩盖的小随机读。 |

竞争力分析中应分别核算：

- **稳态平均带宽是否足够**；
- **最坏分层/路由偏斜下是否仍能掩盖**；
- **4 KB 粒度是否导致读放大**；
- **写带宽、写缓冲和 KV 更新是否形成瓶颈**；
- **高读时延能否被足够深的预取队列隐藏**。

### 3.2 A5 拓扑

本对话采用的 A5 抽象：

- 刀片内 8 NPU full-mesh；
- 跨刀片组成 64 NPU Clos 互联域；
- 每 NPU 7 个 UB port 用于刀片内 mesh，合计双向带宽按 784 GB/s 建模；
- 每 NPU 8 个 port 接入 Unions/Clos，原始双向带宽按 896 GB/s 建模；
- UB port 单口双向带宽按 112 GB/s 建模。

仿真中 EP8 使用刀片内 mesh，EP64 使用跨刀片 Clos。该模型只考虑通信带宽、固定时延和 MoE 层间同步，不代表真实集合通信库的全部开销。

## 4. HBF 部署方案

### 4.1 PD 分离与数据放置

建议基线方案：

- **激活**：放 DRAM，按 `K × 本次 forward token 数` 估算，并受 max-num-batched-tokens 限制。
- **权重**：放 HBF，按层滚动预取到 DRAM；利用大 batch 摊薄权重读取。
- **KV cache**：容量主体放 HBF；Prefill 逐层滚动写入/读取，Decode 使用 DRAM 热缓存 + HBF 冷缓存。
- **P→D 迁移**：通过 scale-out 网络传输请求状态和必要 KV，不要求大规模超节点承担 EP/TP 通信。

Decode KV 设计参考 FlashOffloading 思路：热缓存、分层管理、miss 合并及预取。对话中采用的 miss union 量级约为 300 token/请求/步，但这不是 GLM-5.2 在 HBF 上的实测结果。

### 4.2 Prefill 激活估算

GLM-5.2 的激活近似：

```text
激活显存 ≈ K × max_num_batched_tokens
K ≈ 99 KB/token/die
```

该 K 由论文两个数据点交叉验证：

```text
1.67 GB @ 16,384 tokens
13.26 GB @ 131,072 tokens
```

chunk=128K 时，激活约可控制在 24 GB 可见 DRAM 内，但仍需与 KV 热缓存、专家缓冲、通信缓冲和运行时预留共同做容量规划，不能独立占满 DRAM。

### 4.3 64K、EP8、IndexShare 工作点

采用的部署设想：

- 21 个 full 层的 KV 驻留 DRAM；
- 57 个 share 层放 HBF，share 层至少具有一个完整层的预取窗口；
- KV 按 TP2/CP2 分片；
- EP8 每卡 32 个本地 experts；
- 全量预取每卡本地专家，每步固定约 45.4 GB，HBF 读取约 56.7 ms。

解析估算得到：

| 项目 | 估算值 |
|---|---:|
| MoE + KV 总需求 | 约 58.1 ms |
| BS=12 时 ITL | 约 59.7 ms |
| HBF 占用 | 约 97.4% |
| 建议工作点 | BS=13～16 起，并继续验证偏斜与尾延迟 |

BS=12 的 DRAM 估算：

| 组成 | 容量 |
|---|---:|
| Full 层 KV | 10.1 GB |
| Share 层热缓存 | 5.1 GB |
| Dense 相关 | 2.3 GB |
| 专家缓冲 | 1.8 GB |
| 激活 | 1.0 GB |
| 余量 | 3.7 GB |

该结果说明“刚好掩盖”非常脆弱：97.4% 的带宽占用几乎没有吸收路由热点、KV miss 突增和集合通信抖动的能力。竞争力分析应把 BS=12 视为理论边界，而非推荐 SLA 工作点。

### 4.4 8 卡形态与 P→D 网络

已得到的粗略判断：

- 权重可驻留，EP all-to-all 在目标大 batch 下占比可低于 1%；
- TP8 all-reduce 裸开销约 16%，采用 DP-attention 和通信重叠后可降至约 4%～8%；
- P→D 迁移平均需求约 0.57 GB/s/卡，即约 4.5 Gbps/卡；
- 主要系统性代价是 prefix cache 组亲和、请求迁移、调度碎片和故障域管理。

上述比例依赖具体序列长度、batch、KV 命中和重叠效率，后续不能直接当作端到端实测收益。
