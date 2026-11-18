# -*- coding: utf-8 -*-
"""P4 图表重建 v2：用 EP32 GLM-5.2 实测（950DT）校准非 MoE 开销，再叠加 K3.1 Pro MoE roofline。
T(B,G,s) = T_base(B) - moe_GLM32(B) + moe_K31(B,G,s)
T_base: 实测 ITL 分段线性插值；bs>48 按 2.6ms/B（bs32->48 均值）外推。
7 条曲线：EP8/EP64 x s={0,0.25,0.5}（无 EPLB） + 实测锚点。"""
import zipfile, io, shutil
import numpy as np
import openpyxl

PPTX = r"D:\HBF\hbf-inference\hbf-inference.pptx"
TMP  = r"D:\HBF\hbf-inference\tmp_chart.pptx"

# ---- 实测锚点 ----
MEAS_B   = [1,4,8,12,16,20,24,28,32,36,40,44,48]
MEAS_ITL = [40.6,44.5,53.2,59.1,66.7,73.1,83.2,88.6,97.9,107.9,115.2,122.2,138.9]
EXTRAP_SLOPE = (138.9-97.9)/(48-32)  # 2.5625 ms/B

def t_base(B):
    if B <= 48:
        return float(np.interp(B, MEAS_B, MEAS_ITL))
    return 138.9 + EXTRAP_SLOPE*(B-48)

# ---- MoE roofline ----
rng = np.random.default_rng(7)
BW = 3.2e12; TFLOPS = 486e12*0.4
def zipf(n,s):
    r=np.arange(1,n+1); p=1.0/r**s; return p/p.sum()
def mc_load(evals,G,N,s,trials=200):
    if evals<=0: return 1.0
    cnt=rng.multinomial(int(round(evals)),zipf(N,s),size=trials)
    g=cnt.reshape(trials,G,N//G).sum(axis=2)
    return float((g.max(1)/g.mean(1)).mean())

# GLM-5.2: 75 MoE 层, 256 experts, top8, q4, expert 18.9MB / 75.5MFLOP
GLM_LAYERS, GLM_N, GLM_TOPK = 75, 256, 8
GLM_TW, GLM_TC = 18.9e6/BW, 75.5e6/TFLOPS
def moe_glm32(B):
    L = mc_load(4*B*GLM_TOPK/32, 32, GLM_N, 0.25)
    return GLM_LAYERS*max(8*GLM_TW, L*(4*B*GLM_TOPK/32)*GLM_TC)*1e3

# K3.1 Pro: 92 MoE 层, 896 experts, top16, q4, expert 16.5MB / 66MFLOP
K_LAYERS, K_N, K_TOPK = 92, 896, 16
K_TW, K_TC = 16.5e6/BW, 66e6/TFLOPS
def moe_k31(B,G,s):
    L = mc_load(4*B*K_TOPK/G, G, K_N, s)
    return K_LAYERS*max((K_N//G)*K_TW, L*(4*B*K_TOPK/G)*K_TC)*1e3

Bs = [4,8,12,16,24,32,40,48,64,96,128,192,256]
def curve(G,s):
    xs, ys = [], []
    for B in Bs:
        T = t_base(B) - moe_glm32(B) + moe_k31(B,G,s)
        xs.append(round(3000/T,1)); ys.append(round(B*3000/T))
    return xs, ys

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
print("实测EP32:", " ".join(f"({x},{y})" for x,y in zip(mx,my)))

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
    items = "".join(dlbl(i, t, color) for i, t in labels)
    return (f'<c:dLbls>{items}<c:showLegendKey val="0"/><c:showVal val="0"/>'
            f'<c:showCatName val="0"/><c:showSerName val="0"/><c:showPercent val="0"/>'
            f'<c:showBubbleSize val="0"/></c:dLbls>')

def ser(i, name, color, xs, ys, measured=False, labels=()):
    xc, yc = COLS[2*i], COLS[2*i+1]
    n = len(xs)
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
        f'<c:max val="1500"/><c:min val="0"/></c:scaling><c:delete val="0"/><c:axPos val="l"/>'
        f'{gridlines()}{axis_title("每 NPU 输出吞吐（tokens/s）", "-5400000", "0.02", "0.40")}'
        f'<c:numFmt formatCode="#,##0" sourceLinked="0"/><c:majorTickMark val="out"/>'
        f'<c:minorTickMark val="none"/><c:tickLblPos val="nextTo"/>{axline()}{axis_txpr("-60000000")}'
        f'<c:crossAx val="1"/><c:crosses val="autoZero"/><c:crossBetween val="between"/>'
        f'<c:majorUnit val="300"/></c:valAx>')

allsers = S + [("EP32 实测 · GLM-5.2（校准锚点）", "222222", mx, my)]
# 稀疏标注：模型曲线标 bs ∈ {4,24,48,128,256}（idx 0,4,7,10,12）；实测标 {4,16,32,48}（idx 1,4,7,12）
MODEL_LBL = [(0,"4"),(4,"24"),(7,"48"),(10,"128"),(12,"256")]
MEAS_LBL  = [(1,"4"),(4,"16"),(7,"32"),(12,"48")]
sers = "".join(ser(i, n, c, x, y, measured=(i==6),
                   labels=MEAS_LBL if i==6 else MODEL_LBL)
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

# ---- 工作簿 ----
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
print("chart v2 written")
