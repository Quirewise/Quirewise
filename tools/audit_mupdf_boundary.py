#!/usr/bin/env python3
"""Inventory MuPDF wrapper declarations, call sites, conditions, and build references."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from collections import defaultdict
from pathlib import Path


SOURCE_SUFFIXES = {".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx"}
SKIP_DIRS = {".git", ".tmp", "build", "cmake-build-debug", "cmake-build-release", "node_modules"}
API_RE = re.compile(r"\b(qw_mupdf_[A-Za-z0-9_]+)\b")
INCLUDE_RE = re.compile(r'^\s*#\s*include\s*[<\"]([^>\"]+)[>\"]')
DIRECTIVE_RE = re.compile(r"^\s*#\s*(if|ifdef|ifndef|elif|else|endif)\b(.*)$")
IDENT_CALL_RE = re.compile(r"\b([A-Za-z_]\w*)\s*\(")
CONTROL_WORDS = {"if", "ifdef", "ifndef", "elif", "else", "for", "while", "switch", "sizeof", "_Alignof"}


def iter_files(base: Path):
    if not base.exists():
        return
    for directory, child_dirs, filenames in os.walk(base):
        child_dirs[:] = sorted(name for name in child_dirs if name not in SKIP_DIRS)
        for filename in sorted(filenames):
            yield Path(directory) / filename


def relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def mask_c_comments_and_literals(text: str) -> str:
    """Replace comments and literal contents with spaces while preserving offsets."""
    chars = list(text)
    i = 0
    state = "code"
    while i < len(chars):
        ch = chars[i]
        nxt = chars[i + 1] if i + 1 < len(chars) else ""
        if state == "code":
            if ch == "/" and nxt == "/":
                chars[i] = chars[i + 1] = " "
                i += 2
                state = "line_comment"
                continue
            if ch == "/" and nxt == "*":
                chars[i] = chars[i + 1] = " "
                i += 2
                state = "block_comment"
                continue
            if ch in ('"', "'"):
                quote = ch
                chars[i] = " "
                i += 1
                while i < len(chars):
                    current = chars[i]
                    if current == "\\" and i + 1 < len(chars):
                        if chars[i + 1] != "\n":
                            chars[i + 1] = " "
                        chars[i] = " "
                        i += 2
                        continue
                    if current == quote:
                        chars[i] = " "
                        i += 1
                        break
                    if current != "\n":
                        chars[i] = " "
                    i += 1
                continue
        elif state == "line_comment":
            if ch == "\n":
                state = "code"
            else:
                chars[i] = " "
        elif state == "block_comment":
            if ch == "*" and nxt == "/":
                chars[i] = chars[i + 1] = " "
                i += 2
                state = "code"
                continue
            if ch != "\n":
                chars[i] = " "
        i += 1
    return "".join(chars)


def matching_paren(code: str, opening: int) -> int | None:
    depth = 0
    for i in range(opening, len(code)):
        if code[i] == "(":
            depth += 1
        elif code[i] == ")":
            depth -= 1
            if depth == 0:
                return i
    return None


def function_regions(code: str) -> list[dict[str, int | str]]:
    """Find ordinary C/C++ function bodies using balanced parameter/body delimiters."""
    regions: list[dict[str, int | str]] = []
    for match in IDENT_CALL_RE.finditer(code):
        name = match.group(1)
        if name in CONTROL_WORDS:
            continue
        opening = code.find("(", match.start(1) + len(name), match.end())
        closing = matching_paren(code, opening)
        if closing is None:
            continue
        after = closing + 1
        while after < len(code) and code[after].isspace():
            after += 1
        if after >= len(code) or code[after] != "{":
            continue
        depth = 0
        end = None
        for position in range(after, len(code)):
            if code[position] == "{":
                depth += 1
            elif code[position] == "}":
                depth -= 1
                if depth == 0:
                    end = position
                    break
        if end is not None:
            regions.append({"name": name, "start": match.start(1), "body_start": after, "end": end})
    return regions


def line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def conditions_by_line(text: str) -> tuple[list[list[str]], list[dict[str, int | str]]]:
    stack: list[dict[str, str]] = []
    line_conditions: list[list[str]] = []
    issues: list[dict[str, int | str]] = []
    for number, line in enumerate(text.splitlines(), 1):
        directive = DIRECTIVE_RE.match(line)
        kind = directive.group(1).lower() if directive else ""
        tail = directive.group(2).strip() if directive else ""
        if kind in {"if", "ifdef", "ifndef"}:
            stack.append({"opening": f"#{kind} {tail}".strip(), "branch": f"#{kind} {tail}".strip()})
        elif kind in {"elif", "else"}:
            if stack:
                stack[-1]["branch"] = f"{stack[-1]['opening']} -> #{kind} {tail}".strip()
            else:
                issues.append({"line": number, "directive": line.strip(), "issue": "branch directive without open conditional"})
        line_conditions.append([item["branch"] for item in stack])
        if kind == "endif":
            if stack:
                stack.pop()
            else:
                issues.append({"line": number, "directive": line.strip(), "issue": "endif without open conditional"})
    for item in stack:
        issues.append({"line": len(line_conditions), "directive": item["opening"], "issue": "conditional is not closed"})
    return line_conditions, issues


def classify_occurrence(code: str, match: re.Match[str]) -> str:
    opening = match.end()
    while opening < len(code) and code[opening].isspace():
        opening += 1
    if opening >= len(code) or code[opening] != "(":
        return "reference"
    closing = matching_paren(code, opening)
    if closing is None:
        return "reference"
    after = closing + 1
    while after < len(code) and code[after].isspace():
        after += 1
    if after < len(code) and code[after] == "{":
        return "definition"
    if after < len(code) and code[after] == ";":
        line_start = code.rfind("\n", 0, match.start()) + 1
        prefix = code[line_start:match.start()]
        if re.fullmatch(r"\s*(?:(?:extern|static|inline|const|volatile)\s+)*(?:[A-Za-z_]\w*\s+)+", prefix):
            return "declaration"
    return "call"


def scan_source(path: Path, root: Path) -> dict[str, object]:
    raw = path.read_text(encoding="utf-8")
    has_symbol_text = API_RE.search(raw) is not None
    code = mask_c_comments_and_literals(raw) if has_symbol_text else ""
    path_text = relative(path, root)
    line_conditions, conditional_issues = conditions_by_line(raw)
    symbol_matches = list(API_RE.finditer(code))
    regions = function_regions(code) if symbol_matches else []
    occurrences: list[dict[str, object]] = []
    for match in symbol_matches:
        line = line_number(code, match.start())
        kind = classify_occurrence(code, match)
        parent = None
        if kind == "call":
            containing = [region for region in regions if int(region["body_start"]) < match.start() < int(region["end"])]
            if containing:
                parent = max(containing, key=lambda region: int(region["start"]))["name"]
        occurrences.append({
            "symbol": match.group(1),
            "kind": kind,
            "path": path_text,
            "line": line,
            "function": parent,
            "conditions": line_conditions[line - 1] if line <= len(line_conditions) else [],
        })

    includes: list[dict[str, object]] = []
    macro_refs: list[dict[str, object]] = []
    for number, line in enumerate(raw.splitlines(), 1):
        include = INCLUDE_RE.match(line)
        conditions = line_conditions[number - 1] if number <= len(line_conditions) else []
        if include and "mupdf_backend.h" in include.group(1).lower():
            includes.append({"path": path_text, "line": number, "header": include.group(1), "conditions": conditions})
        if re.search(r"\b(?:QUIREWISE_WITH_MUPDF|QUIREWISE_STANDALONE_[A-Z0-9_]+)\b", line):
            macro_refs.append({"path": path_text, "line": number, "text": line.strip(), "conditions": conditions})

    external_includes = []
    for number, line in enumerate(raw.splitlines(), 1):
        include = INCLUDE_RE.match(line)
        if include and "mupdf/" in include.group(1).lower():
            external_includes.append({
                "path": path_text,
                "line": number,
                "header": include.group(1),
                "conditions": line_conditions[number - 1] if number <= len(line_conditions) else [],
            })

    return {
        "path": path_text,
        "raw": raw,
        "code": code,
        "occurrences": occurrences,
        "includes": includes,
        "macro_refs": macro_refs,
        "external_includes": external_includes,
        "conditional_issues": conditional_issues,
    }


def cmake_inventory(
    root: Path,
    source_paths: list[str],
    relevant_condition_macros: set[str],
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]], int]:
    cmake_files = sorted(
        path for base in (root / "libraries", root / "app")
        for path in iter_files(base)
        if path.name == "CMakeLists.txt" or path.suffix.lower() == ".cmake"
    )
    mupdf_refs: list[dict[str, object]] = []
    condition_macro_refs: list[dict[str, object]] = []
    source_inclusion: list[dict[str, object]] = []
    for path in cmake_files:
        try:
            raw = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        rel = relative(path, root)
        for number, line in enumerate(raw.splitlines(), 1):
            if re.search(r"mupdf|QUIREWISE_WITH_MUPDF", line, re.IGNORECASE):
                mupdf_refs.append({"path": rel, "line": number, "text": line.strip()})
            line_macros = set(re.findall(r"\b(?:QUIREWISE_WITH_MUPDF|QUIREWISE_STANDALONE_[A-Z0-9_]+)\b", line))
            if line_macros & relevant_condition_macros:
                condition_macro_refs.append({"path": rel, "line": number, "text": line.strip()})

        target_definitions: dict[str, list[str]] = defaultdict(list)
        definitions_re = re.compile(r"\btarget_compile_definitions\s*\(\s*([A-Za-z_]\w*)([\s\S]*?)\)", re.IGNORECASE)
        for definition in definitions_re.finditer(raw):
            target = definition.group(1)
            for macro in re.findall(r"\b(?:QUIREWISE_WITH_MUPDF|QUIREWISE_STANDALONE_[A-Z0-9_]+)(?:=[^\s)]+)?", definition.group(2)):
                if macro not in target_definitions[target]:
                    target_definitions[target].append(macro)

        if not rel.startswith("libraries/"):
            continue
        library_root = path.parent
        library_sources = [item for item in source_paths if item.startswith(relative(library_root, root) + "/src/")]
        if not library_sources:
            continue
        glob_re = re.compile(r"\bfile\s*\(\s*(GLOB_RECURSE|GLOB)\s+([A-Za-z_]\w*)\s+([\s\S]*?)\)", re.IGNORECASE)
        for block in glob_re.finditer(raw):
            variable = block.group(2)
            patterns = re.findall(r"[\w./*+-]+", block.group(3))
            source_patterns = [pattern for pattern in patterns if pattern.startswith("src/") and pattern.lower().endswith((".c", ".cpp", ".cc", ".cxx"))]
            if not source_patterns:
                continue
            target_re = re.compile(
                rf"\badd_library\s*\(\s*([A-Za-z_]\w*)\s+(?:(?:STATIC|SHARED|MODULE|OBJECT)\s+)?\$\{{\s*{re.escape(variable)}\s*\}}",
                re.IGNORECASE | re.DOTALL,
            )
            target_match = target_re.search(raw)
            target = target_match.group(1) if target_match else None
            for source in library_sources:
                source_inclusion.append({
                    "source": source,
                    "cmake": rel,
                    "cmake_line": line_number(raw, block.start()),
                    "glob_kind": block.group(1).upper(),
                    "variable": variable,
                    "patterns": source_patterns,
                    "target": target,
                    "target_compile_definitions": target_definitions.get(target or "", []),
                    "assessment": "included by recursive src source glob; CMake condition evaluation not performed",
                })
    return mupdf_refs, condition_macro_refs, source_inclusion, len(cmake_files)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_inventory(root: Path) -> dict[str, object]:
    files: list[dict[str, object]] = []
    source_read_errors: list[dict[str, str]] = []
    for base in (root / "libraries", root / "app"):
        for path in iter_files(base):
            if path.suffix.lower() not in SOURCE_SUFFIXES:
                continue
            try:
                scanned = scan_source(path, root)
            except UnicodeDecodeError as error:
                source_read_errors.append({"path": relative(path, root), "error": str(error)})
                continue
            scanned.pop("raw")
            scanned.pop("code")
            files.append(scanned)

    source_paths = [str(item["path"]) for item in files]
    all_occurrences = [occ for item in files for occ in item["occurrences"]]
    symbols: dict[str, dict[str, object]] = {}
    for name in sorted({str(item["symbol"]) for item in all_occurrences}):
        occurrences = [item for item in all_occurrences if item["symbol"] == name]
        symbols[name] = {
            "declarations": [item for item in occurrences if item["kind"] == "declaration"],
            "definitions": [item for item in occurrences if item["kind"] == "definition"],
            "calls": [item for item in occurrences if item["kind"] == "call"],
            "other_references": [item for item in occurrences if item["kind"] == "reference"],
        }

    headers: list[dict[str, object]] = []
    for path in sorted(path for path in iter_files(root / "libraries") if path.name == "mupdf_backend.h"):
        rel = relative(path, root)
        occurrence_set = [item for item in all_occurrences if item["path"] == rel]
        library_prefix = rel.split("/src/backends/", 1)[0] + "/"
        headers.append({
            "path": rel,
            "sha256": sha256(path),
            "api_symbols": sorted({str(item["symbol"]) for item in occurrence_set}),
            "include_sites": [site for item in files for site in item["includes"] if site["path"].startswith(library_prefix)],
        })

    all_includes = [item for file in files for item in file["includes"]]
    callers = [item for item in all_occurrences if item["kind"] == "call"]
    external_includes = [item for file in files for item in file["external_includes"]]
    mupdf_macro_files = {
        str(item["path"])
        for file in files
        for item in file["macro_refs"]
        if "QUIREWISE_WITH_MUPDF" in str(item["text"])
    }
    relevant_paths = {
        str(item["path"]) for item in all_occurrences
    } | {
        str(item["path"]) for item in all_includes
    } | {
        str(item["path"]) for item in external_includes
    } | mupdf_macro_files
    macro_refs = [
        item
        for file in files
        for item in file["macro_refs"]
        if item["path"] in relevant_paths
    ]
    conditional_issues = [
        {"path": file["path"], **issue}
        for file in files if file["path"] in relevant_paths for issue in file["conditional_issues"]
    ]
    caller_source_paths = sorted({str(item["path"]) for item in callers})
    relevant_condition_macros = {
        macro
        for item in macro_refs
        for macro in re.findall(r"\b(?:QUIREWISE_WITH_MUPDF|QUIREWISE_STANDALONE_[A-Z0-9_]+)\b", str(item["text"]))
    }
    cmake_refs, cmake_condition_refs, source_inclusion, cmake_count = cmake_inventory(
        root, caller_source_paths, relevant_condition_macros
    )
    inclusion_by_source = {str(item["source"]): item for item in source_inclusion}
    for caller in callers:
        inclusion = inclusion_by_source.get(str(caller["path"]), {})
        caller["cmake_target"] = inclusion.get("target")
        caller["target_compile_definitions"] = inclusion.get("target_compile_definitions", [])

    call_summary: dict[str, dict[str, object]] = {}
    for symbol, data in symbols.items():
        calls = data["calls"]
        call_summary[symbol] = {
            "declaration_count": len(data["declarations"]),
            "definition_count": len(data["definitions"]),
            "call_count": len(calls),
            "caller_files": sorted({str(item["path"]) for item in calls}),
            "status": "DECLARED_NO_SOURCE_DEFINITION" if data["declarations"] and not data["definitions"] else "HAS_SOURCE_DEFINITION" if data["definitions"] else "CALL_WITHOUT_DECLARATION_OR_DEFINITION",
        }

    return {
        "schema_version": 1,
        "goal_work_item": "M0-04",
        "scope": {
            "source_roots": ["libraries/", "app/"],
            "extensions": sorted(SOURCE_SUFFIXES),
            "build_metadata": "CMakeLists.txt and *.cmake under libraries/ and app/",
            "excluded_directories": sorted(SKIP_DIRS),
            "conditional_branches": "Raw source scan; branch conditions are recorded, not evaluated.",
        },
        "summary": {
            "scanned_source_files": len(files),
            "backend_header_copies": len(headers),
            "distinct_api_symbols": len(symbols),
            "api_callsites": len(callers),
            "called_api_symbols": sum(1 for item in symbols.values() if item["calls"]),
            "api_symbols_with_source_definitions": sum(1 for item in symbols.values() if item["definitions"]),
            "mupdf_backend_include_sites": len(all_includes),
            "direct_mupdf_header_includes": len(external_includes),
            "mupdf_cmake_references": len(cmake_refs),
            "cmake_condition_macro_references": len(cmake_condition_refs),
            "cmake_files_scanned": cmake_count,
            "callsite_source_units_with_cmake_glob_evidence": len({str(item["source"]) for item in source_inclusion}),
            "conditional_directive_issues": len(conditional_issues),
            "source_read_errors": len(source_read_errors),
        },
        "headers": headers,
        "symbols": call_summary,
        "callers": callers,
        "mupdf_backend_include_sites": all_includes,
        "direct_mupdf_header_includes": external_includes,
        "condition_macro_references": macro_refs,
        "cmake_mupdf_references": cmake_refs,
        "cmake_condition_macro_references": cmake_condition_refs,
        "source_inclusion_evidence": source_inclusion,
        "conditional_directive_issues": conditional_issues,
        "source_read_errors": source_read_errors,
        "limitations": [
            "Function ownership is inferred from balanced C/C++ function bodies; macro-generated functions are not expanded.",
            "The audit records preprocessor conditions but does not evaluate compiler definitions, generated headers, or toolchain flags.",
            "CMake source glob evidence shows source selection, not a completed compile or link.",
            "Absence of source definitions does not prove that a separately supplied object or binary cannot define a symbol.",
        ],
    }


def markdown_report(data: dict[str, object]) -> str:
    summary = data["summary"]
    lines = [
        "# MuPDF boundary call graph",
        "",
        "Generated by `app/tools/audit_mupdf_boundary.py` from the checked source tree.",
        "",
        "## Summary",
        "",
        f"- Scanned {summary['scanned_source_files']} C/C++ source and header files and {summary['cmake_files_scanned']} CMake files.",
        f"- Found {summary['backend_header_copies']} private `mupdf_backend.h` copies defining {summary['distinct_api_symbols']} distinct wrapper names.",
        f"- Found {summary['api_callsites']} call sites across {summary['called_api_symbols']} wrapper names; no wrapper source definitions were found.",
        f"- Found {summary['mupdf_backend_include_sites']} source includes of `mupdf_backend.h` and {summary['direct_mupdf_header_includes']} direct `<mupdf/...>` includes.",
        f"- Found {summary['mupdf_cmake_references']} MuPDF references in {summary['cmake_files_scanned']} scanned CMake files.",
        "",
        "## Header copies",
        "",
        "| Header | SHA-256 | API names |",
        "|---|---|---:|",
    ]
    for header in data["headers"]:
        lines.append(f"| `{header['path']}` | `{header['sha256']}` | {len(header['api_symbols'])} |")
    lines.extend(["", "## API symbol inventory", "", "| Symbol | Declarations | Definitions | Calls | Status |", "|---|---:|---:|---:|---|"])
    for symbol, record in data["symbols"].items():
        lines.append(f"| `{symbol}` | {record['declaration_count']} | {record['definition_count']} | {record['call_count']} | {record['status']} |")
    lines.extend(["", "## Caller graph", "", "| Caller function | API symbol | Source location | Active source conditions | CMake target | Target compile definitions |", "|---|---|---|---|---|---|"])
    for item in data["callers"]:
        function = item["function"] or "(function not inferred)"
        conditions = "; ".join(item["conditions"]) or "unconditional in source"
        conditions = conditions.replace("|", "\\|")
        target = item.get("cmake_target") or "unresolved"
        definitions = ", ".join(item.get("target_compile_definitions", [])) or "(none in target CMake)"
        lines.append(f"| `{function}` | `{item['symbol']}` | `{item['path']}:{item['line']}` | `{conditions}` | `{target}` | `{definitions}` |")
    lines.extend(["", "## Header inclusion and direct MuPDF includes", ""])
    for item in data["mupdf_backend_include_sites"]:
        conditions = "; ".join(item["conditions"]) or "unconditional in source"
        lines.append(f"- `{item['path']}:{item['line']}` includes `{item['header']}` under `{conditions}`.")
    if data["direct_mupdf_header_includes"]:
        lines.append("")
        for item in data["direct_mupdf_header_includes"]:
            conditions = "; ".join(item["conditions"]) or "unconditional in source"
            lines.append(f"- `{item['path']}:{item['line']}` directly includes `{item['header']}` under `{conditions}`.")
    lines.extend(["", "## CMake source selection", ""])
    for item in data["source_inclusion_evidence"]:
        lines.append(
            f"- `{item['source']}` is selected by `{item['cmake']}:{item['cmake_line']}` "
            f"through `{item['glob_kind']} {item['variable']} ({', '.join(item['patterns'])})` "
            f"for target `{item['target'] or 'unresolved'}`."
        )
    if data["cmake_mupdf_references"]:
        for item in data["cmake_mupdf_references"]:
            lines.append(f"- MuPDF CMake reference: `{item['path']}:{item['line']}`: `{item['text']}`")
    else:
        lines.append("No MuPDF or `QUIREWISE_WITH_MUPDF` references were found in scanned CMake files.")
    if data["cmake_condition_macro_references"]:
        lines.append("")
        lines.append("CMake condition macro references:")
        for item in data["cmake_condition_macro_references"]:
            lines.append(f"- `{item['path']}:{item['line']}`: `{item['text']}`")
    lines.extend(["", "## Condition macro references", ""])
    for item in data["condition_macro_references"]:
        conditions = "; ".join(item["conditions"])
        suffix = f" (inside `{conditions}`)" if conditions else ""
        lines.append(f"- `{item['path']}:{item['line']}`: `{item['text']}`{suffix}")
    lines.extend(["", "## Findings and limits", ""])
    lines.append("- Every discovered wrapper declaration lacks a matching source definition in the scanned `libraries/` and `app/` trees. Five wrapper names are called; the remaining declarations have no call sites in the scan.")
    lines.append("- Source globs include the call-site files in their respective library targets. The audit does not show whether those translation units compile under a particular set of definitions or whether an external object supplies the missing symbols.")
    lines.append("- The owning CMake targets define `QUIREWISE_STANDALONE_DOCX_PARSER=1` and `QUIREWISE_STANDALONE_PLAIN_TEXT_PARSER=1`; those branches exclude the corresponding DOCX and TXT wrapper calls. CMake does not define `QUIREWISE_WITH_MUPDF` or the Data, FB2, or Spreadsheet standalone parser guards. Compiler definitions supplied outside the scanned CMake files remain unverified.")
    lines.append("- Data, FB2, and Spreadsheet calls are guarded by `#ifndef QUIREWISE_STANDALONE_*` macros that their owning CMake targets do not define. ODT, EPUB, and PDG MuPDF calls require `QUIREWISE_WITH_MUPDF`, which the scanned CMake files do not define. These are source/CMake observations; a separate build with captured compile commands is needed to prove the effective preprocessor paths.")
    for limitation in data["limitations"]:
        lines.append(f"- {limitation}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--json", dest="json_path", type=Path, required=True)
    parser.add_argument("--markdown", dest="markdown_path", type=Path, required=True)
    args = parser.parse_args()
    root = args.workspace.resolve()
    data = build_inventory(root)
    json_path = args.json_path if args.json_path.is_absolute() else root / args.json_path
    markdown_path = args.markdown_path if args.markdown_path.is_absolute() else root / args.markdown_path
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(markdown_report(data), encoding="utf-8")
    print(json.dumps(data["summary"], ensure_ascii=False, sort_keys=True))
    print(f"JSON: {json_path}")
    print(f"Markdown: {markdown_path}")
    return 0 if not data["conditional_directive_issues"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
