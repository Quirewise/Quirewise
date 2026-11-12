#!/usr/bin/env python3
"""Smoke-test the ported quirewise CLI with a real conversion round trip.

The test writes a small HTML file inside a temporary directory, converts it to
PDF, extracts the text back, checks --check, and verifies that existing outputs
are never overwritten. It also covers the PDG page routes: a PDZ container and
a UVZ bundle whose page payload is a PDF must be rasterised through the
internal PDF engine (no external rasteriser). It is invoked by
run_acceptance.py as the app.smoke step so every build matrix exercises the
CLI.
"""
from __future__ import annotations

import base64
import hashlib
import pathlib
import struct
import subprocess
import sys
import tempfile
import zipfile

HTML = "<html><body><h1>CLI port</h1><p>Smoke test.</p></body></html>"
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQ"
    "DwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)

# --- PDG page-payload PDF fixtures -----------------------------------------
# The PDZ container table is encrypted with the engine's TEA-128 variant; the
# helpers below mirror quirewise-crypto's qw_crypto_pdg_tea128_ecb_decrypt so
# the fixture can be built without a Quirewise dependency.

_M32 = 0xFFFFFFFF
_TEA_DELTA = 0x61C88647
_TEA_SUM0 = 0xE3779B90
_PDZ_CATALOG_KEY = (
    b"4D346125645E6543205C6240795C206A50346141634C6B6F655C742F505E6466"
)
_PDZ_KEY_CONST = (0x00820208, 0x01220208, 0x00805038, 0x00920208)


def _tea_f(a: int, s: int, ka: int, kb: int) -> int:
    return (((a >> 5) + ka) ^ ((a << 4) + kb) ^ (a + s)) & _M32


def _tea_encrypt_block(block: bytes, key: tuple[int, int, int, int]) -> bytes:
    v0, v1, v2, v3 = struct.unpack("<4I", block)
    for round_index in range(15, -1, -1):
        total = (_TEA_SUM0 + round_index * _TEA_DELTA) & _M32
        v0 = (v0 + _tea_f(v1, total, key[1], key[0])) & _M32
        v1 = (v1 + _tea_f(v2, total, key[3], key[2])) & _M32
        v2 = (v2 + _tea_f(v3, total, key[3], key[0])) & _M32
        v3 = (v3 + _tea_f(v0, total, key[1], key[2])) & _M32
    return struct.pack("<4I", v0, v1, v2, v3)


def _pdz_catalog_key() -> tuple[int, int, int, int]:
    digest = hashlib.md5(_PDZ_CATALOG_KEY).digest()
    words = []
    for index in range(4):
        value = struct.unpack("<I", digest[index * 4:index * 4 + 4])[0]
        words.append(value ^ _PDZ_KEY_CONST[index])
    return tuple(words)


def _pdz_container(members: list[tuple[bytes, bytes]]) -> bytes:
    """Build a %pdgz container with plaintext members and an encrypted table."""
    header = bytearray(0x60)
    header[0:5] = b"%pdgz"
    header[8:12] = b"1.01"
    header[0x0D] = 4
    header[0x0F] = 2
    header[0x1C:0x1C + 17] = b"Made by PacketPdg"
    payload = bytearray()
    table = bytearray()
    cursor = 0x60
    for name, data in members:
        table += name.ljust(12, b"\x00") + struct.pack("<II", cursor, len(data))
        payload += data
        cursor += len(data)
    while len(table) % 16:
        table += b"\x00"
    while len(table) // 20 < len(members):
        table += b"\x00" * 20
    key = _pdz_catalog_key()
    encrypted = b"".join(
        _tea_encrypt_block(bytes(table[index:index + 16]), key)
        for index in range(0, len(table), 16))
    struct.pack_into("<I", header, 0x14, 0x60 + len(payload))
    struct.pack_into("<I", header, 0x18, len(encrypted))
    return bytes(header) + bytes(payload) + encrypted


def _pdg_pdf_page(pdf: bytes) -> bytes:
    """Wrap a PDF in a PDG type 0x00 page blob (payload stored as-is)."""
    header = bytearray(0x8C)
    header[0:2] = b"HH"
    header[2] = 1
    header[0x0F] = 0x00
    struct.pack_into("<I", header, 0x18, 0x8C)
    struct.pack_into("<I", header, 0x1C, len(pdf))
    return bytes(header) + pdf


