# 全自写改造总计划（Zero-Vendored）

> 状态：计划生效（2026-11-10）。目标：Quirewise 工作区内不再包含任何第三方实现代码。
> 关联：[DjVu 替换设计](djvu-replacement.md)、[JPEG 替换设计](jpeg-replacement.md)、
> [LZMA/XZ 替换设计](lzma-replacement.md)、[AES 替换设计](aes-replacement.md)。

## 1. 目标与完成定义

**完成定义（全部满足才算完成）：**

- `third_party/`、`vendor/`、`lzma_sdk/` 下的实现文件 **0 个**，非自写行数 **0**；
- SBOM `bundled` 组件由 5 个降为 **0**；许可证清单只剩第一方 MIT；
- 公共 API、包名、CMake 导出、7z 方法号与错误码不变；
- 依赖图仍无环，生产路径仍无外部运行库；
- 四套验收矩阵（含新增 vendored 门禁）全绿，ASan/UBSan 与模糊测试无诊断；
- 代表夹具的解码正确性与性能达标（见第 6 节）；
- 独立复核签字，tag `v0.2.0-rc1` 发布。

**明确不在范围内：**

- 测试素材（pdf.js/ITU 语料、DjVu 参考图）：保留并登记来源，不要求自造；
- 字符集映射表：已由 `libraries/quirewise-charset/tools/generate_charset_tables.py`
  从公开字符集数据生成，保留生成器与数据版本记录；
- 测试夹具与生成数据之外的第三方工具（CMake/Ninja/GCC/Python）属于工具链，不是发布物。

## 2. 现状清单（2026-11-10）

| 组件 | 仓库/路径 | 文件 | 行数 | 实际用途 | 替换方式 |
|---|---|---:|---:|---|---|
| stb_image ×2 | `image/third_party/stb`、`pdg/third_party/stb` | 2 | 15,976 | JPEG 像素解码（结构校验已自写）、TIFF 内嵌 JPEG、PDG 编码页 | 自写 JPEG 解码器（Image） |
| LZMA SDK | `compression/src/internal/lzma_sdk` | 31 | 12,722 | LZMA1/LZMA2/XZ、BCJ/Delta 过滤、CRC64/SHA-256 | 自写 range coder + LZMA/XZ（Compression） |
| djvudec | `page/src/formats/djvu/vendor` | 18 | 9,230 | DjVu IFF/BZZ/JB2/IW44/文本/渲染 | 自写 DjVu 解码器（Page） |
| tiny-AES | `crypto/third_party/aes` | 2 | 674 | AES-128 ECB（NCM 音乐、PDF 解密） | 自写 AES（Crypto） |
| **合计** | | **53** | **38,602** | 已全部归零（2026-11-10） |

> 2026-11-10 进度：DjVu（9,230 行）、tiny-AES（674 行）、stb_image ×2（15,976 行）
> 与 LZMA SDK（12,722 行）已全部替换并删除。**当前非自写实现：0 文件 / 0 行**，
> 门禁白名单已归零。

## 3. 门禁机制

`app/tools/audit_vendored_sources.py` 扫描工作区内 `third_party`、`vendor`、
`lzma_sdk` 目录下的实现文件，与 `app/vendored-allowlist.json` 逐项比对：

- 每条白名单固定 `path`、`sha256`、`lines`；**只减不增**；
- 白名单外出现新文件、白名单条目已不存在、或内容变化 → 门禁失败；
- 替换某组件后删除对应白名单条目，树干净即门禁通过。

接入点：`run_acceptance.py` 的 `gate.vendored-sources` 步骤（矩阵由 80 步变为 81 步）、
`release_self_audit.py`（`EXPECTED_STEPS` 同步）、CI 工作流。

## 4. 工作流与顺序

| 编号 | 工作流 | 写入范围 | 前置 | 预估 |
|---|---|---|---|---:|
| W0 | 门禁、基线、依赖决策 | `app/tools`、`app/vendored-allowlist.json` | — | 2–3 人日 |
| W1 | DjVu 自写 | `libraries/quirewise-page/src/formats/djvu` | W0 | 12–18 人日 |
| W2 | JPEG 自写 | `libraries/quirewise-image/src/formats/image`、`pdg/src/formats/pdg`（调用点） | W0 | 6–8 人日 |
| W3 | LZMA/XZ 自写 | `libraries/quirewise-compression/src/internal/lzma` | W0 | 8–10 人日 |
| W4 | AES 自写 | `libraries/quirewise-crypto/src` | W0 | 1 人日 |
| W5 | 收口与发布 | 全部 + 文档 + 证据 | W1–W4 | 4–6 人日 |

顺序：**W1 优先**；W2/W3/W4 在 DjVu 达到 D2（JB2 完成）后并行启动；
W5 在四条流各自通过后执行。

## 5. 里程碑与工期

| 周 | 主线 | 并行线 | 里程碑 |
|---|---|---|---|
| 1 | W0 → W1-D1（IFF/ZP/BZZ） | — | bitonal 逐字节对齐 |
| 2 | W1-D2（JB2）、D3（IW44 起步） | W4（AES） | multipage 对齐、AES 替换完成 |
| 3 | W1-D3/D4/D5 收口 | W2（JPEG 启动） | DjVu vendor 删除、page 矩阵绿 |
| 4 | W2 收尾 | W3（LZMA 启动） | stb 删除、image 矩阵绿 |
| 5 | W3 收尾 + W5 收口 | — | SDK 删除、四矩阵 81 步、签字、tag |

