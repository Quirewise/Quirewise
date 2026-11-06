#!/usr/bin/env python3
"""Compile every installed public header in isolation (DEP-003).

The check installs nothing and changes nothing. It scans an installed prefix
for public headers, generates one translation unit per header that includes
only that header, and runs the system C compiler with ``-fsyntax-only``. It
also reports any header whose name belongs to a forbidden third-party library
so an install-prefix leak cannot pass silently.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

FORBIDDEN_HEADER_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("third_party_header:zlib", re.compile(r"(?i)^zlib(?:conf)?\.h$")),
    ("third_party_header:jpeg", re.compile(r"(?i)^jpe?glib\.h$")),
    ("third_party_header:stb", re.compile(r"(?i)^stb_[a-z0-9_]+\.h$")),
    ("third_party_header:webp", re.compile(r"(?i)^(?:decode|encode|mux|demux)\.h$")),
    ("third_party_header:openjpeg", re.compile(r"(?i)^openjpeg\.h$")),
    ("third_party_header:djvulibre", re.compile(r"(?i)^ddjvuapi\.h$")),
    ("third_party_header:mupdf", re.compile(r"(?i)^fitz\.h$")),
    ("third_party_header:lzma", re.compile(r"(?i)^lzma\.h$")),
    ("third_party_header:iconv", re.compile(r"(?i)^iconv\.h$")),
)


def find_compiler(explicit: str | None) -> str:
    if explicit:
        return explicit
    for name in ("cc", "gcc", "clang"):
        found = shutil.which(name)
        if found:
            return found
    raise SystemExit("error: no C compiler found; pass --compiler")


def collect_headers(include_root: Path) -> list[Path]:
    return sorted(
        path
        for path in include_root.rglob("*")
        if path.is_file() and path.suffix.lower() in {".h", ".hpp", ".hh"}
    )


def third_party_leaks(include_root: Path, headers: list[Path]) -> list[dict[str, str]]:
    leaks: list[dict[str, str]] = []
    for header in headers:
        relative = header.relative_to(include_root).as_posix()
        for rule, pattern in FORBIDDEN_HEADER_PATTERNS:
            if pattern.search(header.name) or pattern.search(relative):
                leaks.append({"rule": rule, "path": relative})
                break
    return leaks


def compile_header(
    compiler: str, include_root: Path, header: Path, extra_flags: list[str],
    workdir: Path
) -> dict[str, object]:
    relative = header.relative_to(include_root).as_posix()
    source = workdir / "probe.c"
    source.write_text(f'#include "{relative}"\n', encoding="utf-8")
    command = [
        compiler, "-std=c11", "-fsyntax-only",
        f"-I{include_root.as_posix()}", *extra_flags, source.name,
    ]
    completed = subprocess.run(
        command, cwd=workdir, capture_output=True, text=True, timeout=120
    )
    return {
        "header": relative,
        "exit_code": completed.returncode,
        "stderr": completed.stderr.strip()[:2000],
        "stdout": completed.stdout.strip()[:1000],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefix", type=Path, required=True,
                        help="installed prefix (must contain include/)")
    parser.add_argument("--compiler", help="C compiler executable")
    parser.add_argument("--json", type=Path, help="write the full JSON report")
    parser.add_argument("--flag", action="append", default=[],
                        help="extra compiler flag passed to every probe")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    include_root = args.prefix.resolve() / "include"
    if not include_root.is_dir():
        print(f"error: missing include directory: {include_root}", file=sys.stderr)
        return 2
    headers = collect_headers(include_root)
    if not headers:
        print(f"error: no public headers under {include_root}", file=sys.stderr)
        return 2
    compiler = find_compiler(args.compiler)
    leaks = third_party_leaks(include_root, headers)

    results: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="qw-header-check-") as temporary:
        workdir = Path(temporary)
        for header in headers:
            results.append(
                compile_header(compiler, include_root, header, args.flag, workdir)
            )

    failures = [item for item in results if item["exit_code"] != 0]
    report = {
        "prefix": str(include_root),
        "compiler": compiler,
        "header_count": len(results),
        "failure_count": len(failures),
        "third_party_leak_count": len(leaks),
        "third_party_leaks": leaks,
        "headers": results,
        "exit_code": 1 if failures or leaks else 0,
    }
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8", newline="\n",
        )

    print(
        f"public headers: {len(results)} compiled, {len(failures)} failed, "
        f"{len(leaks)} third-party leaks"
    )
    for item in failures:
        print(f"FAIL {item['header']}")
        if item["stderr"]:
            for line in str(item["stderr"]).splitlines()[:10]:
                print(f"  {line}")
    for leak in leaks:
        print(f"LEAK {leak['path']} ({leak['rule']})")
    return int(report["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
