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
import zipfile

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

        workspace = pathlib.Path(__file__).resolve().parents[2]
        djvu = workspace / "libraries/quirewise-page/tests/data/djvu/multipage.djvu"
        if djvu.is_file():
            (root / "book.djvu").write_bytes(djvu.read_bytes())
            run(exe, ["book.djvu"], root)
            djvu_pdf = root / "book.pdf"
            if not djvu_pdf.is_file() or djvu_pdf.read_bytes()[:5] != b"%PDF-":
                return fail("DjVu to PDF produced no PDF")
            check = run(exe, ["book.djvu", "--check"], root)
            if check.stdout.strip() != "OK":
                return fail(f"DjVu --check printed {check.stdout!r}")

        srt = workspace / "app/testfile/subtitle/srt/example.srt"
        if srt.is_file():
            subtitle_pdf = root / "subtitle.pdf"
            run(exe, [str(srt), "-o", str(subtitle_pdf)], root)
            if (not subtitle_pdf.is_file() or
                    subtitle_pdf.read_bytes()[:5] != b"%PDF-"):
                return fail("subtitle to PDF produced no PDF")
            check = run(exe, [str(srt), "--check"], root)
            if check.stdout.strip() != "OK":
                return fail(f"subtitle --check printed {check.stdout!r}")

        wav = workspace / "app/testfile/audio/wav/Sine440Hz_S16.wav"
        if wav.is_file():
            check = run(exe, [str(wav), "--check"], root)
            if check.stdout.strip() != "OK":
                return fail(f"audio --check printed {check.stdout!r}")

        (root / "data.json").write_text(
            '{"name": "Quirewise", "items": [1, 2, {"ok": true}]}',
            encoding="utf-8")
        run(exe, ["data.json"], root)
        data_pdf = root / "data.pdf"
        if not data_pdf.is_file() or data_pdf.read_bytes()[:5] != b"%PDF-":
            return fail("JSON to PDF produced no PDF")

        with zipfile.ZipFile(root / "comic.cbz", "w") as archive:
            archive.writestr("page-01.png", PNG_1X1)
            archive.writestr("page-02.png", PNG_1X1)
        run(exe, ["comic.cbz"], root)
        comic_pdf = root / "comic.pdf"
        if not comic_pdf.is_file() or comic_pdf.read_bytes()[:5] != b"%PDF-":
            return fail("CBZ to PDF produced no PDF")

        # Batch conversion into --out-dir.
        outdir = root / "out"
        outdir.mkdir()
        run(exe, ["sample.html", "notes.txt", "--out-dir", str(outdir)], root)
        for name in ("sample.pdf", "notes.pdf"):
            if not (outdir / name).is_file():
                return fail(f"--out-dir did not produce {name}")

        # A4 page boxes for raster page routes.
        if djvu.is_file():
            a4_pdf = root / "a4.pdf"
            run(exe, ["book.djvu", "--page", "a4", "-o", str(a4_pdf)], root)
            if b"/MediaBox [0 0 595 842]" not in a4_pdf.read_bytes():
                return fail("--page a4 did not emit an A4 media box")

        # --quiet suppresses success output.
        quiet_check = run(exe, ["sample.html", "--check", "--quiet"], root)
        if quiet_check.stdout.strip():
            return fail("--quiet still printed success output")

        # Audio track selection is accepted by --check.
        if wav.is_file():
            run(exe, [str(wav), "--check", "--audio-track", "1"], root)

    print("CLI smoke OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
