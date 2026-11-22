#!/usr/bin/env python3
"""Create and (optionally) push the release tag for one candidate version.

The release process (app/docs/release-process.md) only allows a tag once every
gate has passed, so the checks are part of the tool rather than a checklist:

1. every repository is clean;
2. ``release-lock.json`` matches the checked-out commits;
3. every local HEAD is present on its origin;
4. the release directory holds five green matrix summaries (four platforms
   plus the sanitizer matrix);
5. ``reviewer-signoff.md`` exists and ``release_self_audit.py`` passes without
   ``--allow-pending-signoff``;
6. ``ci-run.json`` in the release directory records a green Actions run on the
   current app HEAD (``conclusion == "success"`` and a matching ``head_sha``).

Without ``--apply`` the tool only reports the tag it would create, which makes
it safe to run during preparation. ``--push`` is required to publish the tags;
nothing is pushed implicitly.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

TAG_PATTERN = re.compile(r"^v\d+\.\d+\.\d+(?:-rc\d+)?$")
SUMMARY_NAMES = (
    "static-summary.json",
    "shared-summary.json",
    "linux-static-summary.json",
    "linux-shared-summary.json",
    "sanitizer-summary.json",
)


def git(repo: Path, *args: str, timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True,
                          text=True, timeout=timeout)


def repositories(workspace: Path) -> list[Path]:
    return [workspace / "app", workspace / "external-consumer-template"] + [
        path for path in sorted((workspace / "libraries").glob("quirewise-*"))
    ]


def run_tool(app: Path, *args: str, timeout: int = 900) -> int:
    return subprocess.run([sys.executable, *args], cwd=str(app.parent),
                          text=True, timeout=timeout).returncode


def check_clean(workspace: Path, repos: list[Path]) -> tuple[bool, str]:
    dirty = [repo.relative_to(workspace).as_posix()
             for repo in repos if git(repo, "status", "--porcelain").stdout.strip()]
    if dirty:
        return False, "dirty repositories: " + ", ".join(dirty)
    return True, f"{len(repos)} repositories clean"


def check_lock(workspace: Path) -> tuple[bool, str]:
    app = workspace / "app"
    code = run_tool(app, str(app / "tools" / "fetch_workspace.py"),
                    "--workspace", str(workspace), "--verify-only")
    return code == 0, "release-lock matches the checkouts" if code == 0 else \
        "release-lock does not match the checkouts"


def check_remote(workspace: Path, out: Path) -> tuple[bool, str]:
    app = workspace / "app"
    code = run_tool(app, str(app / "tools" / "check_remote_heads.py"),
                    "--workspace", str(workspace), "--out", str(out),
                    "--require-pushed", "--timeout", "60")
    return code == 0, "every local HEAD is on its origin" if code == 0 else \
        "some local HEADs are missing on origin (see the report above)"


def check_matrices(release: Path) -> tuple[bool, str]:
    missing = [name for name in SUMMARY_NAMES if not (release / name).is_file()]
    if missing:
        return False, "missing matrix summaries: " + ", ".join(missing)
    failures = []
    for name in SUMMARY_NAMES:
        data = json.loads((release / name).read_text(encoding="utf-8"))
        if data.get("failed"):
            failures.append(f"{name}: {', '.join(data['failed'])}")
    if failures:
        return False, "matrix failures: " + "; ".join(failures)
    steps = [len(json.loads((release / name).read_text(encoding="utf-8"))
                 .get("steps", [])) for name in SUMMARY_NAMES]
    return True, f"5 matrices green ({steps[0]} steps each)"


def check_signoff(release: Path, app_head: str) -> tuple[bool, str]:
    """A signature only counts when it names the commit it approves.

    The file must exist, mention the app HEAD it was written against (at least
    the first seven characters) and state a passing conclusion, so a stale or
    blank template cannot pass the gate.
    """
    signoff = release / "reviewer-signoff.md"
    if not signoff.is_file():
        return False, "reviewer-signoff.md is missing"
    text = signoff.read_text(encoding="utf-8-sig", errors="replace")
    lowered = text.lower()
    head = app_head.strip().lower()
    if head and head[:7] not in lowered and head not in lowered:
        return False, (f"reviewer-signoff.md does not name the app HEAD "
                       f"{head[:7]}")
    passed = any(marker in lowered
                 for marker in ("通过", "pass", "approved", "approve"))
    if not passed:
        return False, "reviewer-signoff.md does not record a passing conclusion"
    return True, "reviewer sign-off names the app HEAD and passes"


def check_docs(workspace: Path, static_prefix: Path) -> tuple[bool, str]:
    app = workspace / "app"
    code = run_tool(app, str(app / "tools" / "verify_docs_claims.py"),
                    "--workspace", str(workspace),
                    "--prefix", str(static_prefix))
    return code == 0, ("README claims match the build" if code == 0 else
                       "README claims are stale: run verify_docs_claims.py")


def check_ci(release: Path, app_head: str) -> tuple[bool, str]:
    path = release / "ci-run.json"
    if not path.is_file():
        return False, "no ci-run.json: record the successful Actions run first"
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if data.get("conclusion") != "success":
        return False, (f"recorded CI run {data.get('run_number')} concluded "
                       f"{data.get('conclusion')}")
    head = str(data.get("head_sha") or "")
    if head != app_head:
        return False, (f"recorded CI run ran on {head[:12] or 'unknown'}, not "
                       f"the current app HEAD {app_head[:12]}")
    return True, (f"CI run {data.get('run_number')} is green on "
                  f"{data.get('repository', 'an unknown repository')}")


def check_audit(workspace: Path, release: Path, static_prefix: Path,
                shared_prefix: Path, report: Path) -> tuple[bool, str]:
    app = workspace / "app"
    args = [str(app / "tools" / "release_self_audit.py"),
            "--workspace", str(workspace),
            "--release-dir", str(release),
            "--static-prefix", str(static_prefix),
            "--shared-prefix", str(shared_prefix),
            "--require-sanitizer", "--require-pushed"]
    if report.is_file():
        args += ["--report", str(report)]
    code = run_tool(app, *args)
    return code == 0, "self-audit PASS" if code == 0 else "self-audit did not pass"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--workspace", type=Path, default=Path("."))
    parser.add_argument("--version", required=True,
                        help="annotated tag to create, for example v0.3.0-rc1")
    parser.add_argument("--release-dir", type=Path,
                        help="release evidence directory (default: the newest "
                             "directory under .tmp/release)")
    parser.add_argument("--report", type=Path,
                        help="rendered acceptance report used by the audit")
    parser.add_argument("--apply", action="store_true",
                        help="create the tags locally once every gate passes")
    parser.add_argument("--push", action="store_true",
                        help="push the created tags to origin (implies --apply)")
    parser.add_argument("--offline-preview", action="store_true",
                        help="skip the origin lookup so a dry run finishes on a "
                             "flaky network; never allowed with --apply")
    args = parser.parse_args()

    if not TAG_PATTERN.match(args.version):
        parser.error(f"invalid version {args.version!r}: expected vX.Y.Z or vX.Y.Z-rcN")
    if args.push:
        args.apply = True
    if args.offline_preview and args.apply:
        parser.error("--offline-preview cannot be combined with --apply/--push")

    workspace = args.workspace.resolve()
    app = workspace / "app"
    repos = repositories(workspace)
    release = (args.release_dir or sorted(
        (workspace / ".tmp" / "release").glob("*"))[-1]).resolve()
    report = (args.report or workspace / "docs" / "reports" /
              f"RELEASE_ACCEPTANCE_REPORT_{release.name}.md").resolve()
    static_prefix = workspace / ".tmp" / "acceptance" / "windows-static" / "install"
    shared_prefix = workspace / ".tmp" / "acceptance" / "windows-shared" / "install"

    checks = [
        ("repositories", lambda: check_clean(workspace, repos)),
        ("lock", lambda: check_lock(workspace)),
        ("remote", (lambda: (True, "skipped by --offline-preview"))
         if args.offline_preview else
         (lambda: check_remote(workspace, release / "remote-heads.json"))),
        ("matrices", lambda: check_matrices(release)),
        ("docs", lambda: check_docs(workspace, static_prefix)),
        ("signoff", lambda: check_signoff(
            release, git(app, "rev-parse", "HEAD").stdout.strip())),
        ("ci", lambda: check_ci(release, git(app, "rev-parse", "HEAD").stdout.strip())),
        ("audit", lambda: check_audit(workspace, release, static_prefix,
                                      shared_prefix, report)),
    ]
    failed = 0
    for name, probe in checks:
        try:
            ok, detail = probe()
        except subprocess.TimeoutExpired:
            ok, detail = False, "timed out"
        print(f"[{'ok' if ok else 'FAIL'}] {name}: {detail}")
        if not ok:
            failed += 1
    if failed:
        print(f"\n{failed} gate(s) failed; {args.version} was not created.")
        return 1

    message = f"Quirewise {args.version}"
    if not args.apply:
        print(f"\nall gates passed: would tag {len(repos)} repositories as "
              f"{args.version}")
        return 0

    created = []
    for repo in repos:
        name = repo.relative_to(workspace).as_posix()
        existing = git(repo, "tag", "--list", args.version).stdout.strip()
        if existing:
            print(f"skip {name}: tag {args.version} already exists")
            continue
        result = git(repo, "tag", "-a", args.version, "-m", message,
                     timeout=120)
        if result.returncode != 0:
            print(f"error: cannot tag {name}: {result.stderr.strip()}")
            return 1
        created.append(name)
    print(f"created {args.version} in {len(created)} repositories")
    if not args.push:
        print("not pushed (pass --push to publish)")
        return 0
    for repo in repos:
        name = repo.relative_to(workspace).as_posix()
        for attempt in range(1, 6):
            result = git(repo, "push", "origin", args.version, timeout=300)
            if result.returncode == 0:
                break
            print(f"retry {name} tag push ({attempt}/5): "
                  f"{result.stderr.strip().splitlines()[-1] if result.stderr else ''}")
        else:
            print(f"error: cannot push the tag in {name}")
            return 1
    print(f"pushed {args.version} from {len(repos)} repositories")
    return 0


if __name__ == "__main__":
    sys.exit(main())
