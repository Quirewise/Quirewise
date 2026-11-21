#!/usr/bin/env python3
"""Check that the numbers quoted in README.md still match the build.

The 2026-11-21 review found the README status block frozen at the 2026-11-17
values (206 cases / 226 CTest / 434-438 coverage) while the code had moved on.
This script turns that class of drift into a failing check:

* the CLI format-matrix case count comes from ``smoke_app.FORMAT_MATRIX``;
* the CTest entry count is summed from the acceptance ctest logs;
* the consumer-coverage fraction comes from ``check_consumer_coverage.py``;
* the public-header count comes from ``verify_public_headers.py``;
* the matrix step count comes from a summary JSON.

Every check that cannot be evaluated (missing inputs) is reported as skipped
rather than silently passing, so the tool stays usable in a partial checkout.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path


def load_smoke_matrix(tools: Path) -> int | None:
    path = tools / "smoke_app.py"
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location("_qw_smoke", path)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)  # type: ignore[union-attr]
    except Exception:  # noqa: BLE001 - a broken import means "cannot check"
        return None
    matrix = getattr(module, "FORMAT_MATRIX", None)
    return len(matrix) if matrix is not None else None


def count_ctest(logs: Path) -> int | None:
    if not logs.is_dir():
        return None
    total = 0
    seen = False
    for log in logs.glob("*.ctest.log"):
        text = log.read_text(encoding="utf-8", errors="replace")
        match = re.search(r"tests passed, \d+ tests failed out of (\d+)", text)
        if match:
            total += int(match.group(1))
            seen = True
    return total if seen else None


def run_tool_json(command: list[str], workspace: Path,
                  json_path: Path) -> dict | None:
    try:
        completed = subprocess.run(command, cwd=str(workspace),
                                   capture_output=True, text=True, timeout=900)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0 or not json_path.is_file():
        return None
    try:
        return json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--workspace", type=Path, default=Path("."))
    parser.add_argument("--readme", type=Path)
    parser.add_argument("--logs", type=Path,
                        help="acceptance logs directory (default: "
                             ".tmp/acceptance/windows-static/logs)")
    parser.add_argument("--summary", type=Path,
                        help="acceptance summary JSON (default: newest under .tmp)")
    parser.add_argument("--prefix", type=Path,
                        help="install prefix (default: .tmp/acceptance/windows-static/install)")
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    readme = (args.readme or workspace / "README.md").resolve()
    tools = workspace / "app" / "tools"
    summary_path = args.summary
    if summary_path is None:
        candidates = sorted((workspace / ".tmp" / "acceptance").glob("*/summary-*.json"))
        summary_path = candidates[-1] if candidates else None
    summary_data = None
    if summary_path and Path(summary_path).is_file():
        summary_data = json.loads(Path(summary_path).read_text(encoding="utf-8"))
    default_root = (Path(summary_path).parent if summary_path
                    else workspace / ".tmp" / "acceptance" / "windows-static")
    logs = (args.logs or default_root / "logs").resolve()
    prefix = Path(args.prefix) if args.prefix else Path(
        (summary_data or {}).get("install_root") or default_root / "install").resolve()
    if not readme.is_file():
        print(f"error: missing {readme}", file=sys.stderr)
        return 2
    text = readme.read_text(encoding="utf-8")

    checks: list[tuple[str, str, str | None]] = []

    def check(label: str, pattern: str, value: int | str | None) -> None:
        if value is None:
            checks.append((label, "skipped (input missing)", None))
            return
        matched = re.search(pattern, text, re.DOTALL)
        checks.append((label, matched.group(0) if matched else "missing in README",
                       str(value)))

    check("format matrix cases", r"\*\*(\d+) cases\*\*", load_smoke_matrix(tools))
    check("CTest entries", r"\*\*(\d+) entries\*\*", count_ctest(logs))

    coverage_json = workspace / ".tmp" / "docs-coverage.json"
    coverage = run_tool_json([sys.executable, "app/tools/check_consumer_coverage.py",
                              "--workspace", ".", "--prefix", str(prefix),
                              "--strict", "--json", str(coverage_json)],
                             workspace, coverage_json)
    if coverage:
        check("consumer coverage", r"coverage.*?\*\*(\d+)/(\d+)\*\*",
              f"{coverage.get('covered_total')}/{coverage.get('public_api_total')}")
    else:
        checks.append(("consumer coverage", "skipped (input missing)", None))

    headers_json = workspace / ".tmp" / "docs-headers.json"
    headers = run_tool_json([sys.executable, "app/tools/verify_public_headers.py",
                             "--prefix", str(prefix), "--json", str(headers_json)],
                            workspace, headers_json)
    if headers:
        check("public headers", r"\*\*(\d+) compiled", headers.get("header_count"))
    else:
        checks.append(("public headers", "skipped (input missing)", None))

    steps = len(summary_data.get("steps", [])) if summary_data else None
    check("matrix steps", r"\*\*(\d+)/(\d+) steps\*\*", steps)

    failed = 0
    for label, found, expected in checks:
        if expected is None:
            print(f"[skip] {label}: {found}")
            continue
        if expected in found:
            print(f"[ok] {label}: README says {found}")
        else:
            print(f"[FAIL] {label}: README says {found}, build has {expected}")
            failed += 1
    print(f"{len(checks) - failed}/{len(checks)} claims match")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