墙钟约 5 周（3–4 条并行流）；单人串行约 8 周。

## 6. 验证基线

| 工作流 | 正确性判据 | 回归手段 |
|---|---|---|
| DjVu | 与 `tests/data/djvu/*.ref.pgm/ppm` **逐字节一致**；多页顺序与文本一致 | 现有 `djvu_decode_test` + 新增单元测试 + 差分脚本 |
| JPEG | 与替换前 stb 输出比较，像素差 **≤1 LSB**；尺寸/通道/错误码严格一致 | 150 个 image 夹具 + 定向样本 + fuzz |
| LZMA/XZ | 与替换前 SDK 输出**逐字节相等**（单块/多块/过滤链/各校验） | 语料哈希 + 损坏输入 + fuzz |
| AES | FIPS-197 / NIST SP 800-38A 向量一致 | NCM、PDF 解密回归 |
| 全局 | 解码时间 ≤ 现实现 1.5×；内存上限不回退 | 基准脚本 + CTest 超时 |

基线在替换开始前用当前实现固化（哈希/参考图），避免“用新实现自证新实现”。

## 7. 每个工作流的验收清单

1. 源码：目标目录无第三方文件；`git log` 可回溯；新代码通过边界审计（无第三方头/符号）。
2. API：公共头无变化；包配置与导出未变；依赖图无新增外部边。
3. 测试：单元测试 + 差分测试 + 模糊冒烟 + ASan/UBSan 全绿；资源上限与错误分类保持。
4. 文档：包 README、支持矩阵、PROVENANCE 清理说明、SBOM/许可证同步。
5. 发布：四套矩阵 81 步全绿；self-audit PASS；独立复核；tag。

## 8. 风险与回滚

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| DjVu 算术编码/小波实现偏差 | 高 | 高 | 分 D1–D4 四步，每步逐字节对齐；失败即回滚到上一里程碑 |
| XZ 过滤器/校验组合覆盖不足 | 中 | 高 | 语料矩阵 + 与 SDK 逐字节差分 + fuzz |
| JPEG 渐进/CMYK/重启边界 | 中 | 中 | 语料差分 + 定向构造 + 1 LSB 容差 |
| 性能回退 | 中 | 中 | 基准门槛 1.5×；查表与内联优化 |
| 工期超支 | 中 | 中 | W1 可独立交付（容器+JB2+文本）；IW44 可顺延 |

回滚策略：删除工作流白名单条目前，旧实现始终在 git 历史中；每个里程碑单独提交，
可单独 revert。

## 9. 进度记录

| 日期 | 工作流 | 状态 | 证据 |
|---|---|---|---|
| 2026-11-10 | 计划文档（总计划 + 4 份工作流设计） | 完成 | 本文档、`djvu-replacement.md`、`jpeg-replacement.md`、`lzma-replacement.md`、`aes-replacement.md` |
| 2026-11-10 | W0 门禁工具与白名单 | 完成 | `app/tools/audit_vendored_sources.py`、`app/vendored-allowlist.json`（53 文件 / 38,602 行，PASS） |
| 2026-11-10 | W1 D1 容器+ZP+BZZ | 完成 | page `f9f268b`：`djvu_iff/djvu_zp/djvu_bzz` + 2 项新 CTest；`text.djvu` TXTz 解压与替换前基线逐字节一致（66 字节） |
| 2026-11-10 | W1 D2 JB2 | 完成 | page `685ff35`：`djvu_jb2` 记录层、直接/交叉位图编码、符号库与 blit；`bitonal.djvu` 渲染与 `bitonal.ref.pgm` 逐字节一致，page 测试 7/7 |
| 2026-11-10 | W1 D3 IW44 | 完成（灰阶） | page `7a45cc3`：`djvu_iw44` 小波/桶解码/渐进层；`photo.djvu` 与 `photo.ref.ppm` 逐字节一致，page 测试 8/8；彩色路径待语料 |
| 2026-11-10 | W1 D4/D5 集成与移除 vendor | 完成 | page `b1f9605`：`djvu_doc` 页面层 + `djvu_api.c` 切换第一方实现；`vendor/` 18 文件删除；门禁白名单 53→35 条（29,372 行） |
| 2026-11-10 | W0 门禁接入验收矩阵 | 完成 | `run_acceptance.py` 新增 `gate.vendored-sources`（第 81 步）；`release_self_audit.py` `EXPECTED_STEPS=81`；报告闸门表新增一行 |
| 2026-11-10 | W4 AES 自写 | 完成 | crypto：自写 AES-128（密钥扩展/加解密/ECB），删除 tiny-AES；known-answer 测试通过；白名单 35→33 条（28,698 行） |
| 2026-11-10 | W2 JPEG 自写 | 完成 | image/pdg：jpeg_decoder.c（baseline/progressive、IDCT、上采样、YCbCr/RGB）接入三处调用；删除 stb_image ×2；image 测试 12/12；白名单 33→31 条（12,722 行） |
| 2026-11-10 | W3 LZMA/XZ 自写 | 完成 | compression 345649c 后：internal/lzma.c（LZMA1/LZMA2、概率模型、距离槽）+ internal/xz_dec.c（容器/index/footer、Delta/BCJ、CRC32/CRC64/SHA-256）；9 组 xz 差分（none/crc32/crc64/sha256、preset 0/6/9、delta、x86）全通过；白名单 0 条（0 行） |
| 待办 | Phase 5 发布收尾（矩阵重跑、SBOM/锁/报告、独立评审、tag） | 下一步 | — |
