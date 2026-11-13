# 图像、矢量图与归档

> 状态（2026-11-14）：本页按当前实现重写。旧版本描述的是迁移前的产品（stb_image、libwebp、
> libjxl、libavif、LibRaw、7-Zip SDK 等外部后端），这些路线已全部移除或从未进入发布包。
> 当前发布包只有第一方实现，未实现的入口稳定返回 `UNSUPPORTED`。

## 1. 图像输入

`quirewise-image` 通过内容探测（`qw_image_probe`）识别并解码以下格式：

JPEG（基线/渐进式）、PNG（含 APNG/MNG 默认帧）、GIF87a/89a（首帧）、BMP、TIFF（顶层 IFD）、
WebP（VP8/VP8L/Alpha/动画帧）、JP2/J2K、PSD/PSB（扁平合成图）、OpenEXR（单 part 扫描线）、
Radiance HDR、Softimage PIC、TGA、PCX、PFM、DDS（BC1/DXT1 首层）、QOI、XPM/XBM/WBMP、
PBM/PGM/PPM/PNM/PAM、ICO/CUR、ICNS、SGI、Sun Raster、MIFF、DICOM（单帧未压缩）、XCF。

GIF/WebP/TIFF/ICO/CUR/ICNS 的多帧/多条目可在库层展开为多页；CLI 目前只取单页转 PDF。

明确不支持（探测可能成功，解码返回 `UNSUPPORTED`）：AVIF、HEIC/HEIF、JPEG XL、PCD、
相机 RAW（DNG/TIFF-CFA、CR3、RAF、X3F、CRW、MRW）。发布包不含去马赛克实现，也不链接
LibRaw。

## 2. 编解码实现归属

| 路线 | 解析/解码 | 说明 |
|---|---|---|
| PNG | 第一方 | 块顺序、CRC、色彩类型、滤波、Adam7、16 位样本 |
| JPEG | 第一方 | marker/段/霍夫曼表/帧与扫描头/熵数据；8 位单/三/四分量，基线+渐进式 |
| WebP | 第一方 | RIFF/VP8X/VP8/VP8L/ALPH/ANIM/ANMF，静态与动画帧 |
| JP2/J2K | 第一方 | 容器、packet、tier-1、DWT、MQ、灰度/sRGB/SYCC/CMYK 子集 |
| TIFF | 第一方 | Classic/BigTIFF、strip、PackBits/LZW/Deflate/G4/受限 JPEG strip |
| GIF/BMP/TGA/PSD/EXR/HDR/PNM/QOI/PCX/DDS/XPM/SGI/RAS/MIFF/DCM | 第一方 | 各自子集见测试与头文件 |
| RAW / AVIF / HEIC / JXL / PCD | 无解码器 | 仅探测，解码返回 `UNSUPPORTED` |
| 归档解压（ZIP/7z/XZ/LZMA） | 第一方 `quirewise-compression` | 不链接 Zlib/LibLZMA/7-Zip |

所有解码器受统一资源限制约束（像素、维度、帧数、字节数）；超限返回 `RESOURCE_LIMIT`。

## 3. 图像输出

发布包**没有公开的图像编码接口**。`quirewise-image` 的公共 API 只有探测、格式名和
解码；`document` 包内置的 PNG 编码器只服务于 "PDF → 单页 PNG" 这一个 CLI 路线
（144 dpi，首页）。

历史文档中"可写出 PNG、JPEG、BMP、TIFF、WebP、GIF、APNG、MNG、PSD/PSB、JP2、DDS、
PFM、QOI、WBMP、PPM/PAM、XBM、ICO/CUR、TGA、PCX、Sun Raster、SGI、XPM、MIFF、ICNS、
AVIF/HEIC/JXL"的列表与当前 API 不符；这些写出器不在发布范围内。

## 4. 矢量与打印图形

| 格式 | 能力 | 边界 |
|---|---|---|
| SVG/SVGZ | 第一方子集解析与 RGBA8 栅格化（文档单位 2×）；SVGZ 先解 gzip | 仅覆盖自研解析器的图形/路径子集；透明区域白底合成，不保留矢量结构、链接、动画、元数据 |
| EPS / PS / legacy AI | 无实现 | 历史文档声称的 PDF 互转已不在发布包内 |
| EMF/WMF/CGM/CDR/VSD/FODG | 无实现 | 未进入发布包 |

SVG/SVGZ 已接入 CLI：`.svg/.svgz` 可用 `--to pdf`（以及 `--check`）栅格化为单页 PDF；`--page image|a4` 控制页面框。仅支持自研子集，含 `<text>` 等未支持特性时返回 `UNSUPPORTED`。

## 5. 漫画与归档

| 输入/输出 | 能力 | 边界 |
|---|---|---|
| CBZ | 自研 ZIP reader 读取图像成员，按自然数顺序逐页；支持 Stored/Deflate、ZIP64、CRC 和传统 ZipCrypto | WinZip AES 等加密方法不支持 |
| CBT | 自研 USTAR reader（GNU longname/PAX path）；内容交给图像解码器 | 稀疏 TAR、超大展开不支持 |
| CBR/RAR | 归档包只解析 RAR4/RAR5 头与条目元数据，**不解压**；comic 路由只接受 ZIP/USTAR | 因此 CBR 在发布包内不可用 |
| CB7/7z | `quirewise-archive` 提供 7z 头解析与受限解包（Copy/LZMA/LZMA2/Delta/BCJ） | comic 路由未接 7z；加密、PPMd、BZip2、多 folder 不支持 |
| 图像目录 | `quirewise-image` 可非递归枚举支持格式的目录 | CLI 没有目录输入 |

归档成员按"文件名 + 支持格式"筛选；页面输出不保留条目名、压缩方式或源元数据。
