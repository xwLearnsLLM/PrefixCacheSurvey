from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle
from matplotlib import font_manager

OUT = Path(r"D:\HBF\multilevel_prefix_cache_figures")
OUT.mkdir(parents=True, exist_ok=True)

# Prefer Microsoft YaHei, with common CJK fallbacks for portability.
for candidate in ["Microsoft YaHei", "msyh.ttc", "SimHei", "Noto Sans CJK SC"]:
    try:
        font_manager.findfont(candidate, fallback_to_default=False)
        plt.rcParams["font.family"] = candidate
        break
    except Exception:
        continue
plt.rcParams["axes.unicode_minus"] = False

C = {
    "ink": "#243447", "muted": "#637083", "line": "#9AA8B8",
    "blue": "#DCEBFA", "blue_edge": "#3978B8",
    "green": "#DFF2E4", "green_edge": "#3C8C58",
    "orange": "#FFF0D9", "orange_edge": "#C67B22",
    "purple": "#EEE6F8", "purple_edge": "#7956A8",
    "red": "#FBE4E4", "red_edge": "#B94A48",
    "gray": "#F1F4F7", "dark": "#34495E", "white": "#FFFFFF",
}


def box(ax, x, y, w, h, text, fc=C["white"], ec=C["line"], lw=1.4,
        fs=10.5, color=C["ink"], style="round,pad=0.018,rounding_size=0.025",
        weight="normal", zorder=3, dashed=False):
    p = FancyBboxPatch((x, y), w, h, boxstyle=style, linewidth=lw,
                       edgecolor=ec, facecolor=fc, zorder=zorder,
                       linestyle="--" if dashed else "-")
    ax.add_patch(p)
    ax.text(x+w/2, y+h/2, text, ha="center", va="center", fontsize=fs,
            color=color, weight=weight, zorder=zorder+1, linespacing=1.35)
    return p


def arrow(ax, x1, y1, x2, y2, color=C["blue_edge"], lw=1.6,
          style="-|>", rad=0, dashed=False, zorder=4):
    p = FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style,
                        mutation_scale=13, linewidth=lw, color=color,
                        connectionstyle=f"arc3,rad={rad}", zorder=zorder,
                        linestyle="--" if dashed else "-")
    ax.add_patch(p)
    return p


def title(ax, main, sub=None):
    ax.text(0.5, 0.975, main, transform=ax.transAxes, ha="center", va="top",
            fontsize=20, weight="bold", color=C["ink"])
    if sub:
        ax.text(0.5, 0.932, sub, transform=ax.transAxes, ha="center", va="top",
                fontsize=10.5, color=C["muted"])


def canvas(figsize):
    fig, ax = plt.subplots(figsize=figsize, dpi=180)
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    fig.patch.set_facecolor("white"); ax.set_facecolor("white")
    return fig, ax


def save(fig, name):
    fig.savefig(OUT / name, bbox_inches="tight", facecolor="white", dpi=180)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Figure 1: software sharing domains
# ---------------------------------------------------------------------------
fig, ax = canvas((18, 11))
title(ax, "多级前缀缓存的软件共享域原型",
      "坐标系统一为 L1＝HBM、L2＝CPU DRAM、L3＝SSD／外部存储；虚线表示控制或可选边界")
cols = [(0.035, 0.305), (0.355, 0.305), (0.675, 0.29)]
for x, w in cols:
    box(ax, x, 0.065, w, 0.825, "", fc="#FCFDFE", ec="#D7DEE6", lw=1.2)

