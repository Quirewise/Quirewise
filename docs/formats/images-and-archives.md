# 图像、矢量图与归档

## 图像输入

普通图像输入路线覆盖 JPEG、PNG、BMP、GIF、TIFF、WebP、JP2/J2K、PCX、PFM、DDS、ICNS、ICO/CUR、XPM、SGI、Sun Raster、DICOM、PSB、MIFF、MNG、APNG、OpenEXR、QOI、WBMP、PBM/PGM/PPM/PNM/PAM、TGA、PSD、Radiance HDR、PIC 和 XBM；相机 RAW 另覆盖 DNG/TIFF-CFA、CR3、RAF、X3F、CRW 和 MRW 的已识别子集。

动画 WebP、多个 TIFF IFD、ICO/CUR/ICNS 中受支持的图像项可展开为页面。单图、非递归图像目录、CBZ/CBR/CB7 可共享页面解码路线。

下表列出关键子集；未列出的 codec 特性不应推定为受支持。

## 解析器归属

标签描述格式结构由谁解析。自研解析器可以调用通用编解码库处理压缩数据；例如 PNG 的块、校验和、滤波、调色板和 Adam7 扫描均由项目代码解析，zlib 只负责解压 zlib/DEFLATE 数据流。

| 格式路线 | 标签 | 解析实现 |
|---|---|---|
| PNG 静态图像及 PNG 默认图像 | 自研 | `png_decoder.c` 负责 chunk 顺序与 CRC、色彩类型和透明度、扫描线滤波、子字节/16 位样本及 Adam7；zlib 负责压缩数据解码。 |
| BMP 文件和 PAGE 内嵌 BMP | 自研 | `bmp_decoder.c` 解析 CORE、INFO、V2、V3、V4、V5 DIB 头、调色板、行对齐和 RGB/位域像素；支持 BI_RGB、BI_BITFIELDS、BI_ALPHABITFIELDS，alpha 合成白底。RLE、JPEG/PNG 压缩 BMP 与色彩配置文件暂不支持。 |
| TGA | 自研 | `tga_codec.c` 解析头部、颜色表、方向和原始/RLE 像素包；支持索引色、灰度、15/16/24/32 位真彩色及 16/32 位 alpha。交错扫描和 TGA 2.0 附加元数据不处理，透明像素合成白底。 |
| GIF87a/GIF89a | 自研 | `gif_codec.c` 解析逻辑屏幕、全局/局部色表、图形控制扩展、图像描述符和 LZW 子块；输出首帧，支持交错和透明索引。动画后续帧及纯文本扩展不处理。 |
| JPEG（基线/渐进式 DCT） | 自研 | `jpeg_parser.c` 解析 marker、段长度、量化/霍夫曼表、帧与扫描头、熵数据转义和重启标记；随后由 stb 解码为像素。支持 8 位单/三/四分量帧，算术编码、无损与其它 SOF 模式不支持。 |
| WebP（静态/动画容器） | 自研 | `webp_parser.c` 解析 RIFF 长度、VP8X 特性标记、图像/帧 chunk 边界、尺寸和动画帧区域；libwebp 负责 VP8/VP8L 像素解码。 |
| JPEG XL | 自研 | `jxl_parser.c` 解析裸 codestream 标记，或校验 JXL signature/ftyp 与 `jxlc`/`jxlp` box 序列；libjxl 负责 codestream 解码。 |
| AVIF、HEIC/HEIF | 自研 | `heif_parser.c` 解析 ftyp 品牌、ISO BMFF box 边界及 meta 中 hdlr/pitm/iloc/iinf/iprp/ipco/ipma/ispe；libavif/libheif 负责图像解码。 |
| 相机 RAW | 自研 | `raw_parser.c` 校验 TIFF/BigTIFF 的 DNG/CFA 标记和 IFD/SubIFD 边界、CR3 的 BMFF box 序列，以及 RAF、X3F、CRW、MRW 的文件签名和最小头长；`raw_codec.c` 将 LibRaw 限定为 RAW 解包、去马赛克和像素输出后端。 |
| PSD/PSB | 自研 | `psb_codec.c` 共享解析 PSD v1 与 PSB v2 的复合图像头、通道平面及 raw/PackBits 行数据；仅支持 8 位 RGB、可选 alpha 合成白底。图层和元数据不读取。 |
| Radiance HDR/RGBE | 自研 | `hdr_codec.c` 解析 Radiance 头、FORMAT、分辨率轴顺序、raw/旧式重复像素和新式逐通道 RLE；输出时按 2.2 gamma 转成 8 位 RGB。XYZE、曝光和色彩校正元数据不应用。 |
| Softimage PIC | 自研 | `pic_codec.c` 单独解析头部、通道包、8 位样本及 raw/pure RLE/mixed RLE；输出 RGB24，alpha 合成白底。 |
| ICO/CUR、ICNS、MNG、PAGE 中嵌入的 PNG | 自研 | 容器保留各自格式解析器；ICNS 条目校验和页面解码统一使用项目的 PNG 解析器。 |
| RAR4/RAR5 / CBR | 自研 | `rar4_parser.c`、`rar5_parser.c` 自研校验归档头、文件头、文件名和压缩数据范围，并提供版本、solid 标记、展开大小及可用的条目 CRC；`rar4_filename_parser.c` 自研解码 RAR4 压缩 Unicode 文件名。`comic_rar_format.c` 只收集解析后的条目和图像页；`comic_rar_decoder.c` 负责 solid 前置条目选择、展开大小/CRC/资源限制及 spool。method 0 直接提取并校验；RAR 压缩数据交给 7-Zip 的 RAR1/2/3/5 raw codec，codec 只接收解析器确定的单个压缩数据范围，不读取或解析归档头。RAR5 当前接受 method 1、Huffman 版本 0/1 且字典不超过单成员资源上限；RAR4 压缩版本受 40 版上限约束。加密、多卷和未支持的压缩变体仍会失败。 |

