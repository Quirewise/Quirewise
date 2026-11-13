> **历史快照（2026-11-14 注）**：本文件记录的是当时一轮运行的原始结果，其中的失败项与
> “需要静态 FFmpeg/pkg-config”等描述属于迁移前状态，不代表当前发布包。当前能力与验收以
> [格式能力总览](app/docs/formats/support-matrix.md)、[2026-11-12 验收报告](RELEASE_ACCEPTANCE_REPORT_2026-11-12.md)
> 和 [2026-11-14 缺陷修补报告](MAINTENANCE_REPORT_2026-11-14.md) 为准。
# Conversion Smoke Results

Date: 2026-10-18 (Asia/Singapore).

## PAGE/CONTAINER end-to-end acceptance

Command: `rtk python tools/check_acceptance.py --build-dir .tmp/build/windows/page-focused-c0550390ec5c4876839a8c9008037445`

Result: PASS, 20 checks.

- Offline bookkey extraction: 9/9 containers.
- CONTAINER member extraction: all recorded member size/SHA-256 checks passed.
- PDF conversion: native-member routes produced 220, 238, and 440 pages; image-page routes produced 225, 308, 319, 240, and 186 pages.
- PAGE batch corpus: 39 expected successes and the two recorded negative samples.
- Exclusive-output check: a second write to the same PDF path failed and the original output hash stayed unchanged; extracted member bytes also remained unchanged.

Acceptance artifacts are retained at `.tmp/acceptance/b4aabc1866484283884abac613f88e7a`; the exclusive-output check is at `.tmp/acceptance/exclusive-a7387c2a1afc451cbdf9fff54055b7bd`.

## Sample conversion and detection smoke test

The test harness called the Quirewise in-memory conversion API from the latest available full static DLL (`.tmp/build/windows/release/20261018T143157348-e4c8b08e887649e786b7960feb5395b1/page.dll`). The current full rebuild could not reach compilation because this machine has no static FFmpeg pkg-config packages (`libavformat`, `libavcodec`, `libavutil`, and `libswresample`). These smoke results use the latest available DLL; the PAGE/CONTAINER acceptance above uses a focused executable linked with the newly compiled exclusive-file helper.

Result: 27 checks, 16 passed and 11 failed.

- Audio/container-to-WAV: 9/9 passed (AAC, AC-3, E-AC-3, M4A, MP3, OGG/Opus, 3GP audio, and Matroska audio).
- GIF-to-PDF: passed, one PDF page.
- Image-to-PDF: ICO, PBM, PGM, PPM, PNM, and PAM did not convert; PBM was detected as TXT. These fixtures expose missing or misrouted PNM/ICO support.
- Video container detection: 6/11 passed. AVI, FLV, M2TS, MPEG, and TS were unknown. MP4 and 3GP inputs are identified by the current detector as M4A; MKV/WebM and OGV take their shared container routes.

The initially selected Big Buck Bunny `.mkv` source was checked by signature and starts with ISO-BMFF `ftyp/isom`, not Matroska EBML. It was moved to `video/mp4/` and renamed `.mp4`; the MKV slot now uses a Chromium sample verified to start with EBML signature `1A 45 DF A3`.

The complete per-file results, including exit codes and converter notes, are in SAMPLE_SMOKE_RESULTS.csv. Generated PDFs/WAVs and the harness are retained under `.tmp/acceptance/sample-convert-final-d2108f47c9fb416c86f3b2d5ecd0f9c6`.



## Office document sample checks

Nine OpenOffice-hosted OOXML samples were downloaded into `_license-review/openoffice/`; their individual file licenses are not specified in the sample listing, so they remain local-only. The source page lists Word, Excel, and PowerPoint filter test documents and variants ([test-doc list](https://www.openoffice.org/sc/testdocs/filetype/), [site license](https://www.openoffice.org/license.html)).

A further 9 conversion calls produced 3 successful process exits and 6 failures. None is counted as a correct Office conversion: the three PPTX/PPTM/POTX files were detected and converted through the comic-archive route. DOCM/DOTX/DOTM were detected as DOCX but failed with `DOCX package has no readable word/document.xml` even though that member exists in each ZIP. XLSX/XLSM/XLTX remained unknown.

Combined smoke runs: 36 total; 19 exit code 0, 17 nonzero. Three exit-0 office runs were false successes due to the wrong conversion route. Detailed results are appended in SAMPLE_SMOKE_RESULTS.csv; office artifacts are retained under `.tmp/acceptance/sample-office-f300e6f0744345dfb1b4b4302073165f`.

## Rebuild limitation

A normal `build.ps1 -Config Release` run stopped before compiling project sources because pkgconf could not find the static FFmpeg packages. The focused PAGE/CONTAINER bundle compiled and linked `src/core/workspace.c` with the prior static library, then passed the repository acceptance suite. A complete current-source build and conversion matrix rerun require the static FFmpeg prefix to be available.
