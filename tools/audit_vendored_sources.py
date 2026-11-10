#!/usr/bin/env python3
"""Fail when vendored third-party implementations escape the allow-list.

A vendored implementation is any C/C++/assembly source file that lives under a
directory named ``third_party``, ``third-party``, ``vendor``, ``vendored`` or
``lzma_sdk``.  The allow-list (``app/vendored-allowlist.json``) pins every
remaining file by repository-relative path, normalised SHA-256 and line count.
Replacing a component means deleting its entries; the gate then stays green
only once the tree is clean, so the allow-list can only shrink.

Line endings are normalised (CRLF -> LF) before hashing so the allow-list is
valid on Windows and Linux checkouts alike.

Usage:
    python app/tools/audit_vendored_sources.py --workspace .
    python app/tools/audit_vendored_sources.py --workspace . --update
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

VENDOR_DIRS = {"third_party", "third-party", "vendor", "vendored", "lzma_sdk"}
SKIP_DIRS = {".git", ".tmp", "build", "out", "CMakeFiles", "node_modules"}
SOURCE_SUFFIXES = {
    ".c", ".h", ".cc", ".cpp", ".cxx", ".hpp", ".hh", ".s", ".asm", ".inc",
}
DEFAULT_ALLOWLIST = Path("app") / "vendored-allowlist.json"


def normalise(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def count_lines(data: bytes) -> int:
    if not data:
        return 0
    return data.count(b"\n") + (0 if data.endswith(b"\n") else 1)


def entry_for(root: Path, path: Path) -> dict:
    data = normalise(path.read_bytes())
    return {
        "path": path.relative_to(root).as_posix(),
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
        "lines": count_lines(data),
    }


def scan(root: Path) -> dict[str, dict]:
    found: dict[str, dict] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in SKIP_DIRS]
        directory = Path(dirpath)
        rel_parts = set(directory.relative_to(root).parts)
        if not (rel_parts & VENDOR_DIRS):
            continue
        for name in filenames:
            if Path(name).suffix.lower() not in SOURCE_SUFFIXES:
                continue
            item = entry_for(root, directory / name)
            found[item["path"]] = item
    return found


def load_allowlist(path: Path) -> dict[str, dict]:
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = data.get("files", [])
    return {item["path"]: item for item in entries}


def write_allowlist(path: Path, found: dict[str, dict]) -> None:
    payload = {
        "schema": 1,
        "note": (
            "Vendored implementation sources that still need a first-party "
            "replacement. Entries may only be removed; adding or editing an "
            "entry requires a reviewed replacement plan. Hashes use LF-normalised "
            "content so the list is portable across checkouts."
        ),
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "file_count": len(found),
        "line_count": sum(item["lines"] for item in found.values()),
        "files": [found[key] for key in sorted(found)],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def compare(found: dict[str, dict], allowed: dict[str, dict]) -> dict:
    unexpected = sorted(set(found) - set(allowed))
    stale = sorted(set(allowed) - set(found))
    mismatched = []
    for key in sorted(set(found) & set(allowed)):
        if found[key]["sha256"] != allowed[key]["sha256"] or \
                found[key]["lines"] != allowed[key]["lines"]:
            mismatched.append({
                "path": key,
                "allowed": allowed[key],
                "found": found[key],
            })
    return {
        "vendored_files": len(found),
        "vendored_lines": sum(item["lines"] for item in found.values()),
        "allowed_files": len(allowed),
        "allowed_lines": sum(item["lines"] for item in allowed.values()),
        "unexpected": unexpected,
        "stale": stale,
        "mismatched": mismatched,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path,
                        default=Path(__file__).resolve().parents[2])
    parser.add_argument("--allowlist", type=Path,
                        help="allow-list path (default: <workspace>/app/vendored-allowlist.json)")
    parser.add_argument("--update", action="store_true",
                        help="rewrite the allow-list from the current tree")
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()

    root = args.workspace.resolve()
    allowlist = (args.allowlist or (root / DEFAULT_ALLOWLIST)).resolve()
    found = scan(root)

    if args.update:
        write_allowlist(allowlist, found)
        print(f"allow-list written: {allowlist} "
              f"({len(found)} files, {sum(i['lines'] for i in found.values())} lines)")
        return 0

    report = compare(found, load_allowlist(allowlist))
    ok = not (report["unexpected"] or report["stale"] or report["mismatched"])
    report["overall"] = "PASS" if ok else "FAIL"
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(f"vendored sources: {report['vendored_files']} files / "
          f"{report['vendored_lines']} lines "
          f"(allow-list {report['allowed_files']} / {report['allowed_lines']})")
    if report["unexpected"]:
        print(f"unexpected: {len(report['unexpected'])}")
        for path in report["unexpected"][:20]:
            print(f"  + {path}")
    if report["stale"]:
        print(f"stale: {len(report['stale'])}")
        for path in report["stale"][:20]:
            print(f"  - {path}")
    if report["mismatched"]:
        print(f"mismatched: {len(report['mismatched'])}")
        for item in report["mismatched"][:20]:
            print(f"  ! {item['path']}")
    print("PASS: vendored sources match the allow-list" if ok
          else "FAIL: vendored sources do not match the allow-list")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
