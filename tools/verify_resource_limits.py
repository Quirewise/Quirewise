import re
import sys
from pathlib import Path

REQUIRED = {
    "archive": ["max_entries", "MAX_SIZE"],
    "image": ["MAX_PIXEL", "MAX_FRAME"],
    "page": ["MAX_PAGE"],
    "data": ["MAX_DEPTH"],
    "text": ["MAX_DEPTH", "MAX_LIST_DEPTH"],
    "document": ["MAX_DECODED_PIXEL", "MAX_ARCHIVE_ENTR"],
    "ebook": ["MAX_TEXT_ARCHIVE_ENTR", "MAX_MEMBER_NAME_BYTES"],
    "audio": ["MAX_FRAME", "MAX_REPEAT_DEPTH"],
    "vector": ["MAX_PIXEL", "MAX_INPUT_BYTES"],
    "subtitle": ["MAX_INPUT_BYTES"],
    "spreadsheet": ["MAX_CONTENT_BYTES"],
    "comic": ["QW_COMIC_ERR_RESOURCE_LIMIT"],
    "compression": ["OUTPUT_FULL"],
    "pdg": ["MAX_PARALLEL_JOBS"],
}


def source_text(package):
    root = Path("libraries") / f"quirewise-{package}" / "src"
    return "\n".join(p.read_text(encoding="utf-8", errors="replace")
                     for p in root.rglob("*.c"))


def main():
    findings = 0
    for package, symbols in REQUIRED.items():
        text = source_text(package)
        missing = [s for s in symbols if s not in text]
        status = "ok" if not missing else "missing " + ",".join(missing)
        print(f"{package}: {status} ({', '.join(symbols)})")
        if missing:
            findings += 1
    print(f"resource limits: {findings} findings")
    return 1 if findings else 0


sys.exit(main())
