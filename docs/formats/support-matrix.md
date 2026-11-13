# 格式能力总览（三态口径）

> 状态：2026-11-14 按当前代码重新核对。旧版本把"库里有解析器"与"CLI 能转换"混为一谈，
> 本页改用三态描述：
>
> - **CLI 可达**：`quirewise` 可执行文件能完成的转换；
> - **仅库 API**：库包公开了接口，但统一转换入口/CLI 没有路由；
> - **不支持**：没有实现，入口稳定返回 `UNSUPPORTED`。
>
> 三者都以当前 HEAD 的代码为准；历史文档中依赖 Ghostscript、veraPDF、FFmpeg、LibRaw、
> MuPDF 等外部后端的路线不在发布包内。

## 1. 输入类别总览

| 输入类别 | 代表格式 | CLI 可达 | 仅库 API | 不支持 |
|---|---|---|---|---|
| PDF | PDF 1.x–1.7 | PDF→PDF（透传/合并书签页）、PDF→TXT（无 OCR）、PDF→PNG（首页 144 dpi） | 逐页栅格化、文本抽取、多文档合并 | PDF/A（需外部 veraPDF）、有用户口令的加密文档、OCR |
| Office 文本 | DOCX/DOCM/DOTX/DOTM、ODT/OTT/FODT | →PDF | HTML/版式模型（`qw_docx_parse`、`qw_odt_parse`） | 旧版 .doc、宏语义、页眉页脚、浮动环绕、VML/EMF/WMF、纵向合并 |
| 演示文稿 | PPTX/PPTM/POTX/POTM/PPSX/PPSM、ODP/OTP/FODP | →PDF（仅文字） | 幻灯片文字/版式 HTML | 形状位置、图片、图表、备注、动画、母版 |
| HWPX | HWPX | →PDF（段落/简单表格） | 版式 HTML | 旧版 HWP、样式、图片、加密部件 |
| 邮件 | EML | →PDF（正文；附件只列名称） | MIME 解析、附件数据 | MSG、签名语义、RFC 2231 文件名 |
| XPS | XPS/OpenXPS | — | 页面 XML 读取 | →PDF（缺少 XPS→版式/PDF 适配层） |
| 电子书 | EPUB/KEPUB、MOBI/AZW3/AZW、FB2、PMLZ、TXTZ、HTMLZ | →PDF | 段落/章节模型 | DRM、HUFF/CDIC 压缩的 MOBI、CHM/LIT/LRF/PDB/RB/SNB/TCR |
| 轻量标记 | TXT、Markdown、HTML | →PDF | 读取后转 HTML/Markdown | RTF、AsciiDoc、LaTeX、Org、RST、Textile、Typst、DocBook、Man、MediaWiki 的统一转换入口（库里有读取器，CLI 未接线） |
| 工作簿 | XLSX/XLSM/XLTX、BIFF8 XLS/XLT、ODS/OTS/FODS、CSV/TSV | →PDF（按工作表渲染表格） | 单元格/公式缓存读取 | **任何工作簿写出**（库是只读解析器）、公式重算、图表/图片/合并区域样式 |
| 结构化数据 | JSON、JSONL、YAML、TOML、XML、OPML、IPYNB、vCard | →PDF（值树渲染为表格/列表） | 类型化值树、XML 序列化 | 其它格式的写出器、YAML anchor/tag、XML DTD 之外的校验 |
| 字幕 | SRT、WebVTT、LRC、MicroDVD、TTML、ASS/SSA、SAMI、SCC | →PDF（时间轴文本页） | cue 模型、格式互转 | 样式/定位/说话人/特效保留、字幕封装 |
| 单页图像 | JPEG、PNG、BMP、GIF、TIFF、WebP、JP2/J2K、QOI、Netpbm、PSD/PSB、EXR、HDR、TGA、PCX、ICO/ICNS、DDS、XPM/XBM、SGI、RAS、MIFF、DCM 等 | →PDF（单页） | 解码、动画/多页展开、图像写出（PNG/JPEG/BMP/TIFF/WebP/…） | AVIF/HEIC/JXL/PCD 解码、RAW 去马赛克 |
| 相机 RAW | DNG/TIFF-CFA、CR3、RAF、X3F、CRW、MRW | — | 文件签名/结构探测 | **像素解码恒返回 `UNSUPPORTED`**（发布包不含 LibRaw 或自研去马赛克） |
| 矢量 | SVG/SVGZ | — | 子集解析 + RGBA 栅格化 | SVG→PDF/图像（CLI 无路由）、EPS/PS/AI |
| CAD | DXF（ASCII/binary）、DWG R13–R2018 | →PDF（A4 栅格）、→TXT（文本清单） | 文档模型、RGBA/SVG 渲染（SVG 文本可读） | DWG 图层句柄/块/ATTRIB、MTEXT/HATCH/ACIS/3D/代理对象、精确 NURBS、CJK 字形 |
| 漫画归档 | CBZ、CBT | →PDF（图像页；坏页告警，`--check` 失败） | 归档页序/页字节 | CBR/CB7（RAR 仅解析头、7z 未接入 comic 路由）、其它归档 |
| 图像目录 | 目录 | — | 非递归枚举（`quirewise-image` 的 image_folder） | CLI 目录输入 |
| 标准音频 | WAV/RIFX/RF64/BW64/Wave64、AIFF/AIFC、CAF、AU、DSF/DFF/DSS、VOC、FLAC、MP1/2/3、AAC、AMR、AC-3/E-AC-3、DTS、TTA、TAK、WavPack、APE、Musepack、WMA/ASF、M4A/MP4、Matroska/WebM、Ogg/Opus | `--check` 容器/包解析 | 包读取、加密音乐解密（NCM/QMC/KGM/KWM） | 解码到 PCM、重采样、编码/封装、播放 |
| 视频、字体、3D | MP4 视频、TTF/OTF 等、STL/GLTF | — | — | 没有对应库 |

## 2. 统一边界

1. 格式支持按"输入格式 × 输出格式 × 路线"定义；能解析不等于能写出，扩展名识别也不等于完整兼容。
2. 版式转换只保留已映射的文字、段落、列表、表格和部分图片；源格式的样式、布局、附件、公式和元数据可能丢失。
3. 栅格化会丢失矢量结构、文本选择能力和源元数据；PDF→TXT 只抽取可读文本，不执行 OCR。
4. 公式按文件内缓存结果读取，不重新计算。
5. 页面/图像/归档/结构化数据都有尺寸、页数、节点数和展开大小上限；超限返回 `RESOURCE_LIMIT` 或 `UNSUPPORTED`，不静默降级。
6. 需要后端的路线（PDF/A、RAW 去马赛克、视频）在发布包内一律返回 `UNSUPPORTED`。

## 3. 命令行注记（2026-11-14）

- `quirewise INPUT [--to pdf|txt|png]` 覆盖上表"CLI 可达"列；`-o` 的扩展名必须与 `--to` 一致（否则退出码 2）。
- 非 PDF 输出目前只有 PDF→TXT、PDF→PNG 和 CAD→TXT；其余输入只支持转 PDF。
- `--page image|a4` 作用于 DjVu/PDZ/UVZ/CBZ/CBT 和直接图片输入的页面框（默认 image = 像素尺寸）；CAD 输出固定 A4。
- `--pages auto|body|body+att|all` 只作用于 PDG/PDZ 容器；`--archive-password` 传给 CBZ/CBT 与库的 ZIP 路线；`--audio-track` 只用于音频 `--check`。
- 徽标/密钥/扫描预处理/PDF-A/目录批量仍未接线；`--pdfa` 等未识别选项返回退出码 2。
