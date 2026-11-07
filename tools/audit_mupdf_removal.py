#!/usr/bin/env python3
"""Fail if the legacy MuPDF compatibility boundary reappears in production code.

The removal gate scans tracked C/C++/CMake files in the Quirewise application and
library repositories for the historical wrapper names, private backend header and
MuPDF build references. Documentation, test evidence and this gate itself are out
of scope; the intent is that no installed header, compiled source unit or package
configuration carries the legacy boundary.

Exit code 0 means zero legacy references, 1 means at least one finding was found
or a repository could not be scanned.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

PRODUCTION_SUFFIXES = {
    ".c", ".cc", ".cpp", ".cxx",
    ".h", ".hh", ".hpp", ".hxx",
    ".cmake", ".in",
}
PRODUCTION_NAMES = {"CMakeLists.txt"}

PATTERNS = [
    ("qw_mupdf_symbol", re.compile(r"\bqw_mupdf_[A-Za-z0-9_]+\b")),
    ("mupdf_backend_header", re.compile(r"\bmupdf_backend\.h\b", re.IGNORECASE)),
    ("qw_mupdf_type", re.compile(r"\bQwMuPdf[A-Za-z0-9_]*\b")),
    ("mupdf_condition", re.compile(r"\bQUIREWISE_WITH_MUPDF\b")),
    ("mupdf_include", re.compile(r'#\s*include\s*[<"]mupdf[/"]', re.IGNORECASE)),
    ("mupdf_cmake", re.compile(
        r"\b(?:find_package|find_dependency)\s*\(\s*MuPDF\b|"
        r"\bpkg_check_modules\s*\([^)]*\bmupdf\b|"
        r"\btarget_link_libraries\s*\([^)]*\bmupdf\b",
        re.IGNORECASE,
    )),
]


def repository_roots(workspace: Path) -> list[Path]:
    roots = [workspace / "app"]
    libraries = workspace / "libraries"
    if libraries.is_dir():
        roots.extend(sorted(path for path in libraries.iterdir() if path.is_dir()))
    return [path for path in roots if (path / ".git").exists()]


def tracked_files(repo: Path) -> list[Path]:
    completed = subprocess.run(
        ["git", "-C", str(repo), "ls-files"],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "git ls-files failed")
    result = []
    for line in completed.stdout.splitlines():
        if not line:
            continue
        path = repo / line
        if path.suffix.lower() in PRODUCTION_SUFFIXES or path.name in PRODUCTION_NAMES:
            result.append(path)
    return result


def scan(workspace: Path) -> tuple[list[dict], list[str]]:
    findings: list[dict] = []
    errors: list[str] = []
    for repo in repository_roots(workspace):
        try:
            files = tracked_files(repo)
        except RuntimeError as exc:
            errors.append(f"{repo}: {exc}")
            continue
        for path in files:
            if not path.is_file():
                # Staged deletions remain in `git ls-files` until commit.
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                errors.append(f"{path}: {exc}")
                continue
            for line_number, line in enumerate(text.splitlines(), start=1):
                for kind, pattern in PATTERNS:
                    if pattern.search(line):
                        findings.append({
                            "kind": kind,
                            "path": path.relative_to(workspace).as_posix(),
                            "line": line_number,
                            "text": line.strip()[:240],
                        })
    return findings, errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path,
                        default=Path(__file__).resolve().parents[2])
    parser.add_argument("--json", type=Path)
    parser.add_argument("--markdown", type=Path)
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    findings, errors = scan(workspace)
    summary = {
        "repositories": len(repository_roots(workspace)),
        "findings": len(findings),
        "errors": len(errors),
    }
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps({"summary": summary, "findings": findings, "errors": errors},
                       ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    if args.markdown:
        lines = [
            "# Legacy MuPDF boundary removal gate",
            "",
            f"- Repositories scanned: {summary['repositories']}",
            f"- Findings: {summary['findings']}",
            f"- Read errors: {summary['errors']}",
            "",
        ]
        if findings:
            lines.append("| Kind | Location | Text |")
            lines.append("| --- | --- | --- |")
            for item in findings:
                lines.append(
                    f"| {item['kind']} | `{item['path']}:{item['line']}` | "
                    f"`{item['text']}` |"
                )
        else:
            lines.append("No `qw_mupdf_*`, `mupdf_backend.h`, "
                         "`QUIREWISE_WITH_MUPDF`, `<mupdf/...>` or MuPDF CMake "
                         "references were found in production files.")
        lines.extend(["", "## Read errors", ""])
        lines.extend(f"- {error}" for error in errors) if errors else lines.append("- None")
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, sort_keys=True))
    return 0 if not findings and not errors else 1


if __name__ == "__main__":
    sys.exit(main())
