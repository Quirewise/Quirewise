#!/usr/bin/env python3
"""Validate Quirewise library package boundaries and dependency acyclicity.

The validator intentionally reads the CMake files instead of maintaining a
second dependency manifest.  A package dependency must therefore appear in
both the build-time ``find_package`` calls and the installed package config's
``find_dependency`` calls.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


FIND_PACKAGE_RE = re.compile(r"\bfind_package\s*\(\s*(Quirewise[A-Za-z0-9_]+)")
FIND_DEPENDENCY_RE = re.compile(
    r"\bfind_dependency\s*\(\s*(Quirewise[A-Za-z0-9_]+)"
)
TARGET_RE = re.compile(r"\bQuirewise::([A-Za-z0-9_]+)")
APP_LEAK_RE = re.compile(
    r"(?im)(?:#\s*include[^\r\n]*(?:^|[\\/])app[\\/]|"
    r"add_subdirectory\s*\([^)]*(?:^|[\\/])app[\\/]|"
    r"(?:^|[\\/])app[\\/]src[\\/])"
)
SIBLING_LEAK_RE = re.compile(
    r"(?im)(?:#\s*include[^\r\n]*libraries[\\/]quirewise-|"
    r"#\s*include[^\r\n]*\.\.[\\/]quirewise-|"
    r"add_subdirectory\s*\([^)]*\.\.[\\/]quirewise-)"
)


def package_suffix(directory_name: str) -> str:
    """Return the CMake package suffix for a quirewise-* directory."""

    parts = directory_name.split("-")[1:]
    return "".join(
        part.upper() if part.lower() == "pdg" else part.capitalize()
        for part in parts
    )


def read_utf8(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def normalize_package(package: str, packages: dict[str, str]) -> str | None:
    return packages.get(package.lower())


def collect_packages(libraries_dir: Path) -> dict[str, str]:
    packages: dict[str, str] = {}
    for directory in sorted(libraries_dir.glob("quirewise-*")):
        if not directory.is_dir():
            continue
        package = "Quirewise" + package_suffix(directory.name)
        packages[package.lower()] = directory.name
    return packages


def collect_dependencies(
    library: Path, packages: dict[str, str]
) -> tuple[set[str], set[str], set[str], list[str]]:
    cmake_path = library / "CMakeLists.txt"
    errors: list[str] = []
    if not cmake_path.is_file():
        return set(), set(), set(), [f"{library}: missing CMakeLists.txt"]

    cmake = read_utf8(cmake_path)
    cmake_packages: set[str] = set()
    for match in FIND_PACKAGE_RE.finditer(cmake):
        package = normalize_package(match.group(1), packages)
        if package is None:
            errors.append(
                f"{cmake_path}: unknown Quirewise package {match.group(1)}"
            )
        else:
            cmake_packages.add(package)

    linked_packages: set[str] = set()
    for match in TARGET_RE.finditer(cmake):
        package = normalize_package("Quirewise" + match.group(1), packages)
        if package is not None:
            linked_packages.add(package)
    linked_packages.discard(library.name)

    config_packages: set[str] = set()
    for config_path in sorted((library / "cmake").glob("*.cmake.in")):
        config = read_utf8(config_path)
        for match in FIND_DEPENDENCY_RE.finditer(config):
            package = normalize_package(match.group(1), packages)
            if package is None:
                errors.append(
                    f"{config_path}: unknown Quirewise dependency {match.group(1)}"
                )
            else:
                config_packages.add(package)

    if cmake_packages - config_packages:
        missing = ", ".join(sorted(cmake_packages - config_packages))
        errors.append(
            f"{library.name}: package config omits build dependencies: {missing}"
        )
    if config_packages - cmake_packages:
        extra = ", ".join(sorted(config_packages - cmake_packages))
        errors.append(
            f"{library.name}: package config declares undeclared dependencies: {extra}"
        )
    if linked_packages - cmake_packages:
        undeclared = ", ".join(sorted(linked_packages - cmake_packages))
        errors.append(
            f"{library.name}: links Quirewise targets without find_package: {undeclared}"
        )

    if APP_LEAK_RE.search(cmake) or SIBLING_LEAK_RE.search(cmake):
        errors.append(f"{cmake_path}: cross-package source or app path reference")

    for source in sorted(library.rglob("*")):
        if not source.is_file() or source.suffix.lower() not in {".c", ".h", ".cpp", ".hpp"}:
            continue
        text = read_utf8(source)
        if APP_LEAK_RE.search(text) or SIBLING_LEAK_RE.search(text):
            errors.append(f"{source}: cross-package source or app include")

    dependencies = cmake_packages | linked_packages
    if library.name in dependencies:
        errors.append(f"{library.name}: declares a dependency on itself")
        dependencies.discard(library.name)
    return dependencies, cmake_packages, config_packages, errors


def find_cycle(graph: dict[str, set[str]]) -> list[str] | None:
    state: dict[str, int] = {node: 0 for node in graph}
    stack: list[str] = []

    def visit(node: str) -> list[str] | None:
        state[node] = 1
        stack.append(node)
        for dependency in sorted(graph[node]):
            if dependency not in graph:
                continue
            if state[dependency] == 0:
                cycle = visit(dependency)
                if cycle:
                    return cycle
            elif state[dependency] == 1:
                start = stack.index(dependency)
                return stack[start:] + [dependency]
        stack.pop()
        state[node] = 2
        return None

    for node in sorted(graph):
        if state[node] == 0:
            cycle = visit(node)
            if cycle:
                return cycle
    return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="Quirewise workspace containing libraries/ (default: inferred)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    workspace = args.workspace.resolve()
    libraries_dir = workspace / "libraries"
    if not libraries_dir.is_dir():
        print(f"error: missing library directory: {libraries_dir}", file=sys.stderr)
        return 2

    packages = collect_packages(libraries_dir)
    graph: dict[str, set[str]] = {}
    errors: list[str] = []
    for library in sorted(libraries_dir.glob("quirewise-*")):
        if not library.is_dir():
            continue
        dependencies, _, _, library_errors = collect_dependencies(library, packages)
        graph[library.name] = dependencies
        errors.extend(library_errors)

    cycle = find_cycle(graph)
    if cycle:
        errors.append("dependency cycle: " + " -> ".join(cycle))

    print("Quirewise library dependency graph")
    for library in sorted(graph):
        dependencies = ", ".join(sorted(graph[library])) or "(none)"
        print(f"  {library} -> {dependencies}")

    if errors:
        print("\nDependency validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(f"\nOK: {len(graph)} libraries, no dependency cycles, no app/source leaks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
