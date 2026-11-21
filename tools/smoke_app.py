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


_SCRAMBLE_A = (
    b"132jksdiau34ukjasdflkj!@#234afdji78#%234ADf v\x1c=-\x07"
    b"sdkj908342<ADF>/#w%4t5o8uwrouyouhj8934038p350|+_SDFadwr"
    b"!234gasM,.spfdlp[WEey3dfsfgsf4890^:9!@#56&89384978907890"
    b"54ioerua^3~!2&*(_+*(80w&uidfs9ghidfower239-89taerC(!7a"
) + b"\x00"
_SCRAMBLE_B = (
    b"Afgasdkol!@#$564746Lfat0[9i FDLAas090132!$@##$2354(*^78~*54"
    b"sdfakl;ml;lak;j2a#$2342!@#128-reg;o[werqPWEQRioADSF1234&*"
    b"(6908_)55454!"
) + b"\x00"


def _u8(value: int) -> int:
    return value & 0xFF


def _i16(value: int) -> int:
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def _scramble_tables() -> tuple[list[int], list[int]]:
    fib = [1, 1]
    for _ in range(2, 32):
        fib.append(fib[-1] + fib[-2])
    index = [2, 3]
    state = 1
    value = 5
    while len(index) < 64:
        if value not in (0x19, 0x31, 0x79, 0xA9, 0x121):
            index.append(value)
        state += 1
        if state == 3:
            value += 4
            state = 1
        else:
            value += 2
    return fib, index


def _scramble_positions(header: bytearray) -> list[int]:
    """Mirror of compute_scramble_positions() for a pdg_type 0x1A header."""
    fib, index = _scramble_tables()
    h5e = header[0x5E]
    size16 = header[0x1C] | (header[0x1D] << 8)
    width = header[0x10]
    height = header[0x12]
    size_high = size16 >> 8
    sum_mix = _u8(height + header[0x1C] + width)
    diff_mix = _u8(width - height)
    or_mix = _u8(width | height)
    mul_mix = _u8(width * height)
    run_mix = _i16(sum_mix * diff_mix)
    block_mix = _u8(width * size_high)
    seed = _u8(h5e + width * height * width)
    p0 = (or_mix * mul_mix + size_high * block_mix - run_mix + seed + 250) & 0x1FF
    p12 = (or_mix * or_mix - block_mix * seed + run_mix * mul_mix + 250) & 0x1FF
    mixed = (block_mix * block_mix + sum_mix + diff_mix + or_mix + mul_mix
             + size_high + width)
    v14 = (_SCRAMBLE_A[(mixed + _SCRAMBLE_A[seed % 0xD7]) % 0xD7]
           * _SCRAMBLE_B[(mixed + _SCRAMBLE_B[seed % 0x82]) % 0x82])
    v15 = _SCRAMBLE_A[(diff_mix * mul_mix - size_high) % 0xD7]
    p1 = v14 & 0x1FF
    v16 = fib[(size16 >> 8) & 0x1F]
    p13 = (_SCRAMBLE_B[width % 0x82] * v15) & 0x1FF
    v17 = index[(width * size_high) & 0x3F]
    p2 = v16 & 0x1FF
    p14 = v17 & 0x1FF
    p3 = index[((v17 & 0xFF) * _SCRAMBLE_B[
        (p2 * _SCRAMBLE_A[p2 % 0xD7]) % 0x82]) & 0x3F] & 0x1FF
    p15 = fib[((v16 & 0xFF) * _SCRAMBLE_A[
        (p14 * _SCRAMBLE_B[p14 % 0x82]) % 0xD7]) & 0x1F] & 0x1FF
    short_mix = _i16(p1 * p15)
    positions = [0] * 24
    positions[0] = p0
    positions[1] = p1
    positions[2] = p2
    positions[3] = p3
    positions[4] = p0
    positions[5] = (p12 * p1 - p0) & 0x1FF
    positions[6] = (p14 - p0 * p1) & 0x1FF
    positions[7] = (p3 - p12 * p14) & 0x1FF
    positions[8] = (p12 + p0) & 0x1FF
    positions[9] = (positions[5] + p13) & 0x1FF
    positions[10] = (positions[6]
                     + (p12 * p13 + p2 * p14 - short_mix + p3 + 250)
                     - p1) & 0x1FF
    positions[11] = (positions[7] + positions[8] - p15) & 0x1FF
    positions[12] = p12
    positions[13] = p13
    positions[14] = p14
    positions[15] = p15
    positions[16] = (p12 * short_mix - p14 * p3 + p13 * p13 + 250) & 0x1FF
    positions[17] = (p0 * p0 + p2 * p2 - p12 * p12) & 0x1FF
    positions[18] = (p12 * p13 + p2 * p14 - short_mix + p3 + 250) & 0x1FF
    positions[19] = (p3 * p15) & 0x1FF
    positions[20] = (_SCRAMBLE_B[p12 % 0x82]
                     + _SCRAMBLE_A[positions[16] % 0xD7]) & 0x1FF
    positions[21] = index[((v14 & 0xFF) * _u8(
        (p12 & 0xFF) * (v14 & 0xFF) - (p0 & 0xFF) + (p13 & 0xFF))) & 0x3F] & 0x1FF
    positions[22] = index[_SCRAMBLE_A[positions[6] % 0xD7] & 0x3F] & 0x1FF
    positions[23] = fib[_SCRAMBLE_B[positions[6] % 0x82] & 0x1F] & 0x1FF
    return positions


def _invert_midpoint(payload: bytearray, left: int, right: int) -> None:
    """Undo the decoder's midpoint_sub step so it sees the intended stream."""
    if left == right:
        return
    midpoint = (left >> 1) + (right >> 1)
    value = (payload[left] + right) & 0xFF
    if midpoint != left:
        value ^= payload[midpoint]
    payload[left] = value


