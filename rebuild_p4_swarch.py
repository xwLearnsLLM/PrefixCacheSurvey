# -*- coding: utf-8 -*-
"""重建 show order 第 4 页（slide7.xml）：软件架构详设 = 左侧部件关系图 + 右侧按部件的行为描述。
框架（标题/副标题/页脚/分隔线）克隆自 slide5；部件注册已在上一轮完成，本轮只重写 slide7.xml。"""
import zipfile, re, shutil

PPTX = r"D:\HBF\hbf-inference\hbf-inference.pptx"
TMP  = r"D:\HBF\hbf-inference\tmp_p7b.pptx"
E = 12700

zin = zipfile.ZipFile(PPTX)
s5 = zin.read("ppt/slides/slide5.xml").decode("utf-8")

REMOVE = {"t1-num","t1-title","t1-body","t1-sep","t2-num","t2-title","t2-body",
          "d1-label","d1-req","d1-req-t","d1-arrow1","d1-query","d1-query-t",
          "d1-arrow2","d1-arrow3","d1-hit","d1-hit-t","d1-mig","d1-mig-t",
          "d2-label","d2-kv","d2-kv-t","d2-arrow1","d2-pred","d2-pred-t","d2-out","sum-text"}
def drop(m):
    return "" if re.search(r'name="([^"]*)"', m.group(0)).group(1) in REMOVE else m.group(0)
s7 = re.sub(r'<p:sp>.*?</p:sp>', drop, s5, flags=re.S)
s7 = s7.replace("<a:t>待构建的关键技术</a:t>", "<a:t>软件架构详设</a:t>")
s7 = s7.replace("<a:t>两项引擎级技术，是把硬件成本优势转化为可持续吞吐收益的前提</a:t>",
                "<a:t>按软件部件组织：调度器 · 节点角色 · KV cache 管理器 · decode 运行时</a:t>")
assert s7.count("06 / 07") == 1
s7 = s7.replace("06 / 07", "04 / 07")

FONT = '<a:latin typeface="微软雅黑" panose="020B0503020204020204" charset="-122"/><a:ea typeface="微软雅黑" panose="020B0503020204020204" charset="-122"/>'

def box(sid, x, y, w, h, lines, fill, ln_color, dark_text=False):
    paras = "".join(
        f'<a:p><a:pPr algn="ctr"><a:lnSpc><a:spcPct val="125000"/></a:lnSpc></a:pPr>'
        f'<a:r><a:rPr lang="zh-CN" sz="{sz}"{" b=\"1\"" if b else ""} noProof="1">'
        f'<a:solidFill><a:srgbClr val="{c}"/></a:solidFill>{FONT}</a:rPr><a:t>{t}</a:t></a:r></a:p>'
        for t, sz, b, c in lines)
    return (f'<p:sp><p:nvSpPr><p:cNvPr id="{sid}" name="dg-box-{sid}"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>'
            f'<p:spPr><a:xfrm><a:off x="{x*E}" y="{y*E}"/><a:ext cx="{w*E}" cy="{h*E}"/></a:xfrm>'
            f'<a:prstGeom prst="roundRect"><a:avLst><a:gd name="adj" fmla="val 12000"/></a:avLst></a:prstGeom>'
            f'<a:solidFill><a:srgbClr val="{fill}"/></a:solidFill>'
            f'<a:ln w="12700"><a:solidFill><a:srgbClr val="{ln_color}"/></a:solidFill></a:ln></p:spPr>'
            f'<p:txBody><a:bodyPr wrap="square" lIns="25400" tIns="12700" rIns="25400" bIns="12700" anchor="ctr"/>'
            f'<a:lstStyle/>{paras}</p:txBody></p:sp>')

def arrow(sid, x, y, w, h, color="8A94A0", dash=None, flipH=False, flipV=False, wgt=12700):
    fh = ' flipH="1"' if flipH else ''
    fv = ' flipV="1"' if flipV else ''
    d = f'<a:prstDash val="{dash}"/>' if dash else '<a:prstDash val="solid"/>'
    return (f'<p:cxnSp><p:nvCxnSpPr><p:cNvPr id="{sid}" name="dg-arr-{sid}"/><p:cNvCxnSpPr/><p:nvPr/></p:nvCxnSpPr>'
            f'<p:spPr><a:xfrm{fh}{fv}><a:off x="{x*E}" y="{y*E}"/><a:ext cx="{w*E}" cy="{h*E}"/></a:xfrm>'
            f'<a:prstGeom prst="straightConnector1"><a:avLst/></a:prstGeom>'
            f'<a:ln w="{wgt}" cap="rnd"><a:solidFill><a:srgbClr val="{color}"/></a:solidFill>{d}'
            f'<a:tailEnd type="triangle" w="med" len="med"/></a:ln></p:spPr></p:cxnSp>')

