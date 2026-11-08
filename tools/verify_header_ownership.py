#!/usr/bin/env python3
"""Verify that no two library packages install different bytes at the same path.

Every quirewise-* package installs its own ``include/`` tree into the shared
install prefix. Several packages intentionally vendor the same public-contract
headers (``quirewise/status.h``, ``quirewise/document.h``, ``quirewise/convert.h``,
...) so that each package stays independently installable and the dependency
graph stays acyclic.  That is only safe while every copy of one installed path
is byte-identical: otherwise the public API a consumer sees depends on the
order the packages were installed in.

The gate scans each package's ``include/`` tree, maps it to install-relative
paths, and:

* fails when two packages install different bytes at the same path;
* reports identical duplicates as maintained shared contracts (accepted);
* with ``--strict``, also fails on identical duplicates so a future
  single-owner refactor can be enforced.

Exit code 0 means every shared install path is consistent.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Iterable

SCHEMA = 1

DIRECTORY_INSTALL = re.compile(r"install\s*\(\s*DIRECTORY\s+include/")
EXPLICIT_FILES = re.compile(r"install\s*\(\s*FILES\s+([^)]*)\)")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def audit_package(package: Path) -> tuple[list[tuple[str, Path, str, int]], list[str]]:
    """Return installed include entries and non-fatal notes for one package."""
    include = package / "include"
    notes: list[str] = []
    if not include.is_dir():
        return [], notes

    cmake = package / "CMakeLists.txt"
    text = cmake.read_text(encoding="utf-8", errors="replace")
    if not DIRECTORY_INSTALL.search(text):
        notes.append(
            f"{package.name}: include/ exists but no install(DIRECTORY include/) "
            "rule was found; tree not audited"
        )
        return [], notes
    for match in EXPLICIT_FILES.finditer(text):
        if ".h" in match.group(1):
            notes.append(
                f"{package.name}: explicit install(FILES ...) header rule is not "
                "audited by this gate"
            )

    entries: list[tuple[str, Path, str, int]] = []
    for path in sorted(include.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(include).as_posix()
        entries.append((relative, path, sha256(path), path.stat().st_size))
    return entries, notes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path,
                        default=Path(__file__).resolve().parents[2])
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--strict", action="store_true",
                        help="also fail on byte-identical shared headers")
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    libraries = workspace / "libraries"
    packages = sorted(path for path in libraries.iterdir() if path.is_dir())

    owners: dict[str, list[dict]] = {}
    notes: list[str] = []
    audited = 0
    for package in packages:
        entries, package_notes = audit_package(package)
        notes.extend(package_notes)
        if entries:
            audited += 1
        for relative, path, digest, size in entries:
            owners.setdefault(relative, []).append({
                "package": package.name,
                "path": path.relative_to(workspace).as_posix(),
                "sha256": digest,
                "size": size,
            })

    shared = {relative: items for relative, items in owners.items()
              if len(items) > 1}
    conflicts: dict[str, list[dict]] = {}
    for relative, items in shared.items():
        if len({item["sha256"] for item in items}) > 1:
            conflicts[relative] = items

    print(f"Quirewise public-header ownership: {audited}/{len(packages)} packages, "
          f"{len(owners)} install paths, {len(shared)} shared paths")
    for note in notes:
        print(f"[note] {note}")

    for relative, items in sorted(shared.items()):
        variants = {}
        for item in items:
            variants.setdefault(item["sha256"], []).append(item["package"])
        for digest, names in variants.items():
            size = next(item["size"] for item in items if item["sha256"] == digest)
            print(f"[shared] {relative}  sha256={digest[:16]}  size={size}  "
                  f"packages={', '.join(sorted(names))}")

    for relative, items in sorted(conflicts.items()):
        print(f"[CONFLICT] {relative}: {len({item['sha256'] for item in items})} "
              f"different copies install to the same path")
        for item in sorted(items, key=lambda entry: entry["package"]):
            print(f"    {item['package']}: sha256={item['sha256'][:16]} "
                  f"size={item['size']}")

    result = {
        "schema": SCHEMA,
        "workspace": str(workspace),
        "packages_audited": audited,
        "packages_total": len(packages),
        "install_paths": len(owners),
        "shared_paths": {
            relative: [
                {"package": item["package"], "sha256": item["sha256"],
                 "size": item["size"]}
                for item in items
            ]
            for relative, items in sorted(shared.items())
        },
        "conflicts": sorted(conflicts),
        "notes": notes,
        "strict": args.strict,
    }
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(result, indent=2) + "\n",
                                 encoding="utf-8")

    if conflicts:
        print(f"\nFAIL: {len(conflicts)} installed paths receive different bytes "
              "from different packages; the installed API depends on install order")
        return 1
    if args.strict and shared:
        print(f"\nFAIL: {len(shared)} shared paths exist (--strict)")
        return 1
    if shared:
        print("\nOK: every shared install path is byte-identical")
    else:
        print("\nOK: every install path is owned by exactly one package")
    return 0


if __name__ == "__main__":
    sys.exit(main())
