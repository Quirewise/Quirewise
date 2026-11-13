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

```powershell
cmake -S . -B .tmp/build-app -DQUIREWISE_LINK_IMAGE=ON -DQUIREWISE_LINK_ARCHIVE=ON
cmake --build .tmp/build-app
.\.tmp\build-app\quirewise.exe --libraries
```

The current application executable provides the first CLI slice (C1): it reports
the version and the libraries selected at configure time, and converts a single
file with `--to pdf|txt|png`, `-o FILE` and `--check`. DXF drawings are routed
through `quirewise-vector` (PDF raster or `--to txt` text inventory); DWG
R13/R14/R2000 supports LINE/CIRCLE/ARC/LWPOLYLINE/TEXT, while R2004+ returns
`UNSUPPORTED`.
The remaining options and input routes
follow the [CLI port plan](docs/architecture/cli-port-plan.md).
Conversion dispatch lives in the library packages and is exercised by the
external consumer template as well as the CLI smoke step in
`tools/run_acceptance.py`.

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

The check rejects dependency cycles, package-config dependencies missing from
the build graph, and library source that reaches into another library or the
application.

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
  the list may only shrink (see `docs/architecture/zero-vendored-plan.md`)

The workspace is licensed under the MIT License; see [LICENSE](LICENSE). Every
library and the external consumer template carry the same MIT grant.
