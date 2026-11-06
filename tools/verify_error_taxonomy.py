import re
import sys
from pathlib import Path

PACKAGES = {
    "Archive": ["QW_ARCHIVE_ERR_FORMAT", "QW_ARCHIVE_ERR_RESOURCE_LIMIT"],
    "Audio": ["QW_AUDIO_FORMAT_ERROR", "QW_AUDIO_RESOURCE_LIMIT"],
    "Charset": None,
    "Comic": ["QW_COMIC_ERR_FORMAT", "QW_COMIC_ERR_RESOURCE_LIMIT"],
    "Compression": ["QW_COMPRESSION_INFLATE_ERROR", "QW_COMPRESSION_INFLATE_OUTPUT_FULL"],
    "Crypto": None,
    "Data": ["QW_DATA_ERR_FORMAT", "QW_DATA_ERR_RESOURCE_LIMIT"],
    "Document": ["QW_STATUS_ERR_FORMAT", "QW_STATUS_ERR_RESOURCE_LIMIT"],
    "Ebook": ["QW_EPUB_ERR_FORMAT", "QW_EPUB_ERR_RESOURCE_LIMIT"],
    "Image": ["QW_IMAGE_ERR_FORMAT", "QW_IMAGE_ERR_RESOURCE_LIMIT"],
    "Page": ["QW_PAGE_ERR_FORMAT", "QW_PAGE_ERR_RESOURCE_LIMIT"],
    "PDG": ["PDG_ERR_FORMAT", "PDG_ERR_RESOURCE_LIMIT"],
    "Runtime": None,
    "Spreadsheet": ["QW_SPREADSHEET_ERR_FORMAT", "QW_SPREADSHEET_ERR_RESOURCE_LIMIT"],
    "Subtitle": ["QW_SUBTITLE_FORMAT_ERROR", "QW_SUBTITLE_RESOURCE_LIMIT"],
    "Text": ["QW_STATUS_ERR_FORMAT", "QW_STATUS_ERR_RESOURCE_LIMIT"],
    "Vector": ["QW_SVG_ERR_FORMAT", "QW_SVG_ERR_RESOURCE_LIMIT"],
}


def header_text(package):
    root = Path("libraries") / f"quirewise-{package.lower()}" / "include"
    return "\n".join(p.read_text(encoding="utf-8", errors="replace")
                     for p in sorted(root.rglob("*.h")))


def main():
    findings = 0
    for package, names in PACKAGES.items():
        if names is None:
            print(f"{package}: no parse status enum (boundary package)")
            continue
        text = header_text(package)
        missing = [n for n in names if n not in text]
        values = {}
        for name in names:
            match = re.search(re.escape(name) + r"\s*=\s*(-?\d+)", text)
            if match:
                values[name] = int(match.group(1))
        distinct = "n/a"
        if len(values) == 2:
            distinct = "distinct" if values[names[0]] != values[names[1]] else "COLLISION"
            if values[names[0]] == values[names[1]]:
                findings += 1
        status = "missing:" + ",".join(missing) if missing else "ok"
        print(f"{package}: {status}; {distinct}; values={values}")
        if missing:
            findings += 1
    print(f"error taxonomy: {findings} findings")
    return 1 if findings else 0


sys.exit(main())
