#!/usr/bin/env python3
"""Write ``.tmp/release/repository-heads.json`` from the current checkout.

The release report reads this file for its commit-baseline table. Each entry
records the repository name, HEAD commit, branch and whether the working tree
is clean.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def git(repo: Path, *args: str) -> str:
    try:
        completed = subprocess.run(["git", "-C", str(repo), *args],
                                   capture_output=True, text=True, check=False,
                                   timeout=60)
    except subprocess.TimeoutExpired as error:
        raise SystemExit(f"git {' '.join(args)} timed out in {repo}") from error
    if completed.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed in {repo}: "
                         f"{completed.stderr.strip()}")
    return completed.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path,
                        default=Path(__file__).resolve().parents[2])
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    root = args.workspace.resolve()
    repos = [root / "app", root / "external-consumer-template"]
    repos += sorted((root / "libraries").glob("quirewise-*"))
    out = args.out or root / ".tmp" / "release" / "repository-heads.json"

    entries = []
    for repo in repos:
        entries.append({
            "repo": "app" if repo.name == "app" else repo.name,
            "commit": git(repo, "rev-parse", "HEAD"),
            "branch": git(repo, "branch", "--show-current"),
            "clean": not git(repo, "status", "--porcelain"),
        })
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(entries, indent=4) + "\n", encoding="utf-8")
    print(f"wrote {out} ({len(entries)} repositories)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