def label(sid, x, y, w, h, text, sz=700, color="6B7280", bold=False, align="ctr"):
    b = ' b="1"' if bold else ''
    return (f'<p:sp><p:nvSpPr><p:cNvPr id="{sid}" name="dg-lbl-{sid}"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>'
            f'<p:spPr><a:xfrm><a:off x="{x*E}" y="{y*E}"/><a:ext cx="{w*E}" cy="{h*E}"/></a:xfrm>'
            f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/><a:ln><a:noFill/></a:ln></p:spPr>'
            f'<p:txBody><a:bodyPr wrap="square" lIns="0" tIns="0" rIns="0" bIns="0" anchor="ctr"/><a:lstStyle/>'
            f'<a:p><a:pPr algn="{align}"/><a:r><a:rPr lang="zh-CN" sz="{sz}"{b} noProof="1">'
            f'<a:solidFill><a:srgbClr val="{color}"/></a:solidFill>{FONT}</a:rPr><a:t>{text}</a:t></a:r></a:p>'
            f'</p:txBody></p:sp>')

def comp(sid, x, y, w, title, bullets):
    paras = (f'<a:p><a:pPr algn="l"/><a:r><a:rPr lang="zh-CN" sz="900" b="1" noProof="1">'
             f'<a:solidFill><a:srgbClr val="1F3A5F"/></a:solidFill>{FONT}</a:rPr><a:t>{title}</a:t></a:r></a:p>')
    for t in bullets:
        paras += (f'<a:p><a:pPr algn="l"><a:lnSpc><a:spcPct val="132000"/></a:lnSpc></a:pPr>'
                  f'<a:r><a:rPr lang="zh-CN" sz="750" noProof="1"><a:solidFill><a:srgbClr val="24292F"/></a:solidFill>{FONT}</a:rPr>'
                  f'<a:t>· {t}</a:t></a:r></a:p>')
    return (f'<p:sp><p:nvSpPr><p:cNvPr id="{sid}" name="comp-{sid}"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>'
            f'<p:spPr><a:xfrm><a:off x="{x*E}" y="{y*E}"/><a:ext cx="{w*E}" cy="{70*E}"/></a:xfrm>'
            f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/><a:ln><a:noFill/></a:ln></p:spPr>'
            f'<p:txBody><a:bodyPr wrap="square" lIns="0" tIns="0" rIns="0" bIns="0" anchor="t"/><a:lstStyle/>'
            f'{paras}</p:txBody></p:sp>')

def sumline(sid, txt):
    return (f'<p:sp><p:nvSpPr><p:cNvPr id="{sid}" name="sum-text"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>'
            f'<p:spPr><a:xfrm><a:off x="{48*E}" y="{458*E}"/><a:ext cx="{864*E}" cy="{40*E}"/></a:xfrm>'
            f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/><a:ln><a:noFill/></a:ln></p:spPr>'
            f'<p:txBody><a:bodyPr wrap="square" lIns="0" tIns="0" rIns="0" bIns="0" anchor="t"/><a:lstStyle/>'
            f'<a:p><a:pPr algn="l"><a:lnSpc><a:spcPct val="145000"/></a:lnSpc></a:pPr>'
            f'<a:r><a:rPr lang="zh-CN" sz="900" b="1" noProof="1"><a:solidFill><a:srgbClr val="1F3A5F"/></a:solidFill>{FONT}</a:rPr>'
            f'<a:t>{txt}</a:t></a:r></a:p></p:txBody></p:sp>')

