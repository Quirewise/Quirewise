# 表格、结构化数据与字幕

## 工作簿与分隔文本

| 输入格式 | 读取和转换能力 | 主要限制 |
|---|---|---|
| XLSX/XLSM/XLTX | 按工作簿关系读取工作表和可选共享字符串；可走版式输出或共享类型化工作簿模型。支持的单元格类型、常规公式和缓存值可用于 XLSX/XLTX/ODS/OTS/FODS 输出。 | 最多 256 张工作表、100 万单元格。显示公式缓存值，不计算公式。布局路线不保留样式、数字格式、日期序列、合并区域、图表、图片、宏和模板行为。共享/数组公式可回退到版式路线。 |
| XLS/XLT | 读取 CFB 中的 BIFF8 Workbook/Book 流、共享字符串、单元格及缓存公式结果；可写受限 BIFF8 XLS。 | 仅支持 BIFF8，不支持加密工作簿。公式只迁移缓存结果；日期格式、样式、合并区域、图表、宏、对象和模板行为不保留。SST 字符串不能跨 BIFF 记录续接。 |
| ODS/OTS/FODS | 读取 ODF ZIP 包的 content.xml 或 FODS 平面 XML；可输出 HTML 布局或共享类型化工作簿。 | 最多 256 张表、100 万行、16,384 列及 100 万单元格。公式不重新计算；类型化路线有限保留字符串、数字、布尔、日期、同方言 OpenFormula 公式和缓存值。样式、合并区域、图表、图片、宏和模板语义不保留。 |
| CSV/TSV | 识别逗号、制表符或分号分隔；支持引号字段、转义引号和多行单元格。字段按文本保存，不做类型推断。 | CSV/TSV 输出只接受单工作表；输入按 UTF-8/BOM 读取，不自动转码传统代码页。工作簿输出最多 256 张表。行数、列数和文件大小受限。 |

类型化工作簿可以输出 CSV/TSV，但只接受一张工作表；公式输出为缓存值。写工作簿时，工作表名可从表格前的二级标题取得；缺标题时生成 SheetN。重复或无效工作表名会被拒绝。

## 结构化数据

JSON、JSON Lines、YAML、TOML、XML 和 vCard 通过共享有序数据模型转换。对象成员和数组顺序按输入顺序保留。

| 格式 | 支持范围 | 主要限制 |
|---|---|---|
| JSON | 保留对象/数组顺序及数字原始词法。 | 输入深度、节点数和输出大小有限。 |
| JSON Lines | 每个非空 LF/CRLF 物理行解析为一个 JSON 值。 | 不支持跨物理行的值或空行；空数组无法写成 JSONL。 |
| YAML | 支持单文档的 block/flow mapping、sequence、常见标量、注释和引号字符串。 | 不支持 anchors/aliases、tags、directives、block scalars 或多文档流。 |
| TOML | 支持 assignments、dotted/quoted keys、tables、arrays of tables、arrays、inline tables、常见标量及日期/时间。 | 写出要求根节点为对象；不支持 null 或非有限数值。 |
| XML | 受限 UTF-8 XML 树，可转换到 JSON/JSONL/YAML/TOML；XML 输出遵循 Quirewise 定义的元素数据映射。 | 拒绝 DTD 和自定义实体；不保留注释、处理指令和原始排版；命名空间前缀保留但不解析 URI。 |
| vCard 2.1/3.0/4.0 | 多卡片读取保留属性顺序、分组和原始参数；支持 2.1 的裸参数、quoted-printable 软换行，以及普通属性值中的 ISO-8859-1/Windows-1252 解码；可映射为固定列的表格。写出按 75 octets 折行。 | 其它旧字符集不支持；quoted-printable 值保留编码文本，值保留源转义。 |

结构化数据受输入大小、输出大小、树分配、深度和节点数限制。JSON/JSONL、YAML、TOML 和 XML 不保证往返后保留注释、空白、原始格式或所有格式专有类型。

## 字幕与定时文本

支持 SRT、WebVTT、LRC、MicroDVD、TTML、ASS/SSA、SAMI 和 SCC 之间的受限转换，并可输出 PDF。输入和输出使用 UTF-8，单文件上限 64 MiB。

共享定时字幕模型保留 cue 时间和文本；各格式专有样式、区域、定位、说话人、层、特效和头部元数据可能丢失。主要边界如下：

- MicroDVD 缺少帧率时按 23.976 fps 解释；帧边界会量化，换行使用竖线表示。
- TTML 支持 clock/offset 时间表达式和 begin/end/dur；样式、区域及嵌套 span 时序会扁平化，不支持 seq 容器。
- ASS/SSA 读取 Dialogue 定时和纯文本；样式、override tags、定位、边距、说话人、层和特效不保留。
- SAMI 读取首个字幕 class，展平标记和样式。
- SCC 仅支持 CC1 pop-on 基础/特殊字符子集；输出受行数、行长、字符集和帧量化限制。
- WebVTT 的 NOTE/STYLE/REGION、头部元数据和 cue 样式不保留。
- LRC 忽略 metadata tags；输出到其它字幕格式时使用规则推定的末条结束时间。
