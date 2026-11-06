import re
import sys
from pathlib import Path

header = Path("libraries/quirewise-document/src/backends/mupdf_backend.h")
text = header.read_text(encoding="utf-8")
prototypes = re.findall(r"\b(qw_mupdf_\w+)\s*\(", text)
prototypes = sorted(set(prototypes))

sources = []
root = Path("libraries/quirewise-document/src")
for path in root.rglob("*.c"):
    sources.append(path.read_text(encoding="utf-8", errors="replace"))
blob = "\n".join(sources)

missing = []
for name in prototypes:
    if not re.search(r"\b(?:int|void)\s+" + re.escape(name) + r"\s*\(", blob):
        missing.append(name)

print(f"qw_mupdf_* prototypes: {len(prototypes)}")
for name in prototypes:
    print(" ", name)
print(f"missing definitions: {len(missing)}")
for name in missing:
    print("  MISSING", name)
sys.exit(1 if missing else 0)
