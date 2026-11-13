# PDF 与页面格式

> 状态（2026-11-14）：统一 `quirewise` CLI 已移植（C1–C3 范围），本页按当前代码更正
> 旧版本"CLI 尚未移植 / PDG→PDF 必须外部解码器"的描述。

## 输入

- PDF：xref 表/xref 流/hybrid、`/Type /ObjStm` 对象流；RC4（V1/V2）、AES-128（V4 `/AESV2`）
  与 AES-256（V5/R5–R6 `/AESV3`）加密文档在**用户口令为空**时可打开，其他 security handler
  返回稳定的 `UNSUPPORTED`。
- 页面容器：UVZ / PDZ / CAJ / CEB 由 `quirewise-page` / `quirewise-pdg` 解析；CAJ 的 JP2
  负载经内部 Image 解码；CEB 解密后输出 PDF。
- DjVu：`quirewise-page` 内部解码 BZZ、JB2、IW44、DJVM/DIRM bundled 多页与文本层。
- PDG/PDZ：由 `quirewise-pdg` 解码、解密和渲染。页载荷本身是 PDF 的成员由
  `quirewise-pdg` 返回 `PDG_ERR_EXTERNAL_DECODER_REQUIRED`（库不依赖文档 PDF 引擎）；
  组合层（app 的 page_routes）调用 Document 引擎按 300 dpi 栅格化，并按成员顺序合并
  `pdg_type 0x1A` 发行版 PDF。加密的 0x1A 成员仍会显式失败。

## 输出

- PDF：透传、合并、从 HTML/Office/演示/电子书布局生成（`quirewise-document`）。
- 页面图像：RGB24/Gray8 栅格化。PDF 栅格化会用量化的内置 3×5 近似字体绘制文字，
  并通过 `report.note` 说明 "text uses a built-in approximation font"；复杂变换、
  未支持的绘制操作会在 note 中报告，不静默伪装成功。
- 文本：PDF 文本提取为 UTF-8；DjVu 文本层提取；CAD `--to txt` 输出图纸文本清单。

## 限制

- PDF/A 需要外部 Ghostscript/veraPDF，不属于本发布包范围。
- 精确字形栅格化（当前用内置近似字体）和对象流作为输出格式属于后续项。
- 有用户口令的加密 PDF 不支持；加密文档的合并会被拒绝。
- JBIG2 仅覆盖 generic region（MMR/T.88 算术）、symbol dictionary 与 text region 子集；
  Huffman 字典、refinement、halftone、pattern dictionary、转置 text region 返回
  `UNSUPPORTED`。
- 所有尺寸、DPI、页数、输出字节数都有上限；超限返回 `RESOURCE_LIMIT`。

逐项支持矩阵见 [格式能力总览](support-matrix.md)。
