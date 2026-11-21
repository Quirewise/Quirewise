# 命令行使用

> 状态（2026-11-17）：本文档按当前 `app` 可执行文件重写。下列选项与路线均已实现，
> 并由 `app.smoke`（206 例）和 `run_acceptance.py`（85 步）覆盖；未实现的能力单列在
> “明确不可达”一节，不视为发布能力。

## 1. 基本用法

```text
quirewise INPUT [INPUT ...] [-o FILE] [--to FORMAT] [--check] [--quiet]
          [--out-dir DIR] [--page image|a4] [--pages RULE]
          [--archive-password TEXT] [--pdf-password TEXT] [--mdd FILE]
          [--font-file FILE] [--pdf-reflow | --pdf-pages]
          [--image-crop L,T,R,B] [--image-resize WxH] [--sheet N]
          [--audio-track N]

quirewise --version | --libraries | --help
```

- 输入按内容识别；无法识别或没有对应内部实现时返回 `unsupported`。
- 默认目标为 PDF。`--to` 的规范目标为：

  `pdf`、`txt`、`png`、`json`、`jsonl`、`yaml`、`toml`、`xml`、`vcf`、`srt`、`vtt`、
  `lrc`、`sub`、`ass`、`ssa`、`sami`、`scc`、`ttml`、`csv`、`tsv`、`xlsx`、`ods`、`html`、`md`、
  `docx`、`epub`、`bmp`、`tiff`、`jpg`、`webp`、`gif`、`hdr`、`sgi`、`pcx`、`tga`、`qoi`、
  `ppm`、`htmlz`、`txtz`、`pmlz`、`hwpx`、`opml`、`ipynb`。

  另接受 `text`、`yml`、`vcard`、`tif`、`jpeg`、`markdown` 等别名。`opml`/`ipynb` 目标只支持
  Markdown/TXT 源（标题层级/单 markdown cell），其它源返回 `unsupported`。
- 不指定 `-o` 时，输出使用输入同名文件 + 目标扩展名；`--out-dir` 可把默认输出放进指定目录。
- **已有输出永不覆盖**；失败返回非零状态，并删除不完整输出。
- 多个输入逐个处理，任一失败则最终返回非零；`-o` 只能与单个输入同用。
- `--to` 不能与 `--check` 同用；`-o` 不能与多输入或 `--check` 同用。

## 2. 选项

| 选项 | 说明 |
|---|---|
| `-o, --out FILE` | 指定输出文件；扩展名必须与 `--to` 一致 |
| `--out-dir DIR` | 默认输出名放入 DIR；不能与 `--check` 同用 |
| `--to FORMAT` | 目标格式，见上；默认为 `pdf` |
| `--check` | 只验证输入可读，不写输出；成功打印 `OK`；PDZ/UVZ 有页无法解码时返回非零 |
| `--quiet` | 成功时不打印路径/OK |
| `--page image\|a4` | DjVu/PDZ/UVZ/CBZ/CBT/CB7/CBR 与直接图片输入的页面框；`image`（默认）为像素尺寸，`a4` 为 595.276×841.89 点、等比缩放居中。CAD 输出固定 A4 |
| `--pages auto\|body\|body+att\|all` | PDG/PDZ 容器的页面规则；`auto` 用 meta.xml 的 `<pages>` 匹配 BODY+ATT/BODY/ALL，缺 meta.xml 时回退 ALL |
| `--archive-password TEXT` | CBZ/CBT/CB7 等 ZIP/7z 归档密码（`--zip-password` 为别名） |
| `--pdf-password TEXT` | 加密 PDF 的用户口令 |
| `--mdd FILE` | MDX 词条的配套 MDD 资源包，用于按名内嵌图片 |
| `--font-file FILE` | 把该字体嵌入 PDF 输出：TrueType(glyf) 用 CIDFontType2、OpenType/CFF 用 CIDFontType0，均 Identity-H + ToUnicode；glyf 可变字体按默认实例嵌入。CFF2 可变字体无 PDF 1.x 表示，会返回 `unsupported` 并说明原因。缺省仍用 Helvetica/STSong-Light |
| `--pdf-reflow` | PDF→DOCX/EPUB 输出可编辑文本段落（现为默认；显式写出仍可用） |
| `--pdf-pages` | 强制 PDF→DOCX/EPUB 输出整页图片（回退到旧行为） |
| `--pdfa [1b|2b|3b]` | 输出 PDF/A（默认 1b；XMP + sRGB OutputIntent + 嵌入字体，需配合 `--font-file`） |
| `--image-crop L,T,R,B` | 编码图像输出前按像素裁剪 |
| `--image-resize WxH` | 编码图像输出前缩放；`0` 保持宽高比 |
| `--sheet N` | CSV/TSV 输出的从 1 开始的工作表序号；默认第 1 张 |
| `--audio-track N` | `--check` 音频容器时选择从 1 开始的音轨 |
| `--help` / `--version` / `--libraries` | 帮助、版本、已链接库列表 |

