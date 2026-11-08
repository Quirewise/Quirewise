#!/usr/bin/env python3
"""Build and validate the whole Quirewise workspace from tracked sources.

The runner is intentionally self-contained so the same commands can be used
locally and by CI: it configures, builds, installs and tests every independent
library in dependency order, then configures the external consumer against the
installed prefix, builds the application composition shell, and runs the static
acceptance gates.

Exit code 0 means every requested step succeeded.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

# Topological order: every entry only depends on entries before it.
LIBRARIES = [
    ("quirewise-runtime", "QuirewiseRuntime"),
    ("quirewise-charset", "QuirewiseCharset"),
    ("quirewise-compression", "QuirewiseCompression"),
    ("quirewise-crypto", "QuirewiseCrypto"),
    ("quirewise-archive", "QuirewiseArchive"),
    ("quirewise-data", "QuirewiseData"),
    ("quirewise-image", "QuirewiseImage"),
    ("quirewise-text", "QuirewiseText"),
    ("quirewise-ebook", "QuirewiseEbook"),
    ("quirewise-spreadsheet", "QuirewiseSpreadsheet"),
    ("quirewise-page", "QuirewisePage"),
    ("quirewise-vector", "QuirewiseVector"),
    ("quirewise-audio", "QuirewiseAudio"),
    ("quirewise-comic", "QuirewiseComic"),
    ("quirewise-pdg", "QuirewisePDG"),
    ("quirewise-document", "QuirewiseDocument"),
    ("quirewise-subtitle", "QuirewiseSubtitle"),
]

APP_LINK_OPTIONS = [
    "QUIREWISE_LINK_RUNTIME",
    "QUIREWISE_LINK_IMAGE",
    "QUIREWISE_LINK_ARCHIVE",
    "QUIREWISE_LINK_PAGE",
    "QUIREWISE_LINK_PDG",
    "QUIREWISE_LINK_DOCUMENT",
    "QUIREWISE_LINK_EBOOK",
    "QUIREWISE_LINK_TEXT",
    "QUIREWISE_LINK_DATA",
    "QUIREWISE_LINK_SPREADSHEET",
    "QUIREWISE_LINK_AUDIO",
    "QUIREWISE_LINK_SUBTITLE",
    "QUIREWISE_LINK_VECTOR",
    "QUIREWISE_LINK_COMIC",
]


class Runner:
    def __init__(self, workspace: Path, build_root: Path, install_root: Path,
                 shared: bool, jobs: int, keep: bool, skip_tests: bool):
        self.workspace = workspace
        self.build_root = build_root
        self.install_root = install_root
        self.shared = shared
        self.jobs = jobs
        self.keep = keep
        self.skip_tests = skip_tests
        self.generator = "Ninja" if shutil.which("ninja") else ""
        self.logs = build_root / "logs"
        self.results: list[dict] = []

    def runtime_env(self) -> dict[str, str]:
        env = os.environ.copy()
        if self.shared:
            env["PATH"] = str(self.install_root / "bin") + os.pathsep + env.get("PATH", "")
            env["LD_LIBRARY_PATH"] = (str(self.install_root / "lib") + ":"
                                      + env.get("LD_LIBRARY_PATH", ""))
        return env

    def run(self, name: str, command: list[str], cwd: Path | None = None,
            expect: int = 0) -> bool:
        self.logs.mkdir(parents=True, exist_ok=True)
        log_path = self.logs / f"{name}.log"
        started = time.time()
        printable = " ".join(command)
        with log_path.open("w", encoding="utf-8") as log:
            log.write(f"$ {printable}\n")
            log.flush()
            completed = subprocess.run(
                command, cwd=cwd or self.workspace, env=self.runtime_env(),
                stdout=log, stderr=subprocess.STDOUT, text=True,
            )
        elapsed = time.time() - started
        ok = completed.returncode == expect
        self.results.append({
            "step": name, "command": printable,
            "exit_code": completed.returncode,
            "expected": expect, "ok": ok,
            "seconds": round(elapsed, 2),
            "log": (str(log_path.relative_to(self.workspace))
                    if log_path.is_relative_to(self.workspace) else str(log_path)),
        })
        status = "ok" if ok else "FAIL"
        print(f"[{status}] {name} ({elapsed:.1f}s, exit {completed.returncode})")
        if not ok:
            tail = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-25:]
            print("\n".join(tail))
        return ok

    def cmake(self, name: str, source: Path, build: Path,
              prefix_path: str, extra: list[str]) -> bool:
        if build.exists() and not self.keep:
            shutil.rmtree(build)
        command = [
            "cmake", "-S", str(source), "-B", str(build),
        ] + (["-G", self.generator] if self.generator else []) + [
            "-DCMAKE_BUILD_TYPE=Release",
            f"-DCMAKE_INSTALL_PREFIX={self.install_root}",
            f"-DCMAKE_PREFIX_PATH={prefix_path}",
            "-DCMAKE_FIND_USE_PACKAGE_REGISTRY=OFF",
            "-DCMAKE_FIND_USE_SYSTEM_PACKAGE_REGISTRY=OFF",
            "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON",
            "-DBUILD_TESTING=ON",
        ] + extra
        if not self.run(f"{name}.configure", command):
            return False
        if not self.run(f"{name}.build", ["cmake", "--build", str(build),
                                          "--parallel", str(self.jobs)]):
            return False
        if not self.run(f"{name}.install", ["cmake", "--install", str(build)]):
            return False
        return True

    def ctest(self, name: str, build: Path) -> bool:
        return self.run(f"{name}.ctest", [
            "ctest", "--test-dir", str(build), "--output-on-failure",
            "--timeout", "900",
        ])

    def build_libraries(self) -> bool:
        prefix_path = str(self.install_root)
        extra = ["-DQUIREWISE_BUILD_SHARED=ON"] if self.shared else []
        all_ok = True
        for index, (repo_name, package_name) in enumerate(LIBRARIES, start=1):
            source = self.workspace / "libraries" / repo_name
            build = self.build_root / repo_name
            print(f"== {index}/{len(LIBRARIES)} {repo_name} ({package_name})")
            ok = self.cmake(repo_name, source, build, prefix_path, extra)
            if ok and not self.skip_tests:
                ok = self.ctest(repo_name, build)
            if not ok:
                all_ok = False
                if not self.keep:
                    break
        return all_ok

    def install_licenses(self) -> bool:
        """Copy every first-party LICENSE into the installed release tree.

        The workspace-root LICENSE is a workspace asset, not a repository file.
        CI only checks out ``app/`` into the workspace root, so fall back to the
        application LICENSE and still produce the same 20-file installation.
        """
        docroot = self.install_root / "share" / "doc" / "quirewise"
        docroot.mkdir(parents=True, exist_ok=True)
        root_license = self.workspace / "LICENSE"
        if not root_license.is_file():
            root_license = self.workspace / "app" / "LICENSE"
        entries = [
            (root_license, docroot / "LICENSE"),
            (self.workspace / "app" / "LICENSE", docroot / "application" / "LICENSE"),
            (self.workspace / "external-consumer-template" / "LICENSE",
             docroot / "external-consumer-template" / "LICENSE"),
        ]
        entries += [
            (self.workspace / "libraries" / name / "LICENSE",
             docroot / name / "LICENSE")
            for name, _ in LIBRARIES
        ]
        copied = 0
        for source, destination in entries:
            if not source.is_file():
                print(f"[FAIL] license missing: {source}")
                return False
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            copied += 1
        self.results.append({
            "step": "licenses.copy", "command": "copy LICENSE files",
            "exit_code": 0, "expected": 0, "ok": True, "seconds": 0.0,
            "log": str(docroot),
        })
        print(f"[ok] licenses.copy ({copied} files)")
        return True

    def build_consumer(self) -> bool:
        source = self.workspace / "external-consumer-template"
        build = self.build_root / "external-consumer"
        generator = ["-G", self.generator] if self.generator else []
        if not self.run("consumer.configure", [
            "cmake", "-S", str(source), "-B", str(build), *generator,
            "-DCMAKE_BUILD_TYPE=Release",
            f"-DCMAKE_PREFIX_PATH={self.install_root}",
            "-DCMAKE_FIND_USE_PACKAGE_REGISTRY=OFF",
            "-DCMAKE_FIND_USE_SYSTEM_PACKAGE_REGISTRY=OFF",
        ]):
            return False
        if not self.run("consumer.build", ["cmake", "--build", str(build),
                                           "--parallel", str(self.jobs)]):
            return False
        return self.ctest("consumer", build)

    def build_app(self) -> bool:
        source = self.workspace / "app"
        build = self.build_root / "app"
        extra = [f"-D{option}=ON" for option in APP_LINK_OPTIONS]
        extra.append("-DQUIREWISE_BUILD_PDF_VERIFIER=ON")
        ok = self.cmake("app", source, build, str(self.install_root), extra)
        if not ok:
            return False
        exe = build / "quirewise.exe"
        if not exe.is_file():
            exe = build / "quirewise"
        return self.run("app.smoke", [str(exe), "--libraries"])

    def run_gates(self) -> bool:
        python = sys.executable
        dependency = [python, "app/tools/validate_dependency_graph.py",
                      "--workspace", "."]
        nm = shutil.which("nm")
        if nm and not self.shared:
            # The actual link closure is reconstructed from static archives;
            # shared installs expose import libraries/SONAMEs instead.
            dependency += ["--actual-prefix", str(self.install_root), "--nm", nm]
        gates = [
            ("gate.dependency-graph", dependency),
            ("gate.header-ownership",
             [python, "app/tools/verify_header_ownership.py",
              "--workspace", ".", "--strict"]),
            ("gate.release-boundaries",
             [python, "app/tools/audit_release_boundaries.py",
              "--workspace", "."]),
            ("gate.mupdf-removal",
             [python, "app/tools/audit_mupdf_removal.py",
              "--workspace", "."]),
        ]
        all_ok = True
        for name, command in gates:
            if not self.run(name, command):
                all_ok = False
        return all_ok

    def summary(self) -> dict:
        return {
            "workspace": str(self.workspace),
            "install_root": str(self.install_root),
            "shared": self.shared,
            "steps": self.results,
            "failed": [item["step"] for item in self.results if not item["ok"]],
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path,
                        default=Path(__file__).resolve().parents[2])
    parser.add_argument("--build-dir", type=Path)
    parser.add_argument("--install-dir", type=Path)
    parser.add_argument("--shared", action="store_true")
    parser.add_argument("--jobs", type=int, default=max(2, (os.cpu_count() or 4) // 2))
    parser.add_argument("--keep", action="store_true",
                        help="reuse existing build directories instead of cleaning them")
    parser.add_argument("--skip-consumer", action="store_true")
    parser.add_argument("--skip-app", action="store_true")
    parser.add_argument("--skip-gates", action="store_true")
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument("--summary", type=Path)
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    suffix = "shared" if args.shared else "static"
    build_root = (args.build_dir or workspace / ".tmp" / "acceptance" / suffix).resolve()
    install_root = (args.install_dir or build_root / "install").resolve()
    build_root.mkdir(parents=True, exist_ok=True)
    # A reused install prefix keeps headers that a package stopped installing.
    # Clean the default prefix so the record only contains current outputs.
    if not args.keep and args.install_dir is None and install_root.exists():
        shutil.rmtree(install_root)
    install_root.mkdir(parents=True, exist_ok=True)

    runner = Runner(workspace, build_root, install_root, args.shared,
                    args.jobs, args.keep, args.skip_tests)
    ok = runner.build_libraries()
    if ok:
        ok = runner.install_licenses()
    if ok and not args.skip_consumer:
        ok = runner.build_consumer()
    if ok and not args.skip_app:
        ok = runner.build_app()
    if not args.skip_gates:
        ok = runner.run_gates() and ok

    summary = runner.summary()
    if args.summary:
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        args.summary.write_text(json.dumps(summary, indent=2) + "\n",
                                encoding="utf-8")
    print(json.dumps({"failed": summary["failed"], "steps": len(summary["steps"])},
                     sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
