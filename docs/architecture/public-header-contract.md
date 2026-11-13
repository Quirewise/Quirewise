# 公共头契约与包独立性

> 状态：ACTIVE（2026-11-08，单一所有者模型）。设计评审见
> [shared-contract-ownership.md](shared-contract-ownership.md)。
> 门禁：`app/tools/verify_header_ownership.py --strict`。

## 不变式

1. 每个安装相对路径只有一个所有者包；
2. 同一路径不得由多个包安装，无论内容是否相同；
3. 公共头只允许包含标准 C 头或其他已安装的 Quirewise 公共头；
4. 包只能通过 `find_package(Quirewise<X>)` 获取依赖包的公共头，不得复制源码树
   头文件，也不得通过相对路径引用兄弟仓库。

`run_acceptance.py` 以 `--strict` 运行 `verify_header_ownership.py`：17 个包、
60 个安装路径、**0 条共享路径**才算通过；任何重复路径都会阻断验收。

## 所有权

| 安装路径 | 所有者 | 内容 |
|---|---|---|
| `quirewise/runtime.h` | runtime | ABI 版本、缓冲区分配 |
| `quirewise/status.h` | runtime | `QwStatus`、`QW_API` |
| `quirewise/document.h` | runtime | `QwPageImageKind`、`QwPageImage`、`QwDocument` 提供者契约 |
| `quirewise/format.h` | runtime | `QwFormatId`、`QwInputFormat`、`QwOutputFormat`、`QwConvertOptions`、`QwConvertReport`、`QwConvertStage` |
| `quirewise/convert.h` | document | 转换调度函数声明（`qw_detect_format`、`qw_convert_*`、`qw_check_file` 等） |
| `quirewise/archive.h` | archive | 归档 API |
| `quirewise/xml.h` | data | 有序 XML 树 API |
| `quirewise/cad.h` | vector | DXF/CAD 文档、文本清单与渲染 API |
| `quirewise/plain_text.h` | text | 纯文本 API |
| `quirewise/pml.h`、`quirewise/text_archive.h` | ebook | PML 与文本归档 API（实现所在包） |

依赖关系：上表所有者之外，需要契约类型的 12 个包通过 `Quirewise::Runtime`
（PUBLIC）获取 `status.h`/`document.h`/`format.h`；`runtime` 是叶子，依赖图保持
有向无环。

## 修改公共头的流程

1. 在所有者包内修改头文件；
2. 同步更新该包的安装规则、CMake 导出与消费者用例；
3. 运行 `validate_dependency_graph.py` 与
   `verify_header_ownership.py --strict`；
4. 只有两项门禁都通过，才进入验收矩阵。

## 迁移记录

- 2026-11-08 之前：多个包复制 `status.h`/`document.h`/`convert.h`，96 个源码头
  映射到 58 个安装路径，`convert.h` 出现 3 个版本，安装结果依赖安装顺序。
- 2026-11-08：`convert.h` 统一、`pml.h`/`text_archive.h` 归位到 ebook；随后按
  [设计评审](shared-contract-ownership.md) 将三类契约头上移到 runtime，12 个包
  新增 `Quirewise::Runtime` 边，其余副本全部删除。结果：60 个安装路径、0 条共享
  路径、依赖图无环。
