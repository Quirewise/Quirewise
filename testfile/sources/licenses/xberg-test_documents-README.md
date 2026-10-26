# xberg test corpus

Test documents and ground truth for [xberg](https://github.com/xberg-io/xberg): about 1,400
documents spanning 105 file extensions, and 1,465 ground-truth files saying what extracting them
should produce. 638 of the documents are binaries served from a bucket rather than committed here.

Consumers use it as a git submodule (`xberg/test_documents`) and as the corpus behind the
PDF→Markdown benchmark harness. Two things live here and they are governed differently:

- **Documents.** The inputs. Text formats are committed to git; binaries are not (see below).
- **Ground truth.** What correct extraction looks like. Always committed, always text.

## Getting the documents

**The binary documents are not in this repository, and they are not in Git LFS either.** Git
tracks only text — ground truth, manifests, scripts, and the text-format fixtures. The binaries live
in the public Google Cloud Storage bucket `gs://xberg-test-documents`, content-addressed by sha256
and pinned by `corpus.lock.json`, which maps each repository path to the object that belongs there.

The bucket is world-readable, so fetching needs no credentials, no `gcloud`, and no SDK:

```sh
python3 scripts/fetch_corpus.py                      # everything, ~580 MiB
python3 scripts/fetch_corpus.py --include 'pdf/**'   # just the PDFs
```

Files already present with the right hash are skipped, so re-running is cheap. Several consumers
reference fixtures through `include_bytes!`, so the bytes must be on disk before `cargo build` runs.

In CI, use the shared action, which fetches only what a job needs and caches on the manifest:

```yaml
- uses: xberg-io/actions/fetch-test-documents@v1
  with:
    include: |
      pdf/fake_memo.pdf
```

Anything else can read `corpus.lock.json` and fetch over plain HTTPS directly:

```text
https://storage.googleapis.com/xberg-test-documents/objects/<sha256>
```

### Why a bucket and not Git LFS

The corpus moved off Git LFS. LFS bills bandwidth per clone and makes every consumer authenticate
against it, including CI jobs that need three files out of six hundred. Content-addressed objects in
a public bucket are anonymous to read, cache trivially, and let a job fetch exactly the paths it
uses. `scripts/data/corpus-patterns.txt` was lifted verbatim from the old `.gitattributes` filter list so
the publish set did not change in the move.

## What is in git and what is in the bucket

`scripts/data/corpus-patterns.txt` is the authority. It uses gitignore semantics: a pattern with no `/`
matches a basename at any depth. Every line in it is mirrored in `.gitignore`, and
`scripts/tests/test_publish_corpus.py` fails if the two drift apart.

**Bucket-managed** (never committed): `.pdf .doc .docx .odt .rtf .msg .pst .xls .xlsx .xlsm .xlsb
.xlam .xla .ods .ppt .pptx .pptm .ppsx .odp .key .epub .fb2 .pages .numbers .hwp .hwpx .png .jpg
.jpeg .gif .bmp .webp .tiff .tif .heif .heic .avif .jp2 .jpx .jpm .j2k .j2c .mj2 .ppm .pnm .pgm
.pbm .wav .mp3 .zip .tar .tgz .gz .7z .dbf`, plus `ground_truth/structured/parsebench/*.jsonl`.

**Git-tracked**: everything else — all ground truth, and the text-format fixtures
(`.svg .xml .html .md .rst .org .tex .typ .json .yaml .csv .tsv .eml .opml .ipynb .wp .wpd .wpg
.dot .mmd .puml .fodg` and friends).

The split is by *format*, not by size: a fixture whose bytes a human can read in a diff belongs in
git, because that is where review happens.

## Adding or changing a document

1. Put the file in its directory. If it is a bucket-managed extension, `.gitignore` keeps it out of
   git automatically.
2. Add ground truth under `ground_truth/<ext>/<stem>.{txt,md}` — these **are** committed.
3. Register it with the benchmark harness if it should be scored: a descriptor JSON in
   `xberg/tools/benchmark-harness/fixtures/` (see below).
4. Record provenance. Anything from a third party needs an entry in `ATTRIBUTIONS.md` and, for a
   multi-file set, a `PROVENANCE.md` with per-file sha256 (`wordperfect/PROVENANCE.md` is the
   template).
5. **If the file is bucket-managed**, a maintainer publishes it and commits the refreshed pin:

   ```sh
   python3 scripts/publish_corpus.py --bucket xberg-test-documents --dry-run   # check first
   python3 scripts/publish_corpus.py --bucket xberg-test-documents
   git add corpus.lock.json && git commit
   ```

   This needs write access to the bucket, so **CI cannot do it** — a CI checkout contains no
   binaries to publish. Outside contributors should open a pull request describing the fixture and a
   maintainer publishes it.
6. **Publish before you push the refreshed lock file.** CI verifies that every pinned object
   resolves from the bucket; a lock file that names an object nobody uploaded fails the build.
7. If the fixture uses an extension not yet in `scripts/data/corpus-patterns.txt` and it should be
   bucket-managed, add the pattern to **both** that file and `.gitignore`, with identical text.

Never `git add` a corpus binary. `publish_corpus.py` refuses to run if one was committed.

## Layout

| directory | what |
|---|---|
| `pdf/`, `pdf_scanned/`, `charts/` | 247 PDFs: born-digital, scanned, and chart-heavy |
| `docx/`, `doc/`, `odt/`, `rtf/`, `wordperfect/`, `hwp/`, `hwpx/` | word-processor formats, current and legacy |
| `pptx/`, `ppt/`, `odp/` | presentations |
| `xlsx/`, `xls/`, `data_formats/`, `csv/`, `dbf/` | spreadsheets and tabular data |
| `images/`, `images_extra/` | raster fixtures; `images_extra/` is one file per exotic codec |
| `xml/`, `html/`, `markdown/`, `markup/`, `rst/`, `org/`, `latex/`, `typst/`, `docbook/`, `jats/` | markup and text formats |
| `diagrams/` | vector diagram fixtures for node/edge recovery — see `diagrams/README.md` |
| `email/`, `epub/`, `fictionbook/`, `iwork/`, `jupyter/`, `opml/`, `archives/`, `audio/` | everything else |
| `vendored/` | third-party corpora kept verbatim with their own provenance |
| `ground_truth/` | expected output, one subdirectory per source extension |
| `scripts/` | the corpus tooling: ten entry points over `corpus_tools/`, with `data/` and `tests/` beside them |

## Serving another corpus

The same tooling can serve a corpus whose index lives outside this repository — a private set held
in a private repo, fetched from a private bucket. Every flag defaults to this repository's value,
so the commands above are unchanged.

```sh
python3 scripts/fetch_corpus.py \
  --manifest ../<private-repo>/internal_test_documents/<namespace>/corpus.lock.json \
  --root     ../<private-repo>/internal_test_documents/<namespace>/data \
  --bucket   <private-bucket> --auth
```

`--auth` uses Application Default Credentials, so a local `gcloud auth application-default login`
and workload-identity federation in CI both work without configuration. Anonymous access stays the
default; the credential-free path is what CI proves.

Publishing takes the mirror image — `--manifest`, `--root` and `--patterns` — and refuses two things
outright, because the public bucket cannot un-serve an object and corpus patterns match basenames at
any depth:

- a non-default root, manifest or pattern file aimed at `xberg-test-documents`;
- a `--root` above where those paths say the corpus is, unless `--allow-external-root` says you mean
  it.

Any non-default publish prints the resolved root, file count, byte total and extension histogram and
asks before uploading. Objects are content-addressed, so several manifests can describe subsets of
one bucket at no extra storage cost — a small curated one for CI, a full one for local runs.

A corpus outside this repository should select its files with a single anchored pattern such as
`data/*` rather than a list of extensions. An extension list silently under-publishes whatever it
forgot; an anchored pattern cannot, and it keeps that corpus's own README and checksums out of the
bucket, where they do not belong.

## Ground truth

`ground_truth/<ext>/<stem>.txt` is plaintext ground truth, scored as text-F1.
`ground_truth/<ext>/<stem>.md` is canonical-GFM ground truth, scored structurally. Both may exist;
for pure-OCR fixtures they are byte-identical by design.

Two kinds are not plain text:

- `ground_truth/dot/<stem>.dot` — the node/edge graph a diagram fixture draws, as Graphviz DOT keyed
  by node label. Indexed by `diagrams/manifest.json`, which also carries provenance, the recovery
  class, and the page/bbox of each graph within its document. A document holding more than one
  graph gets `<stem>.g0.dot`, `<stem>.g1.dot`, named by the manifest rather than by convention. An
  empty file means the fixture is a negative control, and the manifest says why. See
  `diagrams/README.md`.
- `ground_truth/structured/` — field- and formula-level extraction targets, with their own manifest.

Two files index the rest:

- `ground_truth/corpus_manifest.json` — the immutable benchmark manifest: per-document hashes,
  source, license, revision, normalization transforms, oracle verdict and scores, cohorts, size
  tier, and tune/eval role, under one frozen top-level hash. **Generated — do not hand-edit.**
- `ground_truth/ground_truth_mapping.json` — a flat `stem → path` index.

The authoritative binding between a document and its ground truth is neither of those: it is the
per-document descriptor in `xberg/tools/benchmark-harness/fixtures/*.json`, which names the
document, its type, its expected frameworks, and its ground-truth files.

## Licensing

`test_documents` is part of xberg, which is MIT-licensed, public, non-commercial open source. The
MIT `LICENSE` covers **our own work** — the tooling, the manifests, the prose. It does not
relicense third-party content: every source document and its upstream ground truth keeps its own
license. See `LICENSES.md` and `ATTRIBUTIONS.md`.

Datasets are handled in two classes:

- **vendor** — permissively licensed (MIT / Apache-2.0 / BSD / CC-BY / CC0 / CDLA-Permissive /
  MPL-2.0 / US public domain). Committed here, with attribution.
- **reference** — non-commercial, ShareAlike, or research-only. **Never redistributed here.**
  Fetched to local staging on demand and used only for non-commercial benchmarking. Their manifest
  entries carry the source URL and license for provenance.

This keeps the public repo free of content it cannot redistribute while still letting the
benchmark use data that cannot be shipped.

## Reproducing the benchmark corpus

The builder for the PDF→Markdown benchmark slice lives in the **xberg** repository, not here:

```sh
python tools/benchmark-harness/scripts/build_corpus.py --stage all
```

It acquires the pinned sources, normalizes ground truth to canonical GFM, gates each document
against an independent text oracle, and writes `pdf/`, `ground_truth/pdf/<stem>.{md,txt}` and the
manifest. Re-running with the same pins is deterministic. This is the only sanctioned way to modify
that slice; hand-added fixtures elsewhere in the corpus are not covered by it.

| dataset | license | ground-truth provenance |
|---|---|---|
| [lazyc/READoc](https://huggingface.co/datasets/lazyc/READoc) | MIT | arXiv GT = author LaTeX→pandoc (no tables); GitHub GT = author README rendered to PDF |
| [llamaindex/ParseBench](https://huggingface.co/datasets/llamaindex/ParseBench) | Apache-2.0 | only `table.jsonl` ships expected markdown (HTML tables); human-verified |
| [bsmock/FinTabNet.c](https://huggingface.co/datasets/bsmock/FinTabNet.c) | CDLA-Permissive-2.0 | financial-statement table crops; GT = canonicalized cell structure rendered to GFM |
| [federalregister.gov](https://www.federalregister.gov) | US-PD (17 U.S.C. §105) | OFR/GPO full-text XML → GFM |

Excluded on purpose: **OmniDocBench** (research-only) and **Nougat** (weights CC-BY-NC, corpus not
distributed).

Upstream ground truth is not committed verbatim — it is normalized to canonical GFM so it can be
scored consistently. The transforms are declared once in the builder's own
`normalize_gt.py` (in the xberg repo, beside `build_corpus.py` above) and applied by it; the per-document `transforms` field in the manifest records what actually ran.

## Verifying

```sh
python3 scripts/verify_corpus.py --bucket xberg-test-documents              # every pin resolves
python3 scripts/verify_corpus.py --bucket xberg-test-documents --sample 20  # download and re-hash
uv run pytest                                                               # tooling tests
```

CI (`.github/workflows/verify-corpus.yaml`) runs the bucket checks on every push and pull request,
on the runner's bare `python3` with no setup step and no install. That is deliberate: it is the
proof that a consumer with a stock interpreter and no credentials can resolve this corpus.
`.github/workflows/test-unit.yml` runs the tooling tests, where installing things is allowed.

The unittest suite also covers the corpus itself where the corpus can contradict its own answer
key — `scripts/tests/test_diagram_manifest.py` checks `diagrams/manifest.json` against the files, against
`corpus.lock.json` for the fixtures that are corpus binaries, and against the ground truth on disk.
Two further checks need renderers and so are not part of CI:

```sh
python3 scripts/check_diagram_ground_truth.py   # needs graphviz; skips cleanly without it
python3 scripts/build_diagram_pdfs.py --check   # needs qpdf, graphviz, librsvg, Chrome, LibreOffice
```
