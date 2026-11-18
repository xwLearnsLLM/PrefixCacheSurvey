# -*- coding: utf-8 -*-
"""P4 图表重建：scatterChart（DeepInfer 风格），6 条曲线 = EP8/EP64 × s∈{0,0.25,0.5}，无 EPLB。
X=每请求输出吞吐(tokens/s), Y=每NPU输出吞吐(tokens/s)。同步更新内嵌 Workbook1.xlsx。"""
import zipfile, io, shutil
import openpyxl

PPTX = r"D:\HBF\hbf-inference\hbf-inference.pptx"
TMP  = r"D:\HBF\hbf-inference\tmp_chart.pptx"

# (name, color, x[], y[])
S = [
    ("EP64 · s=0",    "1F3A5F", [489.4,489.4,489.4,489.4,489.4,353.5], [3915,7830,15660,31319,62639,90506]),
    ("EP64 · s=0.25", "4A6B8A", [489.4,489.4,489.4,489.4,303.8,152.1], [3915,7830,15660,31319,38891,38929]),
    ("EP64 · s=0.5",  "9BB8D3", [489.4,489.4,478.7,241.5,120.7,60.1],  [3915,7830,15317,15459,15446,15390]),
    ("EP8 · s=0",     "8C3A0F", [61.2,61.2,61.2,61.2,61.2,49.3],       [489,979,1957,3915,7830,12625]),
    ("EP8 · s=0.25",  "D95E27", [61.2,61.2,61.2,61.2,61.0,30.5],       [489,979,1957,3915,7803,7818]),
    ("EP8 · s=0.5",   "F2A65A", [61.2,61.2,61.2,61.2,37.6,18.8],       [489,979,1957,3915,4813,4808]),
]
COLS = "ABCDEFGHIJKL"

def numcache(vals):
    pts = "".join(f'<c:pt idx="{i}"><c:v>{v}</c:v></c:pt>' for i, v in enumerate(vals))
    return f'<c:ptCount val="{len(vals)}"/>{pts}'

def ser(i, name, color, xs, ys):
    xc, yc = COLS[2*i], COLS[2*i+1]
    return (f'<c:ser><c:idx val="{i}"/><c:order val="{i}"/>'
            f'<c:tx><c:strRef><c:f>Sheet1!${yc}$1</c:f><c:strCache><c:ptCount val="1"/>'
            f'<c:pt idx="0"><c:v>{name}</c:v></c:pt></c:strCache></c:strRef></c:tx>'
            f'<c:spPr><a:ln w="25400" cap="rnd"><a:solidFill><a:srgbClr val="{color}"/></a:solidFill>'
            f'<a:prstDash val="solid"/><a:round/></a:ln></c:spPr>'
            f'<c:marker><c:symbol val="circle"/><c:size val="6"/><c:spPr>'
            f'<a:solidFill><a:srgbClr val="{color}"/></a:solidFill>'
            f'<a:ln w="12700"><a:solidFill><a:srgbClr val="{color}"/></a:solidFill></a:ln>'
            f'</c:spPr></c:marker>'
            f'<c:xVal><c:numRef><c:f>Sheet1!${xc}$2:${xc}$7</c:f><c:numCache>'
            f'<c:formatCode>General</c:formatCode>{numcache(xs)}</c:numCache></c:numRef></c:xVal>'
            f'<c:yVal><c:numRef><c:f>Sheet1!${yc}$2:${yc}$7</c:f><c:numCache>'
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
        f'<c:max val="500"/><c:min val="0"/></c:scaling><c:delete val="0"/><c:axPos val="b"/>'
        f'{gridlines()}{axis_title("每请求输出吞吐（tokens/s）", "0", "0.42", "0.88")}'
        f'<c:numFmt formatCode="General" sourceLinked="1"/><c:majorTickMark val="out"/>'
        f'<c:minorTickMark val="none"/><c:tickLblPos val="nextTo"/>{axline()}{axis_txpr("-60000000")}'
        f'<c:crossAx val="2"/><c:crosses val="autoZero"/><c:crossBetween val="between"/>'
        f'<c:majorUnit val="100"/></c:valAx>')

y_ax = (f'<c:valAx><c:axId val="2"/><c:scaling><c:orientation val="minMax"/>'
        f'<c:max val="100000"/><c:min val="0"/></c:scaling><c:delete val="0"/><c:axPos val="l"/>'
        f'{gridlines()}{axis_title("每 NPU 输出吞吐（tokens/s）", "-5400000", "0.02", "0.40")}'
        f'<c:numFmt formatCode="#,##0" sourceLinked="0"/><c:majorTickMark val="out"/>'
        f'<c:minorTickMark val="none"/><c:tickLblPos val="nextTo"/>{axline()}{axis_txpr("-60000000")}'
        f'<c:crossAx val="1"/><c:crosses val="autoZero"/><c:crossBetween val="between"/>'
        f'<c:majorUnit val="20000"/></c:valAx>')

sers = "".join(ser(i, *s) for i, s in enumerate(S))
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

# 校验 XML 可解析
import xml.dom.minidom
xml.dom.minidom.parseString(chart)

# 内嵌工作簿
zin = zipfile.ZipFile(PPTX)
wb = openpyxl.load_workbook(io.BytesIO(zin.read("ppt/embeddings/Workbook1.xlsx")))
ws = wb["Sheet1"]
for row in ws.iter_rows(min_row=1, max_row=max(ws.max_row, 8), max_col=max(ws.max_column, 12)):
    for c in row: c.value = None
for i, (name, _, xs, ys) in enumerate(S):
    xc, yc = COLS[2*i], COLS[2*i+1]
    ws[f"{xc}1"] = "x"
    ws[f"{yc}1"] = name
    for j, (x, y) in enumerate(zip(xs, ys)):
        ws[f"{xc}{j+2}"] = x
        ws[f"{yc}{j+2}"] = y
buf = io.BytesIO(); wb.save(buf); xlsx_bytes = buf.getvalue()

with zipfile.ZipFile(TMP, "w") as zout:
    for info in zin.infolist():
        if info.filename == "ppt/charts/chart1.xml": data = chart.encode("utf-8")
        elif info.filename == "ppt/embeddings/Workbook1.xlsx": data = xlsx_bytes
        else: data = zin.read(info.filename)
        ni = zipfile.ZipInfo(info.filename, date_time=info.date_time)
        ni.compress_type = info.compress_type
        ni.external_attr = info.external_attr
        zout.writestr(ni, data)
zin.close()
shutil.move(TMP, PPTX)
print("P4 scatter chart written")