| 格式 | 可读取的主要子集 | 常见转换影响 |
|---|---|---|
| TIFF | Classic TIFF/BigTIFF 顶层 IFD 与 strip；无压缩、PackBits、LZW、Deflate、Group 4 和受限 JPEG strip。 | 不支持 tiled、planar separate、Group 3/RLE、有符号/浮点数据或 ICC/色度学转换；页面输出按 IFD 顺序。 |
| JPEG 2000 | JP2 和裸 J2K；部分灰度、sRGB、SYCC、EYCC、CMYK 组件布局。 | 转为 8 位 Gray/RGB；alpha 合成白底，不保留 ICC 或源元数据。 |
| PCX、PFM、DDS | PCX 的受支持索引/平面模式；PF/Pf 浮点灰度或 RGB；DDS BC1/DXT1 首层。 | PFM 浮点量化到 8 位，不做显示 gamma；DDS 不支持其它压缩格式、mipmap 或 volume。 |
| XPM、XBM、WBMP | 受支持的 C-source 图像数组及黑白子集。 | 不支持 XPM2 或命名 X11 颜色；WBMP/XBM 写出可能按亮度阈值量化。 |
| SGI、Sun Raster | SGI 8 位通道 raw/行 RLE；Sun Raster 未压缩 24 位 RGB。 | 按源方向整理页面；alpha 合成白底。 |
| DICOM | Part 10 显式 VR little-endian，单帧未压缩、无符号 8/16 位 MONOCHROME1/2 或 RGB。 | 不支持压缩、多帧、signed、palette/YBR、modality rescale 或 VOI/window；元数据不保留。 |
| PSD/PSB、MIFF | PSD/PSB 受限 RGB 合成图；MIFF 无压缩 DirectClass RGB/sRGB。 | 不读取图层、profile 或大部分元数据；PSB 不支持多种位深/颜色模式。 |
| MNG、APNG | MNG 单个静态 PNG datastream；APNG 默认图像帧。 | 不处理动画控制操作、后续帧或源时序。 |
| OpenEXR | 单 part、递增 Y 扫描线、32 位 float RGB 的 raw/有限 ZIP raw fallback。 | 不支持 HALF/UINT、alpha、tile、多 part/deep 或一般压缩块；线性值直接量化到 8 位，不做显示 gamma。 |
| ICO/CUR、ICNS | ICO/CUR 的 PNG 和受限 BI_RGB DIB；ICNS 的 PNG-backed chunks。 | ICO/CUR 最大 256×256；CUR 热点与元数据不保留；ICNS legacy/raw chunks 不读。 |

图像像素通常最多 2,000 万；各格式还可能有更严格的维度、通道、帧数、压缩方法和字节数限制。多数路线将透明区域合成到白底，重编码时不保留 EXIF、ICC 等元数据。

## 图像输出

