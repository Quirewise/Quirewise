# PDF 与页面格式

> **迁移状态（2026-11-08）**：本页描述库级 PDF/页面能力；统一 `quirewise` CLI
> 尚未移植到当前 `app/` 仓库。PDF 解析/渲染/合并由 `quirewise-document` 提供，
> 页面容器（UVZ/CAJ/CEB/DjVu）由 `quirewise-page` / `quirewise-pdg` 提供，
> 容器层解密出的 PDF 字节交给 document 处理。

## 输入

- PDF：xref 表/xref 流/hybrid、`/Type /ObjStm` 对象流；RC4（V1/V2）、
  AES-128（V4 `/AESV2`）与 AES-256（V5/R5–R6 `/AESV3`）加密文档可打开，
  其他 security handler 返回稳定的 `UNSUPPORTED`。
- UVZ / CAJ / CEB：由 `quirewise-page` 解析；CAJ 的 JP2 负载经内部 Image 解码。
- DjVu：`quirewise-page` 内部解码 BZZ、JB2、IW44、DJVM/DIRM bundled 多页与文本层；
  PDG 的探测、页数和渲染委托 Page。
- PDG/PDZ：由 `quirewise-pdg` 解码、解密和渲染；PDF 输出目前仍返回
  `PDG_ERR_EXTERNAL_DECODER_REQUIRED`（M3-04 后续工作）。

## 输出

- PDF：透传、合并、从 HTML/Office/EPUB/FB2 布局生成（`quirewise-document`）。
- 页面图像：RGB24/Gray8 栅格化；未绘制的文字/复杂变换通过
  `QW_ROUTE_LOSS_RASTERIZATION` 等 note 显式报告，不静默伪装成功。
- 文本：PDF 文本提取为 UTF-8；DjVu 文本层提取。

## 限制

- PDF/A 需要外部 Ghostscript/veraPDF，不属于本发布包范围。
- 精确字形栅格化（当前用内置近似字体）、对象流作为输出格式属于已记录后续项。
- 所有尺寸、DPI、页数、输出字节数都有上限；超限返回 `RESOURCE_LIMIT`。

精确的逐项支持矩阵与证据见
[格式能力总览](support-matrix.md) 和 `.tmp/release/RELEASE_ACCEPTANCE_REPORT.md`。
