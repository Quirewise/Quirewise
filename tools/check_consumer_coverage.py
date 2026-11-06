#!/usr/bin/env python3
"""Report which declared public API functions the external consumers call.

DEP-005 asks for at least one mapped call per installed public function. This
tool derives the public surface from the installed public headers (function
declarations starting with ``qw_``), intersects it with the symbols actually
exported by the installed archives, and then checks which of them appear in the
external consumer sources. The result is a per-package coverage table plus the
list of uncovered entry points.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

IDENTIFIER_RE = re.compile(r"\b([A-Za-z][A-Za-z0-9_]*)\b")
CALL_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(")

PACKAGE_TARGETS: dict[str, str] = {
    "quirewise-archive": "libquirewise_archive",
    "quirewise-audio": "libquirewise_audio",
    "quirewise-charset": "libquirewise_charset",
    "quirewise-comic": "libquirewise_comic",
    "quirewise-compression": "libquirewise_compression",
    "quirewise-crypto": "libquirewise_crypto",
    "quirewise-data": "libquirewise_data",
    "quirewise-document": "libquirewise_document",
    "quirewise-ebook": "libquirewise_ebook",
    "quirewise-image": "libquirewise_image_decode",
    "quirewise-page": "libquirewise_page",
    "quirewise-pdg": "libquirewise_pdg",
    "quirewise-runtime": "libquirewise_runtime",
    "quirewise-spreadsheet": "libquirewise_spreadsheet",
    "quirewise-subtitle": "libquirewise_subtitle",
    "quirewise-text": "libquirewise_text",
    "quirewise-vector": "libquirewise_vector",
}


def header_declarations(include_dir: Path) -> set[str]:
    """Identifiers mentioned by the installed public headers.

    Public prefixes are not uniform (``qw_*`` plus ``pdg_*``/``pdz_*``), so the
    declared surface is derived by intersecting exported symbols with every
    identifier that appears in the headers. Internal helpers that never appear
    in a public header are therefore excluded.
    """

    names: set[str] = set()
    for header in sorted(include_dir.rglob("*.h")):
        text = header.read_text(encoding="utf-8", errors="replace")
        names.update(IDENTIFIER_RE.findall(text))
    return names


def archive_symbols(archive: Path, nm: str) -> set[str]:
    completed = subprocess.run(
        [nm, "--defined-only", str(archive)],
        capture_output=True, text=True, timeout=120,
    )
    symbols: set[str] = set()
    for line in completed.stdout.splitlines():
        parts = line.split()
        # Only external text symbols are exported API; lowercase "t" is a
        # translation-unit-local function and must not inflate the surface.
        if len(parts) >= 3 and parts[-2] == "T":
            symbols.add(parts[-1])
    return symbols


def consumer_calls(consumer_sources: Path) -> dict[str, set[str]]:
    calls: dict[str, set[str]] = {}
    for source in sorted(consumer_sources.glob("*.c")):
        text = source.read_text(encoding="utf-8", errors="replace")
        calls[source.name] = set(CALL_RE.findall(text))
    return calls


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path("."))
    parser.add_argument("--prefix", type=Path, required=True,
                        help="installed prefix containing lib/")
    parser.add_argument("--consumer-sources", type=Path,
                        default=Path("external-consumer-template/src"))
    parser.add_argument("--nm", default="nm")
    parser.add_argument("--json", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    workspace = args.workspace.resolve()
    prefix = args.prefix.resolve()
    library_dir = prefix / "lib"
    if not library_dir.is_dir():
        print(f"error: no lib/ under {prefix}", file=sys.stderr)
        return 2
    calls = consumer_calls(workspace / args.consumer_sources)
    all_calls: set[str] = set().union(*calls.values()) if calls else set()

    packages: list[dict[str, object]] = []
    total_declared = 0
    total_covered = 0
    for package, target in PACKAGE_TARGETS.items():
        include_dir = workspace / "libraries" / package / "include"
        declared = header_declarations(include_dir) if include_dir.is_dir() else set()
        archive = next(library_dir.glob(target + ".*"), None)
        exported = archive_symbols(archive, args.nm) if archive else set()
        public_api = sorted(declared & exported)
        covered = sorted(set(public_api) & all_calls)
        uncovered = sorted(set(public_api) - all_calls)
        total_declared += len(public_api)
        total_covered += len(covered)
        packages.append(
            {
                "package": package,
                "target": target,
                "declared_in_headers": len(declared),
                "exported": len(exported),
                "public_api": len(public_api),
                "covered": len(covered),
                "coverage": round(len(covered) / len(public_api), 4) if public_api else 0.0,
                "uncovered": uncovered,
            }
        )

    report = {
        "prefix": str(prefix),
        "consumer_sources": str(args.consumer_sources),
        "public_api_total": total_declared,
        "covered_total": total_covered,
        "coverage": round(total_covered / total_declared, 4) if total_declared else 0.0,
        "packages": packages,
    }
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n",
    )
    print(f"public API: {total_declared} functions, {total_covered} called by consumers "
          f"({report['coverage'] * 100:.1f}%)")
    for item in packages:
        print(f"  {item['package']:32s} api={item['public_api']:4d} "
              f"covered={item['covered']:4d} ({item['coverage'] * 100:5.1f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
