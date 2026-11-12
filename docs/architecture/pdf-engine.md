# PDF 引擎架构

> 状态：单一引擎（2026-11-08 完成收敛）。本文记录最终边界与已完成的迁移。

## 最终结构

Quirewise 只有一个 PDF 解析引擎：

| 包 | 职责 | 公共头 |
|---|---|---|
| `quirewise-document` | xref（经典/流/hybrid/增量）、ObjStm、Flate+预测器、RC4/AES-128/AES-256 解密、页树与页面盒、文本抽取（ToUnicode）、栅格化、合并、结构只读查询 | `quirewise/pdf.h`、`quirewise/document.h` |
| `quirewise-page` | 页面容器格式：DjVu、UVZ、CAJ、CEB（解密为 PDF 字节，不解析 PDF 内容） | `quirewise/ceb.h`、`quirewise/djvu.h`、`quirewise/uvz_parser.h`、`quirewise/caj.h` |

容器层拿到的 PDF 字节交给 `quirewise-document` 的公共 API 处理，不再有第二套
xref/ObjStm/页码解析器。

## 已完成的收敛步骤

1. **阶段 0**：document 新增
   - `qw_pdf_open_structure()`：未知口令的加密 PDF 也可打开，页数/页面盒可读，
     文本抽取与栅格化返回稳定 `UNSUPPORTED`；
   - `qw_pdf_page_geometry()`：`/MediaBox`、`/CropBox`、`/Rotate`，畸形盒回退
     US Letter，角度归一化。
2. **阶段 1**：
   - 外部消费者迁移到上述入口；
   - 删除 `quirewise-page` 的 `src/pdf/`（结构解析器与未再使用的 Flate 解码）
     与 `include/quirewise/pdf_parser.h`；
   - 删除 page 的 PDF tolerant 测试，模糊测试保留 DjVu/CAJ/UVZ 部分。

## 行为说明

- 加密：document 支持 V1/V2 RC4、V4 `/AESV2`、V5 `/AESV3`（空用户口令）；
  结构模式下未知口令不影响页数/几何；
- 页面盒：非法 `/MediaBox`/`/CropBox` 回退默认值而不是拒绝整份文档；
- 文本：每个字体优先使用 `/ToUnicode` CMap，缺失时回退 UCS-2/单字节；
- 容器：CEB 解密后的 PDF 由 document 读取，page 不再声称解析 PDF。

## PDG 页内 PDF 载荷

PDG 页（`%pdgz` 容器成员或 UVZ 页）的载荷可能直接是 PDF 文件。PDG 包只识别
并返回该 PDF 字节（`PDG_OUTPUT_PDF`），不解析内容；栅格化由组合层（app 的
page routes）调用本引擎完成，因此仍然只有一个 PDF 引擎：

- `qw_pdf_open` → `qw_pdf_page_geometry` → `qw_pdf_render_page`；
- 页载荷按单页语义处理：只渲染第 1 页，按 300 dpi（与 `PDZ_PDF_DPI` 一致）
  渲染，嵌入 PDF 后保持原始页面尺寸；
- 渲染结果经 PDZ 的 PDF writer 嵌入，页面单位与图片内容流一致；
- `pdg_type 0x1A` 成员保存的是完整的多页发行版 PDF，应按 Route 1 合并而不是
  栅格化；合并尚未实现，容器转换对此保持显式 `UNSUPPORTED`，不静默丢页。

PDG 包本身对 `pdg_render_memory` 的 `PDG_OUTPUT_PDF` 仍返回
`PDG_ERR_EXTERNAL_DECODER_REQUIRED`：包边界不得依赖 document，组合层是唯一
允许同时持有两者的位置。产品路径（CLI 的 PDZ/UVZ 转换）不再需要外部光栅化器。

## 回归与门禁

- document：35 项 CTest（xref/ObjStm/加密/ToUnicode/图像/合并/公开 API）；
- page：3 项 CTest（DjVu 解码、CEB 校验、容器模糊冒烟）；
- 外部消费者 17 项、公共头独立编译、依赖图与边界审计、79 步验收矩阵。

## 非目标

- 不新增 PDF 核心包；
- 不改变 `quirewise/pdf.h` 已发布的函数集合；
- 不引入第三方 PDF 库。
