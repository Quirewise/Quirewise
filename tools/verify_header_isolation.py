#!/usr/bin/env python3
"""Verify installed public headers in isolation (DEP-003).

For every library:
  * build the dependency closure from the declared graph (already validated by
    validate_dependency_graph.py),
  * create a fresh prefix and install ONLY that library and its declared
    Quirewise dependencies,
  * compile every one of its installed public headers with
    ``<cc> -std=c11 -I<prefix>/include -fsyntax-only``.

Also checks that public headers include only installed public headers or
standard C headers, and contain no third-party identifier from the release
denylist.

Usage:
  python verify_header_isolation.py --prefix <full-prefix> --build-root <dir>
                                    --cc <compiler> [--cmake <cmake>]
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

HEADER_INCLUDE_RE = re.compile(r'^\s*#\s*include\s*[<"]([^>"]+)[>"]', re.M)
STANDARD_HEADERS = {
    "assert.h", "complex.h", "ctype.h", "errno.h", "fenv.h", "float.h",
    "inttypes.h", "iso646.h", "limits.h", "locale.h", "math.h", "setjmp.h",
    "signal.h", "stdalign.h", "stdarg.h", "stdatomic.h", "stdbool.h",
    "stddef.h", "stdint.h", "stdio.h", "stdlib.h", "stdnoreturn.h", "string.h",
    "tgmath.h", "threads.h", "time.h", "uchar.h", "wchar.h", "wctype.h",
    "windows.h", "sys/types.h", "sys/stat.h", "unistd.h", "fcntl.h",
}
# Third-party ABI/type prefixes only. Algorithm names such as "crc32", "lzma"
# or "webp" legitimately appear in Quirewise's own API names.
DENY_PATTERNS = [
    r"\bopj_[a-z]", r"\bOPJ_[A-Z]", r"\bfz_[a-z]", r"\bstbi__?[a-z]",
    r"\bddjvu_[a-z]", r"\bLzma(Dec|2Dec|Props|Enc)", r"\bZ7_[A-Za-z]",
    r"\bjpeg_std_error\b", r"\bjpeg_decompress_struct\b",
    r"\bWebPDecoderConfig\b", r"\bWebPBitstreamFeatures\b",
    r"\biconv_t\b", r"\bOPENSSL_[A-Z]", r"\bEVP_[A-Z]",
    r"\bBIGNUM\b", r"\bz_stream\b", r"\bavcodec_[a-z]",
    r"\btiff_[a-z]+\b", r"\bpng_[a-z_]+\b",
]
DENY_REGEX = re.compile("|".join(DENY_PATTERNS))


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=600)


def declared_graph(workspace: Path) -> dict[str, set[str]]:
    script = workspace / "app" / "tools" / "validate_dependency_graph.py"
    result = run([sys.executable, str(script), "--workspace", str(workspace)])
    graph: dict[str, set[str]] = {}
    pattern = re.compile(r"^  (quirewise-[a-z0-9-]+) -> (.+)$", re.M)
    for name, deps in pattern.findall(result.stdout):
        graph[name] = {
            dep.strip() for dep in deps.split(",") if dep.strip() and dep.strip() != "(none)"
        }
    return graph


def find_build_tree(build_root: Path, library: str,
                    template: str = "*{library}") -> Path | None:
    """Locate the configured build directory for a library."""

    exact = build_root / f"build-{library}"
    if (exact / "CMakeCache.txt").is_file():
        return exact
    pattern = template.replace("{library}", library)
    candidates = [
        candidate for candidate in sorted(build_root.glob(pattern))
        if candidate.is_dir() and (candidate / "CMakeCache.txt").is_file()
    ]
    return candidates[0] if candidates else None


def closure(graph: dict[str, set[str]], name: str) -> list[str]:
    seen: set[str] = set()
    stack = list(graph.get(name, set()))
    while stack:
        node = stack.pop()
        if node in seen or node == name:
            continue
        seen.add(node)
        stack.extend(graph.get(node, set()))
    return sorted(seen)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--prefix", type=Path, required=True,
                        help="full installed prefix used to locate build trees")
    parser.add_argument("--build-root", type=Path, required=True,
                        help="directory containing build-<library> trees")
    parser.add_argument("--cc", required=True)
    parser.add_argument("--cmake", default="cmake")
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--build-template", default="*{library}",
                        help="glob template for build directory names")
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    graph = declared_graph(workspace)
    if len(graph) != 17:
        print(f"error: expected 17 libraries, got {len(graph)}", file=sys.stderr)
        return 2

    report = {"libraries": {}, "errors": []}
    failures = 0
    for library in sorted(graph):
        build = find_build_tree(args.build_root, library, args.build_template)
        if build is None:
            report["errors"].append(f"{library}: build tree missing under {args.build_root}")
            failures += 1
            continue
        with tempfile.TemporaryDirectory(prefix="qw-header-isolation-") as temporary:
            prefix = Path(temporary) / "prefix"
            prefix.mkdir()
            for dependency in closure(graph, library) + [library]:
                dep_build = find_build_tree(
                    args.build_root, dependency, args.build_template)
                if dep_build is None:
                    report["errors"].append(
                        f"{library}: dependency build missing: {dependency}")
                    failures += 1
                    continue
                install = run([args.cmake, "--install", str(dep_build),
                               "--prefix", str(prefix)])
                if install.returncode != 0:
                    report["errors"].append(
                        f"{library}: install failed for {dependency}: "
                        f"{install.stderr.strip()[:200]}")
                    failures += 1
            headers = sorted((prefix / "include" / "quirewise").glob("*.h"))
            if not headers:
                report["errors"].append(f"{library}: no public headers installed")
                failures += 1
                continue
            compile_results = []
            for header in headers:
                wrapper = Path(temporary) / "wrapper.c"
                wrapper.write_text(f'#include "quirewise/{header.name}"\n',
                                   encoding="utf-8")
                compile_result = run([
                    args.cc, "-std=c11", f"-I{prefix / 'include'}",
                    "-fsyntax-only", str(wrapper),
                ])
                compile_results.append({
                    "header": header.name,
                    "rc": compile_result.returncode,
                    "stderr": compile_result.stderr.strip()[:300],
                })
                if compile_result.returncode != 0:
                    failures += 1
                    report["errors"].append(
                        f"{library}: header {header.name} does not compile in isolation")
            # Include and identifier hygiene for the isolated set.
            installed = {header.name for header in headers}
            for header in headers:
                text = header.read_text(encoding="utf-8", errors="replace")
                stripped = re.sub(r"/\*.*?\*/|//[^\n]*", " ", text, flags=re.S)
                for include in HEADER_INCLUDE_RE.findall(stripped):
                    if include.startswith("quirewise/"):
                        if include.split("/", 1)[1] not in installed:
                            report["errors"].append(
                                f"{library}/{header.name}: includes non-installed "
                                f"header {include}")
                            failures += 1
                    elif include not in STANDARD_HEADERS:
                        report["errors"].append(
                            f"{library}/{header.name}: includes non-standard header "
                            f"{include}")
                        failures += 1
                for match in DENY_REGEX.finditer(stripped):
                    report["errors"].append(
                        f"{library}/{header.name}: third-party token {match.group(0)}")
                    failures += 1
            report["libraries"][library] = {
                "dependencies": closure(graph, library),
                "headers": len(headers),
                "compiled": sum(1 for item in compile_results if item["rc"] == 0),
                "results": compile_results,
            }
        print(f"{library}: {len(headers)} header(s), isolation OK"
              if all(item["rc"] == 0 for item in compile_results)
              else f"{library}: FAILED")

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                                 encoding="utf-8", newline="\n")

    total_headers = sum(item["headers"] for item in report["libraries"].values())
    print(f"libraries={len(report['libraries'])} headers={total_headers} "
          f"failures={failures}")
    for error in report["errors"][:20]:
        print(f"error: {error}", file=sys.stderr)
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
