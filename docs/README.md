# Quirewise 能力文档

> **迁移状态（2026-11-11）**：当前 `app/` 已提供 CLI C1–C3 范围的能力：
> `quirewise INPUT [INPUT ...] [-o FILE] [--to pdf|txt|png] [--check] [--quiet]
> [--out-dir DIR] [--page image|a4] [--pages RULE] [--archive-password TEXT]
> [--audio-track N]`，文件级转换 API 与主要输入路线（文档、图片、页面族、字幕、结构化数据、
> 漫画归档）已接入；未接线项见[命令行使用](usage/command-line.md)与
> [统一 CLI 移植计划](architecture/cli-port-plan.md)。发布包不包含任何外部格式后端。

本文档集说明 Quirewise 可处理的输入、可生成的输出、转换选项和格式边界。

## 按任务查阅

| 任务 | 文档 |
|---|---|
| 快速查看格式输入与输出方向 | [格式能力总览](formats/support-matrix.md) |
| 转换 PDF、扫描页或 PAGE/CONTAINER/UVZ | [PDF 与页面格式](formats/pdf-and-pages.md) |
| 转换 Office、电子书、HTML 或标记文本 | [文档与文本](formats/documents-and-text.md) |
| 转换工作簿、结构化数据或字幕 | [表格、结构化数据与字幕](formats/spreadsheets-data-subtitles.md) |
| 转换图像、矢量图、漫画归档 | [图像与归档](formats/images-and-archives.md) |
| 读取 DXF 图纸或查看 DWG 支持边界 | [CAD](formats/cad.md) |
| 解析标准音频或受支持的加密音乐容器 | [音频](formats/audio.md) |
| 查看命令行选项和转换参数 | [命令行使用](usage/command-line.md) |
| 生成发布证据、快照与报告 | [发布证据流程](release-process.md) |

## 如何理解格式能力

- 每一项能力都由输入格式、输出格式和转换路线共同决定。能读取某格式不代表能写出该格式。
- 文档所说的“支持”仅适用于明确列出的格式变体和功能子集，不表示完整实现对应标准。
- 格式互转可能改变页面布局、色彩、透明度、动画、附件、公式、元数据或其他专有语义；具体损失列在格式文档中。
- PDF/A 依赖 Ghostscript 重写和显式配置的 veraPDF 验证。需要 MuPDF、FFmpeg 或其他后端的路线仅在相应能力编入程序时可用。**这些外部后端路线不在当前库发布包范围内**：Quirewise 库只返回内部实现或稳定的 `UNSUPPORTED` 状态。
- **音频是解析器（packet reader）**：当前发布包解析音频容器/帧并输出压缩包或 PCM 采样包，不含解码到 PCM、重采样、编码/封装或播放；见[音频](formats/audio.md)。
- 文件输出默认拒绝覆盖已存在的目标。缓存与中间工作文件保留在项目规定的工作目录中。

## 统一入口

统一命令行入口为 **quirewise**：按内容识别输入，支持 `--to pdf|txt|png`、`--check`、多输入、
`--out-dir`、`--page`/`--pages`、`--archive-password` 与 `--audio-track`。完整选项、支持矩阵与
限制见[命令行使用](usage/command-line.md)。密钥、扫描预处理、PDF/A、目录/通配符批量等尚未接线的
能力在该文档中单列，不属于当前 CLI 能力。


## 仓库结构

独立库与根应用的迁移状态见根目录的 [REPOSITORIES.md](../REPOSITORIES.md)。

架构与包边界说明：

- [PDF 引擎架构](architecture/pdf-engine.md)
- [全自写改造总计划（Zero-Vendored）](architecture/zero-vendored-plan.md)
- [DjVu 自写替换设计](architecture/djvu-replacement.md)
- [JPEG 自写解码器设计](architecture/jpeg-replacement.md)
- [LZMA/XZ 自写解码器设计](architecture/lzma-replacement.md)
- [AES 自写设计](architecture/aes-replacement.md)
- [公共头契约与包独立性](architecture/public-header-contract.md)
- [共享公共契约的单一所有者（设计评审）](architecture/shared-contract-ownership.md)