# HiCache
x, w = cols[0]
ax.text(x+w/2, 0.852, "HiCache", ha="center", fontsize=17, weight="bold", color=C["blue_edge"])
ax.text(x+w/2, 0.817, "实例私有前缀树＋可插拔外部层", ha="center", fontsize=10.5, color=C["muted"])
box(ax, x+0.025, 0.405, w-0.05, 0.365, "", fc="#F7FAFD", ec=C["blue_edge"], dashed=True)
ax.text(x+0.04, 0.742, "单个 inference instance", fontsize=10, color=C["blue_edge"], weight="bold")
box(ax, x+0.055, 0.62, w-0.11, 0.09, "L1  HBM\n各 DP rank 私有", fc=C["blue"], ec=C["blue_edge"], weight="bold")
box(ax, x+0.055, 0.465, w-0.11, 0.09, "L2  Host pool\n整个实例私有", fc=C["green"], ec=C["green_edge"], weight="bold")
arrow(ax, x+w/2, 0.615, x+w/2, 0.56)
arrow(ax, x+w/2, 0.555, x+w/2, 0.62, style="<|-")
box(ax, x+0.055, 0.245, w-0.11, 0.115, "L3  Storage backend\nfile：节点本地\nMooncake／HF3FS 等：可集群共享", fc=C["orange"], ec=C["orange_edge"], fs=10)
arrow(ax, x+w/2, 0.46, x+w/2, 0.365)
arrow(ax, x+w/2, 0.36, x+w/2, 0.465, style="<|-")
box(ax, x+0.045, 0.105, w-0.09, 0.075, "跨实例：不能直接读取对方 L2\n只能经由共享 L3 复用", fc=C["red"], ec=C["red_edge"], fs=10)

# LMCache MP
x, w = cols[1]
ax.text(x+w/2, 0.852, "LMCache MP", ha="center", fontsize=17, weight="bold", color=C["green_edge"])
ax.text(x+w/2, 0.817, "节点共享对象缓存＋跨机 P2P", ha="center", fontsize=10.5, color=C["muted"])
for dx, label in [(0.02, "节点 A"), (0.165, "节点 B")]:
    box(ax, x+dx, 0.405, 0.12, 0.365, "", fc="#F8FCF9", ec=C["green_edge"], dashed=True)
    ax.text(x+dx+0.06, 0.742, label, ha="center", fontsize=10, weight="bold", color=C["green_edge"])
    box(ax, x+dx+0.012, 0.64, 0.096, 0.065, "vLLM pods\nL1 HBM 私有", fc=C["blue"], ec=C["blue_edge"], fs=9)
    box(ax, x+dx+0.012, 0.49, 0.096, 0.075, "LMCache server\nL2 DRAM 节点共享", fc=C["green"], ec=C["green_edge"], fs=9, weight="bold")
    arrow(ax, x+dx+0.06, 0.635, x+dx+0.06, 0.57)
    box(ax, x+dx+0.012, 0.275, 0.096, 0.07, "L3 本地 SSD\n默认节点私有", fc=C["orange"], ec=C["orange_edge"], fs=9)
    arrow(ax, x+dx+0.06, 0.485, x+dx+0.06, 0.35)
arrow(ax, x+0.14, 0.528, x+0.165, 0.528, color=C["purple_edge"], lw=2.2, style="<|-|>")
ax.text(x+w/2, 0.573, "跨机 L2：单边 RDMA\nP2P 只读、one-hop", ha="center", fontsize=9.5, color=C["purple_edge"], weight="bold")
box(ax, x+0.045, 0.105, w-0.09, 0.09, "可选共享 L3\nshared: true＋同一 NFS export／S3 bucket\nCoordinator 仅发现成员，不传 KV", fc=C["purple"], ec=C["purple_edge"], fs=9.5)

# Mooncake
x, w = cols[2]
ax.text(x+w/2, 0.852, "Mooncake Store", ha="center", fontsize=17, weight="bold", color=C["purple_edge"])
ax.text(x+w/2, 0.817, "全局对象目录＋分布式副本池", ha="center", fontsize=10.5, color=C["muted"])
box(ax, x+0.035, 0.65, w-0.07, 0.085, "上层推理引擎\nL1 HBM 由引擎私有管理", fc=C["blue"], ec=C["blue_edge"], fs=10, weight="bold")
box(ax, x+0.035, 0.505, w-0.07, 0.08, "Clients＋Transfer Engine\n数据面：RDMA／TCP", fc=C["green"], ec=C["green_edge"], fs=10)
arrow(ax, x+w/2, 0.645, x+w/2, 0.59)
box(ax, x+0.035, 0.32, w-0.07, 0.115, "L2  全局 DRAM 副本池\n跨节点定位与拉取\n（Client 另有本地 HotCache）", fc=C["green"], ec=C["green_edge"], fs=10, weight="bold")
arrow(ax, x+w/2, 0.5, x+w/2, 0.44)
box(ax, x+0.035, 0.18, w-0.07, 0.075, "L3  全局可寻址 SSD 副本池", fc=C["orange"], ec=C["orange_edge"], fs=10)
arrow(ax, x+w/2, 0.315, x+w/2, 0.26)
box(ax, x+0.04, 0.09, w-0.08, 0.055, "Master：元数据／lease／pin／淘汰，不传 KV", fc=C["purple"], ec=C["purple_edge"], fs=9.2)
arrow(ax, x+0.055, 0.145, x+0.055, 0.32, color=C["purple_edge"], dashed=True, rad=-0.25)
arrow(ax, x+w-0.055, 0.145, x+w-0.055, 0.505, color=C["purple_edge"], dashed=True, rad=-0.25)

