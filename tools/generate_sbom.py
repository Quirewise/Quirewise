#!/usr/bin/env python3
"""Generate a CycloneDX-style SBOM and a bundled-source license inventory.

The workspace has no package manager metadata, so the SBOM is derived from the
repositories themselves:

* every ``libraries/quirewise-*`` directory becomes a ``library`` component with
  its CMake project version, git commit and dirty flag,
* every ``third_party`` / bundled-SDK directory becomes a component with the
  license evidence that actually exists on disk,
* declared ``find_package(QuirewiseX CONFIG)`` edges become ``dependencies``.

``--manifest-prefix`` additionally hashes every file in an installed prefix so a
release package can be reviewed field by field.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_VERSION_RE = re.compile(
    r"project\(\s*([A-Za-z0-9_]+)\s+VERSION\s+([0-9]+(?:\.[0-9]+)*)"
)
DEPENDENCY_RE = re.compile(r"find_package\(\s*(Quirewise[A-Za-z0-9_]+)\s+CONFIG")

BUNDLED_LICENSES: tuple[dict[str, object], ...] = (
    {
        "match": "stb",
        "name": "stb_image",
        "version": "2.30",
        "license": "MIT OR Unlicense",
        "note": "license text embedded at the end of stb_image.h",
    },
    {
        "match": "aes",
        "name": "tiny-AES-c",
        "version": "unversioned",
        "license": "Unlicense",
        "note": "UNLICENSE.txt bundled in third_party/aes",
    },
    {
        "match": "lzma_sdk",
        "name": "LZMA SDK (7-Zip)",
        "version": "unversioned",
        "license": "Public Domain",
        "note": "upstream LZMA SDK is public domain; no license file is bundled",
    },
)


def run_git(repo: Path, *args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    if completed.returncode != 0:
        return ""
    return completed.stdout.strip()


def package_name(library: Path) -> str:
    text = (library / "CMakeLists.txt").read_text(encoding="utf-8", errors="replace")
    match = PROJECT_VERSION_RE.search(text)
    return match.group(1) if match else library.name


def package_version(library: Path) -> str:
    text = (library / "CMakeLists.txt").read_text(encoding="utf-8", errors="replace")
    match = PROJECT_VERSION_RE.search(text)
    return match.group(2) if match else "0.0.0"


def declared_dependencies(library: Path) -> list[str]:
    text = (library / "CMakeLists.txt").read_text(encoding="utf-8", errors="replace")
    return sorted({match.group(1) for match in DEPENDENCY_RE.finditer(text)})


def library_components(workspace: Path) -> list[dict[str, object]]:
    components: list[dict[str, object]] = []
    for library in sorted((workspace / "libraries").glob("quirewise-*")):
        if not (library / "CMakeLists.txt").is_file():
            continue
        name = package_name(library)
        version = package_version(library)
        commit = run_git(library, "rev-parse", "HEAD")
        dirty = bool(run_git(library, "status", "--porcelain"))
        components.append(
            {
                "type": "library",
                "bom-ref": f"pkg:generic/quirewise/{library.name}@{version}",
                "name": library.name,
                "group": "quirewise",
                "version": version,
                "purl": f"pkg:generic/quirewise/{library.name}@{version}",
                "properties": [
                    {"name": "cmake.project", "value": name},
                    {"name": "git.commit", "value": commit or "unknown"},
                    {"name": "git.dirty", "value": "true" if dirty else "false"},
                    {"name": "path", "value": library.relative_to(workspace).as_posix()},
                ],
            }
        )
    return components


def bundled_components(workspace: Path) -> list[dict[str, object]]:
    components: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()
    candidates: list[tuple[Path, str]] = []
    for library in sorted((workspace / "libraries").glob("quirewise-*")):
        third_party = library / "third_party"
        if third_party.is_dir():
            for entry in sorted(third_party.iterdir()):
                if entry.is_dir() or entry.is_file():
                    candidates.append((entry, library.name))
        sdk = library / "src" / "internal" / "lzma_sdk"
        if sdk.is_dir():
            candidates.append((sdk, library.name))
    for entry, owner in candidates:
        key = (entry.name, owner)
        if key in seen:
            continue
        seen.add(key)
        license_info = None
        for candidate in BUNDLED_LICENSES:
            if str(candidate["match"]) in entry.name:
                license_info = candidate
                break
        if license_info is None:
            continue
        reference = entry.relative_to(workspace).as_posix()
        components.append(
            {
                "type": "library",
                "bom-ref": f"pkg:generic/{license_info['name']}@{license_info['version']}?bundled={owner}",
                "name": str(license_info["name"]),
                "version": str(license_info["version"]),
                "licenses": [{"license": {"name": str(license_info["license"])}}],
                "properties": [
                    {"name": "bundled.in", "value": owner},
                    {"name": "path", "value": reference},
                    {"name": "license.evidence", "value": str(license_info["note"])},
                ],
            }
        )
    return components


def dependency_edges(workspace: Path) -> tuple[list[dict[str, object]], list[str]]:
    edges: list[dict[str, object]] = []
    warnings: list[str] = []
    for library in sorted((workspace / "libraries").glob("quirewise-*")):
        if not (library / "CMakeLists.txt").is_file():
            continue
        version = package_version(library)
        reference = f"pkg:generic/quirewise/{library.name}@{version}"
        refs = []
        for dependency in declared_dependencies(library):
            target = workspace / "libraries" / dependency.lower().replace("quirewise", "quirewise-", 1)
            if not target.is_dir():
                warnings.append(f"{library.name}: unresolved dependency {dependency}")
                continue
            refs.append(f"pkg:generic/quirewise/{target.name}@{package_version(target)}")
        edges.append({"ref": reference, "dependsOn": sorted(refs)})
    return edges, warnings


def manifest(prefix: Path) -> dict[str, object]:
    files: list[dict[str, object]] = []
    for path in sorted(prefix.rglob("*")):
        if not path.is_file():
            continue
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1 << 20), b""):
                digest.update(block)
        files.append(
            {
                "path": path.relative_to(prefix).as_posix(),
                "size": path.stat().st_size,
                "sha256": digest.hexdigest(),
            }
        )
    return {"prefix": str(prefix), "file_count": len(files), "files": files}


def validate_sbom(sbom: dict[str, object]) -> list[str]:
    problems: list[str] = []
    references = [component["bom-ref"] for component in sbom["components"]]  # type: ignore[index]
    if len(references) != len(set(references)):
        problems.append("duplicate bom-ref values")
    known = set(references)
    for entry in sbom["dependencies"]:  # type: ignore[index]
        if entry["ref"] not in known:
            problems.append(f"dependency ref not in components: {entry['ref']}")
        for target in entry["dependsOn"]:
            if target not in known:
                problems.append(f"dependency target not in components: {target}")
    return problems


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path, required=True,
                        help="CycloneDX JSON output path")
    parser.add_argument("--license-out", type=Path,
                        help="bundled license inventory output path")
    parser.add_argument("--manifest-prefix", type=Path,
                        help="installed prefix to hash into a release manifest")
    parser.add_argument("--manifest-out", type=Path,
                        help="release manifest output path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    workspace = args.workspace.resolve()
    libraries = library_components(workspace)
    if not libraries:
        print("error: no libraries found", file=sys.stderr)
        return 2
    bundled = bundled_components(workspace)
    edges, warnings = dependency_edges(workspace)
    sbom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "metadata": {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "tools": [{"vendor": "Quirewise", "name": "generate_sbom.py", "version": "1"}],
            "component": {
                "type": "application",
                "name": "quirewise-workspace",
                "version": "unversioned",
            },
        },
        "components": libraries + bundled,
        "dependencies": edges,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(sbom, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n",
    )

    if args.license_out:
        inventory = {
            "generated": sbom["metadata"]["timestamp"],
            "first_party": [
                {
                    "component": item["name"],
                    "version": item["version"],
                    "license": "not declared",
                    "path": next(
                        prop["value"] for prop in item["properties"]
                        if prop["name"] == "path"
                    ),
                }
                for item in libraries
            ],
            "bundled": [
                {
                    "component": item["name"],
                    "version": item["version"],
                    "license": item["licenses"][0]["license"]["name"],
                    "path": next(
                        prop["value"] for prop in item["properties"]
                        if prop["name"] == "path"
                    ),
                    "evidence": next(
                        prop["value"] for prop in item["properties"]
                        if prop["name"] == "license.evidence"
                    ),
                }
                for item in bundled
            ],
            "warnings": warnings,
        }
        args.license_out.parent.mkdir(parents=True, exist_ok=True)
        args.license_out.write_text(
            json.dumps(inventory, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8", newline="\n",
        )

    if args.manifest_prefix and args.manifest_out:
        data = manifest(args.manifest_prefix.resolve())
        args.manifest_out.parent.mkdir(parents=True, exist_ok=True)
        args.manifest_out.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8", newline="\n",
        )
        print(f"release manifest: {data['file_count']} files")

    print(f"SBOM: {len(libraries)} libraries, {len(bundled)} bundled components, "
          f"{len(edges)} dependency entries")
    for warning in warnings:
        print(f"warning: {warning}")
    for problem in validate_sbom(sbom):
        print(f"error: {problem}", file=sys.stderr)
    return 1 if validate_sbom(sbom) else 0


if __name__ == "__main__":
    raise SystemExit(main())
