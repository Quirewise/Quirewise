#!/usr/bin/env python3
"""Check out the sibling Quirewise repositories pinned by app/release-lock.json.

Used by CI and by clean-machine reproduction. Repositories are cloned next to
``app/``; an existing clean checkout is moved to the locked commit, and a dirty
checkout is reported instead of being overwritten.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def run(command: list[str], cwd: Path | None = None) -> int:
    completed = subprocess.run(command, cwd=cwd, text=True)
    return completed.returncode


def git_command(token: str | None, *args: str) -> list[str]:
    command = ["git"]
    if token:
        auth = base64.b64encode(f"x-access-token:{token}".encode()).decode()
        command += ["-c", f"http.extraHeader=Authorization: Basic {auth}"]
    command += list(args)
    return command


def token_candidates(explicit: str | None) -> list[str | None]:
    """Authentication attempts in order: explicit flag, environment, anonymous.

    Trying each candidate keeps a stale or under-scoped token from breaking
    clones that another credential (or anonymous access) can serve.
    """
    tokens: list[str] = []
    for value in (explicit,
                  os.environ.get("QUIREWISE_REPOS_TOKEN"),
                  os.environ.get("GITHUB_TOKEN")):
        if value and value not in tokens:
            tokens.append(value)
    tokens.append(None)
    return tokens


def clone(url: str, repo: Path, tokens: list[str | None]) -> bool:
    for index, token in enumerate(tokens):
        if index and repo.exists():
            # A rejected clone can leave a partial directory behind.
            print("retrying the clone with the next credential", file=sys.stderr)
            shutil.rmtree(repo, ignore_errors=True)
        if run(git_command(token, "clone", "--no-checkout", url, str(repo))) == 0:
            return True
    return False


def fetch_commit(repo: Path, commit: str, tokens: list[str | None]) -> bool:
    for token in tokens:
        if run(git_command(token, "-C", str(repo), "fetch", "--quiet",
                           "origin", commit)) == 0:
            return True
    # Servers that disallow fetching an arbitrary commit fall back to a normal
    # fetch before retrying the exact object.
    for token in tokens:
        if run(git_command(token, "-C", str(repo), "fetch", "--quiet", "--tags",
                           "origin")) == 0:
            break
    return run(["git", "-C", str(repo), "cat-file", "-e",
                f"{commit}^{{commit}}"]) == 0


def checkout(repo: Path, url: str, commit: str,
             tokens: list[str | None]) -> bool:
    fresh = not (repo / ".git").exists()
    if fresh:
        print(f"clone {url} -> {repo}")
        if not clone(url, repo, tokens):
            return False
    else:
        # A fresh --no-checkout clone has an empty working tree, which git
        # reports as every tracked file deleted. Only an existing checkout can
        # be dirty in the sense this guard cares about.
        dirty = subprocess.run(["git", "-C", str(repo), "status", "--porcelain"],
                               capture_output=True, text=True).stdout.strip()
        if dirty:
            print(f"error: {repo} has uncommitted changes", file=sys.stderr)
            return False
    print(f"checkout {commit[:12]} in {repo}")
    if not fetch_commit(repo, commit, tokens):
        return False
    return run(["git", "-C", str(repo), "checkout", "--quiet", "--detach",
                commit]) == 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path,
                        default=Path(__file__).resolve().parents[2])
    parser.add_argument("--lock", type=Path)
    parser.add_argument("--token", default=None,
                        help="token for private siblings; the default tries "
                             "QUIREWISE_REPOS_TOKEN, then GITHUB_TOKEN, then "
                             "anonymous access")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    tokens = token_candidates(args.token)
    workspace = args.workspace.resolve()
    lock_path = args.lock or workspace / "app" / "release-lock.json"
    if not lock_path.is_file():
        print(f"error: missing lock file {lock_path}", file=sys.stderr)
        return 2
    # utf-8-sig so a lock file saved by an editor that adds a BOM still parses;
    # a BOM otherwise breaks every CI run at this line.
    lock = json.loads(lock_path.read_text(encoding="utf-8-sig"))
    failures = []
    for entry in lock["repositories"]:
        repo = workspace / entry["path"]
        if args.verify_only:
            if not (repo / ".git").exists():
                failures.append(f"{entry['path']}: missing")
                continue
            head = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                                  capture_output=True, text=True).stdout.strip()
            if head != entry["commit"]:
                failures.append(f"{entry['path']}: {head[:12]} != {entry['commit'][:12]}")
            continue
        if not checkout(repo, entry["url"], entry["commit"], tokens):
            failures.append(entry["path"])
    if failures:
        print("failed repositories:", ", ".join(failures), file=sys.stderr)
        print("check that every repository in app/release-lock.json is published "
              "and the pinned commit has been pushed", file=sys.stderr)
        return 1
    print(f"workspace at lock {lock['generated_utc']} ({len(lock['repositories'])} repos)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