## 3. 支持的转换路线

### 3.1 输入 → PDF

| 输入 | 说明 |
|---|---|
| PDF | 直接透传；多输入时合并 PDF 并汇总书签 |
| DOCX/DOCM/DOTX/DOTM、ODT/OTT/FODT | 版式模型转 PDF（含脚注、页眉页脚、缩进、表格） |
| HTML、EPUB/KEPUB、FB2、HTMLZ/TXTZ/PMLZ | 内部 HTML/版式转 PDF；EPUB 保留表格/列表/图片/脚注结构 |
| PPTX/PPTM/POTX/POTM/PPSX/PPSM、ODP/OTP/FODP | 幻灯片文字、内嵌图片与备注；PDF 中每页生成书签 |
| HWPX | 段落、样式、表格、图片、超链接、页眉页脚/脚注、分栏与分节 |
| EML、MSG | 正文与内嵌图片；附件文本/图片按模型嵌入 |
| MOBI/AZW3/AZW | PalmDOC 文本；HUFF/CDIC 和 DRM 内容返回不支持 |
| 纯文本 / Markdown / RTF | 按行或块渲染；RTF 支持常见字符格式和内嵌 PNG/JPEG |
| XLSX/XLSM/XLTX/XLS/XLT、ODS/OTS/FODS、CSV/TSV | 表格渲染为 PDF 表格 |
| JSON/JSONL/YAML/TOML/XML/OPML/IPYNB/vCard | 类型化值树渲染为表格/列表 |
| SRT/VTT/LRC/MicroDVD/TTML/ASS/SSA/SAMI/SCC | 时间轴文本页 |
| PNG/JPEG/GIF/BMP/WebP/TIFF/JP2/PSD/PNM/QOI/ICO/DICOM 等 | 单页 PDF；默认像素尺寸，可用 `--page a4` |
| SVG/SVGZ | 自研子集栅格化为单页 PDF；未支持特性返回 `unsupported` |
| DjVu | 逐页渲染为多页 PDF |
| PDG/PDZ（`%pdgz`） | 按 `--pages` 规则重建 PDF；PDF 页载荷按 300 dpi 栅格化 |
| UVZ | 逐页解码（图片、PDG 或 PDF 页载荷）为多页 PDF |
| CAJ、CEB、XPS/OpenXPS | 提取/解密/解析后输出 PDF |
| CBZ、CBT、CB7、CBR（stored 条目） | 逐页图片转多页 PDF |
| DXF（ASCII/binary）、DWG R13–R2018 | 栅格化为 A4 单页 PDF；`--to txt` 导出文本清单 |

### 3.2 PDF 输入 → 其它目标

- `--to txt`：文本抽取（无 OCR）。
- `--to html` / `md`：由文本层生成。
- `--to png|jpg|bmp|tiff|webp`：首页 144 dpi 栅格化，可配合 `--image-crop`/`--image-resize`。
- `--to docx|epub`：每页按 120 dpi 栅格化为 JPEG 后嵌入（最多 24 页，保留视觉版式，
  文本不可编辑）。

### 3.3 家族内互转

- **结构化数据**：JSON、JSON Lines、YAML、TOML、vCard、XML 之间互转；OPML/iPynb 作为数据源只读，
  Markdown/TXT 可写出（见下）。
