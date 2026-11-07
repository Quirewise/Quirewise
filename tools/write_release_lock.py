#!/usr/bin/env python3
"""Write app/release-lock.json from the current workspace Git state.

The lock pins every sibling repository to the commit used by the release
acceptance run. CI and clean-machine reproduction use the lock to check out the
same sources without relying on branch tips.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def git(repo: Path, *args: str) -> str:
    completed = subprocess.run(["git", "-C", str(repo), *args],
                               capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed in {repo}: {completed.stderr.strip()}")
    return completed.stdout.strip()


def normalise_url(url: str) -> str:
    if url.endswith(".git"):
        return url
    return url + ".git"


def repository_url(repo: Path, url_base: str) -> str:
    completed = subprocess.run(["git", "-C", str(repo), "remote", "get-url", "origin"],
                               capture_output=True, text=True, check=False)
    if completed.returncode == 0 and completed.stdout.strip():
        return normalise_url(completed.stdout.strip())
    # The three new libraries were created locally before their remotes existed.
    return normalise_url(f"{url_base.rstrip('/')}/{repo.name}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path,
                        default=Path(__file__).resolve().parents[2])
    parser.add_argument("--out", type=Path)
    parser.add_argument("--url-base", default="https://github.com/Quirewise",
                        help="fallback URL base for repositories without an origin remote")
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    entries = []
    roots = sorted((workspace / "libraries").glob("quirewise-*"))
    roots.append(workspace / "external-consumer-template")
    for repo in roots:
        if not (repo / ".git").exists():
            continue
        dirty = bool(git(repo, "status", "--porcelain"))
        if dirty and not args.allow_dirty:
            raise SystemExit(f"dirty repository, commit first: {repo}")
        entries.append({
            "path": repo.relative_to(workspace).as_posix(),
            "url": repository_url(repo, args.url_base),
            "commit": git(repo, "rev-parse", "HEAD"),
        })
    lock = {
        "schema": 1,
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "note": "Pin of the sibling repositories consumed by the Quirewise release.",
        "repositories": entries,
    }
    out = args.out or workspace / "app" / "release-lock.json"
    out.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out} ({len(entries)} repositories)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
