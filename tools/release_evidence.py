#!/usr/bin/env python3
"""Regenerate every derived release artifact from four acceptance matrices.

The four acceptance runs produce build trees, summaries and logs; the release
report is rendered from a smaller, reviewable evidence set under the release
directory. This script is the single entry point that turns one into the other:

* copies the four ``--summary`` files into the release directory;
* regenerates SBOMs, license inventories and install manifests;
* runs public-header, coverage, dependency, boundary, vendored, MuPDF and
  private-header gates;
* records repository heads and the local toolchain.

It does not build or test anything and it does not sign anything. Run the four
matrices first (see app/docs/release-process.md), then this script, then the
independent review, then release_self_audit.py and render_release_report.py.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


def run(command: list[str], root: Path, capture: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        command, cwd=root,
        capture_output=capture, text=True,
    )


def os_label() -> str:
    if os.name == "nt":
        try:
            build = sys.getwindowsversion().build
        except AttributeError:
            build = 0
        return f"Windows {'11' if build >= 22000 else '10'} {platform.machine()}"
    return f"{platform.system()} {platform.release()} {platform.machine()}"


def toolchain() -> dict[str, str]:
    def first_line(command: list[str]) -> str:
        try:
            completed = subprocess.run(command, capture_output=True, text=True,
                                       timeout=30)
        except (OSError, subprocess.TimeoutExpired):
            return "unknown"
        lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
        return lines[0] if lines else "unknown"

    cmake = first_line(["cmake", "--version"])
    if cmake.startswith("cmake version "):
        cmake = cmake[len("cmake version "):]
    cc = first_line(["cc", "--version"])
    if cc == "unknown":
        cc = first_line(["gcc", "--version"])
    return {
        "os": os_label(),
        "cmake": cmake,
        "ninja": first_line(["ninja", "--version"]),
        "cc": cc,
        "python": platform.python_version(),
        "generator": "Ninja" if shutil.which("ninja") else "default",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path("."))
    parser.add_argument("--release-dir", type=Path,
                        default=Path(".tmp/release"))
    parser.add_argument("--static-summary", type=Path, required=True)
    parser.add_argument("--shared-summary", type=Path, required=True)
    parser.add_argument("--linux-static-summary", type=Path, required=True)
    parser.add_argument("--linux-shared-summary", type=Path, required=True)
    parser.add_argument("--sanitizer-summary", type=Path,
                        help="optional Linux ASan+UBSan matrix summary")
    parser.add_argument("--static-prefix", type=Path, required=True)
    parser.add_argument("--shared-prefix", type=Path, required=True)
    parser.add_argument("--nm", default="nm")
    args = parser.parse_args()
    root = args.workspace.resolve()
    release = (root / args.release_dir).resolve()
    release.mkdir(parents=True, exist_ok=True)

    summary_paths = {
        "static-summary.json": args.static_summary,
        "shared-summary.json": args.shared_summary,
        "linux-static-summary.json": args.linux_static_summary,
        "linux-shared-summary.json": args.linux_shared_summary,
    }
    for name, source in summary_paths.items():
        source = (root / source).resolve()
        if not source.is_file():
            print(f"error: missing summary {source}", file=sys.stderr)
            return 2
        shutil.copyfile(source, release / name)
    if args.sanitizer_summary:
        source = (root / args.sanitizer_summary).resolve()
        if not source.is_file():
            print(f"error: missing sanitizer summary {source}", file=sys.stderr)
            return 2
        shutil.copyfile(source, release / "sanitizer-summary.json")
        print("[ok] sanitizer-summary")

    results: list[tuple[str, bool, str]] = []

    def record(name: str, completed: subprocess.CompletedProcess,
               output_file: Path | None = None) -> bool:
        ok = completed.returncode == 0
        if output_file is not None:
            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_text(completed.stdout, encoding="utf-8",
                                   newline="\n")
        tail = (completed.stdout.strip().splitlines() or [""])[-1]
        if not ok:
            tail = (completed.stderr.strip().splitlines() or [tail])[-1]
        results.append((name, ok, tail))
        print(f"[{'ok' if ok else 'FAIL'}] {name}")
        return ok

    def python(*arguments: str) -> list[str]:
        return [sys.executable, "app/tools/" + arguments[0], *arguments[1:]]

    # SBOM, license inventory and install manifests.
    for mode, prefix in (("static", args.static_prefix),
                         ("shared", args.shared_prefix)):
        prefix = (root / prefix).resolve()
        record(
            f"sbom-{mode}",
            run(python("generate_sbom.py", "--workspace", ".",
                       "--out", str(release / f"sbom-{mode}.cdx.json"),
                       "--license-out",
                       str(release / f"license-inventory-{mode}.json"),
                       "--manifest-prefix", str(prefix),
                       "--manifest-out",
                       str(release / f"install-manifest-{mode}.json")), root),
        )
        record(
            f"public-headers-{mode}",
            run(python("verify_public_headers.py", "--prefix", str(prefix),
                       "--json",
                       str(release / f"public-headers-{mode}.json")), root),
        )

    record("library-surfaces",
           run(python("inventory_library_surfaces.py", "--workspace", ".",
                      "--json", str(release / "library-surfaces.json"),
                      "--markdown", str(release / "library-surfaces.md")), root))
    record("dependency-closure",
           run(python("validate_dependency_graph.py", "--workspace", ".",
                      "--actual-prefix",
                      str((root / args.static_prefix).resolve()),
                      "--nm", args.nm,
                      "--json-out", str(release / "dependency-closure.json")),
               root))
    record("error-taxonomy",
           run(python("verify_error_taxonomy.py"), root),
           release / "error-taxonomy.txt")
    record("resource-limits",
           run(python("verify_resource_limits.py"), root),
           release / "resource-limits.txt")
    record("header-ownership",
           run(python("verify_header_ownership.py", "--workspace", ".",
                      "--strict",
                      "--json-out", str(release / "header-ownership.json")),
               root))
    record("release-boundaries",
           run(python("audit_release_boundaries.py", "--workspace", ".",
                      "--json", str(release / "release-boundaries.json"),
                      "--markdown", str(release / "release-boundaries.md")),
               root))
    record("vendored-sources",
           run(python("audit_vendored_sources.py", "--workspace", ".",
                      "--json-out", str(release / "vendored-sources.json")),
               root))
    record("mupdf-removal",
           run(python("audit_mupdf_removal.py", "--workspace", ".",
                      "--json", str(release / "mupdf-removal.json")), root))
    record("private-header-copies",
           run(python("verify_private_header_copies.py", "--workspace", ".",
                      "--json",
                      str(release / "private-header-copies.json")), root))
    record("consumer-coverage",
           run(python("check_consumer_coverage.py", "--workspace", ".",
                      "--prefix",
                      str((root / args.static_prefix).resolve()),
                      "--nm", args.nm,
                      "--json", str(release / "consumer-coverage.json"),
                      "--mapping-out",
                      str(release / "consumer-mapping.json"),
                      "--strict"), root))
    record("repository-heads",
           run(python("write_repository_heads.py", "--workspace", ".",
                      "--out",
                      str(release / "repository-heads.json")), root))

    toolchain_file = release / (
        "toolchain-windows.json" if os.name == "nt" else "toolchain-linux.json")
    toolchain_file.write_text(
        json.dumps(toolchain(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n",
    )
    print(f"[ok] toolchain ({toolchain_file.name})")

    for name in summary_paths:
        data = json.loads((release / name).read_text(encoding="utf-8"))
        steps = len(data.get("steps", []))
        failed = data.get("failed", [])
        print(f"  {name}: {steps} step(s), failed={failed or '[]'}")
        if failed:
            results.append((name, False, f"{len(failed)} failed step(s)"))
    if args.sanitizer_summary:
        data = json.loads((release / "sanitizer-summary.json").read_text(
            encoding="utf-8"))
        steps = len(data.get("steps", []))
        failed = data.get("failed", [])
        print(f"  sanitizer-summary.json: {steps} step(s), "
              f"failed={failed or '[]'}")
        if failed:
            results.append(("sanitizer-summary", False,
                            f"{len(failed)} failed step(s)"))

    failed_names = [name for name, ok, _ in results if not ok]
    if failed_names:
        print("failed evidence steps: " + ", ".join(failed_names),
              file=sys.stderr)
        return 1
    print("release evidence regenerated; next: reviewer sign-off, "
          "release_self_audit.py, render_release_report.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
