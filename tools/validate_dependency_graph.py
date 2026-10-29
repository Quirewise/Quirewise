#!/usr/bin/env python3
"""Validate Quirewise library package boundaries and dependency acyclicity.

The validator intentionally reads the CMake files instead of maintaining a
second dependency manifest.  A package dependency must therefore appear in
both the build-time ``find_package`` calls and the installed package config's
``find_dependency`` calls.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

from audit_release_boundaries import (
    audit_workspace,
    _cmake_commands,
    _strip_c_comments,
    _strip_cmake_comments,
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

    cmake_packages: set[str] = set()
    linked_packages: set[str] = set()
    config_packages: set[str] = set()
    config_root = library / "cmake"
    ignored_directories = {".git", ".codegraph", "__pycache__", "build", "tests", "test"}
    cmake_paths: list[Path] = []
    source_paths: list[Path] = []
    for directory, child_directories, filenames in os.walk(library):
        child_directories[:] = sorted(
            name for name in child_directories
            if name.lower() not in ignored_directories
            and not name.lower().startswith("cmake-build-")
        )
        for filename in sorted(filenames):
            path = Path(directory) / filename
            if filename == "CMakeLists.txt" or path.suffix.lower() == ".cmake" or filename.endswith(".cmake.in"):
                cmake_paths.append(path)
            if path.suffix.lower() in {".c", ".h", ".cpp", ".hpp", ".cc", ".cxx", ".hh", ".hxx"}:
                source_paths.append(path)

    for path in sorted(cmake_paths):
        cmake = _strip_cmake_comments(read_utf8(path))
        for command, arguments, _, _ in _cmake_commands(cmake):
            package_match = re.match(
                r"(?:\"([^\"]+)\"|'([^']+)'|([A-Za-z0-9_:+.-]+))",
                arguments.strip(),
            )
            if command == "find_package" and package_match:
                package_name = next(group for group in package_match.groups() if group)
                if package_name.lower().startswith("quirewise"):
                    package = normalize_package(package_name, packages)
                    if package is None:
                        errors.append(f"{path}: unknown Quirewise package {package_name}")
                    else:
                        cmake_packages.add(package)
            elif command == "find_dependency" and package_match and path.is_relative_to(config_root):
                package_name = next(group for group in package_match.groups() if group)
                if package_name.lower().startswith("quirewise"):
                    package = normalize_package(package_name, packages)
                    if package is None:
                        errors.append(f"{path}: unknown Quirewise dependency {package_name}")
                    else:
                        config_packages.add(package)

            for match in TARGET_RE.finditer(arguments):
                package = normalize_package("Quirewise" + match.group(1), packages)
                if package is not None:
                    linked_packages.add(package)

        if APP_LEAK_RE.search(cmake) or SIBLING_LEAK_RE.search(cmake):
            errors.append(f"{path}: cross-package source or app path reference")
    linked_packages.discard(library.name)

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

    for source in source_paths:
        text = _strip_c_comments(read_utf8(source))
        if APP_LEAK_RE.search(text) or SIBLING_LEAK_RE.search(text):
            errors.append(f"{source}: cross-package source or app include")

    dependencies = cmake_packages | linked_packages
    if library.name in dependencies:
        errors.append(f"{library.name}: declares a dependency on itself")
        dependencies.discard(library.name)
    return dependencies, cmake_packages, config_packages, errors


def validate_install_contract(library: Path) -> tuple[int, list[str]]:
    """Check that each library exports and installs a discoverable CMake package."""

    cmake_path = library / "CMakeLists.txt"
    if not cmake_path.is_file():
        return 0, [f"{library}: missing CMakeLists.txt"]

    cmake = _strip_cmake_comments(read_utf8(cmake_path))
    commands = list(_cmake_commands(cmake))
    errors: list[str] = []
    target_export_sets: set[str] = set()
    installed_export_sets: set[str] = set()
    installs_public_headers = False
    installs_package_config = False
    installs_package_version = False
    generates_package_config = False
    generates_package_version = False
    config_templates = sorted((library / "cmake").glob("*.cmake.in"))

    for command, arguments, _, _ in commands:
        if command == "configure_package_config_file" and re.search(r"Config\.cmake\.in\b", arguments, re.I):
            generates_package_config = True
        elif command == "write_basic_package_version_file" and re.search(r"ConfigVersion\.cmake\b", arguments, re.I):
            generates_package_version = True
        if command != "install":
            continue
        tokens = re.findall(r"[A-Za-z0-9_.$<>:+/\\-]+", arguments)
        if not tokens:
            continue
        kind = tokens[0].upper()
        upper_tokens = [token.upper() for token in tokens]
        if kind == "TARGETS" and "EXPORT" in upper_tokens:
            export_index = upper_tokens.index("EXPORT")
            if export_index + 1 < len(tokens):
                target_export_sets.add(tokens[export_index + 1])
        elif kind == "EXPORT" and len(tokens) > 1:
            installed_export_sets.add(tokens[1])
        elif kind == "DIRECTORY" and re.search(r"(?:^|\s)include[/\\]?(?:\s|$)", arguments, re.I):
            installs_public_headers = True
        elif kind == "FILES":
            installs_package_config |= bool(re.search(r"Config\.cmake\b", arguments, re.I))
            installs_package_version |= bool(re.search(r"ConfigVersion\.cmake\b", arguments, re.I))

    matching_exports = target_export_sets & installed_export_sets
    if not target_export_sets:
        errors.append(f"{library.name}: no install(TARGETS ... EXPORT ...) rule")
    if not installed_export_sets:
        errors.append(f"{library.name}: no install(EXPORT ...) rule")
    if target_export_sets - installed_export_sets:
        missing = ", ".join(sorted(target_export_sets - installed_export_sets))
        errors.append(f"{library.name}: target export sets are not installed: {missing}")
    if not installs_public_headers:
        errors.append(f"{library.name}: public include/ directory is not installed")
    if not config_templates:
        errors.append(f"{library.name}: no cmake package config template")
    if not generates_package_config:
        errors.append(f"{library.name}: no configure_package_config_file rule")
    if not generates_package_version:
        errors.append(f"{library.name}: no write_basic_package_version_file rule")
    if not installs_package_config:
        errors.append(f"{library.name}: no installed package config file")
    if not installs_package_version:
        errors.append(f"{library.name}: no installed package version file")
    return len(matching_exports), errors


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
    installed_package_count = 0
    for library in sorted(libraries_dir.glob("quirewise-*")):
        if not library.is_dir():
            continue
        dependencies, _, _, library_errors = collect_dependencies(library, packages)
        graph[library.name] = dependencies
        errors.extend(library_errors)
        exported_count, install_errors = validate_install_contract(library)
        installed_package_count += bool(exported_count)
        errors.extend(install_errors)

    boundary_report = audit_workspace(workspace)
    for finding in boundary_report["findings"]:
        errors.append(
            f"{finding['path']}:{finding['line']}: {finding['rule']}: {finding['match']}"
        )
    for read_error in boundary_report["read_errors"]:
        errors.append(f"{read_error['path']}: unable to audit UTF-8 source: {read_error['error']}")

    cycle = find_cycle(graph)
    if cycle:
        errors.append("dependency cycle: " + " -> ".join(cycle))

    print("Quirewise library dependency graph")
    print(
        f"Package install audit: {installed_package_count}/{len(graph)} libraries "
        "have a matched target export set"
    )
    print(
        f"Release boundary audit: {boundary_report['finding_count']} findings, "
        f"{boundary_report['read_error_count']} read errors, "
        f"{boundary_report['observation_count']} development-only observations"
    )
    for library in sorted(graph):
        dependencies = ", ".join(sorted(graph[library])) or "(none)"
        print(f"  {library} -> {dependencies}")

    if errors:
        print("\nDependency validation failed:", file=sys.stderr)
        for error in errors[:300]:
            print(f"- {error}", file=sys.stderr)
        if len(errors) > 300:
            print(f"- ... {len(errors) - 300} additional findings", file=sys.stderr)
        return 1

    print(f"\nOK: {len(graph)} libraries, no dependency cycles, no app/source leaks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