def _pdg_pdf_member(pdf: bytes) -> bytes:
    """Wrap a PDF in a realistic pdg_type 0x1A member (scrambled zlib(PDF))."""
    import zlib
    pad = b"".join(hashlib.sha256(str(index).encode()).digest()
                   for index in range(24))
    comment = b"% " + base64.b64encode(pad) + b"\n"
    marker = pdf.rfind(b"startxref")
    padded = pdf[:marker] + comment + pdf[marker:] if marker >= 0 else pdf
    stream = bytearray(zlib.compress(padded))
    header = bytearray(0x8C)
    header[0:2] = b"HH"
    header[2] = 1
    header[0x0F] = 0x1A
    header[0x10] = 200   # width_low keeps the scramble arithmetic non-negative
    header[0x12] = 100   # height_low
    header[0x5E] = 0x5A
    struct.pack_into("<I", header, 0x18, 0x8C)
    struct.pack_into("<I", header, 0x1C, len(stream))
    positions = _scramble_positions(header)
    left, right = positions[9], positions[21]
    if max(left, right) + 0x13 >= len(stream):
        raise RuntimeError("0x1A fixture payload is too small")
    _invert_midpoint(stream, left, right)
    return bytes(header) + bytes(stream)


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


# Real-fixture format matrix: every "CLI reachable" claim in the support
# matrix should have a case here. "token" checks the PDF text layer; "check"
# only parses/renders (used for inputs that would emit very large PDFs).
FORMAT_MATRIX: list[tuple[str, str, str, str | None]] = [
    ("epub", "app/testfile/ebook/epub/lorem-ipsum.epub", "convert", "Lorem ipsum"),
    ("kepub", "app/testfile/ebook/kepub/sample.kepub.epub", "convert", None),
    ("ttml", "app/testfile/subtitle/ttml/sample.ttml", "convert", "Quirewise sample"),
    ("vtt", "app/testfile/subtitle/vtt/example.vtt", "convert", None),
    ("ass", "app/testfile/subtitle/ass/example.ass", "convert", None),
    ("scc", "app/testfile/subtitle/scc/sample.scc", "convert", None),
    ("mobi", "app/testfile/ebook/mobi/lorem-ipsum.mobi", "convert", "Lorem"),
    ("azw3", "app/testfile/ebook/azw3/lorem-ipsum.azw3", "convert", "Lorem"),
    ("fb2", "app/testfile/ebook/fb2/lorem-ipsum.fb2", "convert", "Lorem"),
    ("mdx", "libraries/quirewise-ebook/tests/data/tiny.mdx", "convert",
     "Quirewise sample definition"),
    ("mdx-txt", "libraries/quirewise-ebook/tests/data/tiny.mdx", "totxt",
     "Quirewise sample definition"),
    ("mdd", "libraries/quirewise-ebook/tests/data/tiny.mdd", "check", None),
    ("srt-vtt", "libraries/quirewise-subtitle/tests/data/sample.srt", "to:vtt",
     "Quirewise sample subtitle"),
    ("srt-ttml", "libraries/quirewise-subtitle/tests/data/sample.srt", "to:ttml",
     "<tt xmlns"),
    ("json-yaml", "libraries/quirewise-data/tests/data/sample.json", "to:yaml",
     "Quirewise sample"),
    ("csv-tsv", "libraries/quirewise-spreadsheet/tests/data/sample.csv",
     "to:tsv", "Quirewise sample"),
    ("md-html", "libraries/quirewise-text/tests/data/sample.md", "to:html",
     "<h1>Quirewise sample</h1>"),
    ("html-md", "libraries/quirewise-document/tests/data/sample.html",
     "to:md", "# Quirewise sample"),
    ("md-docx", "libraries/quirewise-text/tests/data/sample.md", "to:docx",
     "PK"),
    ("md-epub", "libraries/quirewise-text/tests/data/sample.md", "to:epub",
     "application/epub+zip"),
    ("pdf-docx", "external-consumer-template/fixtures/one-page.pdf",
     "to:docx", "PK"),
    ("pdf-epub", "external-consumer-template/fixtures/one-page.pdf",
     "to:epub", "application/epub+zip"),
    ("pdf-jpg", "external-consumer-template/fixtures/one-page.pdf", "to:jpg",
     "JFIF"),
    ("pdf-webp", "external-consumer-template/fixtures/one-page.pdf", "to:webp",
     "WEBP"),
    ("md-pmlz", "libraries/quirewise-text/tests/data/sample.md", "to:pmlz",
     "index.pml"),
    ("png-bmp", "external-consumer-template/fixtures/tiny.png", "to:bmp",
     "BM"),
    ("bmp-png", "external-consumer-template/fixtures/pixel.bmp", "to:png",
     "PNG"),
    ("png-tiff", "external-consumer-template/fixtures/tiny.png", "to:tiff",
     "II"),
    ("png-jpg", "external-consumer-template/fixtures/tiny.png", "to:jpg",
     "JFIF"),
    ("bmp-jpg", "external-consumer-template/fixtures/pixel.bmp", "to:jpeg",
     "JFIF"),
    ("png-qoi", "external-consumer-template/fixtures/tiny.png", "to:qoi",
     "qoif"),
    ("png-ppm", "external-consumer-template/fixtures/tiny.png", "to:ppm",
     "P6"),
    ("png-gif", "external-consumer-template/fixtures/tiny.png", "to:gif",
     "GIF89a"),
    ("png-hdr", "external-consumer-template/fixtures/tiny.png", "to:hdr",
     "#?RADIANCE"),
    ("pptx-html", "libraries/quirewise-document/tests/data/image-slide.pptx",
     "to:html", "data:image/png;base64"),
    ("docx-merge", "libraries/quirewise-document/tests/data/vertical-merge.docx",
     "to:html", "rowspan=\"3\""),
    ("fodt-image", "libraries/quirewise-document/tests/data/image-data.fodt",
     "to:html", "data:image/png;base64"),
    ("odp-notes", "libraries/quirewise-document/tests/data/notes-slide.odp",
     "to:html", "Speaker notes"),
    ("xlsx-sheet2", "libraries/quirewise-spreadsheet/tests/data/multi-sheet.xlsx",
     "to:csv", "Second header", ["--sheet", "2"]),
    ("image-crop", "libraries/quirewise-document/tests/data/vml-red.png",
     "to:png", "PNG", ["--image-crop", "8,8,8,8"]),
    ("image-resize", "libraries/quirewise-document/tests/data/vml-red.png",
     "to:png", "PNG", ["--image-resize", "24x12"]),
    ("msg-rtf-image", "libraries/quirewise-document/tests/data/rtf-image.msg",
     "to:html", "data:image/png;base64"),
    ("msg-rtf-table", "libraries/quirewise-document/tests/data/rtf-table.msg",
     "to:html", "<td>A</td>"),
    ("msg-rtf", "libraries/quirewise-document/tests/data/rtf-sample.msg",
     "to:html", "Hello RTF body."),
    ("mdx-engine12", "libraries/quirewise-ebook/tests/data/engine12.mdx",
     "to:txt", "Quirewise sample definition for alpha"),
    ("xps-md-image", "libraries/quirewise-document/tests/data/image.xps",
     "to:md", "![xps image](data:image/png;base64,"),
    ("xps-html", "libraries/quirewise-document/tests/data/sample.xps",
     "to:html", "XPS page text"),
    ("epub-footnote", "libraries/quirewise-document/tests/data/footnote.epub",
     "to:html", "<p class=\"epub-footnote\" id=\"fn1\">"),
    ("epub-hr", "libraries/quirewise-document/tests/data/hr.epub",
     "to:html", "<hr/>"),
    ("epub-figure", "libraries/quirewise-document/tests/data/figure.epub",
     "to:html", "<figcaption>Red square</figcaption>"),
    ("hwpx-headings", "libraries/quirewise-document/tests/data/headings.hwpx",
     "to:html", "<h1>Heading one</h1>"),
    ("pptx-picture-position", "libraries/quirewise-document/tests/data/image-slide.pptx",
     "to:html", "class=\"picture\" style=\"margin-left:96px;margin-top:144px;\""),
    ("pptx-position", "libraries/quirewise-document/tests/data/image-slide.pptx",
     "to:html", "margin-left:96px;margin-top:384px;"),
    ("pptx-text-rotation", "libraries/quirewise-document/tests/data/rotated-text-slide.pptx",
     "to:html", "transform:rotate(90deg)"),
    ("odp-text-rotation", "libraries/quirewise-document/tests/data/rotated-text.odp",
     "to:html", "transform:rotate(90deg)"),
    ("odp-position", "libraries/quirewise-document/tests/data/position-slide.odp",
     "to:html", "margin-left:28px;margin-top:57px;"),
    ("odp-rotation", "libraries/quirewise-document/tests/data/rotated-slide.odp",
     "to:html", "transform:rotate(90deg)"),
    ("pptx-rotation", "libraries/quirewise-document/tests/data/rotated-slide.pptx",
     "to:html", "transform:rotate(90deg)"),
    ("pptx-outline", "libraries/quirewise-document/tests/data/outline-slide.pptx",
     "to:pdf", "/Title (Slide 1)"),
    ("odp-outline", "libraries/quirewise-document/tests/data/outline-slide.odp",
     "to:pdf", "0053006C00690064006500200031"),
    ("odt-outline", "libraries/quirewise-document/tests/data/outline.odt",
     "to:pdf", "/Title (Chapter One)"),
    ("odt-indent", "libraries/quirewise-document/tests/data/indent.odt",
     "to:html", "margin-left:1in"),
    ("odt-endnote", "libraries/quirewise-document/tests/data/endnote.odt",
     "to:html", "<span class=\"odt-endnote\">Endnote body.</span>"),
    ("odt-footnote", "libraries/quirewise-document/tests/data/footnote.odt",
     "to:html", "<sup>[1]</sup>"),
    ("docx-header-style", "libraries/quirewise-document/tests/data/styled-header.docx",
     "to:html", "<strong><em>Styled header</em></strong>"),
    ("docx-endnotes", "libraries/quirewise-document/tests/data/endnotes.docx",
     "to:html", "<sup>[3]</sup>"),
    ("docx-footnotes", "libraries/quirewise-document/tests/data/footnotes.docx",
     "to:html", "<sup>[2]</sup>"),
    ("docx-indent", "libraries/quirewise-document/tests/data/indent.docx",
     "to:html", "text-indent:24px"),
    ("docx-outline", "libraries/quirewise-document/tests/data/outline.docx",
     "to:pdf", "/Title (Chapter One)"),
    ("pdf-metadata-zh", "libraries/quirewise-document/tests/data/meta-zh.html",
     "to:pdf", "/Title <FEFF"),
    ("pdf-metadata", "libraries/quirewise-document/tests/data/meta.html",
     "to:pdf", "/Title (Quarterly Report)"),
    ("pdf-outline-utf16", "libraries/quirewise-document/tests/data/headings-zh.hwpx",
     "to:pdf", "/Title <FEFF"),
    ("pdf-outline-nested", "libraries/quirewise-document/tests/data/headings.hwpx",
     "to:pdf", "/First"),
    ("html-table-style-align", "libraries/quirewise-text/tests/data/table-style-align.html",
     "to:md", "| :---: | ---: |"),
    ("md-table-escaped", "libraries/quirewise-text/tests/data/md-table-escaped.md",
     "to:html", "a | b"),
    ("ass-style", "libraries/quirewise-subtitle/tests/data/styled.ass",
     "to:ass", "{\\pos(100,200)\\i1}Hello"),
    ("ass-speaker", "libraries/quirewise-subtitle/tests/data/speaker.ass",
     "to:ass", ",Default,Alice,10,20,30,Fade,"),
    ("md-block-hr", "libraries/quirewise-text/tests/data/block-hr.md",
     "to:html", "<hr/>"),
    ("md-inline-br", "libraries/quirewise-text/tests/data/inline-br.md",
     "to:html", "Hello<br/>world"),
    ("md-image", "libraries/quirewise-text/tests/data/image.md",
     "to:html", "<img src=\"x.png\" alt=\"diagram\">"),
    ("md-link-title", "libraries/quirewise-text/tests/data/link-title.md",
     "to:html", "title=\"Example\""),
    ("md-strikethrough", "libraries/quirewise-text/tests/data/strike.md",
     "to:html", "<del>gone</del>"),
    ("html-figure-to-md", "libraries/quirewise-text/tests/data/figure.html",
     "to:md", "*A caption*"),
    ("html-q-cite-to-md", "libraries/quirewise-text/tests/data/q-cite.html",
     "to:md", "<q>short</q>"),
    ("html-u-mark-to-md", "libraries/quirewise-text/tests/data/u-mark.html",
     "to:md", "<u>under</u>"),
    ("html-del-to-md", "libraries/quirewise-text/tests/data/del.html",
     "to:md", "~~gone~~ and ~~old~~"),
    ("html-supsub-to-md", "libraries/quirewise-text/tests/data/supsub.html",
     "to:md", "<sup>2</sup>"),
    ("html-img-title-to-md", "libraries/quirewise-text/tests/data/img-title.html",
     "to:md", "![diagram](x.png \"A diagram\")"),
    ("html-dl-to-md", "libraries/quirewise-text/tests/data/dl.html",
     "to:md", ": Detail"),
    ("html-hr-to-md", "libraries/quirewise-text/tests/data/hr.html",
     "to:md", "---"),
    ("md-autolink", "libraries/quirewise-text/tests/data/autolink.md",
     "to:html", "<a href=\"https://example.com\">"),
    ("md-task-list", "libraries/quirewise-text/tests/data/task-list.md",
     "to:html", "disabled checked"),
    ("md-fence-language", "libraries/quirewise-text/tests/data/fence-language.md",
     "to:html", "class=\"language-c\""),
    ("md-setext", "libraries/quirewise-text/tests/data/setext.md",
     "to:html", "<h1>Setext One</h1>"),
    ("md-table", "libraries/quirewise-text/tests/data/md-table.md",
     "to:html", "<th align=\"center\">"),
    ("html-table-align", "libraries/quirewise-text/tests/data/table-align.html",
     "to:md", "| :---: | ---: |"),
    ("pdf-outline-xyz", "libraries/quirewise-document/tests/data/headings.hwpx",
     "to:pdf", "/XYZ"),
    ("pdf-heading-outline", "libraries/quirewise-document/tests/data/headings.hwpx",
     "to:pdf", "/Title (Heading one)"),
    ("hwpx-footnotes", "libraries/quirewise-document/tests/data/footnotes.hwpx",
     "to:html", "class=\"footnote\""),
    ("hwpx-header-footer", "libraries/quirewise-document/tests/data/header-footer.hwpx",
     "to:html", "<footer><p>Footer text</p>"),
    ("hwpx-page-break-pdf", "libraries/quirewise-document/tests/data/page-break.hwpx",
     "to:pdf", "/Count 2"),
    ("hwpx-page-break", "libraries/quirewise-document/tests/data/page-break.hwpx",
     "to:html", "page-break-before:always"),
    ("hwpx-line-spacing", "libraries/quirewise-document/tests/data/paragraph-style.hwpx",
     "to:html", "line-height:160%"),
    ("hwpx-para-style", "libraries/quirewise-document/tests/data/paragraph-style.hwpx",
     "to:html", "text-indent:16px"),
    ("hwpx-highlight", "libraries/quirewise-document/tests/data/styled.hwpx",
     "to:html", "background-color:#FFFF00"),
    ("hwpx-spacing", "libraries/quirewise-document/tests/data/styled.hwpx",
     "to:html", "letter-spacing:0.20em"),
    ("hwpx-supsub", "libraries/quirewise-document/tests/data/styled.hwpx",
     "to:html", "<sup>Super</sup>"),
    ("hwpx-underline", "libraries/quirewise-document/tests/data/styled.hwpx",
     "to:html", "<u><s>Underline strike"),
    ("hwpx-styles", "libraries/quirewise-document/tests/data/styled.hwpx",
     "to:html", "color:#FF0000"),
    ("hwpx-position", "libraries/quirewise-document/tests/data/positioned-image.hwpx",
     "to:html", "margin-left:32px"),
    ("hwpx-align", "libraries/quirewise-document/tests/data/align.hwpx",
     "to:html", "text-align:center"),
    ("hwpx-flip", "libraries/quirewise-document/tests/data/flipped-image.hwpx",
     "to:html", "width=\"192\""),
    ("hwpx-hyperlink", "libraries/quirewise-document/tests/data/hyperlink.hwpx",
     "to:html", "<a href=\"https://example.com\">Example</a>"),
    ("hwpx-sections", "libraries/quirewise-document/tests/data/two-sections.hwpx",
     "to:html", "page-break-before:always"),
    ("hwpx-page-margins", "libraries/quirewise-document/tests/data/page-margins.hwpx",
     "to:html", "padding:48px 96px 48px 96px;"),
    ("hwpx-columns", "libraries/quirewise-document/tests/data/columns.hwpx",
     "to:html", "column-count:2"),
    ("hwpx-cell-margin", "libraries/quirewise-document/tests/data/cell-margin.hwpx",
     "to:html", "padding:4px 8px 4px 8px"),
    ("hwpx-cell-align", "libraries/quirewise-document/tests/data/cell-align.hwpx",
     "to:html", "writing-mode:vertical-rl"),
    ("hwpx-cell-border", "libraries/quirewise-document/tests/data/cell-border.hwpx",
     "to:html", "border:2px solid #336699"),
    ("hwpx-cell-background", "libraries/quirewise-document/tests/data/cell-background.hwpx",
     "to:html", "background-color:#FFCC00"),
    ("hwpx-table-spans", "libraries/quirewise-document/tests/data/table-spans.hwpx",
     "to:html", "colspan=\"2\""),
    ("hwpx-rotation", "libraries/quirewise-document/tests/data/rotated-image.hwpx",
     "to:html", "width=\"192\""),
    ("hwpx-crop", "libraries/quirewise-document/tests/data/crop-image.hwpx",
     "to:html", "width=\"192\""),
    ("epub-table-caption", "libraries/quirewise-document/tests/data/table-caption.epub",
     "to:html", "<caption>Quarterly totals</caption>"),
    ("epub-definition-list", "libraries/quirewise-document/tests/data/definition-list.epub",
     "to:html", "<dl><dt>"),
    ("epub-blockquote", "libraries/quirewise-document/tests/data/blockquote.epub",
     "to:html", "<blockquote><p>"),
    ("htmlz-css", "libraries/quirewise-document/tests/data/image.htmlz",
     "to:html", "<style>body"),
    ("htmlz-image", "libraries/quirewise-document/tests/data/image.htmlz",
     "to:html", "data:image/png;base64"),
    ("htmlz-pdf-image", "libraries/quirewise-document/tests/data/image.htmlz",
     "to:pdf", "/Subtype /Image"),
    ("epub-ordered-list", "libraries/quirewise-document/tests/data/ordered-list.epub",
     "to:html", "<ol><li>First step"),
    ("epub-table-spans", "libraries/quirewise-document/tests/data/table-spans.epub",
     "to:html", "colspan="), 
    ("epub-nested-list", "libraries/quirewise-document/tests/data/nested-list.epub",
     "to:html", "margin-left:2em"),
    ("epub-formatting", "libraries/quirewise-document/tests/data/formatting.epub",
     "to:html", "<ul><li>"),
    ("odp-crop", "libraries/quirewise-document/tests/data/crop-slide.odp",
     "to:html", "data:image/png;base64"),
    ("html-docx-rowspan", "libraries/quirewise-document/tests/data/rowspan.html",
     "to:docx", "w:val=\"restart\""),
    ("html-docx-table", "libraries/quirewise-document/tests/data/table.html",
     "to:docx", "w:gridSpan"),
    ("docx-link", "libraries/quirewise-document/tests/data/link.odt",
     "to:docx", "TargetMode=\"External\""),
    ("epub-epub-image", "libraries/quirewise-document/tests/data/image.epub",
     "to:epub", "OEBPS/images/image0.png"),
    ("epub-docx-image", "libraries/quirewise-document/tests/data/image.epub",
     "to:docx", "word/media/image0.png"),
    ("eml-rfc2231-cont", "libraries/quirewise-document/tests/data/rfc2231.eml",
     "to:html", "附件.txt"),
    ("eml-rfc2231", "libraries/quirewise-document/tests/data/rfc2231.eml",
     "to:html", "中文.txt"),
    ("xlsx-ods-write", "libraries/quirewise-spreadsheet/tests/data/multi-sheet.xlsx",
     "to:ods", "content.xml"),
    ("xlsx-write", "libraries/quirewise-spreadsheet/tests/data/multi-sheet.xlsx",
     "to:xlsx", "xl/worksheets/sheet1.xml"),
    ("xls-sst-continue", "libraries/quirewise-spreadsheet/tests/data/large-sst.xls",
     "to:html", "String1499"),
    ("xls-merge", "libraries/quirewise-spreadsheet/tests/data/merged.xls",
     "to:html", 'rowspan="2"'),
    ("fods-merge", "libraries/quirewise-spreadsheet/tests/data/merged.fods",
     "to:html", 'rowspan="2"'),
    ("xlsx-merge", "libraries/quirewise-spreadsheet/tests/data/merged.xlsx",
     "to:html", 'rowspan="2"'),
    ("odp-image-size", "libraries/quirewise-document/tests/data/image-slide.odp",
     "to:html", 'width="142"'),
    ("odt-sized-image", "libraries/quirewise-document/tests/data/sized-image.odt",
     "to:html", 'width="113"'),
    ("hwpx-size", "libraries/quirewise-document/tests/data/image.hwpx",
     "to:html", 'width="192"'),
    ("docx-vml", "libraries/quirewise-document/tests/data/vml-image.docx",
     "to:html", "data:image/png;base64"),
    ("odt-link", "libraries/quirewise-document/tests/data/link.odt",
     "to:html", 'href="https://example.com"'),
    ("odp-link", "libraries/quirewise-document/tests/data/link-slide.odp",
     "to:html", 'href="https://example.com"'),
    ("odp-html", "libraries/quirewise-document/tests/data/image-slide.odp",
     "to:html", "data:image/png;base64"),
    ("docx-header", "libraries/quirewise-document/tests/data/header-footer.docx",
     "to:html", "docx-header"),
    ("pptx-notes", "libraries/quirewise-document/tests/data/notes-slide.pptx",
     "to:html", "Speaker notes"),
    ("odt-header", "libraries/quirewise-document/tests/data/header-footer.odt",
     "to:html", "odt-header"),
    ("msg-html", "libraries/quirewise-document/tests/data/sample.msg",
     "to:html", "Outlook MSG sample"),
    ("msg-attach", "libraries/quirewise-document/tests/data/sample.msg",
     "to:html", "MSG attachment payload"),
    ("msg-html-body", "libraries/quirewise-document/tests/data/sample.msg",
     "to:html", "Outlook HTML body"),
    ("msg-pdf", "libraries/quirewise-document/tests/data/sample.msg",
     "to:pdf", "/Subtype /Image"),
    ("msg-md", "libraries/quirewise-document/tests/data/sample.msg",
     "to:md", "Outlook HTML body"),
    ("eml-attach", "libraries/quirewise-document/tests/data/attachments.eml",
     "to:html", "data:image/png;base64"),
    ("xps-pdf", "libraries/quirewise-document/tests/data/sample.xps",
     "to:pdf", "%PDF-1.4"),
    ("xps-image", "libraries/quirewise-document/tests/data/image.xps",
     "to:pdf", "/Subtype /Image"),
    ("md-ipynb", "libraries/quirewise-text/tests/data/sample.md", "to:ipynb",
     '"nbformat":4'),
    ("md-opml", "libraries/quirewise-text/tests/data/sample.md", "to:opml",
     "<opml version=\"2.0\">"),
    ("adoc-md", "app/testfile/markup/sample.adoc", "to:md",
     "AsciiDoc Sample"),
    ("org-md", "app/testfile/markup/sample.org", "to:md", "Heading"),
    ("rst-md", "app/testfile/markup/sample.rst", "to:md", "RST Sample"),
    ("tex-md", "app/testfile/markup/sample.tex", "to:md", "LaTeX Sample"),
    ("wiki-md", "app/testfile/markup/sample.mediawiki", "to:md",
     "MediaWiki Sample"),
    ("adoc-pdf", "app/testfile/markup/sample.adoc", "to:pdf", "%PDF-1.4"),
    ("epub-image", "libraries/quirewise-document/tests/data/image.epub",
     "to:html", "data:image/png;base64"),
    ("epub-list", "libraries/quirewise-document/tests/data/unsupported-layout.epub",
     "to:html", "<li>"),
    ("epub-table", "libraries/quirewise-document/tests/data/unsupported-layout.epub",
     "to:html", "</td>"),
    ("mdx-links", "libraries/quirewise-ebook/tests/data/links.mdx",
     "to:html", "Alpha definition"),
    ("mdx-image", "libraries/quirewise-ebook/tests/data/images.mdx",
     "to:html", "data:image/gif;base64",
     ["--mdd", "libraries/quirewise-ebook/tests/data/tiny.mdd"]),
    ("mdx-image-pdf", "libraries/quirewise-ebook/tests/data/images.mdx",
     "to:pdf", "/Subtype /Image",
     ["--mdd", "libraries/quirewise-ebook/tests/data/tiny.mdd"]),
    ("hwpx-image", "libraries/quirewise-document/tests/data/image.hwpx",
     "to:html", "data:image/png;base64"),
    ("png-webp", "external-consumer-template/fixtures/tiny.png", "to:webp",
     "WEBP"),
    ("bmp-webp", "external-consumer-template/fixtures/pixel.bmp", "to:webp",
     "WEBP"),
    ("md-htmlz", "libraries/quirewise-text/tests/data/sample.md", "to:htmlz",
     "index.html"),
    ("md-txtz", "libraries/quirewise-text/tests/data/sample.md", "to:txtz",
     "index.txt"),
    ("md-hwpx", "libraries/quirewise-text/tests/data/sample.md", "to:hwpx",
     "section0.xml"),
    ("htmlz", "app/testfile/ebook/htmlz/lorem-ipsum.htmlz", "convert", "Lorem"),
    ("txtz", "app/testfile/ebook/txtz/lorem-ipsum.txtz", "convert", "Lorem"),
    ("pmlz", "app/testfile/ebook/pmlz/lorem-ipsum.pmlz", "convert", None),
    ("rtf", "app/testfile/document/rtf/lorem-ipsum.rtf", "convert", "Lorem"),
    ("fodt", "app/testfile/document/fodt/sample.fodt", "convert", "Quirewise ODF sample"),
    ("hwpx", "app/testfile/hwp/hwpx/blank.hwpx", "convert", None),
    ("pptx", "app/testfile/_license-review/openoffice/pptx/ms_powerpoint_xml.pptx",
     "convert", "Slide 1"),
    ("odp", "app/testfile/presentation/odp/sample.odp", "convert", None),
    ("ods", "app/testfile/spreadsheet/ods/sample.ods", "convert", None),
    ("xls", "libraries/quirewise-spreadsheet/tests/data/valid.xls", "convert", "Enash:"),
    ("xls-montecarlo", "libraries/quirewise-spreadsheet/tests/data/MonteCarlo.xls",
     "convert", "Monte Carlo"),
    ("cbz", "app/testfile/ebook/cbz/sample.cbz", "convert", None),
    ("cbr", "libraries/quirewise-comic/tests/data/sample.cbr", "to:pdf",
     "%PDF-1.4"),
    ("cb7", "libraries/quirewise-comic/tests/data/sample.cb7", "to:pdf",
     "%PDF-1.4"),
    ("cbt", "app/testfile/ebook/cbt/sample.cbt", "convert", None),
    ("json", "app/testfile/_license-review/xberg/data/json/simple.json", "convert", None),
    ("vcf", "app/testfile/data/vcf/sample.vcf", "convert", None),
    ("dxf", "app/testfile/cad/dxf/robot.dxf", "check", None),
    ("dwg", "app/testfile/cad/line_2007.dwg", "check", None),
    ("pdf-txt", "app/testfile/pdf/basic/lorem-ipsum.pdf", "totxt", "Lorem"),
    ("pdf-png", "app/testfile/pdf/basic/lorem-ipsum.pdf", "topng", None),
    # PDF/A needs an embedded font; veraPDF accepts the result for 1b/2b/3b
    # (2026-11-21), so the CLI route and the structure are covered here.
    ("pdfa-1b", "app/testfile/text/html/lorem-ipsum.htm", "to:pdf",
     "/GTS_PDFA1",
     ["--pdfa", "1b", "--font-file",
      "app/testfile/font/ttf/FileeTest-TrueType.ttf"]),
]


