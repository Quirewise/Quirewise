# LZMA/XZ 自写解码器设计

> 状态：L1 待开工。目标：删除 `compression/src/internal/lzma_sdk`（31 文件 /
> 12,722 行），用第一方 LZMA/LZMA2/XZ 解码器替换。

## 1. 现状

- 编译进 Compression 的 SDK 单元：`LzmaDec`、`Lzma2Dec`、`XzDec`、`Xz`、
  `Bra`/`Bra86`/`BraIA64`、`Delta`、`7zCrc`、`7zCrcOpt`、`XzCrc64`、`XzCrc64Opt`、
  `Sha256`、`Sha256Opt`、`Alloc`、`CpuArch`，由 `src/internal/lzma_sdk_allocator.c`
  与 `src/xz.c` 适配。
- 公共 API 不变：`qw_compression` 的 XZ 与 7z 入口（方法号常量
  `QW_COMPRESSION_7Z_LZMA1_METHOD = 0x030101`、`LZMA2 = 0x21`、`DELTA = 0x03`、
  `X86 = 0x03030103`、`POWERPC = 0x03030205`、`IA64 = 0x03030401`、
  `ARM = 0x03030501`、`ARMTHUMB = 0x03030701`、`SPARC = 0x03030805`）。
- 调用方：Archive（7z/zip 内嵌方法）、Audio（KGM 的 XZ 密钥资源）、
  Document（PDF Flate 之外无 LZMA，但安装包依赖链存在）。

## 2. 目标结构

```
compression/src/internal/lzma/
  lzma_range.c       区间解码器（LZMA 概率模型、bit tree、长度/距离/对齐）
  lzma_dec.c         LZMA1 状态机（literal/match/rep/length/distance 解码）
  lzma2_dec.c        LZMA2 chunk 容器（未压缩块、重置、属性切换）
  xz_dec.c           XZ 容器：stream header/footer、block header、index、边界校验
  xz_filter.c        Delta 与 BCJ（x86/ARM/ARM64/PPC/SPARC/IA64）
  checksums.c        CRC32（复用现有实现）、CRC64、SHA-256
  sevenz_dec.c       7z coder 链编排（方法与属性 -> 过滤器）
```

预估 3,000–3,800 行；公共头与包名不变。Compression 不新增外部依赖：
CRC64/SHA-256 在该包内部实现（与 Crypto 的同名算法各自独立、共享测试向量）。

## 3. 里程碑

| 里程碑 | 内容 | 门禁 | 预估 |
|---|---|---|---|
| **L1 LZMA1** | 区间解码、概率模型、literal/match/rep、属性解析 | 现有 `.lzma`/7z LZMA1 夹具输出与 SDK 逐字节相等 | 3 人日 |
| **L2 LZMA2 + 7z 链** | chunk 状态、方法链、Delta/BCJ 过滤 | 7z 归档（含过滤链）输出逐字节相等 | 2–3 人日 |
| **L3 XZ 容器** | stream/block/index/footer、CRC32/CRC64/SHA-256、多块 | XZ 语料逐字节相等；损坏输入稳定报错 | 2–3 人日 |
| **L4 删除 SDK** | 移除 lzma_sdk 目录与适配文件；fuzz/ASan；门禁白名单删除 31 条 | 四套矩阵全绿 | 1–2 人日 |

## 4. 测试与差分

- **差分基线（替换前）**：用当前 SDK 解码语料并记录 SHA-256：
  - 单块/多块 XZ，CRC32/CRC64/SHA-256/None 四种校验；
  - Delta、x86、ARM、ARM64、PPC、SPARC、IA64 过滤链及组合；
  - 7z 内嵌 LZMA1/LZMA2/Delta/BCJ；
  - KGM 的 XZ 密钥资源与截断/损坏变体。
- **定向错误**：坏头、截断、非法属性、超限输出、字典过大、
  速率/内存上限 → 现有错误码与 `UNSUPPORTED` 分类不变。
- **模糊测试**：新增 `compression_lzma_fuzz`（固定种子），ASan/UBSan/LSan 0 诊断。
- **性能**：典型 8:1 压缩语料解码 ≤ 现实现 1.5×。

## 5. 兼容性与非目标

- 保持方法号、属性编码与 7z coder 链语义；调用方无需改动。
- 只做解码（现有压缩侧同样只提供解码），不实现 LZMA/XZ 编码。
- 不引入 `liblzma`/`xz` 命令行或系统库；测试语料为已提交的二进制。
- BCJ 覆盖以现 SDK 编译进包的范围为准（x86、ARM、ARMThumb、PPC、SPARC、IA64；
  ARM64 视语料需要补充）。