def _pdg_pdf_member(pdf: bytes) -> bytes:
    """Wrap a PDF in a PDG 0x1A page blob (the native PDF-member form)."""
    import zlib
    stream = zlib.compress(pdf)
    header = bytearray(0x8C)
    header[0:2] = b"HH"
    header[2] = 1
    header[0x0F] = 0x1A
    struct.pack_into("<I", header, 0x18, 0x8C)
    struct.pack_into("<I", header, 0x1C, len(stream))
    return bytes(header) + stream


def _pdf_page_fixture() -> bytes:
    """A one-page 72x72 pt PDF drawing an 8x8 grey image."""
    pixels = bytes((index * 37) & 0xFF for index in range(64))
    content = b"q 72 0 0 72 0 0 cm /Im0 Do Q"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 72 72] "
        b"/Resources << /XObject << /Im0 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream",
        b"<< /Type /XObject /Subtype /Image /Width 8 /Height 8 "
        b"/ColorSpace /DeviceGray /BitsPerComponent 8 /Length 64 >>\nstream\n"
        + pixels + b"\nendstream",
    ]
    document = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(document))
        document += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(document)
    document += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for offset in offsets[1:]:
        document += b"%010d 00000 n \n" % offset
    document += (b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n"
                 % (len(objects) + 1, xref))
    return bytes(document)


def _pdf_image_stats(pdf: bytes) -> tuple[int, float]:
    """Distinct byte values and mean byte of the first raw image stream."""
    marker = b"/Subtype /Image"
    position = pdf.find(marker)
    if position < 0:
        return 0, -1.0
    stream = pdf.find(b"stream\n", position)
    length_at = pdf.rfind(b"/Length ", position, stream)
    if stream < 0 or length_at < 0:
        return 0, -1.0
    length = int(pdf[length_at + 8:pdf.find(b" ", length_at + 8)])
    data = pdf[stream + 7:stream + 7 + length]
    if len(data) != length or not data:
        return 0, -1.0
    return len(set(data)), sum(data) / len(data)


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

        # PDG page payload stored as PDF (PDZ container and UVZ page): the
        # page routes rasterise it with the internal PDF engine.
        page_pdf = _pdf_page_fixture()
        (root / "pdzbook.pdz").write_bytes(
            _pdz_container([(b"000001", page_pdf)]))
        run(exe, ["pdzbook.pdz"], root)
        pdzbook_pdf = root / "pdzbook.pdf"
        if (not pdzbook_pdf.is_file() or
                pdzbook_pdf.read_bytes()[:5] != b"%PDF-" or
                b"/Count 1" not in pdzbook_pdf.read_bytes()):
            return fail("PDZ PDF payload page did not become one PDF page")
        distinct, mean = _pdf_image_stats(pdzbook_pdf.read_bytes())
        if distinct < 8 or not 5.0 <= mean <= 250.0:
            return fail("PDZ PDF payload page rendered blank")
        check = run(exe, ["pdzbook.pdz", "--check"], root)
        if check.stdout.strip() != "OK":
            return fail(f"PDZ --check printed {check.stdout!r}")

        with zipfile.ZipFile(root / "uvzbook.uvz", "w") as archive:
            archive.writestr("000001.pdg", _pdg_pdf_page(page_pdf))
        run(exe, ["uvzbook.uvz"], root)
        uvzbook_pdf = root / "uvzbook.pdf"
        if (not uvzbook_pdf.is_file() or
                uvzbook_pdf.read_bytes()[:5] != b"%PDF-" or
                b"/Count 1" not in uvzbook_pdf.read_bytes()):
            return fail("UVZ PDF payload page did not become one PDF page")
        distinct, mean = _pdf_image_stats(uvzbook_pdf.read_bytes())
        if distinct < 8 or not 5.0 <= mean <= 250.0:
            return fail("UVZ PDF payload page rendered blank")
        check = run(exe, ["uvzbook.uvz", "--check"], root)
        if check.stdout.strip() != "OK":
            return fail(f"UVZ --check printed {check.stdout!r}")

        # A pdg_type 0x1A member holds a multi-page publisher PDF; merging it
        # is not implemented, so the container must fail rather than silently
        # drop the page.
        (root / "member.pdz").write_bytes(
            _pdz_container([(b"000001", _pdg_pdf_member(page_pdf))]))
        run(exe, ["member.pdz"], root, expect=1)

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
