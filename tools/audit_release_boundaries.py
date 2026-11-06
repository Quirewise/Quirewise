#!/usr/bin/env python3
"""Static denylist audit for Quirewise production sources and package files.

This is a first-pass source/configuration gate. It scans raw source files, so
disabled ``#if`` branches are included. It deliberately does not claim to
replace compile-command, archive-symbol, installed-header, binary dependency,
or runtime-loader audits; those require built artifacts and are reported as
separate acceptance evidence.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Iterable


AUDIT_ID = "QW-M0-01"
AUDIT_VERSION = 1
SOURCE_SUFFIXES = {
    ".c",
    ".h",
    ".cc",
    ".cpp",
    ".cxx",
    ".hh",
    ".hpp",
    ".hxx",
    ".m",
    ".mm",
    ".py",
    ".cmake",
    ".in",
}
CMAKE_NAMES = {"CMakeLists.txt"}
IGNORED_DIRECTORY_NAMES = {
    ".git",
    ".codegraph",
    "__pycache__",
    "build",
    "cmake-build-debug",
    "cmake-build-release",
    "dist",
    "node_modules",
    ".tmp",
    "tmp",
    "test",
    "tests",
}

HEADER_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("third_party_header:lzma", re.compile(r"(?i)(?:^|[<\"/\\])lzma\.h\b")),
    ("third_party_header:openssl", re.compile(r"(?i)(?:^|[<\"/\\])openssl/")),
    ("third_party_header:webp", re.compile(r"(?i)(?:^|[<\"/\\])webp/")),
    ("third_party_header:openjpeg", re.compile(r"(?i)(?:^|[<\"/\\])openjpeg\.h\b")),
    ("third_party_header:djvulibre", re.compile(r"(?i)(?:^|[<\"/\\])libdjvu/")),
    ("third_party_header:mupdf", re.compile(r"(?i)(?:^|[<\"/\\])mupdf/")),
    ("third_party_header:zlib", re.compile(r"(?i)(?:^|[<\"/\\])zlib\.h\b")),
    ("third_party_header:jpeg", re.compile(r"(?i)(?:^|[<\"/\\])jpeglib\.h\b")),
    ("third_party_header:iconv", re.compile(r"(?i)(?:^|[<\"/\\])iconv\.h\b")),
    ("third_party_header:avif", re.compile(r"(?i)(?:^|[<\"/\\])avif/")),
    ("third_party_header:heif", re.compile(r"(?i)(?:^|[<\"/\\])libheif/")),
    ("third_party_header:jxl", re.compile(r"(?i)(?:^|[<\"/\\])jxl/")),
    ("third_party_header:ffmpeg", re.compile(r"(?i)(?:^|[<\"/\\])libavcodec/")),
    ("third_party_header:libraw", re.compile(r"(?i)(?:^|[<\"/\\])libraw/")),
)

SYMBOL_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("third_party_symbol:lzma", re.compile(r"\blzma_[A-Za-z0-9_]*\b")),
    ("third_party_symbol:openssl_bn", re.compile(r"\bBN_[A-Za-z0-9_]*\b")),
    ("third_party_symbol:openssl_des", re.compile(r"\bDES_[A-Za-z0-9_]*\b")),
    ("third_party_symbol:openssl", re.compile(r"\bOPENSSL_[A-Za-z0-9_]*\b")),
    (
        "third_party_symbol:webp",
        # Real libwebp public identifiers are PascalCase after the ``WebP``
        # prefix (``WebPDecode*``, ``WebPAnimDecoder``...). Quirewise's own
        # WebP lossless types use two consecutive capitals (``WebPLBitReader``,
        # ``WebPLTransform``), so requiring a lower-case second letter keeps
        # the symbol-boundary rule from flagging internal identifiers.
        re.compile(r"\bWebP[A-Z][a-z][A-Za-z0-9_]*\b"),
    ),
    ("third_party_symbol:openjpeg", re.compile(r"\bopj_[A-Za-z0-9_]*\b")),
    ("third_party_symbol:djvulibre", re.compile(r"\bddjvu_[A-Za-z0-9_]*\b")),
    ("third_party_symbol:mupdf", re.compile(r"\bfz_[A-Za-z0-9_]*\b")),
    (
        "third_party_symbol:zlib",
        re.compile(r"\b(?:inflate|deflate)(?:Init|Reset|End)[A-Za-z0-9_]*\b"),
    ),
    (
        "third_party_symbol:jpeg",
        re.compile(
            r"\b(?:jpeg_std_error|jpeg_destroy_decompress|jpeg_create_decompress|"
            r"jpeg_mem_src|jpeg_read_header|jpeg_start_decompress|"
            r"jpeg_read_scanlines|jpeg_finish_decompress)\b"
        ),
    ),
    ("third_party_symbol:iconv", re.compile(r"\biconv_(?:open|close)\b|\biconv\s*\(")),
)
BINARY_GENERIC_ZLIB_SYMBOLS = re.compile(r"\b(?:inflate|deflate|crc32|adler32)\b")
DYNAMIC_LIBRARY_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("third_party_runtime:zlib", re.compile(r"(?i)(?:^|[/\\@\s])(?:lib)?(?:zlib(?:wapi)?|z)(?:[-.]?\d+)?\.(?:dll|dylib|so(?:\.\d+)*)\b")),
    ("third_party_runtime:lzma", re.compile(r"(?i)(?:^|[/\\@\s])(?:lib)?lzma(?:[-.]?\d+)?\.(?:dll|dylib|so(?:\.\d+)*)\b")),
    ("third_party_runtime:openssl_crypto", re.compile(r"(?i)(?:^|[/\\@\s])(?:lib)?crypto(?:[-.]?\d+)?\.(?:dll|dylib|so(?:\.\d+)*)\b")),
    ("third_party_runtime:openssl_ssl", re.compile(r"(?i)(?:^|[/\\@\s])(?:lib)?ssl(?:[-.]?\d+)?\.(?:dll|dylib|so(?:\.\d+)*)\b")),
    ("third_party_runtime:webp", re.compile(r"(?i)(?:^|[/\\@\s])(?:lib)?webp(?:demux)?(?:[-.]?\d+)?\.(?:dll|dylib|so(?:\.\d+)*)\b")),
    ("third_party_runtime:openjpeg", re.compile(r"(?i)(?:^|[/\\@\s])(?:lib)?openjp2(?:[-.]?\d+)?\.(?:dll|dylib|so(?:\.\d+)*)\b")),
    ("third_party_runtime:djvulibre", re.compile(r"(?i)(?:^|[/\\@\s])(?:lib)?(?:djvulibre|ddjvuapi|djvu)(?:[-.]?\d+)?\.(?:dll|dylib|so(?:\.\d+)*)\b")),
    ("third_party_runtime:mupdf", re.compile(r"(?i)(?:^|[/\\@\s])(?:lib)?mupdf(?:[-.]?\d+)?\.(?:dll|dylib|so(?:\.\d+)*)\b")),
    ("third_party_runtime:jpeg", re.compile(r"(?i)(?:^|[/\\@\s])(?:lib)?jpeg(?:[-_]turbo)?(?:[-.]?\d+)?\.(?:dll|dylib|so(?:\.\d+)*)\b")),
    ("third_party_runtime:iconv", re.compile(r"(?i)(?:^|[/\\@\s])(?:lib)?iconv(?:[-.]?\d+)?\.(?:dll|dylib|so(?:\.\d+)*)\b")),
)

DYNAMIC_LOAD_RULE = re.compile(
    r"\b(?:dlopen|dlsym|LoadLibrary(?:A|W|Ex|ExA|ExW)?|GetProcAddress)\b"
)
CMAKE_COMMAND_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
CMAKE_LINK_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("cmake_external_link:zlib", re.compile(r"\bZLIB::ZLIB\b|(?<![A-Za-z0-9_])zlib(?![A-Za-z0-9_])|(?<!\S)-lz(?:lib)?(?=\s|$)", re.I)),
    ("cmake_external_link:lzma", re.compile(r"\bLibLZMA::LibLZMA\b|(?<![A-Za-z0-9_])(?:lib)?lzma(?![A-Za-z0-9_])|(?<!\S)-llzma(?=\s|$)", re.I)),
    ("cmake_external_link:openssl", re.compile(r"\bOpenSSL::(?:SSL|Crypto)\b|(?<![A-Za-z0-9_:])(?:lib)?(?:ssl|crypto)(?![A-Za-z0-9_])|(?<!\S)-l(?:ssl|crypto)(?=\s|$)", re.I)),
    ("cmake_external_link:webp", re.compile(r"\bWebP::[A-Za-z0-9_]+\b|(?<![A-Za-z0-9_])(?:lib)?webp(?:demux)?(?![A-Za-z0-9_])|(?<!\S)-lwebp(?:demux)?(?=\s|$)", re.I)),
    ("cmake_external_link:openjpeg", re.compile(r"\bOpenJPEG::[A-Za-z0-9_]+\b|(?<![A-Za-z0-9_])(?:lib)?openjp2(?![A-Za-z0-9_])|(?<!\S)-lopenjp2(?=\s|$)", re.I)),
    ("cmake_external_link:djvulibre", re.compile(r"(?<![A-Za-z0-9_])(?:lib)?(?:djvu|ddjvuapi)(?![A-Za-z0-9_])|(?<!\S)-l(?:djvu|djvulibre|ddjvuapi)(?=\s|$)", re.I)),
    ("cmake_external_link:mupdf", re.compile(r"(?<![A-Za-z0-9_])(?:lib)?mupdf(?![A-Za-z0-9_])|(?<!\S)-lmupdf(?=\s|$)", re.I)),
    ("cmake_external_link:jpeg", re.compile(r"\bJPEG::JPEG\b|(?<![A-Za-z0-9_])(?:lib)?jpeg(?![A-Za-z0-9_])|(?<!\S)-ljpeg(?=\s|$)", re.I)),
    ("cmake_external_link:iconv", re.compile(r"\bIconv::Iconv\b|(?<![A-Za-z0-9_])(?:lib)?iconv(?![A-Za-z0-9_])|(?<!\S)-liconv(?=\s|$)", re.I)),
    ("cmake_external_link:pkgconfig", re.compile(r"\bPkgConfig::[A-Za-z0-9_]+\b|\bPkgConfig\b", re.I)),
)
def _strip_c_comments(text: str) -> str:
    """Remove C/C++ comments while preserving offsets and line numbers."""

    output = list(text)
    index = 0
    state = "code"
    while index < len(text):
        current = text[index]
        following = text[index + 1] if index + 1 < len(text) else ""
        if state == "code":
            if current == '"':
                state = "string"
            elif current == "'":
                state = "character"
            elif current == "/" and following == "/":
                output[index] = output[index + 1] = " "
                index += 1
                state = "line_comment"
            elif current == "/" and following == "*":
                output[index] = output[index + 1] = " "
                index += 1
                state = "block_comment"
        elif state in {"string", "character"}:
            if current == "\\":
                index += 1
            elif (state == "string" and current == '"') or (
                state == "character" and current == "'"
            ):
                state = "code"
        elif state == "line_comment":
            if current in "\r\n":
                state = "code"
            else:
                output[index] = " "
        elif state == "block_comment":
            if current == "*" and following == "/":
                output[index] = output[index + 1] = " "
                index += 1
                state = "code"
            elif current not in "\r\n":
                output[index] = " "
        index += 1
    return "".join(output)


def _mask_c_strings(text: str) -> str:
    """Mask string and character literals before matching symbol references."""

    output = list(text)
    index = 0
    quote = ""
    escaped = False
    while index < len(text):
        character = text[index]
        if not quote:
            if character in {'"', "'"}:
                quote = character
                output[index] = " "
        elif escaped:
            escaped = False
            if character not in "\r\n":
                output[index] = " "
        elif character == "\\":
            escaped = True
            output[index] = " "
        elif character == quote:
            quote = ""
            output[index] = " "
        elif character not in "\r\n":
            output[index] = " "
        index += 1
    return "".join(output)


def _strip_cmake_comments(text: str) -> str:
    """Remove whole-line and trailing CMake comments without touching strings."""

    output: list[str] = []
    quoted = False
    for line in text.splitlines(keepends=True):
        escaped = False
        cut = len(line)
        for index, character in enumerate(line):
            if escaped:
                escaped = False
                continue
            if character == "\\":
                escaped = True
            elif character == '"':
                quoted = not quoted
            elif character == "#" and not quoted:
                cut = index
                break
        comment = line[cut:]
        preserved = "".join(
            character if character in "\r\n" else " " for character in comment
        )
        output.append(line[:cut] + preserved)
    return "".join(output)


def _cmake_commands(text: str) -> Iterable[tuple[str, str, int, int]]:
    """Yield CMake commands with balanced parentheses and quote awareness."""

    index = 0
    quoted = False
    escaped = False
    while index < len(text):
        character = text[index]
        if escaped:
            escaped = False
            index += 1
            continue
        if character == "\\":
            escaped = True
            index += 1
            continue
        if character == '"':
            quoted = not quoted
            index += 1
            continue
        if quoted or not (character.isalpha() or character == "_"):
            index += 1
            continue

        name_match = CMAKE_COMMAND_NAME.match(text, index)
        if not name_match:
            index += 1
            continue
        open_index = name_match.end()
        while open_index < len(text) and text[open_index].isspace():
            open_index += 1
        if open_index >= len(text) or text[open_index] != "(":
            index = name_match.end()
            continue

        depth = 1
        cursor = open_index + 1
        command_quoted = False
        command_escaped = False
        while cursor < len(text) and depth:
            current = text[cursor]
            if command_escaped:
                command_escaped = False
            elif current == "\\":
                command_escaped = True
            elif current == '"':
                command_quoted = not command_quoted
            elif not command_quoted and current == "(":
                depth += 1
            elif not command_quoted and current == ")":
                depth -= 1
            cursor += 1
        if depth:
            break
        yield name_match.group(0).lower(), text[open_index + 1 : cursor - 1], index, cursor
        index = cursor


def _finding_at(
    findings: list[dict[str, object]],
    rule: str,
    path: Path,
    workspace: Path,
    text: str,
    offset: int,
    matched_text: str,
) -> None:
    findings.append(
        {
            "rule": rule,
            "path": _relative(path, workspace),
            "line": _line_number(text, offset),
            "match": " ".join(matched_text.split())[:160],
        }
    )


def _is_optional_python_validation(path: Path, conditions: list[str], package: str) -> bool:
    return (
        path.name == "CMakeLists.txt"
        and path.parent.name == "app"
        and package.lower() == "python3"
        and any(re.sub(r"\s+", "", condition).upper() == "QUIREWISE_VALIDATE_DEPENDENCIES"
                for condition in conditions)
    )


def _public_include_match(arguments: str) -> tuple[int, str] | None:
    scopes = list(re.finditer(r"\b(PUBLIC|PRIVATE|INTERFACE)\b", arguments, re.I))
    for index, scope in enumerate(scopes):
        if scope.group(1).upper() not in {"PUBLIC", "INTERFACE"}:
            continue
        end = scopes[index + 1].start() if index + 1 < len(scopes) else len(arguments)
        match = re.search(r"third_party|stb/", arguments[scope.end() : end], re.I)
        if match:
            return scope.end() + match.start(), match.group(0)
    return None


def _public_install_match(arguments: str) -> tuple[int, str] | None:
    if not re.match(r"\s*(?:FILES|DIRECTORY)\b", arguments, re.I):
        return None
    match = re.search(r"third_party|stb_image\.h|stb/", arguments, re.I)
    if not match:
        return None
    return match.start(), match.group(0)


def run_self_tests() -> int:
    checks = 0
    assert HEADER_RULES[0][1].search('#include <lzma.h>')
    checks += 1
    assert SYMBOL_RULES[0][1].search("lzma_stream_decoder")
    checks += 1
    assert SYMBOL_RULES[8][1].search("inflateInit2")
    checks += 1
    assert not any(pattern.search("qw_inflate qw_crc32 qw_adler32") for _, pattern in SYMBOL_RULES)
    checks += 1
    assert DYNAMIC_LOAD_RULE.search("handle = dlopen(name, flags)")
    checks += 1
    lexical = _strip_c_comments(
        'const char *url = "https://example.test/dlopen"; '
        'WebPDecodeRGBA(); // GetProcAddress is only mentioned in this comment\n'
    )
    assert SYMBOL_RULES[4][1].search(_mask_c_strings(lexical))
    assert not DYNAMIC_LOAD_RULE.search(_mask_c_strings(lexical))
    checks += 1
    assert SYMBOL_RULES[4][1].search("WebPDecodeRGBA(decoder)")
    assert not SYMBOL_RULES[4][1].search("WebPLBitReader reader")
    assert not SYMBOL_RULES[4][1].search("WebPLTransform transform")
    checks += 1
    assert _is_path_segment("src/internal/lzma_sdk/LzmaDec.c", 13)
    assert not _is_path_segment("lzma_stream_decoder", 0)
    checks += 1
    commands = list(
        _cmake_commands(
            'target_link_libraries(t PRIVATE "$<$<NOT:$<PLATFORM_ID:Windows>>:m>" '
            "LibLZMA::LibLZMA)"
        )
    )
    assert len(commands) == 1 and "LibLZMA::LibLZMA" in commands[0][1]
    checks += 1
    assert _public_include_match(
        'target PUBLIC "$<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/third_party/stb>"'
    )
    checks += 1
    assert not _public_include_match(
        'target PUBLIC "$<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>" '
        'PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}/third_party/aes"'
    )
    checks += 1
    assert _public_install_match("FILES third_party/stb/stb_image.h DESTINATION include")
    checks += 1
    assert _is_optional_python_validation(
        Path("workspace/app/CMakeLists.txt"), ["QUIREWISE_VALIDATE_DEPENDENCIES"], "Python3"
    )
    checks += 1
    assert DYNAMIC_LIBRARY_RULES[1][1].search("liblzma.so.5")
    assert DYNAMIC_LIBRARY_RULES[4][1].search("C:/app/libwebp-7.dll")
    assert not any(pattern.search("libm.so.6") for _, pattern in DYNAMIC_LIBRARY_RULES)
    checks += 1
    assert not CMAKE_LINK_RULES[2][1].search("Quirewise::Crypto")
    assert CMAKE_LINK_RULES[2][1].search("OpenSSL::Crypto")
    assert CMAKE_LINK_RULES[2][1].search("-lcrypto")
    checks += 3
    with tempfile.TemporaryDirectory(prefix="quirewise-audit-") as temporary:
        fixture = Path(temporary)
        source = fixture / "libraries" / "quirewise-fixture" / "src" / "fixture.c"
        source.parent.mkdir(parents=True)
        source.write_text(
            "#if 0\n#include <mupdf/pdf.h>\n#endif\n"
            "int fixture(void) { return qw_inflate(); }\n",
            encoding="utf-8",
            newline="\n",
        )
        cmake_file = source.parents[1] / "CMakeLists.txt"
        cmake_file.write_text(
            "if(FALSE)\nfind_package(OpenSSL REQUIRED)\nendif()\n"
            "install(FILES third_party/private.h DESTINATION include)\n",
            encoding="utf-8",
            newline="\n",
        )
        fixture_report = audit_workspace(fixture)
        fixture_rules = {str(item["rule"]) for item in fixture_report["findings"]}
        assert fixture_report["exit_code"] == 1
        assert "third_party_header:mupdf" in fixture_rules
        assert "cmake_external_package:OpenSSL" in fixture_rules
        assert "public_install_third_party_path" in fixture_rules
        assert not any("qw_inflate" in str(item["match"]) for item in fixture_report["findings"])
        dependency_listing = fixture / "dependencies.txt"
        dependency_listing.write_text("liblzma.so.5\nlibm.so.6\n", encoding="utf-8", newline="\n")
        symbol_listing = fixture / "undefined-symbols.txt"
        symbol_listing.write_text(
            "                 U lzma_code\n                 U crc32\n"
            "00000000 T crc32\n                 U qw_inflate\n",
            encoding="utf-8",
            newline="\n",
        )
        artifact_report = audit_workspace(fixture, [dependency_listing], [symbol_listing])
        artifact_rules = {str(item["rule"]) for item in artifact_report["findings"]}
        assert "third_party_runtime:lzma" in artifact_rules
        assert "artifact_third_party_symbol:lzma" in artifact_rules
        assert "artifact_third_party_symbol:zlib" in artifact_rules
        assert not any("qw_inflate" in str(item["match"]) for item in artifact_report["findings"])
        assert sum(item["rule"] == "artifact_third_party_symbol:zlib" for item in artifact_report["findings"]) == 1
    checks += 1
    print(f"QW-M0-01 self-test: {checks} checks passed")
    return 0


def _relative(path: Path, workspace: Path) -> str:
    return path.relative_to(workspace).as_posix()


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _is_path_segment(text: str, offset: int) -> bool:
    """Return True when a symbol-shaped match is really a path component.

    Bundled sources live under directories such as ``src/internal/lzma_sdk``;
    without this check the ``lzma_*`` symbol rule reports every path mention.
    """

    return offset > 0 and text[offset - 1] in "/\\"


def _finding(
    findings: list[dict[str, object]],
    rule: str,
    path: Path,
    workspace: Path,
    text: str,
    match: re.Match[str],
) -> None:
    findings.append(
        {
            "rule": rule,
            "path": _relative(path, workspace),
            "line": _line_number(text, match.start()),
            "match": " ".join(match.group(0).split())[:160],
        }
    )


def _source_files(workspace: Path) -> Iterable[Path]:
    roots = [workspace / "libraries", workspace / "app" / "src"]
    for root in roots:
        if not root.is_dir():
            continue
        for directory, child_directories, filenames in os.walk(root):
            child_directories[:] = sorted(
                name
                for name in child_directories
                if name.lower() not in IGNORED_DIRECTORY_NAMES
                and not name.lower().startswith("cmake-build-")
            )
            for filename in sorted(filenames):
                path = Path(directory) / filename
                if path.name in CMAKE_NAMES or path.suffix.lower() in SOURCE_SUFFIXES:
                    yield path


def _cmake_files(workspace: Path) -> Iterable[Path]:
    roots = [workspace / "libraries", workspace / "app" / "cmake"]
    app_cmake = workspace / "app" / "CMakeLists.txt"
    if app_cmake.is_file():
        yield app_cmake
    for root in roots:
        if not root.is_dir():
            continue
        for directory, child_directories, filenames in os.walk(root):
            child_directories[:] = sorted(
                name
                for name in child_directories
                if name.lower() not in IGNORED_DIRECTORY_NAMES
                and not name.lower().startswith("cmake-build-")
            )
            for filename in sorted(filenames):
                path = Path(directory) / filename
                if path.name in CMAKE_NAMES or path.suffix.lower() in {".cmake", ".in"}:
                    yield path


def audit_workspace(
    workspace: Path,
    dependency_lists: Iterable[Path] = (),
    undefined_symbol_lists: Iterable[Path] = (),
) -> dict[str, object]:
    workspace = workspace.resolve()
    findings: list[dict[str, object]] = []
    observations: list[dict[str, object]] = []
    read_errors: list[dict[str, str]] = []

    for path in _source_files(workspace):
        try:
            raw_text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError) as error:
            read_errors.append({"path": _relative(path, workspace), "error": str(error)})
            continue
        text = _strip_c_comments(raw_text) if path.suffix.lower() in {
            ".c", ".h", ".cc", ".cpp", ".cxx", ".hh", ".hpp", ".hxx", ".m", ".mm"
        } else raw_text
        for rule, pattern in HEADER_RULES:
            for match in pattern.finditer(text):
                _finding(findings, rule, path, workspace, text, match)
        code_tokens = _mask_c_strings(text) if path.suffix.lower() in {
            ".c", ".h", ".cc", ".cpp", ".cxx", ".hh", ".hpp", ".hxx", ".m", ".mm"
        } else text
        for rule, pattern in SYMBOL_RULES:
            for match in pattern.finditer(code_tokens):
                if _is_path_segment(code_tokens, match.start()):
                    continue
                _finding(findings, rule, path, workspace, text, match)
        for match in DYNAMIC_LOAD_RULE.finditer(code_tokens):
            _finding(findings, "dynamic_loader_api", path, workspace, text, match)

    cmake_file_count = 0
    for path in _cmake_files(workspace):
        cmake_file_count += 1
        try:
            raw_text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError) as error:
            read_errors.append({"path": _relative(path, workspace), "error": str(error)})
            continue
        text = _strip_cmake_comments(raw_text)
        condition_stack: list[str] = []
        for command, arguments, command_start, command_end in _cmake_commands(text):
            stripped_arguments = arguments.strip()
            command_text = text[command_start:command_end]
            arguments_offset = command_start + command_text.find("(") + 1
            if command == "if":
                condition_stack.append(stripped_arguments)
                continue
            if command in {"elseif", "else"}:
                if condition_stack:
                    condition_stack[-1] = stripped_arguments if command == "elseif" else ""
                continue
            if command == "endif":
                if condition_stack:
                    condition_stack.pop()
                continue

            if command in {"find_package", "find_dependency"}:
                package_match = re.match(
                    r"(?:\"([^\"]+)\"|'([^']+)'|([A-Za-z0-9_:+.-]+))",
                    stripped_arguments,
                )
                if package_match:
                    package = next(group for group in package_match.groups() if group)
                    allowed = package.lower().startswith("quirewise") or package.lower() == "threads"
                    if not allowed:
                        target = observations if _is_optional_python_validation(
                            path, condition_stack, package
                        ) else findings
                        rule = (
                            f"cmake_dev_dependency:{package}"
                            if target is observations
                            else f"cmake_external_package:{package}"
                        )
                        _finding_at(target, rule, path, workspace, text, command_start, command_text)

            elif command == "pkg_check_modules":
                _finding_at(
                    findings,
                    "cmake_external_package:PkgConfig",
                    path,
                    workspace,
                    text,
                    command_start,
                    command_text,
                )

            if command in {"find_library", "find_path", "pkg_check_modules"}:
                for rule, pattern in CMAKE_LINK_RULES:
                    for match in pattern.finditer(arguments):
                        _finding_at(
                            findings,
                            rule,
                            path,
                            workspace,
                            text,
                            arguments_offset + match.start(),
                            match.group(0),
                        )
            elif command in {"target_link_libraries", "link_libraries", "target_link_options", "link_options"}:
                for rule, pattern in CMAKE_LINK_RULES:
                    for match in pattern.finditer(arguments):
                        _finding_at(
                            findings,
                            rule,
                            path,
                            workspace,
                            text,
                            arguments_offset + match.start(),
                            match.group(0),
                        )

            if command == "install":
                path_match = _public_install_match(arguments)
                if path_match:
                    argument_offset, matched_path = path_match
                    _finding_at(
                        findings,
                        "public_install_third_party_path",
                        path,
                        workspace,
                        text,
                        arguments_offset + argument_offset,
                        matched_path,
                    )

            if command == "target_include_directories":
                path_match = _public_include_match(arguments)
                if path_match:
                    argument_offset, matched_path = path_match
                    _finding_at(
                        findings,
                        "public_include_third_party_path",
                        path,
                        workspace,
                        text,
                        arguments_offset + argument_offset,
                        matched_path,
                    )

    dependency_list_names: list[str] = []
    for listing in dependency_lists:
        try:
            listing_text = listing.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError) as error:
            read_errors.append({"path": str(listing), "error": str(error)})
            continue
        try:
            listing_name = _relative(listing.resolve(), workspace)
        except ValueError:
            listing_name = listing.name
        dependency_list_names.append(listing_name)
        for line_number, line in enumerate(listing_text.splitlines(), start=1):
            for rule, pattern in DYNAMIC_LIBRARY_RULES:
                match = pattern.search(line)
                if match:
                    findings.append(
                        {
                            "rule": rule,
                            "path": listing_name,
                            "line": line_number,
                            "match": " ".join(match.group(0).split())[:160],
                        }
                    )

    symbol_list_names: list[str] = []
    for listing in undefined_symbol_lists:
        try:
            listing_text = listing.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError) as error:
            read_errors.append({"path": str(listing), "error": str(error)})
            continue
        try:
            listing_name = _relative(listing.resolve(), workspace)
        except ValueError:
            listing_name = listing.name
        symbol_list_names.append(listing_name)
        for line_number, line in enumerate(listing_text.splitlines(), start=1):
            if not re.search(r"(?:^|\s)(?:U|UND|UNDEF|undefined|import)(?:\s|$)", line, re.I):
                continue
            for rule, pattern in SYMBOL_RULES:
                match = pattern.search(line)
                if match:
                    findings.append(
                        {
                            "rule": f"artifact_{rule}",
                            "path": listing_name,
                            "line": line_number,
                            "match": " ".join(match.group(0).split())[:160],
                        }
                    )
            match = BINARY_GENERIC_ZLIB_SYMBOLS.search(line)
            if match:
                findings.append(
                    {
                        "rule": "artifact_third_party_symbol:zlib",
                        "path": listing_name,
                        "line": line_number,
                        "match": match.group(0),
                    }
                )
            match = DYNAMIC_LOAD_RULE.search(line)
            if match:
                findings.append(
                    {
                        "rule": "artifact_dynamic_loader_api",
                        "path": listing_name,
                        "line": line_number,
                        "match": match.group(0),
                    }
                )

    findings.sort(key=lambda item: (str(item["path"]), int(item["line"]), str(item["rule"]), str(item["match"])))
    observations.sort(key=lambda item: (str(item["path"]), int(item["line"]), str(item["rule"])))
    read_errors.sort(key=lambda item: item["path"])
    return {
        "audit_id": AUDIT_ID,
        "audit_version": AUDIT_VERSION,
        "workspace": ".",
        "coverage": {
            "source_roots": ["libraries/", "app/src/"],
            "source_suffixes": sorted(SOURCE_SUFFIXES),
            "conditional_branches": "raw source scanned without preprocessing",
            "cmake_roots": ["libraries/", "app/CMakeLists.txt", "app/cmake/"],
            "cmake_file_count": cmake_file_count,
            "dependency_list_inputs": sorted(dependency_list_names),
            "undefined_symbol_list_inputs": sorted(symbol_list_names),
            "exclusions": sorted(IGNORED_DIRECTORY_NAMES),
            "not_covered": [
                "compiler preprocessor include trees",
                "binary contents are not parsed directly; tool-generated symbol/dependency listings must be supplied",
                "installed prefix contents from a clean build",
            ],
        },
        "finding_count": len(findings),
        "findings": findings,
        "observation_count": len(observations),
        "observations": observations,
        "read_error_count": len(read_errors),
        "read_errors": read_errors,
        "exit_code": 1 if findings or read_errors else 0,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="Quirewise workspace root (default: inferred from this script)",
    )
    parser.add_argument("--json", type=Path, help="write the complete JSON report")
    parser.add_argument("--markdown", type=Path, help="write a concise Markdown report")
    parser.add_argument(
        "--dependency-list",
        type=Path,
        action="append",
        default=[],
        help="audit a dumpbin /DEPENDENTS, readelf -d, otool -L, or equivalent listing",
    )
    parser.add_argument(
        "--undefined-symbol-list",
        type=Path,
        action="append",
        default=[],
        help="audit an nm -u / llvm-nm -u / dumpbin /SYMBOLS listing",
    )
    parser.add_argument("--self-test", action="store_true", help="run built-in denylist and parser checks")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.self_test:
        return run_self_tests()
    report = audit_workspace(args.workspace, args.dependency_list, args.undefined_symbol_list)
    json_text = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json_text, encoding="utf-8", newline="\n")
    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        summary = [
            f"# {AUDIT_ID} Source and Package Baseline",
            "",
            f"- Scanner version: {AUDIT_VERSION}",
            f"- Findings: {report['finding_count']}",
            f"- Non-blocking observations: {report['observation_count']}",
            f"- Read errors: {report['read_error_count']}",
            f"- Exit code: {report['exit_code']}",
            "- Conditional branches: scanned from raw source, without preprocessing",
            "- Binary contents are not parsed directly; use the dependency and undefined-symbol listing inputs",
            "- Installed-prefix contents require a separate clean install audit",
            "",
        ]
        for item in report["findings"]:
            summary.append(
                f"- `{item['rule']}` — `{item['path']}:{item['line']}` — `{item['match']}`"
            )
        for item in report["read_errors"]:
            summary.append(f"- `read_error` — `{item['path']}` — `{item['error']}`")
        for item in report["observations"]:
            summary.append(
                f"- `review` — `{item['path']}:{item['line']}` — `{item['rule']}` — `{item['match']}`"
            )
        args.markdown.write_text("\n".join(summary) + "\n", encoding="utf-8", newline="\n")

    print(
        f"{AUDIT_ID} v{AUDIT_VERSION}: {report['finding_count']} findings, "
        f"{report['read_error_count']} read errors, "
        f"{report['observation_count']} development-tool observations"
    )
    printed = 0
    for item in report["findings"]:
        print(f"{item['path']}:{item['line']}: {item['rule']}: {item['match']}")
        printed += 1
        if printed == 100:
            break
    if report["finding_count"] > printed:
        print(f"... {report['finding_count'] - printed} additional findings are in the JSON report")
    for item in report["read_errors"]:
        print(f"{item['path']}: read_error: {item['error']}")
    for item in report["observations"]:
        print(f"{item['path']}:{item['line']}: {item['rule']}: {item['match']}")
    return int(report["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
