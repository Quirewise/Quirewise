# JPEG 自写解码器设计

> 状态：J1 待开工。目标：删除 `image/third_party/stb` 与 `pdg/third_party/stb`
> （共 2 文件 / 15,976 行），用第一方 JPEG 解码器替换。

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
