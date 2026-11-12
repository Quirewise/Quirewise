#!/usr/bin/env python3
"""Detect drift between private headers intentionally copied across packages.

Several libraries keep an identical private copy of a shared contract header
(for example ``src/core/byte_utils.h``) so each package stays independently
buildable without a new public dependency. Those copies are only safe while
they stay byte-identical. This gate pins the current identical copies in
``app/tools/private-header-copies.json`` and fails when a pinned repository
changes its bytes.

Rules:

* deleting a copy is always allowed (the allow-list can only shrink);
* repositories with their own variant of a same-named header are ignored;
* a new identical copy of a pinned path is accepted and reported;
* a pinned repository whose copy exists with different bytes fails the gate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

DEFAULT_MANIFEST = Path("app/tools/private-header-copies.json")


def private_headers(workspace: Path):
    libraries = workspace / "libraries"
    for repo in sorted(libraries.glob("quirewise-*")):
        src = repo / "src"
        if not src.is_dir():
            continue
        for path in sorted(src.rglob("*.h")):
            yield repo.name, path.relative_to(src).as_posix(), path


def scan(workspace: Path) -> dict[str, dict[str, list[str]]]:
    """path -> sha256 -> repositories carrying that variant."""

    groups: dict[str, dict[str, list[str]]] = {}
    for repo, relative, path in private_headers(workspace):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        groups.setdefault(relative, {}).setdefault(digest, []).append(repo)
    return groups


def build_manifest(groups: dict[str, dict[str, list[str]]]) -> dict:
    pinned: dict[str, dict[str, object]] = {}
    for relative, variants in sorted(groups.items()):
        shared = [(digest, repos) for digest, repos in variants.items()
                  if len(repos) >= 2]
        if len(shared) != 1:
            # No dominant shared copy (or several), so it is not a shared
            # contract; leave it to the package that owns the variant.
            continue
        digest, repos = shared[0]
        pinned[relative] = {
            "sha256": digest,
            "repositories": sorted(repos),
        }
    return {"paths": pinned}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path("."))
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--write-manifest", action="store_true",
                        help="regenerate the pinned manifest from this tree")
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    manifest_path = (workspace / args.manifest
                     if not args.manifest.is_absolute() else args.manifest)
    groups = scan(workspace)

    if args.write_manifest:
        manifest = build_manifest(groups)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8", newline="\n",
        )
        print(f"wrote {manifest_path.name}: {len(manifest['paths'])} pinned path(s)")
        return 0

    if not manifest_path.is_file():
        print(f"error: missing {manifest_path}; run with --write-manifest",
              file=sys.stderr)
        return 2
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    drift: list[dict[str, str]] = []
    accepted: list[dict[str, object]] = []
    for relative, record in sorted(manifest.get("paths", {}).items()):
        variants = groups.get(relative, {})
        pinned_digest = record["sha256"]
        for repo in record["repositories"]:
            found = [digest for digest, repos in variants.items()
                     if repo in repos]
            if not found:
                continue  # deletion is allowed
            if found[0] != pinned_digest:
                drift.append({
                    "path": relative,
                    "repository": repo,
                    "expected": pinned_digest,
                    "actual": found[0],
                })
        for digest, repos in variants.items():
            if digest == pinned_digest:
                extra = sorted(set(repos) - set(record["repositories"]))
                if extra:
                    accepted.append({
                        "path": relative,
                        "new_repositories": extra,
                    })

    report = {
        "pinned_paths": len(manifest.get("paths", {})),
        "drift": drift,
        "new_identical_copies": accepted,
    }
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8", newline="\n",
        )

    print(f"private header copies: {report['pinned_paths']} pinned path(s), "
          f"{len(drift)} drifted, {len(accepted)} new identical copy group(s)")
    if drift:
        for item in drift:
            print(f"  drifted: {item['path']} in {item['repository']}",
                  file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
