# 命令行使用

> **状态（2026-11-11）**：本文档已按当前 `app` 的可执行文件重写。下列命令与选项均已实现并通过
> `app.smoke`（四套验收矩阵）覆盖；未实现的能力单列在“尚未移植”一节，不视为发布能力。

## 1. 基本用法

```
quirewise INPUT [INPUT ...] [-o FILE] [--to FORMAT] [--check] [--quiet]
          [--out-dir DIR] [--page image|a4] [--pages RULE]
          [--archive-password TEXT] [--audio-track N]

quirewise --version | --libraries | --help
```

- 输入按内容识别；无法识别或没有对应内部实现时返回 `unsupported`。
- 默认目标为 PDF；`--to` 目前支持 `pdf`、`txt`、`png`（非 PDF 输出仅用于 PDF 输入）。
- 不指定 `-o` 时，输出使用输入同名文件 + 目标扩展名；`--out-dir` 可把默认输出放进指定目录。
- **已有输出永不覆盖**；失败返回非零状态。
- 多个输入逐个处理，任一失败则最终返回非零；`-o` 只能与单个输入同用。

## 2. 选项

| 选项 | 说明 |
|---|---|
| `-o, --out FILE` | 指定输出文件 |
| `--out-dir DIR` | 默认输出名放入 DIR |
| `--to FORMAT` | 目标格式：`pdf`（默认）、`txt`、`png` |
| `--check` | 只验证输入可读，不写输出；成功打印 `OK`；PDZ/UVZ 有页无法解码时返回非零 |
| `--quiet` | 成功时不打印路径/OK |
| `--page image\|a4` | 页面族/漫画/图片栅格 PDF 的页面框；A4 为 595.276×841.89 点，等比缩放居中 |
| `--pages auto\|body\|body+att\|all` | PDG/PDZ 容器的页面规则；`auto` 用 meta.xml 的 `<pages>` 匹配 BODY+ATT/BODY/ALL，缺 meta.xml 时回退 ALL |
| `--archive-password TEXT` | CBZ 解包密码（`--zip-password` 为别名） |
| `--audio-track N` | `--check` 音频容器时选择从 1 开始的音轨 |
| `--help` / `--version` / `--libraries` | 帮助、版本、已链接库列表 |

## 3. 当前支持的输入 → PDF 路线

| 输入 | 说明 |
|---|---|
| PDF | 直接透传 |
| DOCX/DOCM/DOTX、ODT/OTT/FODT | 内部布局转 PDF |
| HTML、EPUB（reflow）、FB2 | 内部 HTML/布局转 PDF |
| CSV/TSV、XLSX/XLSM/XLTX/XLS/XLT、ODS/OTS/FODS | 表格渲染为 PDF 表格 |
| 纯文本 / Markdown（txt/md 等） | 按行渲染段落 |
| PNG/JPEG/GIF/BMP/WebP/TIFF 等图片 | 单页 PDF，页面框可用 `--page` 控制 |
| DjVu | 逐页渲染为多页 PDF |
| PDG/PDZ（`%pdgz`） | 按 `--pages` 规则重建 PDF；页载荷本身是 PDF 时由内部 PDF 引擎按 300 dpi 栅格化首页；`pdg_type 0x1A` 发行版 PDF 成员由内部 Document 引擎按成员顺序合并 |
| UVZ | 逐页解码（图片、PDG 或 PDF 页载荷）为多页 PDF |
| CAJ、CEB | 提取/解密为 PDF |
| SRT/VTT/LRC/ASS/SSA/SAMI/MicroDVD/SCC | 时间轴文本页转 PDF |
| JSON/JSONL/YAML/TOML/XML/OPML/IPYNB/vCard | 类型化值树渲染为表格/列表后转 PDF |
| CBZ（ZIP）、CBT（USTAR） | 逐页图片转多页 PDF |
| DXF（ASCII/binary）、DWG R13/R14/R2000/R2004/R2007 | DXF 解析图层/块/常用实体；DWG 当前解码 LINE/CIRCLE/ARC/LWPOLYLINE/TEXT（R2007 TEXT 暂未接入）；栅格化为 A4 单页 PDF。文本暂为占位条，可用 `--to txt` 导出文本清单 |

PDF 输入还可以用 `--to txt`（文本抽取，无 OCR）或 `--to png`（首页栅格化，144 dpi）。
DXF/DWG 输入可用 `--to txt` 导出图纸文本清单（每行一个 TEXT/MTEXT），用
`--to pdf` 生成栅格页；DWG R2010+ 在 CLI 中返回 `UNSUPPORTED`。

PDZ/UVZ 转换中若有成员或页无法解码，转换仍会写出可读页，但会在 stderr 打印
`warning: N page(s) skipped: ...`；`--check` 对这种情况返回非零，避免把部分可读
误判为完整成功。

`--check` 额外支持音频容器扫描（WAV/W64、AIFF/AIFC、CAF、DSF/DFF/DSS、M4A/MP4、Matroska/WebM、
MPC、WMA/ASF、AU、ADTS AAC、FLAC、MP2/MP3、AMR、AC-3、DTS、TTA、TAK、WavPack、VOC、APE、
Ogg/Opus），只解析容器/包，不解码。

## 4. 示例

```bash
quirewise manual.docx -o manual.pdf
quirewise scan.pdf --to txt -o scan.txt
quirewise cover.png --page a4 -o cover.pdf
quirewise book.djvu --page a4 --out-dir out
quirewise notes.txt summary.md --out-dir out
quirewise book.pdz --pages body+att -o book.pdf
quirewise track.flac --check --audio-track 1
quirewise report.xlsx -o report.pdf --check      # 错误：--check 不写输出
```

## 5. 退出码

| 码 | 含义 |
|---|---|
| 0 | 全部成功 |
| 1 | 转换/检查失败（含输出已存在、格式不支持、解析失败） |
| 2 | 用法错误（未知选项、缺少输入、`-o` 与多输入/`--check` 冲突、目标格式不支持） |

## 6. 尚未移植（明确不在当前 CLI 能力内）

- `--key`、`--ekey`、`--ekey-db`、`--kgm-key`、`--kgm-db`：密钥选项尚未接入公开转换 API；
- 扫描预处理（`--binarize`、`--deskew`、`--crop`、`--dewarp`、`--despeckle`、`--ccitt-g4` 等）：
  库内扫描转换路线未暴露到文件 API；
- `--pdfa`、`--optimize`：PDF/A 依赖外部后端（Ghostscript/veraPDF），发布包不包含；
- 目录/通配符批量与并发：当前仅支持显式多个文件；
- 音频解码/转码：`quirewise-audio` 仍是 packet reader，CLI 不提供音频输出；
- 视频处理：不存在视频库；
- 旧 CLI 的专用工具（`container_extract`、`container2pdf`、`page_batch`）未移植。

## 7. 与旧文档的关系

旧版本文档描述的是迁移前产品（FFmpeg libav、MuPDF、统一 CLI 全量选项）。当前发布包只包含
内部实现与本文列出的路线；其余入口应返回稳定的 `UNSUPPORTED`。支持子集以各库文档与
`app/tools/run_acceptance.py` 的验收结果为准。
