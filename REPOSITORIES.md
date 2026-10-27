# Repository migration map

| Repository | Domain | Source packages migrated | Status |
|---|---|---|---|
| quirewise-runtime | shared runtime contract | new | created |
| quirewise-image | raster images, folders, scan processing | image, image-folder-parser, image-processing | built and consumer-linked |
| quirewise-archive | ZIP, TAR, RAR, 7z | archive, rar, seven-zip | built and consumer-linked |
| quirewise-page | PDF, UVZ, DjVu, CAJ, CEB | page-related packages | built and consumer-linked |
| quirewise-pdg | PDG/PDZ decoding and rendering | pdg, pdz | built and consumer-linked |
| quirewise-document | Office, presentation, XPS, email | document packages | built locally; consumer packaging cleanup pending |
| quirewise-ebook | EPUB, MOBI, FB2, PML, HTMLZ | ebook packages | built and consumer-linked; format-isolated |
| quirewise-text | text and markup formats | text packages | built |
| quirewise-data | JSON, YAML, TOML, XML, vCard, OPML, DocBook | data packages | built |
| quirewise-spreadsheet | workbook formats | spreadsheet-parser | built locally; consumer packaging cleanup pending |
| quirewise-audio | audio and encrypted music | audio-parser, encrypted-music-parser | built |
| quirewise-subtitle | timed text | subtitle-parser | built |
| quirewise-vector | SVG and SVGZ | svg, svgz-parser | built locally; consumer packaging cleanup pending |
| quirewise-comic | comic archives | comic-archive-parser | built locally; consumer packaging cleanup pending |

Libraries are located in the sibling `../libraries/` directory. Every old source is preserved under the top-level `../.to_delete/` directory. No legacy source is deleted during this migration.
