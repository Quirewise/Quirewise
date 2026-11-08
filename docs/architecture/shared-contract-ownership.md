# 共享公共契约的单一所有者（设计评审）

> 状态：Accepted（2026-11-08）。取代 `public-header-contract.md` 中"多包复制同一
> 契约头"的过渡方案。
> 关联：DEP-003（公共头纯净）、DEP-008（内部依赖图）、`app/tools/verify_header_ownership.py`。

## 1. 背景与问题

17 个库包各自安装 `include/`，历史上把统一时代的三类"共享契约头"复制进了多个
包：

- `quirewise/status.h`（`QwStatus`、`QW_API`）——9 个包各一份；
- `quirewise/document.h`（`QwPageImageKind`、`QwDocument` 提供者契约）——12 个包各一份；
- `quirewise/convert.h`（约 200 个 `QwFormatId`、`QwConvertOptions`、`QwConvertReport`）——11 个包各一份，且出现 3 个不同版本。

96 个源码头文件最终安装到 58 个唯一路径，安装结果取决于安装顺序；`pml.h`、
`text_archive.h` 还出现"声明在 text 包、实现在 ebook 包"的所有权错位。上一轮
通过"副本必须字节一致 + 门禁"消除了当前的顺序依赖，但复制本身仍是维护负担，
也是下一次漂移的来源。

## 2. 备选方案

| 方案 | 做法 | 优点 | 缺点 |
|---|---|---|---|
| A. 维持复制 + 一致性门禁 | 保留 11/12 份副本，`verify_header_ownership.py` 强制字节一致 | 零依赖图变化，改动最小 | 每次改契约头要同步 11 份；门禁只能事后发现 |
| **B. runtime 单一所有者（采纳）** | 三个契约头上移到 `quirewise-runtime`；需要它们的包加一条 `Quirewise::Runtime` 边 | 单一事实来源；依赖图仍无环；runtime 从"孤儿包"变为真正的平台层 | 12 个包新增指向 runtime 的边；公共头路径迁移 |
| C. 新增 `quirewise-core` 包 | 新建第 18 个仓库承载契约类型 | 语义最干净 | 新增仓库需要 lock/SBOM/消费者/验收全套，成本最高 |
| D. 各包私有化类型 | 每包 `src/` 内自带类型头，不安装 | 零依赖边 | 类型定义重复且可能数值漂移，最差 |

采纳 **B**：runtime 是文档化分层中的最底层（"Quirewise Runtime / Platform"），
本身无依赖，作为类型/状态契约的单一所有者不会引入环；相比 C 不增加仓库与发布
面，相比 A 消除复制。

## 3. 目标结构

```
QuirewiseRuntime (leaf, no Quirewise deps)
  include/quirewise/status.h      QwStatus + QW_API
  include/quirewise/document.h    QwPageImageKind / QwPageImage / QwDocument + 回调
  include/quirewise/format.h      QwFormatId / QwInputFormat / QwOutputFormat /
                                  QwConvertOptions / QwConvertReport / QwConvertStage /
                                  QW_CONVERT_OPTIONS_INIT
        ^
        |  PUBLIC（头文件需要）
        |
archive audio data document ebook image page pdg spreadsheet subtitle text vector
```

- `quirewise-document` 保留 `quirewise/convert.h`，但只声明**它自己实现的**
  调度函数（`qw_detect_format`、`qw_format_name`、`qw_convert_*`、`qw_buffer_free`、
  `qw_check_file`），并 include runtime 的 `format.h`/`status.h`。
- 其余 10 个包删除 `convert.h`，私有代码改用 `quirewise/format.h`（仅类型）。
- 所有包删除 `status.h`、`document.h` 副本，统一从 runtime 获取。
- 所有权保持不变：`archive.h`→archive，`xml.h`→data，`plain_text.h`→text，
  `pml.h`/`text_archive.h`→ebook。

## 4. 依赖图变化

新增 12 条边，全部指向 runtime（叶子），不产生环：

| 包 | 新增边 |
|---|---|
| archive, audio, data, document, ebook, image, page, pdg, spreadsheet, subtitle, text, vector | → `quirewise-runtime` |

charset、compression、crypto 不引用契约类型，保持无 runtime 依赖。
`document` 的其它边（archive/data/compression/ebook/image/spreadsheet/crypto）
不变。拓扑序中 runtime 仍是第一个。

## 5. 公共 API 变化

1. 新增三个公共头：`quirewise/status.h`、`quirewise/document.h`、
   `quirewise/format.h`（由 runtime 安装）。
2. `quirewise/convert.h` 只由 `quirewise-document` 安装，内容收敛为调度函数声明；
   类型定义移到 `format.h`。
3. `quirewise-page`、`quirewise-ebook` 不再安装 `convert.h`（它们从未实现其中
   声明的调度函数）；其私有代码改用 `format.h`。
4. 全部包不再安装重复的 `status.h`/`document.h`；安装路径内容由 runtime 唯一决定。
5. `QwFormatId` 的数值保持 canonical 表（Page 变体中的两个 `RESERVED_PAGE` 值
   已在上一轮移除）。

## 6. 验收与门禁

- `validate_dependency_graph.py`：17 库、无环、无 app/源码泄漏；新增 12 条边必须
  与实际链接闭包一致。
- `verify_header_ownership.py --strict`：**0 条共享安装路径**（单一所有者），并
  接入 `run_acceptance.py`。
- `verify_public_headers.py`：安装头独立编译 0 失败、0 第三方泄漏。
- `verify_header_isolation.py`：每包只安装自身与依赖闭包后，公共头 0 失败。
- `check_consumer_coverage.py`：外部消费者对导出 API 的覆盖不下降（当前 357/357）。
- `run_acceptance.py`：Windows/MinGW 与 Linux 的静态/共享矩阵全绿（本机先跑
  static + shared）。

## 7. 迁移步骤

1. runtime：新增三个头（`format.h` 从 `convert.h` 拆分；其余两个移动）。
2. document：重写 `convert.h` 为纯声明；删除本包 `status.h`/`document.h`；
   CMake 增加 runtime 依赖。
3. 其余 11 个包：删除副本；CMake 增加 `find_package(QuirewiseRuntime)`、
   `target_link_libraries(<lib> PUBLIC Quirewise::Runtime)`；
   `cmake/Quirewise<X>Config.cmake.in` 增加 `find_dependency(QuirewiseRuntime)`；
   私有 include 从 `convert.h` 改为 `format.h`。
4. 消费者模板：`document.c` 继续使用 `convert.h`；其余不需要改动。
5. 更新 DEP 文档的公共头与依赖基线、发布门禁说明。
6. 逐仓库提交；验证通过后按仓库推送。

## 8. 风险与回滚

| 风险 | 缓解 |
|---|---|
| runtime 成为中心节点 | runtime 保持叶子、只含类型/状态与极小 ABI；无循环可能；DEP 图门禁持续校验 |
| 12 个包同时改 CMake 导致配置失败 | 按拓扑序全量重跑验收；失败按.first log 定位 |
| 消费者包含路径缺失 | runtime 依赖设为 PUBLIC，安装 Config 用 find_dependency 传递 |
| 静态链接顺序问题 | runtime 为叶子归档且无未解析符号；whole-archive 门禁覆盖 |
| 个别包实际不需要 runtime | 只对引用契约头的 12 个包加边；charset/compression/crypto 不加 |

回滚：整体保留旧副本的提交；按仓库逐一 `git revert` 即可恢复到"复制 + 一致性
门禁"状态，依赖图会自动回到无 runtime 边。