ax.text(0.5, 0.028, "关键判据：共享域由软件索引、命名空间和访问协议决定，而非由 DRAM／SSD 的物理位置决定。",
        ha="center", fontsize=11.5, color=C["ink"], weight="bold")
save(fig, "fig1_shared_domains.png")


# ---------------------------------------------------------------------------
# Figure 2: logical hit sequences
# ---------------------------------------------------------------------------
fig, axes = plt.subplots(3, 1, figsize=(18, 14), dpi=180)
fig.patch.set_facecolor("white")
fig.suptitle("连续前缀命中的逻辑时序", fontsize=21, weight="bold", color=C["ink"], y=0.997)
fig.text(0.5, 0.94, "实线箭头为数据或请求流；虚线为控制流。省略线程池、重试、ACK 与 TP 同步细节。",
         ha="center", va="top", fontsize=10.5, color=C["muted"])


def sequence_panel(ax, heading, actors, actor_colors, steps, note):
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    ax.add_patch(FancyBboxPatch((0.008, 0.02), 0.984, 0.94,
                               boxstyle="round,pad=0.008,rounding_size=0.02",
                               fc="#FDFEFE", ec="#D9E0E7", lw=1.1))
    ax.text(0.025, 0.89, heading, fontsize=15, weight="bold", color=C["ink"], va="center")
    xs = [0.13 + i * (0.76 / (len(actors)-1)) for i in range(len(actors))]
    for x, name, color in zip(xs, actors, actor_colors):
        box(ax, x-0.058, 0.70, 0.116, 0.105, name, fc=color[0], ec=color[1], fs=9.5, weight="bold")
        ax.plot([x, x], [0.16, 0.695], color="#B7C1CC", lw=1.2, ls="--", zorder=1)
    # steps: (from, to, y, text, kind, rad)
    for idx, (a, b, y, text, kind, rad) in enumerate(steps, 1):
        is_ctrl = kind == "ctrl"
        is_data = kind == "data"
        color = C["purple_edge"] if is_ctrl else (C["green_edge"] if is_data else C["blue_edge"])
        arrow(ax, xs[a], y, xs[b], y, color=color, lw=2.0 if is_data else 1.5,
              dashed=is_ctrl, rad=rad)
        xm = (xs[a] + xs[b]) / 2
        ax.text(xm, y+0.025, f"{idx}  {text}", ha="center", va="bottom", fontsize=9.2,
                color=color, bbox=dict(fc="white", ec="none", pad=0.8))
    ax.text(0.5, 0.075, note, ha="center", fontsize=10, color=C["muted"])

sequence_panel(
    axes[0], "A  HiCache：外部 L3 命中必须经本地 L2 暂存，再加载 L1",
    ["前缀树／调度器", "L1  HBM", "L2  Host pool", "L3  Storage"],
    [(C["gray"], C["line"]), (C["blue"], C["blue_edge"]),
     (C["green"], C["green_edge"]), (C["orange"], C["orange_edge"])],
    [(0, 1, 0.61, "本地 RadixTree 最长前缀匹配", "req", 0),
     (0, 3, 0.49, "查询连续 key 的存储命中长度", "ctrl", 0),
     (3, 2, 0.36, "prefetch：L3 → L2", "data", 0),
     (2, 1, 0.23, "达到阈值后 H2D：L2 → L1", "data", 0)],
    "未命中部分由 GPU 重算；host pool 不足时可放弃 storage hit。L3 不会直接向 HBM 提供正常命中数据。")

