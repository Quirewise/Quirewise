#!/usr/bin/env python3
"""Build a deterministic inventory of each Quirewise library's release surface."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Iterable

from audit_release_boundaries import _cmake_commands, _strip_c_comments, _strip_cmake_comments


INVENTORY_ID = "QW-M0-03"
INVENTORY_VERSION = 1
SOURCE_SUFFIXES = {".c", ".h", ".cc", ".cpp", ".cxx", ".hh", ".hpp", ".hxx"}
IGNORED_DIRECTORY_NAMES = {
    ".git",
    ".codegraph",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    ".tmp",
    "tmp",
}
TEST_DIRECTORY_NAMES = {"test", "tests", "testing", "testdata", "test-data"}
TEST_FILE_RULE = re.compile(r"(?i)(?:^test_|_test\.|_tests?\.|^tests?\.)")
FORMAT_FUNCTION_RULE = re.compile(r"\b(qw_[A-Za-z0-9_]+)\s*\([^;{}]*?\)\s*\{", re.S)
FORMAT_TOKEN_RULE = re.compile(r"\b(?:QW_)?FORMAT_[A-Z0-9_]+\b")
PACKAGE_CONFIG_RULE = re.compile(r"\b(?:Quirewise[A-Za-z0-9_]*Config(?:Version)?\.cmake)\b", re.I)
C_TYPE_KEYWORDS = {
    "auto", "bool", "char", "const", "double", "enum", "extern", "float",
    "int", "long", "register", "restrict", "short", "signed", "static",
    "struct", "typedef", "union", "unsigned", "void", "volatile", "_Bool",
}


def read_utf8(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def package_name(directory_name: str) -> str:
    parts = directory_name.split("-")[1:]
    suffix = "".join(
        part.upper() if part.lower() == "pdg" else part.capitalize() for part in parts
    )
    return "Quirewise" + suffix


def iter_files(root: Path) -> Iterable[Path]:
    if not root.is_dir():
        return
    for directory, child_directories, filenames in os.walk(root):
        child_directories[:] = sorted(
            name
            for name in child_directories
            if name.lower() not in IGNORED_DIRECTORY_NAMES
            and not name.lower().startswith("cmake-build-")
        )
        for filename in sorted(filenames):
            yield Path(directory) / filename


def cmake_files(library: Path) -> list[Path]:
    return sorted(
        path
        for path in iter_files(library)
        if path.name == "CMakeLists.txt"
        or path.suffix.lower() == ".cmake"
        or path.name.endswith(".cmake.in")
    )


def public_api_names(header: Path) -> list[str]:
    text = _strip_c_comments(read_utf8(header))
    text = re.sub(r"(?m)^[ \t]*#.*$", "", text)
    names: set[str] = set()
    for declaration in text.split(";"):
        if "(" not in declaration or "typedef" in declaration:
            continue
        prefix = declaration[: declaration.find("(")]
        tokens = re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", prefix)
        if tokens:
            candidate = tokens[-1]
            if candidate not in C_TYPE_KEYWORDS | {"if", "while", "switch", "for", "return"}:
                names.add(candidate)
    return sorted(names)


def git_value(repository: Path, *arguments: str) -> str | None:
    result = subprocess.run(
        ["git", *arguments],
        cwd=repository,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def inventory_library(library: Path, workspace: Path) -> dict[str, object]:
    files = list(iter_files(library))
    headers = sorted(
        path for path in files if "include" in path.relative_to(library).parts and path.suffix.lower() in {".h", ".hpp", ".hh", ".hxx"}
    )
    public_headers = [
        {
            "path": path.relative_to(library).as_posix(),
            "api_declarations": public_api_names(path),
        }
        for path in headers
    ]

    format_sources = sorted(
        path
        for path in files
        if path.suffix.lower() in SOURCE_SUFFIXES
        and "formats" in path.relative_to(library).parts
        and not any(part.lower() in TEST_DIRECTORY_NAMES for part in path.relative_to(library).parts)
    )
    format_entries = []
    for path in format_sources:
        text = _strip_c_comments(read_utf8(path))
        functions = sorted(set(FORMAT_FUNCTION_RULE.findall(text)))
        formats = sorted(set(FORMAT_TOKEN_RULE.findall(text)))
        format_entries.append(
            {
                "path": path.relative_to(library).as_posix(),
                "candidate_entry_functions": functions,
                "format_tokens": formats,
            }
        )

    target_definitions: list[dict[str, str]] = []
    target_aliases: list[dict[str, str]] = []
    export_names: dict[str, str] = {}
    link_edges: list[dict[str, object]] = []
    install_rules: list[str] = []
    installed_package_files: list[str] = []
    test_commands: list[dict[str, str]] = []
    ctest_enabled = False
    cmake_paths = cmake_files(library)
    for cmake_path in cmake_paths:
        text = _strip_cmake_comments(read_utf8(cmake_path))
        relative_cmake_path = cmake_path.relative_to(library).as_posix()
        for command, arguments, _, _ in _cmake_commands(text):
            tokens = re.findall(r'"([^\"]*)"|\'([^\']*)\'|([^ \t\r\n]+)', arguments)
            flat_tokens = [next((item for item in group if item), "") for group in tokens]
            flat_tokens = [token.strip() for token in flat_tokens if token.strip()]
            if command in {"add_library", "add_executable", "add_custom_target"} and flat_tokens:
                name = flat_tokens[0]
                if name.startswith("$"):
                    target_definitions.append(
                        {"name": name, "kind": command, "defined_in": relative_cmake_path, "dynamic": "true"}
                    )
                elif "ALIAS" in [item.upper() for item in flat_tokens]:
                    alias_index = [item.upper() for item in flat_tokens].index("ALIAS")
                    target_aliases.append(
                        {
                            "alias": name,
                            "target": flat_tokens[alias_index + 1] if alias_index + 1 < len(flat_tokens) else "",
                            "defined_in": relative_cmake_path,
                        }
                    )
                else:
                    kind = command
                    for item in flat_tokens[1:4]:
                        if item.upper() in {"STATIC", "SHARED", "MODULE", "OBJECT", "INTERFACE", "UNKNOWN", "IMPORTED"}:
                            kind = f"{command}:{item.upper()}"
                            break
                    target_definitions.append(
                        {"name": name, "kind": kind, "defined_in": relative_cmake_path}
                    )
            elif command == "set_target_properties" and flat_tokens:
                property_match = re.search(r"\bEXPORT_NAME\s+([^\s)]+)", arguments, re.I)
                if property_match:
                    for target in flat_tokens[1:]:
                        if target.upper() == "PROPERTIES":
                            break
                        export_names[target] = property_match.group(1).strip('"')
            elif command == "target_link_libraries" and flat_tokens:
                target = flat_tokens[0]
                dependencies = sorted(set(re.findall(r"\bQuirewise::[A-Za-z0-9_]+\b", arguments)))
                link_edges.append(
                    {
                        "target": target,
                        "quirewise_targets": dependencies,
                        "defined_in": relative_cmake_path,
                    }
                )
            elif command == "install":
                normalized = " ".join(arguments.split())
                install_rules.append(f"{relative_cmake_path}: install({normalized})")
                installed_package_files.extend(PACKAGE_CONFIG_RULE.findall(arguments))
            elif command == "enable_testing" or (command == "include" and re.match(r"\s*CTest\b", arguments, re.I)):
                ctest_enabled = True
            elif command == "add_test":
                normalized_test = " ".join(arguments.split())
                test_commands.append(
                    {"defined_in": relative_cmake_path, "command": f"add_test({normalized_test})"}
                )

    test_files = sorted(
        path
        for path in files
        if path.suffix.lower() in SOURCE_SUFFIXES | {".cmake", ".in", ".py"}
        and (
            any(part.lower() in TEST_DIRECTORY_NAMES for part in path.relative_to(library).parts)
            or TEST_FILE_RULE.search(path.name)
        )
    )
    formats_root = library / "src" / "formats"
    tests_root = [path for path in files if any(part.lower() in TEST_DIRECTORY_NAMES for part in path.relative_to(library).parts)]
    branch = git_value(library, "branch", "--show-current")
    commit = git_value(library, "rev-parse", "HEAD")
    status = git_value(library, "status", "--short")

    return {
        "repository": library.relative_to(workspace).as_posix(),
        "package": package_name(library.name),
        "git": {"branch": branch, "commit": commit, "worktree_clean": status == ""},
        "public_headers": public_headers,
        "public_header_count": len(public_headers),
        "format_source_root_present": formats_root.is_dir(),
        "format_source_count": len(format_entries),
        "format_entries": format_entries,
        "cmake_files": [path.relative_to(library).as_posix() for path in cmake_paths],
        "cmake_target_definitions": sorted(target_definitions, key=lambda item: (item["name"], item["defined_in"])),
        "cmake_target_aliases": sorted(target_aliases, key=lambda item: (item["alias"], item["defined_in"])),
        "cmake_export_names": dict(sorted(export_names.items())),
        "cmake_quirewise_link_edges": sorted(link_edges, key=lambda item: (item["target"], item["defined_in"])),
        "install_rules": sorted(set(install_rules)),
        "installed_package_files_referenced": sorted(set(installed_package_files)),
        "test_entrypoints": {
            "ctest_enabled": ctest_enabled,
            "add_test_commands": sorted(test_commands, key=lambda item: (item["defined_in"], item["command"])),
            "test_file_count": len(test_files),
            "test_files": [path.relative_to(library).as_posix() for path in test_files],
            "status": "PRESENT" if ctest_enabled or test_commands or tests_root else "UNVERIFIED",
        },
    }


def build_inventory(workspace: Path) -> dict[str, object]:
    workspace = workspace.resolve()
    libraries_dir = workspace / "libraries"
    libraries = sorted(path for path in libraries_dir.glob("quirewise-*") if path.is_dir())
    records = [inventory_library(library, workspace) for library in libraries]
    return {
        "inventory_id": INVENTORY_ID,
        "inventory_version": INVENTORY_VERSION,
        "workspace": ".",
        "library_count": len(records),
        "libraries": records,
        "extraction_notes": [
            "Public API names are derived from semicolon-terminated declarations in installed include candidates; review complex callback and macro declarations manually.",
            "Format entries list all source/header units under src/formats and candidate qw_* function definitions; this is a source inventory, not proof that every unit is part of a production target.",
            "CMake target and install records are parsed from raw CMake, including conditional branches; generator-expression and variable-expanded target lists may require manual resolution.",
            "Test entry status is UNVERIFIED when no test directory or CTest command is declared; file presence alone does not prove a test runs.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="Quirewise workspace root (default: inferred from this script)",
    )
    parser.add_argument("--json", type=Path, help="write the complete inventory as JSON")
    parser.add_argument("--markdown", type=Path, help="write the review inventory as Markdown")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    inventory = build_inventory(args.workspace)
    json_text = json.dumps(inventory, indent=2, ensure_ascii=False) + "\n"
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json_text, encoding="utf-8", newline="\n")
    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            f"# {INVENTORY_ID} Quirewise 库表面清单",
            "",
            f"- 清单版本：{INVENTORY_VERSION}",
            f"- 库数量：{inventory['library_count']}",
            "- API 函数名为静态提取候选；格式源码不代表已进入默认生产目标。",
            "",
        ]
        for library in inventory["libraries"]:
            lines.extend(
                [
                    f"## {library['repository']}",
                    "",
                    f"- 包：`{library['package']}`",
                    f"- Git：`{library['git']['branch']}` / `{library['git']['commit']}` / clean={library['git']['worktree_clean']}",
                    f"- 公共头：{library['public_header_count']}",
                    f"- 格式源码单元：{library['format_source_count']}",
                    f"- CMake target：{len(library['cmake_target_definitions'])} definitions, {len(library['cmake_target_aliases'])} aliases",
                    f"- 安装规则：{len(library['install_rules'])}",
                    f"- 测试入口：{library['test_entrypoints']['status']} ({library['test_entrypoints']['test_file_count']} files, {len(library['test_entrypoints']['add_test_commands'])} add_test commands)",
                    "",
                    "### 公共 API 声明候选",
                    "",
                ]
            )
            for header in library["public_headers"]:
                names = ", ".join(f"`{name}`" for name in header["api_declarations"]) or "（未提取到函数声明）"
                lines.append(f"- `{header['path']}`：{names}")
            lines.extend(["", "### 格式源码入口候选", ""])
            for entry in library["format_entries"]:
                funcs = ", ".join(f"`{name}`" for name in entry["candidate_entry_functions"]) or "（无 qw_* 定义候选）"
                lines.append(f"- `{entry['path']}`：{funcs}")
            lines.extend(["", "### 安装规则", ""])
            lines.extend(f"- `{rule}`" for rule in library["install_rules"])
            lines.extend(["", "### 测试入口", ""])
            if library["test_entrypoints"]["add_test_commands"]:
                lines.extend(
                    f"- `{item['defined_in']}`：`{item['command']}`"
                    for item in library["test_entrypoints"]["add_test_commands"]
                )
            else:
                lines.append("- 无 CTest add_test 命令；需人工核对是否有非 CTest 测试入口。")
            lines.append("")
        lines.extend(["## 提取边界", ""])
        lines.extend(f"- {note}" for note in inventory["extraction_notes"])
        args.markdown.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    missing_git = sum(
        library["git"]["commit"] is None or library["git"]["branch"] is None
        for library in inventory["libraries"]
    )
    unverified_tests = sum(
        library["test_entrypoints"]["status"] == "UNVERIFIED"
        for library in inventory["libraries"]
    )
    print(
        f"{INVENTORY_ID} v{INVENTORY_VERSION}: {inventory['library_count']} libraries, "
        f"{missing_git} missing git identities, {unverified_tests} libraries without a declared test entry"
    )
    for library in inventory["libraries"]:
        print(
            f"{library['repository']}: headers={library['public_header_count']} "
            f"format_units={library['format_source_count']} "
            f"targets={len(library['cmake_target_definitions'])} "
            f"install_rules={len(library['install_rules'])} "
            f"tests={library['test_entrypoints']['status']}"
        )
    return 0 if inventory["library_count"] == 14 and missing_git == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
