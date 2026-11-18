from pathlib import Path
import re
from urllib.parse import urlparse, parse_qs, unquote

root = Path(r"D:\HBF")
report = root / "multilevel_prefix_cache_abstraction.md"
text = report.read_text(encoding="utf-8")
errors = []

# Required two-chapter structure.
chapters = re.findall(r"^# (.+)$", text, flags=re.M)
body_chapters = chapters[1:] if chapters and chapters[0].startswith("多级、多机前缀缓存管理") else chapters
expected = ["一、架构抽象", "二、缓存算法抽象"]
if body_chapters != expected:
    errors.append(f"Top-level chapters mismatch: {chapters}")

# Local images.
images = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", text)
if len(images) != 3:
    errors.append(f"Expected 3 images, found {len(images)}")
for rel in images:
    p = root / rel
    if not p.is_file():
        errors.append(f"Missing image: {rel}")
    elif p.stat().st_size >= 3 * 1024 * 1024:
        errors.append(f"Image exceeds 3 MiB: {rel}")

# Citation structure and transport encoding.
citations = re.findall(r"\[([^\]]+)\]\((kimi-cite://web\?[^)]+)\s+\"citation\"\)", text)
if len(citations) < 20:
    errors.append(f"Too few citations: {len(citations)}")
for label, target in citations:
    query = target.split("?", 1)[1]
    params = parse_qs(query)
    if "url" not in params:
        errors.append(f"Citation lacks URL: {label}")
        continue
    source_url = params["url"][0]
    if not source_url.startswith("https://"):
        errors.append(f"Bad source URL: {label}")
    if "text" in params and len(params["text"][0]) > 400:
        errors.append(f"Citation text over 400 chars: {label}")

# Any ordinary HTTP links would violate the required citation form.
for match in re.finditer(r"https?://", text):
    # URLs inside a kimi-cite target are percent encoded and should not match.
    errors.append(f"Bare HTTP link near offset {match.start()}")

for marker in ["TODO", "TBD", "{{", "}}", "[[", "]]"]:
    if marker in text:
        errors.append(f"Unresolved marker: {marker}")

# Guardrails against the specific misreadings this report must avoid.
required_phrases = [
    "推理实例私有", "节点级共享", "单边 RDMA", "lease-bucket",
    "EP 域不是 LMCache 的共享域边界", "推理实例 → 工作进程",
    "不能笼统画成 SSD→GPU 直通", "不保证 `L1⊆L2`", "P→D 与缓存下沉必须解耦",
]
for phrase in required_phrases:
    if phrase not in text:
        errors.append(f"Missing required conclusion: {phrase}")

print(f"Report: {report}")
print(f"Characters: {len(text)}; lines: {len(text.splitlines())}")
print(f"Top-level chapters: {chapters}")
print(f"Images: {len(images)}; citations: {len(citations)}")
print(f"Tables: {sum(1 for line in text.splitlines() if line.startswith('|---'))}")
print(f"Code fences: {text.count('```')}")
if errors:
    print("VALIDATION FAILED")
    for e in errors:
        print("-", e)
    raise SystemExit(1)
print("VALIDATION PASSED")