sequence_panel(
    axes[1], "B  LMCache MP：跨机命中对端节点共享 DRAM，复制到本机后再 H2D",
    ["请求方 vLLM", "本机 LMCache", "对端 LMCache", "Coordinator"],
    [(C["blue"], C["blue_edge"]), (C["green"], C["green_edge"]),
     (C["green"], C["green_edge"]), (C["purple"], C["purple_edge"])],
    [(0, 1, 0.61, "本机 lookup miss；发现对端", "ctrl", 0),
     (1, 2, 0.49, "请求对端 locate／read lock", "ctrl", 0),
     (2, 1, 0.36, "单边 RDMA：对端 DRAM → 本机 DRAM", "data", 0),
     (1, 0, 0.23, "本机 H2D：DRAM → HBM", "data", 0)],
    "Coordinator 只负责成员发现；P2P 为 read-only、one-hop，不写对端，也不经多个 peer 链式转发。")

sequence_panel(
    axes[2], "C  Mooncake：SSD 副本先物化为临时 DRAM，再由请求方拉取",
    ["请求方 Client", "Master", "持有方 Client", "SSD"],
    [(C["blue"], C["blue_edge"]), (C["purple"], C["purple_edge"]),
     (C["green"], C["green_edge"]), (C["orange"], C["orange_edge"])],
    [(0, 1, 0.61, "Get：解析 object 与副本位置", "ctrl", 0),
     (1, 2, 0.49, "返回 SSD 副本位置并保护 lease", "ctrl", 0),
     (3, 2, 0.36, "SSD → 持有方临时 DRAM", "data", 0),
     (2, 0, 0.23, "RDMA／TCP：临时 DRAM → 请求方", "data", 0)],
    "最后由上层推理引擎执行 DRAM → HBM。当前逻辑路径仍经 DRAM，不能抽象为已有 SSD → GPU 直通。")

fig.subplots_adjust(top=0.93, bottom=0.025, left=0.018, right=0.985, hspace=0.16)
save(fig, "fig2_hit_sequence.png")


# ---------------------------------------------------------------------------
# Figure 3: write and eviction algorithms
# ---------------------------------------------------------------------------
fig, ax = canvas((18, 12))
title(ax, "写入时机与淘汰算法：三种实现不能统称为简单 LRU",
      "包含关系是写入策略与生命周期共同形成的状态属性，而非层级名称天然具有的性质")

# Column backgrounds and headings
for x, w, heading, sub, color in [
    (0.025, 0.305, "HiCache", "RadixTree 叶淘汰＋策略化下沉", C["blue_edge"]),
    (0.35, 0.305, "LMCache MP", "对象 LRU／ARC＋异步多后端写入", C["green_edge"]),
    (0.675, 0.30, "Mooncake", "lease bucket＋pin＋offload", C["purple_edge"]),
]:
    box(ax, x, 0.06, w, 0.825, "", fc="#FCFDFE", ec="#D7DEE6", lw=1.2)
    ax.text(x+w/2, 0.847, heading, ha="center", fontsize=16, weight="bold", color=color)
    ax.text(x+w/2, 0.812, sub, ha="center", fontsize=10, color=C["muted"])

# HiCache policies
x, w = 0.025, 0.305
box(ax, x+0.018, 0.66, w-0.036, 0.105,
    "write_through\n首次插入：L1 → L2；DMA ACK 后 L2 → L3",
    fc=C["blue"], ec=C["blue_edge"], fs=9.8)
box(ax, x+0.018, 0.52, w-0.036, 0.105,
    "write_through_selective\n第 2 次复用触发下沉；随后走同一 ACK 路径",
    fc=C["green"], ec=C["green_edge"], fs=9.8)
box(ax, x+0.018, 0.38, w-0.036, 0.105,
    "write_back\n仅在 L1 淘汰时下沉尚未 backup 的节点",
    fc=C["orange"], ec=C["orange_edge"], fs=9.8)
