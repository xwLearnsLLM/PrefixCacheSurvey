# -*- coding: utf-8 -*-
"""P4 图表重建 v3（修正 bug：每卡 evals = q*B*topk，不除 G；EP 计算时间 = 组内最大负载卡）。
校准：T(B,G,s) = T_base(B) - moe_GLM32(B) + moe_K31(B,G,s)  [无 EPLB]"""
import zipfile, io, shutil
import numpy as np
import openpyxl

PPTX = r"D:\HBF\hbf-inference\hbf-inference.pptx"
TMP  = r"D:\HBF\hbf-inference\tmp_chart.pptx"

MEAS_B   = [1,4,8,12,16,20,24,28,32,36,40,44,48]
MEAS_ITL = [40.6,44.5,53.2,59.1,66.7,73.1,83.2,88.6,97.9,107.9,115.2,122.2,138.9]
EXTRAP_SLOPE = (138.9-97.9)/(48-32)
def t_base(B):
    return float(np.interp(B, MEAS_B, MEAS_ITL)) if B <= 48 else 138.9 + EXTRAP_SLOPE*(B-48)

rng = np.random.default_rng(7)
BW = 3.2e12; TFLOPS = 486e12*0.4
def zipf(n,s):
    r=np.arange(1,n+1); p=1.0/r**s; return p/p.sum()
