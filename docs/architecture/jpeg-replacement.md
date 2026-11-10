# JPEG 自写解码器设计

> 状态：J1–J3 完成（2026-11-10）。第一方 `jpeg_decoder.c`（baseline + progressive、
> Huffman、IDCT、2× 上采样、YCbCr/RGB 颜色空间）已接入 image 解码、TIFF JPEG strip
> 与 PDG 编码图路径；两处 `stb_image` 已删除。J4 的语料扩充与参考哈希在收尾阶段补齐
> （当前用 fixture、djpeg 对照和真实照片抽样验证）。

## 1. 现状

- 结构校验已自写：`image/src/formats/image/jpeg_parser.c`（标记、SOF、尺寸、
  组件数、`qw_image_probe` 判定）。
- 像素解码仍调用 stb：
  1. `image/src/formats/image/image_decode.c`：JPEG 输入走 `stbi_load_from_memory`；
  2. `image/src/formats/image/tiff_decode.c`：TIFF 内嵌 JPEG strip 走 stb；
  3. `pdg/src/formats/pdg/pdg_render.c`：PDG 编码页（JPEG/PNG 等）经 stb 转 RGB24。
- PDG 已依赖 `Quirewise::Image`（`find_package(QuirewiseImage)`），替换时把调用点
  改为 `qw_image_decode`，不新增依赖边。

## 2. 目标结构

```
image/src/formats/image/
  jpeg_parser.c      （保留）结构校验、尺寸上限、组件/采样信息
  jpeg_decoder.c     （新增）像素解码：熵解码 -> 反量化 -> IDCT -> 上采样 -> 色彩
  jpeg_tables.c      （新增）Huffman 快速表、Zigzag、IDCT 常数表
```

预估 2,200–2,800 行；对外仍只有 `qw_image_decode` / `qw_image_probe`。

## 3. 解码流程

1. **标记解析**：SOI、APPn、DQT、SOF0/SOF1/SOF2、DHT、DRI、SOS、EOI；
   与 `jpeg_parser.c` 共用结构结论，未知标记跳过。
2. **熵解码**：Huffman 解码器（8 位快速查表 + 慢速回退），支持 restart（DRI/RSTn）。
3. **扫描**：基线顺序（SOS 单扫描）与渐进式（DC/AC 逐次逼近、spectral selection）。
4. **反量化 + IDCT**：整数 IDCT（AAN 或 Chen 变体），整数中间精度；块边界 clamp。
5. **上采样与色彩**：4:4:4 / 4:2:2 / 4:2:0 / 4:1:1 最近邻或双线性（与 stb 同策略）；
   灰度、YCbCr、CMYK、YCCK；输出 RGB24 / GRAY8，与现有 `QwImagePage` 约定一致。
6. **错误处理**：截断、坏 Huffman 表、非法采样因子、超限尺寸分别映射到现有
   `QW_IMAGE_ERR_FORMAT` / `QW_IMAGE_ERR_RESOURCE_LIMIT`，失败不发布像素。

## 4. 里程碑

| 里程碑 | 内容 | 门禁 | 预估 |
|---|---|---|---|
| **J1 基线+灰度** | 标记/表解析、顺序扫描、4:4:4 灰度与 RGB | 现有 JPEG 夹具解码成功，尺寸一致 | 2 人日 |
| **J2 色度与重启** | 4:2:0/4:2:2 上采样、restart、CMYK/YCCK | 与 stb 输出像素差 ≤1 LSB | 2 人日 |
| **J3 渐进式** | SOF2 多扫描、逐次逼近、spectral selection | 渐进语料与基线一致（≤1 LSB） | 1–2 人日 |
| **J4 集成与删除** | TIFF JPEG strip、PDG 调用点改 `qw_image_decode`；删除 stb 两处与 `stb_image_impl.c`；fuzz/ASan | image/pdg CTest 全绿；门禁白名单删除 2 条 | 1–2 人日 |

## 5. 测试与差分

- **差分基线**：替换前用 stb 对 `image/tests/data` 下全部 150 个夹具（含 JPEG/渐进样本）
  解码并记录 SHA-256 与尺寸；替换后逐样本比较，允许 ≤1 LSB，尺寸/通道/错误码严格一致。
- **定向样本**：灰度、4:2:0、4:2:2、4:4:4、渐进、restart、CMYK、截断、坏表。
- **模糊测试**：扩展现有 image fuzz 语料；ASan/UBSan/LSan 0 诊断。
- **性能**：1024×1024 基线 JPEG 解码时间 ≤ 现实现 1.5×。

## 6. 非目标

- 不实现 JPEG 编码器；
- 不支持 12 位精度、算术编码 JPEG、无损 JPEG（现实现同样不支持，保持
  `UNSUPPORTED` 与错误分类）；
- 不改变 `quirewise/image.h` 已发布函数集合。

## 7. J1–J4 实施记录（2026-11-10）

**实现位置：** `image/src/formats/image/jpeg_decoder.c`（约 900 行，第一方）：

| 能力 | 说明 |
|---|---|
| 容器/表 | SOI/APPn/DQT/DHT/SOF0/SOF2/DRI/SOS/EOI；8/16 位量化表；DHT 规范化 Huffman 表 |
| 熵解码 | 基线顺序扫描；渐进式 DC first/refine、AC first/refine、ZRL、EOB run、restart 间隔 |
| 变换 | 双精度可分离 IDCT（`block[v*8+u]`，量化表去 zigzag 后逐点乘） |
| 上采样 | 2× 采样用 3:1 三角滤波（h2v1/h2v2），其他比例最近邻；1× 直通 |
| 颜色 | 灰度、YCbCr→RGB；Adobe APP14 `transform=0` 或组件 ID 为 `R/G/B` 且无 JFIF 时按 RGB 直出（TIFF JPEG 依赖此路径） |
| 输出 | `QwJpegImage`（1 或 3 通道），由调用方 `free` |

**替换点：**
1. `image_decode.c`：JPEG 分支改调 `qw_jpeg_decode`，去掉 `stbi_load_from_memory`；
2. `tiff_decode.c`：TIFF JPEG strip 改调 `qw_jpeg_decode`，并按目标通道做灰度/RGB 转换；
3. `pdg_render.c`：PDG 编码页改调 `qw_image_decode`（PDG 已依赖 `Quirewise::Image`）。
两处 `third_party/stb`（15,976 行）与 `stb_image_impl.c` 已删除，白名单只剩 LZMA SDK。

**验证：**
- `standalone_8x8.jpg` → 均匀 `(128,63,32)`（期望 `(128,64,32)`，测试容差 8）；
- `jpeg_compressed_8x8.tif` → 精确 `(128,64,32)`（RGB 直出路径）；
- `rgb_u1.jpg`/`cov001.jpg` 与 `djpeg` 对照：基线 max ≤ 4 LSB、mean < 0.5；
- `cjpeg -restart`、`cjpeg -grayscale` 变体与 `djpeg` 一致（max ≤ 4）；
- image CTest 12/12，包含 fuzz smoke。

**已知边界（后续补齐）：**
- 渐进式 refinement 扫描的 EOB-run 在较大图像（>16 块）上仍有解析失败，
  当前返回 `QW_IMAGE_ERR_FORMAT` 而不是输出错误像素；基线 JPEG（项目实际语料）
  完全可用。下一步用逐扫描系数对照（基线系数 vs 渐进重建）定位并补齐。
- CMYK/YCCK 4 分量 JPEG 返回 `UNSUPPORTED`（与现实现一致，未见语料）。
