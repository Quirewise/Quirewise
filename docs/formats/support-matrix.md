# 格式能力总览

> **发布范围（2026-11-07）**：本表沿用迁移前的能力清单。当前可独立发布的
> Quirewise 包只包含内部实现的路线；标注 LibRaw、Ghostscript、veraPDF、FFmpeg、
> MuPDF 或类似外部后端的路线不在发布范围内，相应入口必须返回稳定的
> `UNSUPPORTED`。实际支持子集以 `libraries/*/docs` 和验收证据为准。

本页按输入类别汇总 Quirewise 可用的转换方向。精确子集、参数和限制见各分类文档。

## 转换方向

| 输入类别 | 代表格式 | 可用输出方向 |
|---|---|---|
| PDF 与扫描文档 | PDF、PAGE、CONTAINER、UVZ、DjVu、CAJ、KDH、CEB | PDF；PDF 还可输出受限图像、TXT，或经验证生成 PDF/A。 |
| Office 与电子书 | DOCX/DOCM/DOTX/DOTM、ODT/OTT/FODT、HWPX、EPUB/KEPUB、MOBI/AZW3、FB2、XPS/OpenXPS | PDF、共享版式输出；MOBI/AZW3 和 XPS 的读取子集见[文档与文本](documents-and-text.md)。 |
| 演示文稿 | PPTX/PPTM/POTX/POTM/PPSX/PPSM、ODP/OTP/FODP | 以页面文字为主的 PDF、HTML 和共享版式输出。 |
| 文本与邮件 | TXT、HTML、Markdown、RTF、EML、HTMLZ、TXTz、PMLz 及轻量标记文本 | PDF、HTML、文本/标记格式、EPUB、DOCX、HWPX 等共享版式输出。 |
| 工作簿 | XLSX/XLSM/XLTX、BIFF8 XLS/XLT、ODS/OTS/FODS、CSV/TSV | PDF、HTML、文本/标记格式、XLSX/XLTX、ODS/OTS/FODS、CSV/TSV；部分路线使用类型化工作簿模型。 |
| 结构化数据 | JSON、JSONL、YAML、TOML、XML、vCard 2.1/3.0/4.0 | 支持格式之间的类型化转换；部分数据也可转换为表格或版式输出。 |
| 字幕 | SRT、WebVTT、LRC、MicroDVD、TTML、ASS/SSA、SAMI、SCC | 受支持字幕格式之间转换，或转换为 PDF。 |
| 单页图像 | JPEG、PNG、BMP、GIF、TIFF、WebP、JP2/J2K、QOI、Netpbm 等 | PDF 和已注册的单页图像 writer；动画或多页输入只在明确支持的目标上保留为多页。 |
| 相机 RAW | DNG/TIFF-CFA、CR3、RAF、X3F、CRW、MRW 等 | PDF 和已注册的单页图像 writer；像素解码与去马赛克受 LibRaw 构建能力约束。 |
| 矢量与打印图形 | SVG/SVGZ、EPS、PS、带 Illustrator 标记的 legacy AI | PDF、单页图像；部分路线可在 PDF 与 EPS/PS 之间转换。SVG 输出仅接受受支持页面图像。 |
| 漫画与图像归档 | CBZ、CBR/RAR/RAR5、CB7/7z、CBT/USTAR、图像目录 | PDF、CBZ、CBT；归档成员按支持的图像格式逐页处理。 |
| 标准音频 | MP2、MP3、FLAC、Musepack、M4A/AAC、WAV、OGG、Opus、AIFF、CAF、WMA、Matroska/WebM、DSF/DFF/DSS 等 | 已注册音频输出之间转码；具体解析子集、编解码器、采样率、位深和容器要求见[音频](audio.md)。 |
| 加密音乐容器 | NCM、QMC、KGM/KGMA/VPR、旧版 KWM | 在密钥和容器变体受支持时解密并转为已注册音频格式。 |

## 通用边界

1. 格式支持按具体变体和转换方向定义；扩展名识别不是完整格式兼容性的证明。
2. 页面和图像路线有像素、页数、维度及编码限制；归档和结构化文档有展开大小、成员数、节点数及深度限制。
3. 版式转换通常只保留已映射的文字、段落、列表、链接、表格或图片。源格式的高级样式、布局、附件和元数据可能丢失。
4. 栅格化会丢失矢量内容、文本选择能力和源 PDF 元数据。PDF→TXT 只抽取可读取文本，不执行 OCR。
5. 公式按文件内缓存结果读取，不会由 Quirewise 重新计算。
6. 需要后端的路线受程序构建能力约束。PDF/A 还要求配置 veraPDF；未配置或验证未通过时不发布 PDF/A 结果。

可选扫描页处理、CLI 格式别名和参数分别见[PDF 与页面格式](pdf-and-pages.md)及[命令行使用](../usage/command-line.md)。
