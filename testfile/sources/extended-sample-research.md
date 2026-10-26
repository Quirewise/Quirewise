# Extended sample research

Research date: 2026-10-18. All paths below are recorded in SAMPLE_PROVENANCE.csv and SHA256SUMS.csv.

## License-review candidates

- Sembiance format samples: https://sembiance.com/fileFormatSamples/ . The site provides directly downloadable fixtures but no per-file redistribution license was found. These files are kept under `_license-review/sembiance/`.
- FFmpeg samples: `https://samples.ffmpeg.org/A-codecs/tak/lostchord-tak_1_0.tak` and `https://fate-suite.ffmpeg.org/cavs/cavs.mpg`. The FATE MPEG-PS file was stream-copied to a raw CAVS elementary stream. File-specific redistribution terms were not found; candidates stay under `_license-review/ffmpeg/`.
- DFF/DSF: `tests/dsd64-dff.testfile` and `tests/dsd64-dsf.testfile` from the `file` repository at commit `4ee5ca8fb938c3168bcededd0ce7c2e03daea485`. `file(1)` and FFprobe identify the actual DSDIFF/DSF structures. Fixture rights are not stated; candidates stay under `_license-review/libmagic/`.
- ISO 9660: Sembiance `archive/iso/test.iso`; `file(1)` identifies an ISO 9660 filesystem and bsdtar lists its files. License not stated; local-only.
- Pocket Word: Sembiance `document/pocketWordDocument/00ReadMe.001` is recognized by `file(1)` as a Pocket Word v2 document. It is stored with the `.psw` extension for format dispatch; license not stated.

## Generated fixtures

- `ebook/cb7/sample.cb7`: a valid 7z comic archive made from the project-generated CC0 comic sample; bsdtar lists its PNG page and ComicInfo.xml.
- `archive/tar7z/sample.tar.7z`: a 7z wrapper around the existing project-generated CC0 TAR fixture; bsdtar lists the nested TAR.
- `archive/egg/minimal-store.egg`: a one-entry, store-mode ALZip EGG v1 archive generated from the CC0 EGG specification at https://github.com/alkegi/docs/blob/master/egg.md. The independent `unegg.py` parser lists the member and verifies its CRC during extraction.

No converter runtime dependency was added. The tools used above were used only to collect, generate, or inspect fixtures.
- MacWrite II sample `Binn-Erker.MacWriteII.mcw` was recovered from the 2001 Internet Archive snapshot of the author's sample page; its individual file license is not stated, so it remains local-only.
- ALZ fixture `t.alz` is pinned to patool commit `eb8185c6ef6e5fc0ed22a495d0c7bf18bb7d8c58`; patool's `test_unalz.py` uses it for listing and extraction checks. The individual archive license is not stated, so it remains local-only.
- A SheetJS fixture manifest references `test_files/artifacts/wps/write.et`, but the accessible Gitea raw endpoint returned an HTML sign-in page and the file is not tracked in that commit; it was excluded. ET remains missing.
- T602 searches found historical editor installers and format references but no standalone `.602` document sample.
- WPS documentation identifies `.dps` as its native presentation format; public WPS template downloads found during this search were PPTX, not DPS.
- No shareable DRM-free AZW4 sample was found. The publicly documented format is a PDF payload in a Palm database and is usually DRM-protected.

## Final six-format follow-up (2026-10-18)

- T602: the [Baycom terminal page](https://packet-radio.hys.cz/baycom-terminal/) identifies `baycom.602` as a T602 document, but its two linked RAR archives do not contain that document. The [Czech forum thread](https://pc-help.cnews.cz/viewtopic.php?t=224231) has only JPEG attachments. The Archive.org CDX query returned no capture for the named file. No standalone `.602` sample was recovered.
- WPS ET: the [official WPS ET page](https://www.wps.com/feature/et-file/) confirms `.et` is a native WPS spreadsheet and that changing an extension does not convert a file. No independently downloadable ET workbook was found; the SheetJS fixture path remains unavailable and was not bypassed.
- WPS DPS: [WPS documentation](https://open.wps.cn/documents/app-integration-dev/docs-center/online-preview-edit/format) identifies `.dps` as a native presentation type. The [public template gallery](https://explore.wps.com/templates) provides previews and export guidance for PPTX/PDF, but no raw DPS download.
- AZW4: [MobileRead's format page](https://wiki.mobileread.com/wiki/AZW4) describes a PDF payload inside a Palm database wrapper and says the format is usually DRM-protected. Its [first sample-analysis post](https://www.mobileread.com/forums/showpost.php?p=1725677&postcount=126) explicitly refers to a non-DRM Amazon Print Replica sample but does not attach or link to the book. No shareable, DRM-free AZW4 file was found.