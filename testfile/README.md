# Quirewise Test Samples

This directory contains input fixtures mapped to the Filee snapshot format registry. Having a sample means there is a file available for conversion checks; it does not imply that Quirewise currently converts it successfully.

## Coverage

- Format IDs in reference registry: 244
- Format IDs with collected samples: 158
- Format IDs with local-only candidates awaiting license review: 82
- Format IDs with no sample found yet: 4
- Collected sample files: 180
- License-review sample files: 124
- Checksums recorded in SHA256SUMS.csv: 304

## Files

- FORMAT_SAMPLE_MATRIX.csv — one row per registered format ID, including aliases and sample paths.
- NEED_USER_SAMPLES.md — formats still missing samples and local candidates awaiting license review.
- SAMPLE_PROVENANCE.csv — per-file source, repository snapshot, and license status.
- SHA256SUMS.csv — byte lengths and SHA-256 checks for collected and quarantined sample files.
- SAMPLE_SMOKE_RESULTS.csv and TEST_RESULTS.md — conversion smoke-test outcomes.
- sources/ — copied README, license, and manifest snapshots for the corpora used.
- _license-review/ — local-only candidates whose source does not state the file license; excluded from Git and do not redistribute until resolved.

## Sample sources and licensing

- [Imazen codec-corpus](https://github.com/imazen/codec-corpus): generated PNM/PAM and GIF conformance samples are public domain/CC0; the image-rs dataset is listed as MIT.
- [Open Media Test Corpus](https://github.com/bandusix/open-media-test-corpus): per-file source, license, URL, and checksum are recorded in the copied manifest. BSD-3-Clause and CC-BY-3.0 samples are in the main sample tree; files whose source license is unstated stay under _license-review/open-media/.
- Apache OpenOffice filter-test files add local candidates for OOXML formats; the individual downloads are not explicitly licensed in the sample listing and remain under _license-review/openoffice/. The site lists DOCX, XLSX, XLSM, PPTX, and macro/template variants ([test documents](https://www.openoffice.org/sc/testdocs/filetype/), [site license](https://www.openoffice.org/license.html)).
- Existing samples retain their original licenses in SAMPLE_PROVENANCE.csv; review that file before copying or redistributing any asset.

- Apache Tika regression fixtures are pinned to commit `fe5ba58bc1bee4f37217c32a05a9b74db7fa51ba`; source repository code is Apache-2.0, but individual fixture rights are not stated, so files stay local-only under `_license-review/tika/`.
- SampleFiles.org publishes files for testing and provides direct downloads, but no redistribution license was found; candidates stay local-only under `_license-review/samplefiles.org/`.

- Project-generated synthetic samples cover open formats where a valid fixture can be created locally; their generation details and any inherited font license are recorded in `sources/generated-fixtures-note.md`.
- Apache Tika SVN fixtures are candidates only because individual fixture licenses are not stated; see `sources/apache-tika-svn-fixtures-note.md`.
- CC0 RAR/CBR fixtures come from [ssokolow/rar-test-files](https://github.com/ssokolow/rar-test-files), pinned to `16b785c2b1b504e99fc307676e5369a26d3ce060`.
- CC0 eBook source files come from [openpreserve/format-corpus](https://github.com/openpreserve/format-corpus), pinned to `366f068cec399d0cdfd61fa473de3ab6dc858098`.
- HWPX sample comes from [KnifeLemon/Filee](https://github.com/KnifeLemon/Filee), pinned to `ff56a0cd1e2516516df3737d8d1cfb7ac69738dc`, under the repository MIT license.

## Main sample layout

image/, pdf/, document/, hwp/, spreadsheet/, presentation/, ebook/, archive/, audio/, video/, subtitle/, vector/, cad/, 3d/, font/, text/, data/, and email/ are grouped by format family.

## Tests

The latest recorded PAGE/CONTAINER acceptance and sample smoke checks are in TEST_RESULTS.md. Failures there represent current converter gaps and remain useful regression inputs.

## Additional sample research

- CDR, LWP, CWK, Pocket Word, TCR, DSS, APE, Musepack, RPM, LHA, TZ, and ISO candidates from [Sembiance FileFormatSamples](https://sembiance.com/fileFormatSamples/) remain local-only because individual file licenses are not stated.
- TAK and CAVS candidates come from the FFmpeg sample corpus; file-specific licenses are not stated, so they remain local-only. The CAVS elementary stream was copied out of the FATE MPEG-PS sample.
- DFF and DSF parser fixtures come from the `file` project test suite; individual fixture licensing is not stated, so they remain local-only.
- CB7, TAR.7Z, and a minimal store-mode EGG file were generated from CC0 fixture content or the CC0 EGG specification. The EGG structure and CRC were validated with an independent parser.
- MacWrite II and ALZ candidates are recorded under `_license-review/`; their individual file licenses are unstated, so they remain local-only.
- SheetJS references a `write.et` fixture, but GitHub has disabled the test-files repository and the reachable mirror returned HTML; no ET file was accepted as a sample.