单页 Gray8/RGB24 页面可写出 PNG、JPEG、BMP、TIFF、WebP、GIF、APNG、MNG、PSD/PSB、JP2、DDS、PFM、QOI、WBMP、PPM/PAM、XBM、ICO/CUR、TGA、PCX、Sun Raster、SGI、XPM、MIFF 和 ICNS；AVIF、JPEG XL、HEIC/HEIF 等也有受限写入路线。

输出能力按 writer 的具体约束执行：

- JPEG 为有损编码；已有 JPEG 压缩页面在兼容路径下可直接复制。
- DDS 输出单级、无透明通道的 BC1/DXT1。
- APNG 最多 1,000 帧、总计最多 2,000 万像素，帧尺寸与类型须一致；输出使用固定帧时长。
- GIF 输出当前为单帧 3-3-2 调色板。
- ICO/CUR 为不透明单项；CUR 热点固定为原点。
- ICNS 写出与正方形页面尺寸匹配的单个 PNG-backed 图标块，不生成多尺寸图标套件。
- PSB/PSD 为扁平化 8 位 RGB 合成图，不保留图层。
- PFM 写归一化 float32；HDR 写 RGBE，但从 8 位输入不能恢复源 HDR 动态范围。
- AVIF/HEIC 为单图有损路线；JPEG XL 为单帧 Gray/RGB lossless 路线。

## 矢量与打印图形

| 格式 | 能力 | 边界 |
|---|---|---|
| SVG/SVGZ | 自研 SVG 子集解析和栅格化；SVGZ 先用通用 gzip 解码。支持的图形输出为 PDF/图像；单页图像也可封装为 SVG data URI，支持 gzip 输出。 | 仅支持自研解析器覆盖的基础图形和路径；其它 SVG 特性返回不支持。渲染按文档单位 2×；最多 32 MiB 输入、2,000 万像素和 128 MiB SVG 输出。透明区域白底合成，不保留矢量结构、链接、动画和元数据；SVGZ 拒绝多成员和尾随数据。 |
| EPS/PS | EPS/PS 转 PDF；PDF 可写为 EPS 或 PS。 | EPS 按 bounding box 裁切，EPS 输出限单页；字体、颜色和矢量语义可能变化。 |
| legacy PostScript AI | 仅识别带 Illustrator Creator 标记的旧式 PostScript AI，再走 PS 到 PDF 路线。 | 不覆盖现代 AI/PDF 变体。 |

## 漫画与归档

| 输入/输出 | 能力 | 边界 |
|---|---|---|
| CBZ | 读取 ZIP 图像成员，按自然数顺序逐页解压、渲染；支持 Stored/Deflate、ZIP64、CRC 和传统 ZipCrypto。 | WinZip AES 和其它压缩方法不支持。 |
| CBR/RAR/RAR5 | 项目解析器确定条目范围、顺序及 solid 依赖；单成员的压缩数据交给 7-Zip RAR raw codec 解码，输出按声明大小和可用 CRC 校验。RAR archive reader 不参与解析或解码。 | RAR 加密、分卷、未支持扩展、RAR5 method/Huffman 变体及超出单成员字典资源上限的条目不支持。 |
| CB7/7z | 自研解析头部、文件项和数据流；支持单 packed stream、单 folder、线性 coder chain，以及 Copy、LZMA/LZMA2、Delta 和常见 BCJ filter；Deflate 支持单独编码器 stream。Solid folder 可按子流拆分文件。 | 不支持加密、密码、PPMd、BZip2、Deflate 与其他 coder 混链、多 folder、多 packed stream、AdditionalStreamsInfo 或外置文件名。 |
| CBT/USTAR | 自研 USTAR reader 校验头、校验和与条目边界，支持八进制/base-256 size、prefix、GNU longname 和 PAX path/size；图像内容继续交给通用图像 codec；也可将页面写成带校验和与块对齐的 CBT。 | 归档成员数、单成员及总展开大小受限；GNU/PAX 扩展数据最多 1 MiB；稀疏 TAR 项不支持。 |
| 图像目录 | 非递归读取目录中的支持格式，按自然数顺序输出页面；可混合 PAGE 文件。 | PDF/DjVu payload 会逐页展开，PDF 页面按 144 DPI 栅格化；各图像遵循本页所列 codec 限制。 |

归档图片成员的识别依赖条目名称和扩展名。页面输出通常不保留原条目名、归档压缩方式或源元数据。
