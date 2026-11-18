# -*- coding: utf-8 -*-
"""新增「软件架构：KV 管理与 PD 调度」页：克隆 slide5 框架，插入 sldIdLst 第 4 位（show order 第 4 页），
四个象限：01 KV cache 管理 / 02 集群划分 / 03 prefill 调度器 / 04 请求生命周期。"""
import zipfile, re, shutil

PPTX = r"D:\HBF\hbf-inference\hbf-inference.pptx"
TMP  = r"D:\HBF\hbf-inference\tmp_p7.pptx"
E = 12700

zin = zipfile.ZipFile(PPTX)
s5 = zin.read("ppt/slides/slide5.xml").decode("utf-8")

REMOVE = {"t1-num","t1-title","t1-body","t1-sep","t2-num","t2-title","t2-body",
          "d1-label","d1-req","d1-req-t","d1-arrow1","d1-query","d1-query-t",
          "d1-arrow2","d1-arrow3","d1-hit","d1-hit-t","d1-mig","d1-mig-t",
          "d2-label","d2-kv","d2-kv-t","d2-arrow1","d2-pred","d2-pred-t","d2-out","sum-text"}
def drop(m):
    return "" if re.search(r'name="([^"]*)"', m.group(0)).group(1) in REMOVE else m.group(0)
s7, _ = re.subn(r'<p:sp>.*?</p:sp>', drop, s5, flags=re.S)

# 标题 / 副标题 / 页码（单 run 直接换文本）
s7 = s7.replace("<a:t>待构建的关键技术</a:t>", "<a:t>软件架构：KV 管理与 PD 调度</a:t>")
s7 = s7.replace("<a:t>两项引擎级技术，是把硬件成本优势转化为可持续吞吐收益的前提</a:t>",
                "<a:t>前缀 KV 两级缓存（HBF→ASU）· 纯P/PD 混合集群 · 命中率感知调度 · 请求全生命周期</a:t>")
assert s7.count("05 / 06") == 1
s7 = s7.replace("05 / 06", "04 / 07")

FONT = '<a:latin typeface="微软雅黑" panose="020B0503020204020204" charset="-122"/><a:ea typeface="微软雅黑" panose="020B0503020204020204" charset="-122"/>'
def sp_num(sid, x, y, txt):
    return (f'<p:sp><p:nvSpPr><p:cNvPr id="{sid}" name="b{sid}-num"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>'
            f'<p:spPr><a:xfrm><a:off x="{x*E}" y="{y*E}"/><a:ext cx="{40*E}" cy="{22*E}"/></a:xfrm>'
            f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/><a:ln><a:noFill/></a:ln></p:spPr>'
            f'<p:txBody><a:bodyPr wrap="none" lIns="0" tIns="0" rIns="0" bIns="0" rtlCol="0"/><a:lstStyle/>'
            f'<a:p><a:pPr><a:lnSpc><a:spcPct val="120000"/></a:lnSpc></a:pPr>'
            f'<a:r><a:rPr lang="zh-CN" sz="1600" b="1" noProof="1"><a:solidFill><a:srgbClr val="D95E27"/></a:solidFill>{FONT}</a:rPr>'
            f'<a:t>{txt}</a:t></a:r></a:p></p:txBody></p:sp>')
def sp_title(sid, x, y, txt):
    return (f'<p:sp><p:nvSpPr><p:cNvPr id="{sid}" name="b{sid}-title"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>'
            f'<p:spPr><a:xfrm><a:off x="{(x+40)*E}" y="{(y+2)*E}"/><a:ext cx="{380*E}" cy="{18*E}"/></a:xfrm>'
            f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/><a:ln><a:noFill/></a:ln></p:spPr>'
            f'<p:txBody><a:bodyPr wrap="none" lIns="0" tIns="0" rIns="0" bIns="0" rtlCol="0"/><a:lstStyle/>'
            f'<a:p><a:pPr><a:lnSpc><a:spcPct val="120000"/></a:lnSpc></a:pPr>'
            f'<a:r><a:rPr lang="zh-CN" sz="1300" b="1" noProof="1"><a:solidFill><a:srgbClr val="1F3A5F"/></a:solidFill>{FONT}</a:rPr>'
            f'<a:t>{txt}</a:t></a:r></a:p></p:txBody></p:sp>')
def sp_body(sid, x, y, bullets):
    paras = "".join(
        f'<a:p><a:pPr algn="l"><a:lnSpc><a:spcPct val="138000"/></a:lnSpc></a:pPr>'
        f'<a:r><a:rPr lang="zh-CN" sz="800" noProof="1"><a:solidFill><a:srgbClr val="24292F"/></a:solidFill>{FONT}</a:rPr>'
        f'<a:t>· {t}</a:t></a:r></a:p>' for t in bullets)
    return (f'<p:sp><p:nvSpPr><p:cNvPr id="{sid}" name="b{sid}-body"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>'
            f'<p:spPr><a:xfrm><a:off x="{(x+40)*E}" y="{(y+28)*E}"/><a:ext cx="{420*E}" cy="{150*E}"/></a:xfrm>'
            f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/><a:ln><a:noFill/></a:ln></p:spPr>'
            f'<p:txBody><a:bodyPr wrap="square" lIns="0" tIns="0" rIns="0" bIns="0" rtlCol="0" anchor="t"/><a:lstStyle/>'
            f'{paras}</p:txBody></p:sp>')
