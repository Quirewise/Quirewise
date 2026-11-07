# PDF 与页面格式

> **迁移状态（2026-11-07）**：本页描述库级 PDF/页面能力；统一 `quirewise` CLI
> 尚未移植到当前 `app/` 仓库。所有路线由 `quirewise-page` / `quirewise-pdg`
> 提供，并只在 Quirewise 内部实现范围内声明支持。

## 输入

- PDF：经典对象表与 `/Type /ObjStm` 对象流；RC4 加密文档可打开，AES-256 等
  未实现的 security handler 返回稳定的 `UNSUPPORTED`。
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
- 加密 PDF 的 AES-256、文字栅格化、对象流作为输出格式属于已记录后续项。
- 所有尺寸、DPI、页数、输出字节数都有上限；超限返回 `RESOURCE_LIMIT`。

精确的逐项支持矩阵与证据见
[格式能力总览](support-matrix.md) 和 `.tmp/release/RELEASE_ACCEPTANCE_REPORT.md`。
