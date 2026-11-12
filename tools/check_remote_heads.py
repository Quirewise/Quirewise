#!/usr/bin/env python3
"""Record whether each repository's local HEAD is present on its origin.

The release report must not claim that commits are "published" just because
the local lock verifies: a lock can pin commits that no remote can serve. This
tool compares each local HEAD with ``git ls-remote origin HEAD`` and writes a
reviewable JSON record. It is read-only and never pushes anything.

Exit code 0 means the comparison ran; pass --require-pushed to fail when any
repository is behind its remote (the normal state before the release owner
authorizes a push).
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def git(repo: Path, *args: str, timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, text=True, timeout=timeout)


def repositories(workspace: Path) -> list[Path]:
    return [workspace / "app", workspace / "external-consumer-template"] + [
        path for path in sorted((workspace / "libraries").glob("quirewise-*"))
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--require-pushed", action="store_true")
    args = parser.parse_args()
    workspace = args.workspace.resolve()

    entries: list[dict[str, object]] = []
    for repo in repositories(workspace):
        name = repo.relative_to(workspace).as_posix()
        try:
            local = git(repo, "rev-parse", "HEAD").stdout.strip()
        except (OSError, subprocess.SubprocessError):
            local = ""
        remote = None
        error = None
        try:
            completed = git(repo, "ls-remote", "origin", "HEAD",
                            timeout=args.timeout)
            line = completed.stdout.strip().splitlines()
            if completed.returncode == 0 and line:
                remote = line[0].split()[0]
            else:
                error = completed.stderr.strip() or "no remote HEAD"
        except (OSError, subprocess.SubprocessError) as exc:
            error = str(exc)
        entries.append({
            "repo": name,
            "local": local,
            "remote": remote,
            "pushed": bool(local and remote and local == remote),
            "error": error,
        })

    pushed = sum(1 for item in entries if item["pushed"])
    report = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total": len(entries),
        "pushed_count": pushed,
        "all_pushed": pushed == len(entries),
        "repositories": entries,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8", newline="\n")
    print(f"remote heads: {pushed}/{len(entries)} local HEADs are on origin")
    for item in entries:
        if not item["pushed"]:
            print(f"  not pushed: {item['repo']} {str(item['local'])[:12]} "
                  f"(remote {str(item['remote'])[:12] if item['remote'] else 'n/a'})")
    if args.require_pushed and pushed != len(entries):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