def sp_sum(sid, x, y, txt):
    return (f'<p:sp><p:nvSpPr><p:cNvPr id="{sid}" name="sum-text"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>'
            f'<p:spPr><a:xfrm><a:off x="{x*E}" y="{y*E}"/><a:ext cx="{864*E}" cy="{40*E}"/></a:xfrm>'
            f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/><a:ln><a:noFill/></a:ln></p:spPr>'
            f'<p:txBody><a:bodyPr wrap="square" lIns="0" tIns="0" rIns="0" bIns="0" rtlCol="0" anchor="t"/><a:lstStyle/>'
            f'<a:p><a:pPr algn="l"><a:lnSpc><a:spcPct val="150000"/></a:lnSpc></a:pPr>'
            f'<a:r><a:rPr lang="zh-CN" sz="900" b="1" noProof="1"><a:solidFill><a:srgbClr val="1F3A5F"/></a:solidFill>{FONT}</a:rPr>'
            f'<a:t>{txt}</a:t></a:r></a:p></p:txBody></p:sp>')

BLOCKS = [
    (701, 48, 92, "01", "前缀 KV cache 管理", [
        "两级：全局集中式 ASU + 每卡 HBF；新 KV block 先落 HBF",
        "HBF 满时按 LRU 淘汰到 ASU",
        "淘汰约束：每个请求始终前序 blocks 命中 ASU、后续 blocks 命中 HBF，保证滚动顺序加载",
    ]),
    (702, 492, 92, "02", "集群划分（以 4 节点为例）", [
        "1 个纯 P 节点 + 3 个 PD 混合节点（节点 = 8 NPU 单元）",
        "PD 混合节点平时持续 batch decode",
        "新 prefill 请求到达且 P 节点负载重时，抢占 PD 节点做 prefill",
    ]),
    (703, 48, 272, "03", "Prefill 调度器（打分函数综合权衡）", [
        "负载优先：优先纯 P 节点、排队最短者；P 负载重则抢占 PD 节点",
        "命中率优先：倾向分配到本地 HBF 命中长度最长的节点",
        "命中率 ≈95%+ 的请求 prefill 近似 decode → 放 PD 节点，算完就地 decode（多轮对话常见）",
        "效果：纯 P 节点自然沉淀长序列、低命中的长尾 prefill",
    ]),
    (704, 492, 272, "04", "请求生命周期", [
        "路径二选一：全程 PD 混合节点 / 纯 P prefill → PD 混合 decode",
        "prefill 前：若他节点 HBF 命中率更高，先把其 HBF KV 写入 ASU",
        "prefill 时：从 ASU / HBF 滚动加载 KV、边加载边算",
        "prefill 后：纯 P → 边算边滚动卸载到 ASU；PD → 落 HBF 就地 decode",
        "decode 前：index cache 拉入 HHM-DRAM（不可稀疏，必须全量）",
        "decode 时：HHM-DRAM 热缓存 buffer 动态冷热换入",
    ]),
]
shapes = ""
for sid, x, y, num, title, bullets in BLOCKS:
    shapes += sp_num(sid, x, y, num) + sp_title(sid+10, x, y, title) + sp_body(sid+20, x, y, bullets)
shapes += sp_sum(750, 48, 460,
    "调度打分函数统一平衡负载与命中率：纯 P 节点沉淀长尾 prefill，PD 混合节点承载主流流量、就地 decode 免 KV 传输。")

assert s7.count("</p:spTree>") == 1
s7 = s7.replace("</p:spTree>", shapes + "</p:spTree>")

# ---- 注册 slide7，插入 sldIdLst 第 4 位 ----
ct = zin.read("[Content_Types].xml").decode("utf-8")
assert "slides/slide7.xml" not in ct
ct = ct.replace("</Types>",
    '<Override PartName="/ppt/slides/slide7.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/></Types>')

prels = zin.read("ppt/_rels/presentation.xml.rels").decode("utf-8")
new_rid = max(int(m) for m in re.findall(r'Id="rId(\d+)"', prels)) + 1
prels = prels.replace("</Relationships>",
    f'<Relationship Id="rId{new_rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide7.xml"/></Relationships>')

pres = zin.read("ppt/presentation.xml").decode("utf-8")
new_sid = max(int(m) for m in re.findall(r'<p:sldId id="(\d+)"', pres)) + 1
ids = re.findall(r'<p:sldId [^/]*/>', pres)
assert len(ids) == 6
pres = pres.replace(ids[2], ids[2] + f'<p:sldId id="{new_sid}" r:id="rId{new_rid}"/>')

s7rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\r\n'
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
    zout.writestr("ppt/slides/slide7.xml", s7.encode("utf-8"))
    zout.writestr("ppt/slides/_rels/slide7.xml.rels", s7rels.encode("utf-8"))
zin.close()
shutil.move(TMP, PPTX)
print("slide7 inserted at show position 4")
