# 统一 CLI 移植计划（C1–C4）

> 状态：C1 完成（2026-11-11）：文件级 API 与 CLI 骨架已实现，`app.smoke` 在四套矩阵中
> 执行 HTML→PDF→TXT、`--check`、拒绝覆盖的端到端检查。C2–C4 待推进。

## 背景

`quirewise/convert.h` 已经声明了文件级转换 API，但只有两个内存转换函数有实现：

| 函数 | 现状 |
|---|---|
| `qw_convert_to_pdf_memory` | 已实现（PDF/ZIP DOCX/ODT/flat ODF/HTML） |
| `qw_convert_to_format_memory` | 已实现（PDF→TXT/PNG；其他输入→PDF） |
| `qw_detect_format` / `qw_format_name` | 仅声明 |
| `qw_convert_file` / `qw_convert_file_to_format` / `qw_check_file` | 仅声明 |

因此 CLI 的第一步不是参数解析，而是补齐文件级 API；CLI 本身保持薄层，只做参数、
目标格式映射、默认输出路径与错误呈现。

## C1：文件 API + CLI 骨架（本阶段）

- 实现 `qw_detect_format`、`qw_format_name`（复用内部 `format_registry` 探测）。
- 实现 `qw_convert_file`、`qw_convert_file_to_format`、`qw_check_file`：
  - 读取输入（512 MiB 上限）、UTF-8 路径（Windows 走 `_wfopen`/`_waccess`）；
  - PDF 输出走 `qw_doc_convert_memory`（扩展名决定 EPUB reflow）；
  - 非 PDF 输出走 `qw_convert_to_format_memory`；
  - 输出不覆盖已存在路径，失败删除半成品；
  - `--check`：PDF 逐页渲染验证，其他输入执行一次 PDF 转换路线并丢弃输出。
- CLI 参数：`--to FORMAT`、`-o/--out FILE`、`--check`、`--quiet`、`--version`、
  `--libraries`、`--help`；默认输出 PDF，目标扩展名替换输入扩展名。
- C1 支持的目标：`pdf`、`txt`、`png`（与当前调度实现一致）；其他目标返回
  `UNSUPPORTED` 并给出说明。

验收：HTML→PDF、PDF→TXT、`--check`、重复输出拒绝；`app` 在四套矩阵中可构建运行。

### C1 已落地（2026-11-11）

- `qw_detect_format` / `qw_format_name`：内容嗅探（PDF、DjVu、PNG/JPEG/GIF/BMP/WebP、
  FLAC/MP3/OGG/WAV/AIFF/CAF、ZIP/EPUB、HTML/FB2/ODT），并回退到格式注册表。
- `qw_convert_file` / `qw_convert_file_to_format` / `qw_check_file`：UTF-8 路径
  （Windows 宽字符）、512 MiB 输入上限、输出不覆盖、失败删除半成品。
- `qw_check_file`：PDF 逐页渲染验证；其他输入执行一次 PDF 转换并丢弃输出。
- CLI：`--to pdf|txt|png`、`-o/--out`、`--check`、`--quiet`、`--version`、
  `--libraries`、`--help`；默认输出为输入同名 + 目标扩展名。
- 覆盖范围：输入→PDF 支持 PDF/DOCX/ODT/FODT/HTML/EPUB(reflow)/FB2/CSV/TSV；
  非 PDF 输出当前仅 PDF→TXT/PNG；未知或音频输入的 `--check` 返回 `UNSUPPORTED`。
- 回归：`quirewise_document_convert_file` CTest；`app.smoke` 端到端 CLI 检查。

## C2：扩展转换调度

### C2 已落地（部分，2026-11-11）

- **纯文本 / Markdown → PDF**：`txt`/`text`/`md`/`markdown` 扩展名走段落渲染，
  跳过 UTF-8 BOM。
- **图片 → PDF**：PNG/JPEG/GIF/BMP/WebP/TIFF 等由 `qw_image_probe` 探测，
  解码为 Gray8/RGB24 后写入单页 PDF；新增公开的
  `qw_raster_pages_to_pdf` 支持多页栅格（未压缩图像 XObject）。
- **表格 → PDF**：XLSX/XLSM/XLTX/XLS/XLT/ODS/OTS/FODS 解析后按全部工作表
  渲染为 HTML 表格再转 PDF；CSV/TSV 保持原有路径。
- **页面族 → PDF（app 侧路由）**：
  - DjVu：逐页 `qw_djvu_render_page` → 多页栅格 PDF；
  - PDG/PDZ（`%pdgz`）：`pdz_pdf_from_pdz` 直接生成 PDF；
  - UVZ：逐页读取，优先 `qw_image_decode`，否则 `pdg_render_memory`；
  - CAJ：经典 CAJ 与 KDH 两条 PDF 提取路线；
  - CEB：`qw_ceb_decrypt_to_pdf`。
- **字幕 → PDF（app 侧路由）**：SRT/VTT/LRC/ASS/SSA/SAMI/MicroDVD/SCC 解析为
  时间轴 + 文本页，经内部 HTML 布局写 PDF。
- **结构化数据 → PDF（app 侧路由）**：JSON/JSONL/YAML/TOML/XML/OPML/IPYNB/vCard
  解析为类型化值树，对象/数组渲染成表格与列表后写 PDF。
- **漫画归档 → PDF（app 侧路由）**：CBZ（ZIP）与 CBT（USTAR）逐页解码为
  多页栅格 PDF；CBR/CB7 暂不支持。
- **音频 `--check`（app 侧）**：容器/包扫描（不解码）；PCM 容器若路由不暴露
  包序列，按“容器已解析”通过并注明。
- **检测**：`qw_detect_format` 增加图片兜底与常见 magic。

### C2 剩余

- 页面族/扫描选项（页面规则、扫描预处理、密钥）；
- CBR/CB7 等漫画归档（需要 RAR/7z 解包）。

## C3：选项与批量

- 选项映射到 `QwConvertOptions`：`--key`、`--pages`、`--archive-password`、
  `--zip-password`、`--audio-track`、`--ekey`、`--kgm-key`、扫描页选项；
- `--pdfa`/`--optimize` 在 PDF/A 后端可用时接入；
- `--out-dir`、批量输入（目录/通配符）与 `--quiet` 语义统一。

## C4：验收与发布

- `app/tools/run_acceptance.py` 增加 CLI 冒烟步骤（HTML→PDF→TXT、--check、拒绝覆盖），
  `EXPECTED_STEPS` 同步；
- 更新 `app/docs/usage/command-line.md` 的状态注记为“已移植范围 + 未覆盖项”；
- `app/docs/formats/support-matrix.md` 增加“CLI 可用”列或注记；
- 发布证据（报告/SBOM/lock）随下一候选重新生成。

## 非目标（本计划不做）

- 视频处理；
- 音频解码/编码（保持 parser-only，CLI 仅解析与检查）；
- PDF/A 的 veraPDF/Ghostscript 外部后端（仍返回 UNSUPPORTED）。
