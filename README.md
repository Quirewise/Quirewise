# Quirewise application

The root repository is the application and composition repository. Format
implementations live in independent, sibling Git repositories:

- `quirewise-runtime`
- `quirewise-charset`
- `quirewise-compression`
- `quirewise-crypto`
- `quirewise-image`
- `quirewise-archive`
- `quirewise-page`
- `quirewise-pdg`
- `quirewise-document`
- `quirewise-ebook`
- `quirewise-text`
- `quirewise-data`
- `quirewise-spreadsheet`
- `quirewise-audio`
- `quirewise-subtitle`
- `quirewise-vector`
- `quirewise-comic`

The application never compiles a nested copy of those repositories. Install the
libraries, add their install prefixes to `CMAKE_PREFIX_PATH`, and select the
libraries to compose with `QUIREWISE_LINK_*` options.

> Every `QUIREWISE_LINK_*` option defaults to `OFF`. A plain
> `cmake -S . -B build` builds a shell that only prints `--version`,
> `--libraries` and `--help`; conversions require at least
> `QUIREWISE_LINK_DOCUMENT` plus the packages its routes use.

```powershell
cmake -S . -B .tmp/build-app -G Ninja `
  -DCMAKE_PREFIX_PATH=<install-prefix> `
  -DQUIREWISE_LINK_RUNTIME=ON -DQUIREWISE_LINK_IMAGE=ON `
  -DQUIREWISE_LINK_ARCHIVE=ON -DQUIREWISE_LINK_PAGE=ON `
  -DQUIREWISE_LINK_PDG=ON -DQUIREWISE_LINK_DOCUMENT=ON `
  -DQUIREWISE_LINK_EBOOK=ON -DQUIREWISE_LINK_TEXT=ON `
  -DQUIREWISE_LINK_DATA=ON -DQUIREWISE_LINK_SPREADSHEET=ON `
  -DQUIREWISE_LINK_AUDIO=ON -DQUIREWISE_LINK_SUBTITLE=ON `
  -DQUIREWISE_LINK_VECTOR=ON -DQUIREWISE_LINK_COMIC=ON
cmake --build .tmp/build-app
.\.tmp\build-app\quirewise.exe --libraries
```

## CLI scope

`quirewise INPUT [INPUT ...] [--to pdf|txt|png] [-o FILE] [--out-dir DIR]
[--check] [--quiet] [--page image|a4] [--pages RULE]
[--archive-password TEXT] [--audio-track N]`

- PDF, DOCX/ODT/HTML/EPUB/FB2, PPTX/ODP, HWPX, EML, MOBI/AZW3, HTMLZ/TXTZ/PMLZ, RTF,
  spreadsheets, subtitles, structured data, images, DjVu/PDZ/UVZ/CAJ/CEB,
  CBZ/CBT and DXF/DWG convert to PDF.
- PDF also converts to TXT (text extraction, no OCR) and PNG (first page).
- `--check` verifies inputs without writing; audio inputs are parsed as
  container/packet streams.
- Outputs are never overwritten and the `-o` extension must match `--to`.
- DXF/DWG `--to txt` emits the drawing text inventory.
- Unreachable routes (RTF, XPS, SVG, RAW, CBR/CB7, image folders, legacy Office)
  return a stable `unsupported`; see
  [the support matrix](docs/formats/support-matrix.md).
- Options that are not wired (`--key`, scan preprocessing, `--pdfa`,
  `--optimize`, directory batches) are documented in
  [the command line reference](docs/usage/command-line.md).

The CAD routing (DXF/DWG) landed after the `v0.2.1-rc1` tag; it is covered by
the repository tests and app smoke, not by the tagged acceptance matrices.

## Validate the workspace

Build and test every library, the external consumer and the application shell,
then run the static boundary gates:

```powershell
python tools/run_acceptance.py --workspace ..
```

The same runner accepts `--shared` for shared-library builds and
`--skip-consumer`/`--skip-app` for narrower loops. It is used by the GitHub
Actions workflow.

Validate the independent-library dependency graph alone:

```powershell
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
python tools/validate_dependency_graph.py --workspace ..
```

The same check is available as a CMake target when configuring with
`-DQUIREWISE_VALIDATE_DEPENDENCIES=ON`:

```powershell
cmake --build .tmp/build-app --target quirewise_validate_dependencies
```

## Release checks

- `tools/audit_release_boundaries.py` — third-party header/symbol/CMake denylist
- `tools/audit_mupdf_removal.py` — legacy MuPDF boundary removal gate
- `tools/verify_public_headers.py` / `tools/verify_header_isolation.py` — public
  header independence
- `tools/verify_header_ownership.py` — no two packages install different bytes
  at the same public-header path (shared vendored headers must stay identical)
- `tools/check_consumer_coverage.py` — exported API to consumer call mapping
- `tools/generate_sbom.py` — CycloneDX SBOM, license inventory and installed
  prefix manifest
- `tools/verify_pdf_pages.c` — render-based PDF check (blank or solid pages,
  unknown image filters); built with `QUIREWISE_BUILD_PDF_VERIFIER=ON`
- `tools/audit_vendored_sources.py` — vendored-source gate: every remaining
  third-party implementation file is pinned in `vendored-allowlist.json`, and
  the list may only shrink

The workspace is licensed under the MIT License; see [LICENSE](LICENSE). Every
library and the external consumer template carry the same MIT grant.
