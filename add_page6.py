# -*- coding: utf-8 -*-
"""新增第6页：相关工作对比大表。克隆 slide5 框架（保留 title/subtitle/sum/footer），删除正文形状，插入 11 行大表。"""
import zipfile, re, shutil

PPTX = r"D:\HBF\hbf-inference\hbf-inference.pptx"
TMP  = r"D:\HBF\hbf-inference\tmp_p6.pptx"
E = 12700

zin = zipfile.ZipFile(PPTX)
s5 = zin.read("ppt/slides/slide5.xml").decode("utf-8")

# ---- 1) 删除第5页正文形状，保留框架 ----
REMOVE = {"t1-num","t1-title","t1-body","t1-sep","t2-num","t2-title","t2-body",
          "d1-label","d1-req","d1-req-t","d1-arrow1","d1-query","d1-query-t",
          "d1-arrow2","d1-arrow3","d1-hit","d1-hit-t","d1-mig","d1-mig-t",
          "d2-label","d2-kv","d2-kv-t","d2-arrow1","d2-pred","d2-pred-t","d2-out"}
def drop(m):
    return "" if re.search(r'name="([^"]*)"', m.group(0)).group(1) in REMOVE else m.group(0)
s6, n = re.subn(r'<p:sp>.*?</p:sp>', drop, s5, flags=re.S)
print("shapes before/after:", len(re.findall(r'<p:sp>', s5)), "->", len(re.findall(r'<p:sp>', s6)))

# ---- 2) 对比表 ----
COLS = [128, 118, 282, 336]   # = 864px
X, Y = 48, 92
HDR_H, ROW_H = 16, 32

def rpr(sz, bold, color):
    b = ' b="1"' if bold else ''
    return (f'<a:rPr lang="zh-CN" sz="{sz}"{b} noProof="1"><a:solidFill><a:srgbClr val="{color}"/></a:solidFill>'
            f'<a:latin typeface="微软雅黑" panose="020B0503020204020204" charset="-122"/>'
            f'<a:ea typeface="微软雅黑" panose="020B0503020204020204" charset="-122"/></a:rPr>')

def cell(text, kind):
    # kind: 0 header, 1 body, 2 highlight
    fill  = {0: "1F3A5F", 1: "FFFFFF", 2: "EAF1F8"}[kind]
    color = "FFFFFF" if kind == 0 else "333333"
    bold  = kind == 0
    sz    = 700 if kind == 0 else 600
    return (f'<a:tc><a:txBody><a:bodyPr/><a:lstStyle/><a:p><a:pPr algn="l"/>'
            f'<a:r>{rpr(sz, bold, color)}<a:t>{text}</a:t></a:r></a:p></a:txBody>'
            f'<a:tcPr marL="25400" marR="25400" marT="12700" marB="12700" anchor="ctr">'
            f'<a:lnL w="0"><a:noFill/></a:lnL><a:lnR w="0"><a:noFill/></a:lnR>'
            f'<a:lnT w="0"><a:noFill/></a:lnT>'
            f'<a:lnB w="6350"><a:solidFill><a:srgbClr val="D9DEE4"/></a:solidFill></a:lnB>'
            f'<a:solidFill><a:srgbClr val="{fill}"/></a:solidFill></a:tcPr></a:tc>')

ROWS = [
    ("工作（出处）", "场景", "方法要点", "与本方案差异"),
    ("先驱：FlexGen / LLM-in-a-Flash / PowerInfer（ICML'23–SOSP'24）", "单卡 / 端侧",
     "权重分层 offload、冷热神经元流式加载，大 batch 摊薄 I/O", "思想源头（容量换成本）；本方案面向中心推理集群"),
    ("MoE 卸载系列：EdgeMoE / MoE-Infinity / Fiddler（ICLR'25 等）", "单机 MoE",
     "专家驻外存，激活时加载 + 预测预取", "本方案专家权重驻 HBF 滚动预取，配合 EP8 单元化调度"),
    ("H³（SK hynix · IEEE CAL'26）", "单机混合封装",
     "只读数据（权重/共享 KV）放 HBF；吞吐/功耗 2.69×", "读写分离同思路；本方案把 KV 也分层进 HBF"),
    ("FlashAccel（中科院计算所 · 2607.10186）", "单 GPU + HBF",
     "HBF 感知布局 + 流水掩盖 40× 读延迟；100ms 约束下吞吐 2.49×", "滚动预取一致；本方案扩展为 8 卡自洽单元 + PD 融合"),
    ("MoE-in-a-Box（华为 · 2609.15636）", "一体机（Kimi-K3 负载）",
     "权重 HBF + 状态 DRAM；近端带宽需求 33.3→1.4–4.0 s⁻¹", "与本构想几乎同构的直接印证；本方案面向集群化与跨模型混部"),
    ("Mooncake / Dynamo / HiCache（工业界已商用）", "中心化 KV 池",
     "KV 卸载至 CPU RAM / SSD / 远端存储", "本方案以 HBF 替代远端 KV 池，存储层次减一级"),
    ("“HBF Sucks?”（2608.11668）", "GPU + 真实 trace",
     "反方：HBF 直接替换 SSD，端到端延迟恶化 2–5.5×", "其失效三条件（读在关键路径/写多于读/带宽不可持续）即本方案设计约束"),
    ("Hot-Cold Tiering（KAIST · 2609.25782）", "agentic serving",
     "HBM 热缓存 + HBF 冷容量，每 GPU 并发会话 24×", "本方案 decode KV 冷热二级缓存的学术对应（FlashOffloading）"),
    ("Lachesis / Write-Aware KV（KAIST · 2610.08378 等）", "KV 寿命管理",
     "生命周期感知放置；低复用 KV 不写 HBF，寿命延长 1.19–3.13×", "直接支撑本方案写预算与前缀缓存均衡策略"),
    ("本方案（Ascend 950-HBF）", "中心推理集群",
     "HBF 原生：8 卡自洽单元、PD 融合调度、EPLB 均衡、跨模型零开销切换", "公开文献中尚无同场景的系统工作"),
]

