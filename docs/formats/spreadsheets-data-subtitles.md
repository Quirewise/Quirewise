# 表格、结构化数据与字幕

> 状态（2026-11-14）：`quirewise-spreadsheet`、`quirewise-data`、`quirewise-subtitle`
> 当前都是**只读解析器**（XML 除外，它有序列化接口）。旧版本描述的工作簿写出、
> 结构化数据互转、字幕互转均未进入公开 API；CLI 只提供这些输入的 →PDF 路线。

## 1. 工作簿与分隔文本

| 输入格式 | 读取能力 | 主要限制 |
|---|---|---|
| XLSX/XLSM/XLTX | 按工作簿关系读取工作表和共享字符串；单元格值、常规公式缓存值 | 最多 256 张工作表、100 万单元格；不计算公式；样式、合并区域、图表、图片、宏、模板行为不保留 |
| XLS/XLT | 读取 CFB 中的 BIFF8 Workbook/Book 流、共享字符串、单元格及缓存公式结果 | 仅 BIFF8；不支持加密工作簿；SST 字符串不能跨记录续接 |
| ODS/OTS/FODS | 读取 ODF ZIP 包的 content.xml 或 FODS 平面 XML | 最多 256 张表、100 万行、16,384 列、100 万单元格；公式不重算 |
| CSV/TSV | 识别逗号/制表符/分号；支持引号、转义引号、多行单元格 | 字段按文本保存，不做类型推断；输入按 UTF-8/BOM 读取 |

**没有工作簿写出器**：`quirewise-spreadsheet` 不提供 XLSX/XLS/ODS/CSV 的输出 API，
`document` 只负责把工作簿渲染成 PDF 表格。CLI 的 `--to` 只接受 pdf/txt/png，不存在
表格目标格式。

## 2. 结构化数据

| 格式 | 读取能力 | 主要限制 |
|---|---|---|
| JSON | 对象/数组顺序、数字原始词法 | 输入深度、节点数、输出大小受限 |
| JSON Lines | 每个非空 LF/CRLF 物理行一个值 | 不支持跨行值或空行 |
| YAML | 单文档 block/flow mapping、sequence、常见标量、注释、引号字符串 | 不支持 anchors/aliases、tags、directives、block scalars、多文档流 |
| TOML | assignments、dotted/quoted keys、tables、arrays of tables、inline tables、日期时间 | 写出要求根节点为对象；不支持 null |
| XML | 受限 UTF-8 XML 树；创建/查询/序列化 | 拒绝 DTD 和自定义实体（可选 DTD 校验）；不保留注释和处理指令；命名空间前缀保留但不解析 URI |
| vCard 2.1/3.0/4.0 | 多卡片、属性顺序、分组、原始参数、QP 软换行 | 其它旧字符集不支持 |
| OPML / iPynb | 经共享 XML/JSON 树读取 | 专有扩展不保留 |

公开的写出接口只有 `qw_xml_serialize`（XML 树 → 字节），以及 CLI 的"值树 → PDF 表格/列表"。
**JSON/YAML/TOML/vCard 之间没有公开互转 API**，历史文档中的"支持格式之间的类型化转换"
与当前代码不符。

## 3. 字幕与定时文本

`quirewise-subtitle` 是解析器：读取 SRT、WebVTT、LRC、MicroDVD、TTML、ASS/SSA、SAMI、SCC
为共享 cue 模型（开始/结束时间、标识、设置、文本）。**没有公开的写出/互转 API**；
CLI 提供这些格式的 →PDF（时间轴文本页）路线。

主要边界：

- MicroDVD 缺少帧率时按 23.976 fps 解释；帧边界量化。
- TTML 支持 clock/offset 时间表达式和 begin/end/dur；样式、区域及嵌套 span 时序会扁平化，不支持 seq 容器。
- ASS/SSA 读取 Dialogue 定时和纯文本；样式、override tags、定位、边距、说话人、层和特效不保留。
- SAMI 读取首个字幕 class，展平标记和样式。
- SCC 仅支持 CC1 pop-on 基础/特殊字符子集。
- WebVTT 的 NOTE/STYLE/REGION、头部元数据和 cue 样式不保留。
- LRC 忽略 metadata tags。
- 输入和输出（PDF）使用 UTF-8，单文件上限 64 MiB。