_CACHE={}
def mc_load(group_evals,G,N,s,trials=200):
    key=(int(group_evals),G,N,s)
    if key in _CACHE: return _CACHE[key]
    cnt=rng.multinomial(int(round(group_evals)),zipf(N,s),size=trials)
    g=cnt.reshape(trials,G,N//G).sum(axis=2)
    L=float((g.max(1)/g.mean(1)).mean())
    _CACHE[key]=L; return L

# GLM-5.2 EP32 校准项：每卡平均 evals = 4B*8=32B（组内总 32B*32）
GLM_TW, GLM_TC = 18.9e6/BW, 75.5e6/TFLOPS
def moe_glm32(B):
    L = mc_load(32*B*32, 32, 256, 0.25)
    return 75*max(8*GLM_TW, L*32*B*GLM_TC)*1e3

# K3.1 Pro：每卡平均 evals = 4B*16=64B（组内总 64B*G）
K_TW, K_TC = 16.5e6/BW, 66e6/TFLOPS
def moe_k31(B,G,s):
    L = mc_load(64*B*G, G, 896, s)
    return 92*max((896//G)*K_TW, L*64*B*K_TC)*1e3

Bs = [4,8,12,16,24,32,40,48,64,96,128,192,256]
def curve(G,s):
    xs, ys = [], []
    for B in Bs:
        T = t_base(B) - moe_glm32(B) + moe_k31(B,G,s)
        xs.append(round(3000/T,1)); ys.append(round(B*3000/T))
    return xs, ys

# 交叉点
print("== 交叉点 B*（EP8 吞吐 > EP64 的最小 B）==")
for s in (0.0,0.25,0.5):
    cross=None
    for B in range(1,257):
        t8 = t_base(B)-moe_glm32(B)+moe_k31(B,8,s)
        t64= t_base(B)-moe_glm32(B)+moe_k31(B,64,s)
        if t8<t64: cross=B; break
    print(f"s={s}: B*={cross}")

S = []
for name, color, G, s in [
    ("EP64 · s=0",    "1F3A5F", 64, 0.0),
    ("EP64 · s=0.25", "4A6B8A", 64, 0.25),
    ("EP64 · s=0.5",  "9BB8D3", 64, 0.5),
    ("EP8 · s=0",     "8C3A0F", 8, 0.0),
    ("EP8 · s=0.25",  "D95E27", 8, 0.25),
    ("EP8 · s=0.5",   "F2A65A", 8, 0.5),
]:
    xs, ys = curve(G,s)
    S.append((name, color, xs, ys))
    print(name, " ".join(f"({x},{y})" for x,y in zip(xs,ys)))

mx = [round(3000/t,1) for t in MEAS_ITL]
my = [round(B*3000/t) for B,t in zip(MEAS_B, MEAS_ITL)]

# ---- chart XML ----
def numcache(vals):
    pts = "".join(f'<c:pt idx="{i}"><c:v>{v}</c:v></c:pt>' for i,v in enumerate(vals))
    return f'<c:ptCount val="{len(vals)}"/>{pts}'
COLS = "ABCDEFGHIJKLMN"
def dlbl(idx, text, color):
    return (f'<c:dLbl><c:idx val="{idx}"/><c:delete val="0"/>'
            f'<c:tx><c:rich><a:bodyPr/><a:lstStyle/><a:p><a:pPr>'
            f'<a:defRPr lang="zh-CN" sz="700" noProof="1"/></a:pPr>'
            f'<a:r><a:rPr lang="zh-CN" sz="700" noProof="1">'
            f'<a:solidFill><a:srgbClr val="{color}"/></a:solidFill>'
            f'<a:latin typeface="微软雅黑" panose="020B0503020204020204" charset="-122"/>'
            f'<a:ea typeface="微软雅黑" panose="020B0503020204020204" charset="-122"/></a:rPr>'
            f'<a:t>{text}</a:t></a:r></a:p></c:rich></c:tx>'
            f'<c:dLblPos val="t"/><c:showLegendKey val="0"/><c:showVal val="1"/>'
            f'<c:showCatName val="0"/><c:showSerName val="0"/><c:showPercent val="0"/>'
            f'<c:showBubbleSize val="0"/></c:dLbl>')
def dlbls(labels, color):
    items = "".join(dlbl(i,t,color) for i,t in labels)
    return (f'<c:dLbls>{items}<c:showLegendKey val="0"/><c:showVal val="0"/>'
            f'<c:showCatName val="0"/><c:showSerName val="0"/><c:showPercent val="0"/>'
            f'<c:showBubbleSize val="0"/></c:dLbls>')
def ser(i, name, color, xs, ys, measured=False, labels=()):
    xc, yc = COLS[2*i], COLS[2*i+1]; n = len(xs)
    if measured:
        style = ('<c:spPr><a:ln w="19050" cap="rnd"><a:solidFill><a:srgbClr val="222222"/></a:solidFill>'
                 '<a:prstDash val="dash"/></a:ln></c:spPr>'
                 '<c:marker><c:symbol val="square"/><c:size val="7"/><c:spPr>'
                 '<a:solidFill><a:srgbClr val="222222"/></a:solidFill>'
                 '<a:ln w="12700"><a:solidFill><a:srgbClr val="222222"/></a:solidFill></a:ln></c:spPr></c:marker>')
    else:
        style = (f'<c:spPr><a:ln w="25400" cap="rnd"><a:solidFill><a:srgbClr val="{color}"/></a:solidFill>'
                 f'<a:prstDash val="solid"/><a:round/></a:ln></c:spPr>'
                 f'<c:marker><c:symbol val="circle"/><c:size val="6"/><c:spPr>'
                 f'<a:solidFill><a:srgbClr val="{color}"/></a:solidFill>'
                 f'<a:ln w="12700"><a:solidFill><a:srgbClr val="{color}"/></a:solidFill></a:ln>'
                 f'</c:spPr></c:marker>')
    return (f'<c:ser><c:idx val="{i}"/><c:order val="{i}"/>'
            f'<c:tx><c:strRef><c:f>Sheet1!${yc}$1</c:f><c:strCache><c:ptCount val="1"/>'
            f'<c:pt idx="0"><c:v>{name}</c:v></c:pt></c:strCache></c:strRef></c:tx>'
            f'{style}{dlbls(labels, color)}'
            f'<c:xVal><c:numRef><c:f>Sheet1!${xc}$2:${xc}${n+1}</c:f><c:numCache>'
            f'<c:formatCode>General</c:formatCode>{numcache(xs)}</c:numCache></c:numRef></c:xVal>'
            f'<c:yVal><c:numRef><c:f>Sheet1!${yc}$2:${yc}${n+1}</c:f><c:numCache>'
            f'<c:formatCode>General</c:formatCode>{numcache(ys)}</c:numCache></c:numRef></c:yVal>'
            f'<c:smooth val="0"/></c:ser>')
def axis_txpr(rot):
    return (f'<c:txPr><a:bodyPr rot="{rot}" spcFirstLastPara="0" vertOverflow="ellipsis" vert="horz" '
            f'wrap="square" anchor="ctr" anchorCtr="1"/><a:lstStyle/><a:p><a:pPr>'
            f'<a:defRPr lang="zh-CN" sz="800" b="0" i="0" u="none" strike="noStrike" kern="1200" baseline="0" noProof="1">'
            f'<a:solidFill><a:schemeClr val="tx1"/></a:solidFill>'
            f'<a:latin typeface="微软雅黑" panose="020B0503020204020204" charset="-122"/>'
            f'<a:ea typeface="+mn-ea"/><a:cs typeface="+mn-cs"/></a:defRPr></a:pPr></a:p></c:txPr>')
def axis_title(text, rot, lx, ly):
    return (f'<c:title><c:tx><c:rich><a:bodyPr rot="{rot}" spcFirstLastPara="0" vertOverflow="ellipsis" '
            f'vert="horz" wrap="square" anchor="ctr" anchorCtr="1"/><a:lstStyle/><a:p><a:pPr>'
            f'<a:defRPr lang="zh-CN" sz="1000" noProof="1"><a:solidFill><a:schemeClr val="tx1"/></a:solidFill>'
            f'<a:latin typeface="微软雅黑" panose="020B0503020204020204" charset="-122"/>'
            f'<a:ea typeface="+mn-ea"/><a:cs typeface="+mn-cs"/></a:defRPr></a:pPr>'
            f'<a:r><a:rPr lang="zh-CN" sz="800" noProof="1"/><a:t>{text}</a:t></a:r></a:p></c:rich></c:tx>'
            f'<c:layout><c:manualLayout><c:xMode val="edge"/><c:yMode val="edge"/>'
            f'<c:x val="{lx}"/><c:y val="{ly}"/></c:manualLayout></c:layout><c:overlay val="0"/></c:title>')
def gridlines():
    return ('<c:majorGridlines><c:spPr><a:ln w="12700" cap="flat"><a:solidFill>'
            '<a:srgbClr val="EDF0F3"/></a:solidFill><a:prstDash val="solid"/><a:round/></a:ln></c:spPr></c:majorGridlines>')
def axline():
    return ('<c:spPr><a:ln w="12700" cap="flat"><a:solidFill><a:srgbClr val="888888"/></a:solidFill>'
            '<a:prstDash val="solid"/><a:round/></a:ln></c:spPr>')
x_ax = (f'<c:valAx><c:axId val="1"/><c:scaling><c:orientation val="minMax"/>'
        f'<c:max val="80"/><c:min val="0"/></c:scaling><c:delete val="0"/><c:axPos val="b"/>'
        f'{gridlines()}{axis_title("每请求输出吞吐（tokens/s）", "0", "0.42", "0.88")}'
        f'<c:numFmt formatCode="General" sourceLinked="1"/><c:majorTickMark val="out"/>'
        f'<c:minorTickMark val="none"/><c:tickLblPos val="nextTo"/>{axline()}{axis_txpr("-60000000")}'
        f'<c:crossAx val="2"/><c:crosses val="autoZero"/><c:crossBetween val="between"/>'
        f'<c:majorUnit val="20"/></c:valAx>')
y_ax = (f'<c:valAx><c:axId val="2"/><c:scaling><c:orientation val="minMax"/>'
        f'<c:max val="1400"/><c:min val="0"/></c:scaling><c:delete val="0"/><c:axPos val="l"/>'
        f'{gridlines()}{axis_title("每 NPU 输出吞吐（tokens/s）", "-5400000", "0.02", "0.40")}'
        f'<c:numFmt formatCode="#,##0" sourceLinked="0"/><c:majorTickMark val="out"/>'
        f'<c:minorTickMark val="none"/><c:tickLblPos val="nextTo"/>{axline()}{axis_txpr("-60000000")}'
        f'<c:crossAx val="1"/><c:crosses val="autoZero"/><c:crossBetween val="between"/>'
        f'<c:majorUnit val="200"/></c:valAx>')

allsers = S + [("EP32 实测 · GLM-5.2（校准锚点）", "222222", mx, my)]
MODEL_LBL = [(0,"4"),(4,"24"),(7,"48"),(10,"128"),(12,"256")]
MEAS_LBL  = [(1,"4"),(4,"16"),(7,"32"),(12,"48")]
sers = "".join(ser(i,n,c,x,y,measured=(i==6),labels=MEAS_LBL if i==6 else MODEL_LBL)
               for i,(n,c,x,y) in enumerate(allsers))
chart = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\r\n'
    '<c:chartSpace xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart" '
    'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
    '<c:date1904 val="0"/><c:lang val="zh-CN"/><c:roundedCorners val="0"/>'
    '<c:chart><c:autoTitleDeleted val="1"/><c:plotArea><c:layout/>'
    f'<c:scatterChart><c:scatterStyle val="lineMarker"/><c:varyColors val="0"/>{sers}'
    '<c:axId val="1"/><c:axId val="2"/></c:scatterChart>'
    f'{x_ax}{y_ax}'
    '<c:spPr><a:noFill/><a:ln><a:noFill/></a:ln></c:spPr></c:plotArea>'
    '<c:legend><c:legendPos val="b"/><c:layout/><c:overlay val="0"/>'
    '<c:txPr><a:bodyPr/><a:lstStyle/><a:p><a:pPr>'
    '<a:defRPr lang="zh-CN" sz="800" noProof="1"><a:solidFill><a:schemeClr val="tx1"/></a:solidFill>'
    '<a:latin typeface="微软雅黑" panose="020B0503020204020204" charset="-122"/>'
    '<a:ea typeface="+mn-ea"/><a:cs typeface="+mn-cs"/></a:defRPr></a:pPr></a:p></c:txPr></c:legend>'
    '<c:plotVisOnly val="1"/><c:dispBlanksAs val="gap"/></c:chart>'
    '<c:spPr><a:noFill/><a:ln><a:noFill/></a:ln></c:spPr>'
    '<c:externalData r:id="rId1"><c:autoUpdate val="0"/></c:externalData></c:chartSpace>'
)
import xml.dom.minidom; xml.dom.minidom.parseString(chart)

zin = zipfile.ZipFile(PPTX)
wb = openpyxl.load_workbook(io.BytesIO(zin.read("ppt/embeddings/Workbook1.xlsx")))
ws = wb["Sheet1"]
for row in ws.iter_rows(min_row=1, max_row=max(ws.max_row,14), max_col=max(ws.max_column,14)):
    for c in row: c.value = None
for i,(name,_,xs,ys) in enumerate(allsers):
    xc, yc = COLS[2*i], COLS[2*i+1]
    ws[f"{xc}1"]="x"; ws[f"{yc}1"]=name
    for j,(x,y) in enumerate(zip(xs,ys)):
        ws[f"{xc}{j+2}"]=x; ws[f"{yc}{j+2}"]=y
buf=io.BytesIO(); wb.save(buf); xlsx_bytes=buf.getvalue()

with zipfile.ZipFile(TMP,"w") as zout:
    for info in zin.infolist():
        if info.filename=="ppt/charts/chart1.xml": data=chart.encode("utf-8")
        elif info.filename=="ppt/embeddings/Workbook1.xlsx": data=xlsx_bytes
        else: data=zin.read(info.filename)
        ni=zipfile.ZipInfo(info.filename, date_time=info.date_time)
        ni.compress_type=info.compress_type; ni.external_attr=info.external_attr
        zout.writestr(ni, data)
zin.close(); shutil.move(TMP, PPTX)
print("chart v3 written")
