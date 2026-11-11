#!/usr/bin/env python3
"""Smoke-test the ported quirewise CLI with a real conversion round trip.

The test writes a small HTML file inside a temporary directory, converts it to
PDF, extracts the text back, checks --check, and verifies that existing outputs
are never overwritten. It is invoked by run_acceptance.py as the app.smoke
step so every build matrix exercises the CLI.
"""
from __future__ import annotations

import base64
import pathlib
import subprocess
import sys
import tempfile

HTML = "<html><body><h1>CLI port</h1><p>Smoke test.</p></body></html>"
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQ"
    "DwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def fail(message: str) -> "NoReturn":
    print(f"FAIL: {message}", file=sys.stderr)
    sys.exit(1)


def run(exe: pathlib.Path, args: list[str], cwd: pathlib.Path,
        expect: int = 0) -> subprocess.CompletedProcess:
    completed = subprocess.run(
        [str(exe), *args], cwd=cwd, capture_output=True, text=True,
    )
    if completed.returncode != expect:
        print(completed.stdout, end="")
        print(completed.stderr, end="", file=sys.stderr)
        return fail(f"command {' '.join(args)} exited {completed.returncode}, "
                    f"expected {expect}")
    return completed


def main() -> int:
    if len(sys.argv) != 2:
        return fail("usage: smoke_app.py <quirewise executable>")
    exe = pathlib.Path(sys.argv[1]).resolve()
    if not exe.is_file():
        return fail(f"missing executable: {exe}")

    version = subprocess.run([str(exe), "--version"], capture_output=True,
                             text=True)
    if version.returncode != 0 or "Quirewise application" not in version.stdout:
        return fail(f"--version failed: {version.stdout} {version.stderr}")
    libraries = subprocess.run([str(exe), "--libraries"], capture_output=True,
                               text=True)
    if libraries.returncode != 0:
        return fail(f"--libraries failed: {libraries.stderr}")

    with tempfile.TemporaryDirectory(prefix="qw-cli-") as directory:
        root = pathlib.Path(directory)
        (root / "sample.html").write_bytes(b"\xef\xbb\xbf\n" + HTML.encode())
        run(exe, ["sample.html"], root)
        pdf = root / "sample.pdf"
        if not pdf.is_file() or pdf.stat().st_size < 8:
            return fail("HTML to PDF produced no output")
        if pdf.read_bytes()[:5] != b"%PDF-":
            return fail("HTML to PDF output is not a PDF")

        run(exe, ["sample.pdf", "--to", "txt"], root)
        text = (root / "sample.txt").read_text(encoding="utf-8", errors="replace")
        if "CLI port" not in text:
            return fail("PDF to TXT lost the rendered text")

        check = run(exe, ["sample.html", "--check"], root)
        if check.stdout.strip() != "OK":
            return fail(f"--check printed {check.stdout!r}")

        before = pdf.read_bytes()
        run(exe, ["sample.html", "-o", "sample.pdf"], root, expect=1)
        if pdf.read_bytes() != before:
            return fail("existing output was overwritten")

        run(exe, ["sample.pdf", "--to", "jpg"], root, expect=2)

        (root / "image.png").write_bytes(PNG_1X1)
        run(exe, ["image.png"], root)
        image_pdf = root / "image.pdf"
        if not image_pdf.is_file() or image_pdf.read_bytes()[:5] != b"%PDF-":
            return fail("image to PDF produced no PDF")

        (root / "notes.txt").write_bytes(b"\xef\xbb\xbfHello\nWorld\n")
        run(exe, ["notes.txt"], root)
        notes_pdf = root / "notes.pdf"
        if not notes_pdf.is_file() or notes_pdf.read_bytes()[:5] != b"%PDF-":
            return fail("text to PDF produced no PDF")

        (root / "table.csv").write_text("a,b\n1,2\n", encoding="utf-8")
        run(exe, ["table.csv"], root)
        table_pdf = root / "table.pdf"
        if not table_pdf.is_file() or table_pdf.read_bytes()[:5] != b"%PDF-":
            return fail("CSV to PDF produced no PDF")

    print("CLI smoke OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