# Tree eviction miniature
ax.text(x+w/2, 0.325, "L1 淘汰：evictable leaves 最小堆", ha="center", fontsize=10.5, weight="bold", color=C["ink"])
box(ax, x+0.115, 0.245, 0.075, 0.048, "父节点", fc=C["gray"], ec=C["line"], fs=9)
for lx, ly, txt in [(x+0.035, 0.165, "叶 A"), (x+0.115, 0.165, "叶 B"), (x+0.195, 0.165, "叶 C")]:
    box(ax, lx, ly, 0.065, 0.048, txt, fc=C["red"], ec=C["red_edge"], fs=9)
    arrow(ax, x+0.152, 0.242, lx+0.0325, 0.216, color=C["line"], lw=1.1, style="-")
ax.text(x+w/2, 0.115, "按 last_access_time 选叶；孩子清空后父节点成为新候选\nL2 自身淘汰只释放 L2，不再触发 L2 → L3",
        ha="center", fontsize=9.4, color=C["muted"], linespacing=1.5)

# LMCache
x, w = 0.35, 0.305
box(ax, x+0.018, 0.66, w-0.036, 0.105,
    "默认 STORE：GPU → CPU\n随后异步写所有已配置持久 adapter",
    fc=C["green"], ec=C["green_edge"], fs=9.8)
box(ax, x+0.018, 0.52, w-0.036, 0.105,
    "对象状态机\nNone → write_locked → ready → read_locked",
    fc=C["blue"], ec=C["blue_edge"], fs=9.8)
box(ax, x+0.018, 0.38, w-0.036, 0.105,
    "buffer-only 例外\nskip_l1：写完或预取读后删除临时 CPU 副本",
    fc=C["orange"], ec=C["orange_edge"], fs=9.8)
box(ax, x+0.025, 0.225, w-0.05, 0.105,
    "CPU 后台水位淘汰\n默认触发 80%，每轮释放 20%\nLRU／ARC／IsolatedLRU；locked 对象跳过",
    fc=C["red"], ec=C["red_edge"], fs=9.6)
box(ax, x+0.025, 0.095, w-0.05, 0.085,
    "持久 adapter：独立 opt-in 水位淘汰\n命中 touch；从 LRU 老端扫描，跳过不可淘汰对象",
    fc=C["gray"], ec=C["line"], fs=9.4)

# Mooncake
x, w = 0.675, 0.30
box(ax, x+0.018, 0.68, w-0.036, 0.085,
    "新对象：先同步落 DRAM\nSSD：eager 或 watermark／on-evict 异步卸载",
    fc=C["green"], ec=C["green_edge"], fs=9.6)
box(ax, x+0.025, 0.565, w-0.05, 0.07,
    "LeaseEvictionIndex：512 shards\n租约截止按 100 ms bucket 归档",
    fc=C["purple"], ec=C["purple_edge"], fs=9.6)
box(ax, x+0.025, 0.455, w-0.05, 0.06,
    "从最早过期 bucket 扫描并重新校验 lease", fc=C["gray"], ec=C["line"], fs=9.5)
arrow(ax, x+w/2, 0.56, x+w/2, 0.52, color=C["purple_edge"])
box(ax, x+0.025, 0.33, w-0.05, 0.08,
    "hard pin／active lease：跳过\nsoft pin：首轮 defer，候选不足时 fallback",
    fc=C["orange"], ec=C["orange_edge"], fs=9.5)
arrow(ax, x+w/2, 0.45, x+w/2, 0.415, color=C["purple_edge"])
box(ax, x+0.025, 0.18, w-0.05, 0.105,
    "释放 DRAM 前检查 SSD 副本\n无完成副本：先 pin＋offload\n已有 SSD：可直接释放 DRAM",
    fc=C["red"], ec=C["red_edge"], fs=9.6)
arrow(ax, x+w/2, 0.325, x+w/2, 0.29, color=C["purple_edge"])
ax.text(x+w/2, 0.115, "另有 Client 本地 HotCache：固定块 LRU\n它与 Master 的全局 lease-bucket 淘汰不是同一层算法",
        ha="center", fontsize=9.2, color=C["muted"], linespacing=1.5)

ax.text(0.5, 0.025, "统一保护原则：正在读写的数据不可淘汰；共享前缀应尽量保留；无后备副本的数据在丢弃前必须迁移或明确允许丢失。",
        ha="center", fontsize=11, color=C["ink"], weight="bold")
save(fig, "fig3_write_eviction.png")

print(f"Figures written to {OUT}")
