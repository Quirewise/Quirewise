# Repository migration map

All 17 libraries are independent Git repositories under `../libraries/`. Each one
configures, builds, installs, installs its public headers and CMake package, and
is consumed by the external consumer template on Windows/MinGW and Ubuntu.

| Repository | Domain | Source packages migrated | Status |
|---|---|---|---|
| quirewise-runtime | shared runtime contract | new | independent package, CTest/consumer pass |
| quirewise-charset | character set conversion | new | independent package, CTest/consumer pass |
| quirewise-compression | DEFLATE/gzip/7z/XZ | new | independent package, CTest/consumer pass |
| quirewise-crypto | RSA/3DES/AES/RC4 primitives | new | independent package, CTest/consumer pass |
| quirewise-image | raster images, folders, scan processing | image, image-folder-parser, image-processing | independent package, CTest/consumer pass |
| quirewise-archive | ZIP, TAR, RAR, 7z | archive, rar, seven-zip | independent package, CTest/consumer pass |
| quirewise-data | JSON, YAML, TOML, XML, vCard, OPML, DocBook | data packages | independent package, CTest/consumer pass |
| quirewise-text | text and markup formats | text packages | independent package, CTest/consumer pass |
| quirewise-page | UVZ, DjVu, CAJ, CEB | page-related packages | independent package, CTest/consumer pass |
| quirewise-pdg | PDG/PDZ decoding and rendering | pdg, pdz | independent package, CTest/consumer pass |
| quirewise-document | Office, presentation, XPS, email, PDF/layout | document packages | independent package, CTest/consumer pass |
| quirewise-ebook | EPUB, MOBI, FB2, PML, HTMLZ | ebook packages | independent package, CTest/consumer pass |
| quirewise-spreadsheet | workbook formats | spreadsheet-parser | independent package, CTest/consumer pass |
| quirewise-audio | audio and encrypted music | audio-parser, encrypted-music-parser | independent package, CTest/consumer pass |
| quirewise-subtitle | timed text | subtitle-parser | independent package, CTest/consumer pass |
| quirewise-vector | SVG and SVGZ | svg, svgz-parser | independent package, CTest/consumer pass |
| quirewise-comic | comic archives | comic-archive-parser | independent package, CTest/consumer pass |

The application repository never compiles a nested copy of these repositories.
It consumes installed CMake packages through `QUIREWISE_LINK_*` options. The
dependency graph is checked by `tools/validate_dependency_graph.py`; the current
graph is acyclic and has no application or sibling source-path dependencies.

Release-wide acceptance is reproduced with:

```powershell
python tools/run_acceptance.py --workspace ..
```

The command builds and installs all 17 libraries in dependency order, runs their
CTest suites, builds the external consumer against the installed prefix, builds
the application shell, and runs the static boundary gates. See
[README.md](README.md) for the individual build instructions.