def check_format_matrix(exe: pathlib.Path, workspace: pathlib.Path,
                        root: pathlib.Path) -> None:
    skipped = []
    for index, entry in enumerate(FORMAT_MATRIX):
        label, relative, mode, token = entry[:4]
        extra = list(entry[4]) if len(entry) > 4 else []
        extra = [str(workspace / arg) if (workspace / arg).is_file() else arg
                 for arg in extra]
        source = workspace / relative
        if not source.is_file():
            # testfile/_license-review is gitignored (the fixtures are
            # third-party license-review documents), so a clean checkout has
            # no copy. Skip those cases loudly instead of failing CI, and keep
            # every other fixture mandatory.
            if "/_license-review/" in relative or \
                    "_license-review/" in relative:
                skipped.append(label)
                continue
            return fail(f"format matrix is missing fixture: {relative}")
        case_dir = root / f"matrix-{index:02d}-{label}"
        case_dir.mkdir()
        if mode.startswith("to:"):
            target = mode[3:]
            out = case_dir / f"out.{target}"
            run(exe, [str(source), *extra, "--to", target, "-o", str(out)],
                case_dir)
            if not out.is_file() or not out.stat().st_size:
                return fail(f"{label} produced no {target} output")
            if token and token.encode("utf-8") not in out.read_bytes():
                return fail(f"{label} output lost {token!r}")
            continue
        if mode == "check":
            completed = run(exe, [str(source), *extra, "--check"], case_dir)
            if completed.stdout.strip() != "OK":
                return fail(f"{label} --check printed {completed.stdout!r}")
            continue
        if mode == "totxt":
            target = case_dir / "out.txt"
            run(exe, [str(source), *extra, "--to", "txt", "-o", str(target)],
                case_dir)
            if (not target.is_file() or
                    token.encode("utf-8") not in target.read_bytes()):
                return fail(f"{label} text output lost {token!r}")
            continue
        if mode == "topng":
            target = case_dir / "out.png"
            run(exe, [str(source), *extra, "--to", "png", "-o", str(target)],
                case_dir)
            if (not target.is_file() or
                    target.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n"):
                return fail(f"{label} did not produce a PNG")
            continue
        run(exe, [str(source), *extra, "--out-dir", str(case_dir)], case_dir)
        pdf = case_dir / (source.stem + ".pdf")
        if not pdf.is_file() or pdf.read_bytes()[:5] != b"%PDF-":
            return fail(f"{label} did not produce a PDF")
        if token:
            text = case_dir / "extracted.txt"
            run(exe, [str(pdf), "--to", "txt", "-o", str(text)], case_dir)
            if (not text.is_file() or
                    token.encode("utf-8") not in text.read_bytes()):
                return fail(f"{label} PDF text lost {token!r}")
    if skipped:
        print(f"format matrix skipped {len(skipped)} case(s) without "
              f"license-review fixtures: {', '.join(skipped)}")
    print(f"format matrix OK ({len(FORMAT_MATRIX) - len(skipped)} cases run of "
          f"{len(FORMAT_MATRIX)})")


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

        run(exe, ["sample.pdf", "--to", "avif"], root, expect=2)
        fixture = (
            pathlib.Path(__file__).resolve().parents[2]
            / "libraries/quirewise-document/tests/data/"
            "encrypted-mutool-aes256-userpw.pdf"
        )
        run(exe, ["--pdf-password", "secret", str(fixture), "--to", "txt",
                  "-o", "userpw.txt"], root)
        run(exe, [str(fixture), "--to", "txt", "-o", "userpw-denied.txt"],
            root, expect=1)

        (root / "image.png").write_bytes(PNG_1X1)
        run(exe, ["image.png"], root)
        image_pdf = root / "image.pdf"
        image_bytes = image_pdf.read_bytes() if image_pdf.is_file() else b""
        if not image_pdf.is_file() or image_bytes[:5] != b"%PDF-":
            return fail("image to PDF produced no PDF")
        # IMAGE mode page box == pixel size and the image fills it (a unit cm
        # would paint the image into a single point).
        if (b"/MediaBox [0 0 1 1]" not in image_bytes or
                b"1.0000 0 0 1.0000" not in image_bytes):
            return fail("image to PDF did not scale the image to the page")

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
        # These were silently skipped when absent; a missing fixture now fails
        # the smoke instead of reducing coverage without a trace.
        required_fixtures = [
            workspace / "libraries/quirewise-page/tests/data/djvu/multipage.djvu",
            workspace / "app/testfile/subtitle/srt/example.srt",
            workspace / "app/testfile/audio/wav/Sine440Hz_S16.wav",
            workspace / "app/testfile/cad/sample.dxf",
            workspace / "app/testfile/cad/hatch.dxf",
            workspace / "app/testfile/cad/line_2000.dwg",
            workspace / "app/testfile/cad/lw_entities-2d.dwg",
            workspace / "app/testfile/cad/line_2004.dwg",
            workspace / "app/testfile/cad/line_2007.dwg",
            workspace / "app/testfile/cad/lw_example2007.dwg",
            workspace / "app/testfile/cad/line_2010.dwg",
        ]
        for fixture in required_fixtures:
            if not fixture.is_file():
                return fail(f"missing required fixture: {fixture}")
        check_format_matrix(exe, workspace, root)
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

        cad = workspace / "app/testfile/cad/sample.dxf"
        if cad.is_file():
            cad_pdf = root / "cad.pdf"
            run(exe, [str(cad), "-o", str(cad_pdf)], root)
            if (not cad_pdf.is_file() or
                    cad_pdf.read_bytes()[:5] != b"%PDF-"):
                return fail("DXF to PDF produced no PDF")
            check = run(exe, [str(cad), "--check"], root)
            if check.stdout.strip() != "OK":
                return fail(f"DXF --check printed {check.stdout!r}")
            cad_txt = root / "cad.txt"
            run(exe, [str(cad), "--to", "txt", "-o", str(cad_txt)], root)
            if not cad_txt.is_file() or b"Sample CAD" not in cad_txt.read_bytes():
                return fail("DXF --to txt did not extract the drawing text")
        hatch = workspace / "app/testfile/cad/hatch.dxf"
        if hatch.is_file():
            hatch_pdf = root / "hatch.pdf"
            run(exe, [str(hatch), "-o", str(hatch_pdf)], root)
            if not hatch_pdf.is_file() or hatch_pdf.read_bytes()[:5] != b"%PDF-":
                return fail("HATCH DXF to PDF produced no PDF")
            check = run(exe, [str(hatch), "--check"], root)
            if check.stdout.strip() != "OK":
                return fail(f"HATCH --check printed {check.stdout!r}")
        dwg = workspace / "app/testfile/cad/line_2000.dwg"
        if dwg.is_file():
            dwg_pdf = root / "cad-dwg.pdf"
            run(exe, [str(dwg), "-o", str(dwg_pdf)], root)
            if (not dwg_pdf.is_file() or
                    dwg_pdf.read_bytes()[:5] != b"%PDF-"):
                return fail("DWG to PDF produced no PDF")
            check = run(exe, [str(dwg), "--check"], root)
            if check.stdout.strip() != "OK":
                return fail(f"DWG --check printed {check.stdout!r}")
        dwg_text = workspace / "app/testfile/cad/lw_entities-2d.dwg"
        if dwg_text.is_file():
            dwg_txt = root / "cad-dwg.txt"
            run(exe, [str(dwg_text), "--to", "txt", "-o", str(dwg_txt)], root)
            if not dwg_txt.is_file() or b"FOO" not in dwg_txt.read_bytes():
                return fail("DWG --to txt did not extract the drawing text")
        dwg2004 = workspace / "app/testfile/cad/line_2004.dwg"
        if dwg2004.is_file():
            pdf2004 = root / "cad-2004.pdf"
            run(exe, [str(dwg2004), "-o", str(pdf2004)], root)
            if not pdf2004.is_file() or pdf2004.read_bytes()[:5] != b"%PDF-":
                return fail("DWG R2004 to PDF produced no PDF")
            check = run(exe, [str(dwg2004), "--check"], root)
            if check.stdout.strip() != "OK":
                return fail(f"DWG R2004 --check printed {check.stdout!r}")
        dwg2007 = workspace / "app/testfile/cad/line_2007.dwg"
        if dwg2007.is_file():
            pdf2007 = root / "cad-2007.pdf"
            run(exe, [str(dwg2007), "-o", str(pdf2007)], root)
            if not pdf2007.is_file() or pdf2007.read_bytes()[:5] != b"%PDF-":
                return fail("DWG R2007 to PDF produced no PDF")
            check = run(exe, [str(dwg2007), "--check"], root)
            if check.stdout.strip() != "OK":
                return fail(f"DWG R2007 --check printed {check.stdout!r}")
            dwg_text_2007 = workspace / "app/testfile/cad/lw_example2007.dwg"
            if dwg_text_2007.is_file():
                text2007 = root / "cad-2007.txt"
                run(exe, [str(dwg_text_2007), "--to", "txt", "-o",
                          str(text2007)], root)
                if not text2007.is_file() or b"teksto simpla" not in \
                        text2007.read_bytes():
                    return fail("DWG R2007 --to txt did not extract text")
        dwg2010 = workspace / "app/testfile/cad/line_2010.dwg"
        if dwg2010.is_file():
            pdf2010 = root / "cad-2010.pdf"
            run(exe, [str(dwg2010), "-o", str(pdf2010)], root)
            if not pdf2010.is_file() or pdf2010.read_bytes()[:5] != b"%PDF-":
                return fail("DWG R2010 to PDF produced no PDF")
            check = run(exe, [str(dwg2010), "--check"], root)
            if check.stdout.strip() != "OK":
                return fail(f"DWG R2010 --check printed {check.stdout!r}")

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

        # A pdg_type 0x1A member holds a complete publisher PDF as a zlib
        # stream; the internal Document merger keeps its pages.
        (root / "member.pdz").write_bytes(
            _pdz_container([(b"000001", _pdg_pdf_member(page_pdf))]))
        run(exe, ["member.pdz"], root)
        member_pdf = root / "member.pdf"
        member = member_pdf.read_bytes()
        if (not member_pdf.is_file() or member[:5] != b"%PDF-" or
                b"/Count 1" not in member):
            return fail("0x1A PDF member did not keep its page")
        distinct, mean = _pdf_image_stats(member)
        if distinct < 8 or not 5.0 <= mean <= 250.0:
            return fail("0x1A PDF member page rendered blank")

        # Mixed container: one raster page followed by one PDF member. The
        # merge must keep both pages in member order.
        (root / "mixed.pdz").write_bytes(
            _pdz_container([(b"000001", PNG_1X1),
                            (b"000002", _pdg_pdf_member(page_pdf))]))
        run(exe, ["mixed.pdz"], root)
        mixed = (root / "mixed.pdf").read_bytes()
        if mixed[:5] != b"%PDF-" or b"/Count 2" not in mixed:
            return fail("mixed PDZ container did not merge two pages")
        first = mixed.find(b"/MediaBox [0 0 0.240 0.240]")
        second = mixed.find(b"/MediaBox [0 0 72 72]")
        if first < 0 or second < 0 or first > second:
            return fail("merged page order is not member order")

        # A damaged 0x1A payload must fail loudly instead of dropping a page.
        broken = bytearray(_pdg_pdf_member(page_pdf))
        struct.pack_into("<I", broken, 0x1C, 24)
        (root / "broken.pdz").write_bytes(
            _pdz_container([(b"000001", bytes(broken))]))
        run(exe, ["broken.pdz"], root, expect=1)

        # A member that cannot be decoded must warn and keep the good pages.
        (root / "partial.pdz").write_bytes(
            _pdz_container([(b"000001", page_pdf),
                            (b"000002", b"this is not a page")]))
        partial = run(exe, ["partial.pdz"], root)
        if b"/Count 1" not in (root / "partial.pdf").read_bytes():
            return fail("partial PDZ container lost its readable page")
        if "skipped" not in partial.stderr:
            return fail("partial PDZ container dropped a page without a warning")
        run(exe, ["partial.pdz", "--check"], root, expect=1)

        # --pages auto resolves against meta.xml instead of always using ALL.
        meta = b'<?xml version="1.0"?><pages>1</pages>'
        (root / "auto.pdz").write_bytes(
            _pdz_container([(b"000001", page_pdf),
                            (b"cov", page_pdf),
                            (b"meta.xml", meta)]))
        run(exe, ["auto.pdz", "--pages", "auto"], root)
        if b"/Count 1" not in (root / "auto.pdf").read_bytes():
            return fail("--pages auto did not resolve to the meta.xml body rule")
        run(exe, ["auto.pdz", "--pages", "all", "-o", "auto-all.pdf"], root)
        if b"/Count 2" not in (root / "auto-all.pdf").read_bytes():
            return fail("--pages all did not select every page member")

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
            if b"/MediaBox [0 0 595.276 841.89]" not in a4_pdf.read_bytes():
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
