# Licensing

`test_documents` is part of **xberg** (<https://github.com/xberg-io/xberg>), which is **MIT-licensed,
public, non-commercial open-source**. Kreuzberg, Inc.'s commercial product lives in a separate repo.

## What the MIT license covers

The repository's MIT `LICENSE` covers **our own work**: the corpus tooling
(`tools/benchmark-harness/scripts/*`), the `corpus_manifest.json`, this file, `ATTRIBUTIONS.md`, and
`README.md`. It does **not** relicense third-party dataset content. Each source document and its
upstream ground truth **retain their own upstream license** (see the table below and
`ATTRIBUTIONS.md`). Our GFM-normalized ground truth is a derivative work carried under its source's
license.

## Government edicts

The corpus contains one municipal ordinance: City of Sugar Land, Texas, Ordinance No. 2197. The
ordinance's enacted legal text is classified as a US public-domain edict of government and is
therefore in the `vendor` class. Its citation, source, scope, and modifications are recorded in
`ATTRIBUTIONS.md` under *City of Sugar Land, Texas — Ordinance No. 2197*.

This classification is specific to that ordinance. Publication by a state or local government does
not by itself place a work in the public domain; agendas, minutes, staff reports, attachments, and
third-party submissions require their own copyright and redistribution review before inclusion.

## Redistribution policy

Datasets are handled by license class:

- **vendor** — permissively licensed (MIT / Apache-2.0 / CC-BY / CC0 / US public-domain). Source PDFs
  and ground truth are **committed** into this repo, with attribution in `ATTRIBUTIONS.md`.
- **reference** — non-commercial (CC-BY-NC), ShareAlike (CC-BY-SA / -NC-SA), or research-only terms.
  These are **not committed**. `build_corpus.py` fetches them to local staging on demand; they are
  used only for **non-commercial benchmarking** of this open-source library and are **never
  redistributed** here. Their manifest entries carry the source URL + license for provenance.

This keeps the public MIT repo free of content it cannot redistribute, while still letting the
non-commercial benchmark use non-commercial data.

## Sources

| dataset | license | policy |
|---|---|---|
| [lazyc/READoc](https://huggingface.co/datasets/lazyc/READoc) | MIT | per-doc |
| [llamaindex/ParseBench](https://huggingface.co/datasets/llamaindex/ParseBench) | Apache-2.0 | reference |
| [bsmock/FinTabNet.c](https://huggingface.co/datasets/bsmock/FinTabNet.c) | CDLA-Permissive-2.0 | vendor |
| [federalregister.gov](https://www.federalregister.gov) | US-PD (17 U.S.C. §105) | vendor |
| [apache/tika](https://github.com/apache/tika) (WordPerfect) | Apache-2.0 | vendor |
| [LibreOffice/core](https://github.com/LibreOffice/core) (writerperfect) | MPL-2.0 | vendor |
| [ross-spencer/opf-format-corpus](https://github.com/ross-spencer/opf-format-corpus) | CC0 | vendor |
| [ImageMagick/ImageMagick](https://github.com/ImageMagick/ImageMagick) | ImageMagick (Apache-2.0-derivative) | vendor |
| [ndl-lab/pdmocrdataset-part1](https://github.com/ndl-lab/pdmocrdataset-part1) | Public Domain Mark 1.0 | vendor |
| [naver-clova-ix/cord-v2](https://huggingface.co/datasets/naver-clova-ix/cord-v2) | CC-BY-4.0 | vendor |
| [TextOCR](https://textvqa.org/textocr/) | CC-BY-4.0 | vendor |
| [ds4sd/DocLayNet](https://huggingface.co/datasets/ds4sd/DocLayNet-v1.1) | CDLA-Permissive-1.0 | vendor |
| [executablebooks/MyST-NB](https://github.com/executablebooks/MyST-NB) | BSD-3-Clause | vendor |
| [google-research-datasets/hiertext](https://github.com/google-research-datasets/hiertext) | CC-BY-SA-4.0 | reference (ShareAlike — not committed) |
| regression corpus: [PubMed Central OA](https://europepmc.org), [Project Gutenberg](https://www.gutenberg.org), [govdocs1](https://digitalcorpora.org), [arXiv](https://arxiv.org) | CC-BY-4.0 / CC0 / US-PD, per document | vendor (1,816) |
| regression corpus, restricted subset | CC-BY-SA, CC-BY-NC*, arXiv nonexclusive-distrib | reference (1,459, not committed) |
| math corpus (136 documents, ~70 upstream projects) | MIT / Apache-2.0 / CC-BY / CC0 / US-PD / MPL-2.0 | vendor |
| math corpus, copyleft subset (12 documents) | CC-BY-SA / GPL / GFDL | reference (not committed) |
| EPUB edge-case corpus (36 documents): Project Gutenberg, Standard Ebooks, IDPF, W3C epub-tests, epubcheck, epub.js, epublib, Internet Archive, synthesized | US-PD / CC0 / W3C / BSD-3 / Apache-2.0 / MIT, per document | vendor |
| City of Sugar Land, Texas, Ordinance No. 2197 | US-PD, edict of government | vendor |

Source-specific provenance is recorded in `ATTRIBUTIONS.md`. WordPerfect corpus provenance is in
`wordperfect/PROVENANCE.md`; math corpus provenance is in `MATH_PROVENANCE.md`; and EPUB edge-case
corpus provenance is in `EPUB_EDGE_CASES.md`.