- **字幕**：SRT、WebVTT、LRC、MicroDVD、TTML、ASS、SSA、SAMI、SCC 之间互转（TTML 写出只含
  begin/end 与文本）。ASS/SSA 直转保留说话人、层/边距/Effect 与覆盖标签。
- **Markdown/TXT** → OPML（标题层级 outline）或 IPYNB（单个 markdown cell，nbformat 4.5）。
- **工作簿**：任意工作簿输入 → XLSX/ODS（全部工作表、值、合并区间）；→ CSV/TSV
  （默认第一张，`--sheet N` 选表）。
- **版式输入**（Office、电子书、EML/MSG、HWPX、MDict、RTF、HTML、纯文本）→
  HTML、Markdown、DOCX、EPUB、HTMLZ、TXTZ、PMLZ、HWPX。
- **图像输入** → PNG/BMP/TIFF/JPEG/WebP/TGA/QOI/PPM/GIF/HDR/SGI/PCX，可先裁剪/缩放。

## 4. 示例

```bash
quirewise manual.docx -o manual.pdf
quirewise scan.pdf --to txt -o scan.txt
quirewise slides.pptx -o slides.pdf
quirewise book.djvu --page a4 --out-dir out
quirewise notes.txt summary.md --out-dir out
quirewise book.pdz --pages body+att -o book.pdf
quirewise encrypted.pdf --pdf-password secret --to txt -o plain.txt
quirewise dictionary.mdx --mdd resources.mdd -o dictionary.pdf
quirewise report.html --font-file NotoSansCJK-Regular.ttf -o report.pdf
quirewise scan.pdf --to docx -o scan.docx   # 默认可编辑文本
quirewise scan.pdf --to docx --pdf-pages -o scan.docx  # 整页图片
quirewise drawing.dxf --to txt -o drawing.txt
quirewise track.flac --check --audio-track 1
quirewise report.xlsx --to xlsx -o copy.xlsx
quirewise sheet.xlsx --to csv --sheet 2 -o sheet2.csv
quirewise captions.srt --to ass -o captions.ass
quirewise report.docx --to htmlz -o report.htmlz
quirewise cover.png --to webp --image-resize 800x0 -o cover.webp
quirewise report.xlsx -o report.pdf --check      # 错误：--check 不写输出
```

## 5. 退出码

| 码 | 含义 |
|---|---|
| 0 | 全部成功 |
| 1 | 转换/检查失败（含输出已存在、格式不支持、解析失败） |
| 2 | 用法错误（未知选项、缺少输入、`-o` 与多输入/`--check` 冲突、目标格式不支持） |

## 6. 明确不可达（返回 `unsupported` 或用法错误）

- PDF/A-1b/2b/3b 已支持并通过 **veraPDF 1.30.4** 外部校验（`--pdfa [1b|2b|3b]` + `--font-file`）；OCR、可编辑的 PDF 版式/表格重建（默认输出可编辑文本，`--pdf-pages` 回退整页图片）；PDF 书签/元数据可读写。
- 旧版 `.doc`/`.wps`/`.pages`、CHM/LIT/LRF/PDB/RB/SNB/TCR、DocBook 的统一转换入口。
- DRM、HUFF/CDIC 压缩的 MOBI、注册码加密词典（`Encrypted="1"`/`"3"`）。
- AVIF/HEIC/JPEG XL/PCD/相机 RAW 解码；EPS/PS/AI、EMF/WMF/CGM/CDR/VSD。
- 压缩的 RAR 条目、WinZip AES 等未支持加密；CB7 仅支持受限 7z 子集。
- 音频解码/转码、视频处理。
- 密钥选项（`--key`/`--ekey` 等）、扫描预处理（`--binarize`/`--deskew` 等）、目录/通配符批量
  与并发；旧 CLI 的专用工具未移植。

## 7. 与旧文档的关系

旧版本文档描述的是迁移前产品（FFmpeg libav、MuPDF、统一 CLI 全量选项）。当前发布包只包含
内部实现与本文列出的路线；其余入口返回稳定的 `UNSUPPORTED`。支持子集以各库文档与
`app/tools/run_acceptance.py` 的验收结果为准。
