# Quirewise 能力文档

> **迁移状态（2026-11-07）**：当前 `app/` 仓库只提供库组合 shell（`--version` /
> `--libraries`）。本文档描述的统一命令行入口尚未移植到新应用仓库；格式能力由
> `libraries/quirewise-*` 提供，并通过 `external-consumer-template` 与
> `app/tools/run_acceptance.py` 验证。发布包不包含任何外部格式后端。

本文档集说明 Quirewise 可处理的输入、可生成的输出、转换选项和格式边界。

## 按任务查阅

| 任务 | 文档 |
|---|---|
| 快速查看格式输入与输出方向 | [格式能力总览](formats/support-matrix.md) |
| 转换 PDF、扫描页或 PAGE/CONTAINER/UVZ | [PDF 与页面格式](formats/pdf-and-pages.md) |
| 转换 Office、电子书、HTML 或标记文本 | [文档与文本](formats/documents-and-text.md) |
| 转换工作簿、结构化数据或字幕 | [表格、结构化数据与字幕](formats/spreadsheets-data-subtitles.md) |
| 转换图像、矢量图、漫画归档 | [图像与归档](formats/images-and-archives.md) |
| 转换标准音频或受支持的加密音乐 | [音频](formats/audio.md) |
| 查看命令行选项和转换参数 | [命令行使用](usage/command-line.md) |

## 如何理解格式能力

- 每一项能力都由输入格式、输出格式和转换路线共同决定。能读取某格式不代表能写出该格式。
- 文档所说的“支持”仅适用于明确列出的格式变体和功能子集，不表示完整实现对应标准。
- 格式互转可能改变页面布局、色彩、透明度、动画、附件、公式、元数据或其他专有语义；具体损失列在格式文档中。
- PDF/A 依赖 Ghostscript 重写和显式配置的 veraPDF 验证。需要 MuPDF、FFmpeg 或其他后端的路线仅在相应能力编入程序时可用。**这些外部后端路线不在当前库发布包范围内**：Quirewise 库只返回内部实现或稳定的 `UNSUPPORTED` 状态。
- 文件输出默认拒绝覆盖已存在的目标。缓存与中间工作文件保留在项目规定的工作目录中。

## 统一入口

统一命令行入口目标为 **quirewise**。它支持按内容识别输入格式、通过 --to 指定输出格式、用 --check 检查当前读取路线，以及按格式选择密钥、音轨、页面规则或扫描预处理选项。完整选项见[命令行使用](usage/command-line.md)。**该 CLI 尚未移植到当前 `app/` 仓库，本节是目标行为说明。**


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