grid = "".join(f'<a:gridCol w="{w*E}"/>' for w in COLS)
trs = f'<a:tr h="{HDR_H*E}">' + "".join(cell(t, 0) for t in ROWS[0]) + '</a:tr>'
for i, row in enumerate(ROWS[1:], 1):
    kind = 2 if i == len(ROWS) - 1 else 1
    trs += f'<a:tr h="{ROW_H*E}">' + "".join(cell(t, kind) for t in row) + '</a:tr>'
total_h = HDR_H + ROW_H * (len(ROWS) - 1)

tbl = (f'<p:graphicFrame><p:nvGraphicFramePr><p:cNvPr id="600" name="rw-table"/>'
       f'<p:cNvGraphicFramePr><a:graphicFrameLocks noGrp="1"/></p:cNvGraphicFramePr><p:nvPr/></p:nvGraphicFramePr>'
       f'<p:xfrm><a:off x="{X*E}" y="{Y*E}"/><a:ext cx="{sum(COLS)*E}" cy="{total_h*E}"/></p:xfrm>'
       f'<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/table">'
       f'<a:tbl><a:tblPr firstRow="1"/><a:tblGrid>{grid}</a:tblGrid>{trs}</a:tbl>'
       f'</a:graphicData></a:graphic></p:graphicFrame>')

# ---- 3) 来源脚注（小字 textbox） ----
def note_rpr():
    return ('<a:rPr lang="zh-CN" sz="700" noProof="1"><a:solidFill><a:srgbClr val="999999"/></a:solidFill>'
            '<a:latin typeface="微软雅黑" panose="020B0503020204020204" charset="-122"/>'
            '<a:ea typeface="微软雅黑" panose="020B0503020204020204" charset="-122"/></a:rPr>')
NOTE = ("注：论文均以 arXiv 编号标注；产业动态——SanDisk×SK hynix 主导 HBF 标准（OCP workstream 2026.02 成立，FMS 2026 发布 spec 0.7，单 stack 最高 512GB），"
        "Google / Tenstorrent / Meta 已入局。来源：所附调研记录（2026.11 核实）+ arXiv 检索补新（FLINT 2608.25062、HBFlex 2609.18675、HBFSim 2609.09800）。")
note = (f'<p:sp><p:nvSpPr><p:cNvPr id="601" name="footnote"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>'
        f'<p:spPr><a:xfrm><a:off x="{48*E}" y="{482*E}"/><a:ext cx="{864*E}" cy="{30*E}"/></a:xfrm>'
        f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/><a:ln><a:noFill/></a:ln></p:spPr>'
        f'<p:txBody><a:bodyPr wrap="square"/><a:lstStyle/><a:p><a:r>{note_rpr()}<a:t>{NOTE}</a:t></a:r></a:p></p:txBody></p:sp>')

assert s6.count("</p:spTree>") == 1
s6 = s6.replace("</p:spTree>", tbl + note + "</p:spTree>")

# ---- 4) 注册 slide6 ----
ct = zin.read("[Content_Types].xml").decode("utf-8")
assert "slides/slide6.xml" not in ct
ct = ct.replace("</Types>",
    '<Override PartName="/ppt/slides/slide6.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/></Types>')

prels = zin.read("ppt/_rels/presentation.xml.rels").decode("utf-8")
ids = [int(m) for m in re.findall(r'Id="rId(\d+)"', prels)]
new_rid = max(ids) + 1
prels = prels.replace("</Relationships>",
    f'<Relationship Id="rId{new_rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide6.xml"/></Relationships>')

pres = zin.read("ppt/presentation.xml").decode("utf-8")
sldids = [int(m) for m in re.findall(r'<p:sldId id="(\d+)"', pres)]
new_sid = max(sldids) + 1
pres = pres.replace("</p:sldIdLst>", f'<p:sldId id="{new_sid}" r:id="rId{new_rid}"/></p:sldIdLst>')

s6rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\r\n'
          '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
          '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>'
          '</Relationships>')

with zipfile.ZipFile(TMP, "w") as zout:
    for info in zin.infolist():
        data = zin.read(info.filename)
        if info.filename == "[Content_Types].xml": data = ct.encode("utf-8")
        elif info.filename == "ppt/_rels/presentation.xml.rels": data = prels.encode("utf-8")
        elif info.filename == "ppt/presentation.xml": data = pres.encode("utf-8")
        ni = zipfile.ZipInfo(info.filename, date_time=info.date_time)
        ni.compress_type = info.compress_type
        ni.external_attr = info.external_attr
        zout.writestr(ni, data)
    zout.writestr("ppt/slides/slide6.xml", s6.encode("utf-8"))
    zout.writestr("ppt/slides/_rels/slide6.xml.rels", s6rels.encode("utf-8"))
zin.close()
shutil.move(TMP, PPTX)
print("slide6 added, rid=rId%d sid=%d" % (new_rid, new_sid))