S = []
# ---- 左：部件关系图（x 48..508, y 92..440） ----
S.append(box(801, 118, 96, 290, 34, [("Prefill 调度器", 950, True, "FFFFFF"), ("打分：节点负载 × 本地 HBF 命中率", 750, False, "D8E2EE")], "1F3A5F", "1F3A5F"))
S.append(arrow(802, 158, 130, 58, 40, flipH=True))                      # 调度器→纯P
S.append(arrow(803, 330, 130, 62, 40))                                  # 调度器→PD
S.append(box(804, 56, 172, 168, 62, [("纯 P 节点 ×1", 900, True, "1F3A5F"), ("长尾 · 低命中 prefill", 750, False, "4A5568"), ("KV 边算边卸载 → ASU", 750, False, "4A5568")], "EAF1F8", "4A6B8A"))
S.append(box(805, 296, 172, 200, 62, [("PD 混合节点 ×3", 900, True, "1F3A5F"), ("主流 batch decode + 抢占 prefill", 750, False, "4A5568"), ("高命中请求就地 prefill→decode", 750, False, "4A5568")], "EAF1F8", "4A6B8A"))
S.append(arrow(806, 224, 158, 72, 12, color="D95E27", dash="dash", wgt=15875))  # 抢占
S.append(label(807, 196, 144, 128, 12, "P 负载重时抢占", sz=700, color="D95E27", bold=True))
S.append(arrow(808, 140, 234, 1, 26))                                   # P→HBF
S.append(arrow(809, 396, 234, 1, 26))                                   # PD→HBF
S.append(box(810, 56, 262, 168, 30, [("节点内每卡 HBF（新 KV 先落）", 750, False, "24292F")], "F2F5F8", "C9D2DC"))
S.append(box(811, 296, 262, 200, 30, [("节点内每卡 HBF（新 KV 先落）", 750, False, "24292F")], "F2F5F8", "C9D2DC"))
S.append(arrow(812, 140, 292, 1, 36))                                   # HBF→ASU
S.append(arrow(813, 340, 292, 1, 36))                                   # HBF→ASU
S.append(label(814, 156, 302, 180, 12, "LRU 淘汰（前序→ASU / 后续→HBF）", sz=700, align="l"))
S.append(arrow(815, 444, 234, 1, 94, color="4A6B8A", flipV=True, wgt=15875))  # ASU→PD 拉取
S.append(label(816, 452, 276, 56, 40, "decode 前拉取 KV / index cache", sz=700, color="4A6B8A", align="l"))
S.append(box(817, 56, 330, 440, 36, [("全局集中式 ASU：KV 冷层 / 前缀缓存池", 850, True, "FFFFFF")], "4A6B8A", "4A6B8A"))
S.append(label(818, 56, 384, 440, 40, "请求路径：全程 PD 混合节点，或 纯 P prefill → PD 混合 decode；"
              "prefill 前若他节点命中率更高，先将其 HBF KV 汇入 ASU", sz=700, align="l"))

# ---- 右：按部件的行为描述（x 520..912） ----
S.append(comp(830, 520, 92, 392, "① KV Cache 管理器（HBF ↔ ASU）", [
    "新 KV block 先落 HBF；HBF 满时按 LRU 淘汰到 ASU",
    "淘汰约束：每个请求前序 blocks 命中 ASU、后续命中 HBF",
]))
S.append(comp(831, 520, 158, 392, "② Prefill 调度器", [
    "负载优先：纯 P 优先、排队最短；P 负载重则抢占 PD 节点",
    "命中率优先：分往本地 HBF 命中长度最长的节点",
    "两原则可能矛盾 → 打分函数综合判断",
]))
S.append(comp(832, 520, 238, 392, "③ 纯 P 节点", [
    "沉淀长序列、低命中率的长尾 prefill（出现概率低）",
    "prefill 同时滚动卸载 KV 到 ASU，供 decode 节点拉取",
]))
S.append(comp(833, 520, 304, 392, "④ PD 混合节点", [
    "平时持续 batch decode；被抢占时插入 prefill step",
    "命中率 ≈95%+ 的请求 prefill 近似 decode → 就地 prefill→decode（多轮对话常见）",
]))
S.append(comp(834, 520, 378, 392, "⑤ Decode 运行时（HHM-DRAM）", [
    "decode 前：index cache 全量拉入 HHM-DRAM（不可稀疏，必须）",
    "decode 时：热缓存 buffer 动态冷热换入",
]))
S.append(sumline(850, "要点：调度打分统一平衡负载与命中率——纯 P 沉淀长尾 prefill，PD 承载主流流量并就地 decode，跨节点 KV 传输只走 ASU 一级。"))

assert s7.count("</p:spTree>") == 1
s7 = s7.replace("</p:spTree>", "".join(S) + "</p:spTree>")
import xml.dom.minidom; xml.dom.minidom.parseString(s7)

with zipfile.ZipFile(TMP, "w") as zout:
    for info in zin.infolist():
        data = s7.encode("utf-8") if info.filename == "ppt/slides/slide7.xml" else zin.read(info.filename)
        ni = zipfile.ZipInfo(info.filename, date_time=info.date_time)
        ni.compress_type = info.compress_type
        ni.external_attr = info.external_attr
        zout.writestr(ni, data)
zin.close()
shutil.move(TMP, PPTX)
print("slide7 rebuilt: 软件架构详设")
