from pathlib import Path

report = Path(r"D:\HBF\HHM_ASU_native_KVC_management.md")
text = report.read_text(encoding="utf-8")
errors = []

required = [
    "24 GB 可用", "3.2 TB/s", "320 GB", "800 GB/s",
    "C_D\\leftrightarrow C_H", "C_D\\leftrightarrow C_A", "C_H\\leftrightarrow C_A",
    "不允许 KV 数据走卡间或节点间 P2P", "lookup(key)", "lock(key)", "unlock(key)",
    "read(key)", "write(key, value)", "delete(key)", "model.forward",
    "稳定热块准入", "算法 1：备份路径", "算法 2：DRAM 上的观察", "算法 3：从 HBF 前沿",
    "lookup+lock", "write_if_absent", "每 DP rank 的 RadixTree",
    "不能由后台线程异步搬迁", "本地 DRAM／HBF 不长期重复保存同一块",
    "$D+A$ | ASU 提供全局备份", "DRAM 是观察与准入层", "时间衰减复用分数",
    "\\operatorname{Hot}(v,t)", "\\operatorname{AdmitH}(v,t)", "\\operatorname{AdmitA}(v,t)",
    "\\operatorname{ColdH}(v,t)", "稳定热迁移不受 $F_D$ 限制",
]
for phrase in required:
    if phrase not in text:
        errors.append(f"Missing required design element: {phrase}")

body = text.split("## 附录 A", 1)[0]
for phrase in ["$D+H$", "$H+A$", "$D+H+A$", "迁移暂态"]:
    if phrase in body:
        errors.append(f"Transient-state detail in main text: {phrase}")

if text.count("```") % 2:
    errors.append("Unbalanced code fences")
if text.count("$$") % 2:
    errors.append("Unbalanced display-math delimiters")
for marker in ["TODO", "TBD", "{{", "[[", "]]"]:
    if marker in text:
        errors.append(f"Unresolved marker: {marker}")

chapters = [line for line in text.splitlines() if line.startswith("## ")]
print(f"Report: {report}")
print(f"Characters: {len(text)}; lines: {len(text.splitlines())}")
print(f"Sections: {len(chapters)}; tables: {sum(1 for line in text.splitlines() if line.startswith('|---'))}")
print(f"Code fences: {text.count('```')}; display-math delimiters: {text.count('$$')}")
if errors:
    print("VALIDATION FAILED")
    for error in errors:
        print("-", error)
    raise SystemExit(1)
print("VALIDATION PASSED")
