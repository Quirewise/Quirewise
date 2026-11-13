# CAD（DXF/DWG）

> **状态（2026-11-13）**：CAD 能力由 `quirewise-vector` 的 `quirewise/cad.h` 提供，
> 是纯 C、零第三方实现的读取与渲染层。CAD 解码参考 `unitedrhino/go-cad`
> 的能力边界，但本仓库没有链接或内置 Go 代码。DXF 覆盖常用 2D 实体；
> DWG 已覆盖 R13/R14/R2000/R2004/R2007/R2010/R2013/R2018 的常用基础实体。

## 1. 输入

| 格式 | 当前能力 |
|---|---|
| DXF ASCII | 读取 `HEADER`、`TABLES/LAYER`、`BLOCKS`、`ENTITIES`；字符集按 `$ACADVER`/`$DWGCODEPAGE` 转换到 UTF-8。 |
| DXF binary（`AutoCAD Binary DXF`） | 与 ASCII 共用同一文档模型；支持字符串、double、int16/int32/int64、布尔和二进制块分组。 |
| DWG R13/R14/R2000（AC1012/AC1014/AC1015） | 段目录、对象图、对象记录、公共实体头，以及 `LINE`/`CIRCLE`/`ARC`/`LWPOLYLINE`/基础 `TEXT` 几何与文本。 |
| DWG R2004（AC1018） | 加密容器头、页表、段表、数据页 LZ77、对象图（`AcDb:Handles`）与对象数据段；同 DXF 的常用实体子集。 |
| DWG R2007（AC1021） | RS 去交织第二头部、页表、段表、R21 数据页解压、`AcDb:Handles` 与对象数据段；同 DXF 的常用实体子集。 |
| DWG R2010/R2013/R2018（AC1024/AC1027/AC1032） | R2004 式分页容器 + UMC/OT 对象记录 + R2010/R2013 实体头；同 DXF 的常用实体子集。 |

DXF 已映射的实体：`LINE`、`LWPOLYLINE`、`POLYLINE`+`VERTEX`、`CIRCLE`、`ARC`、
`ELLIPSE`、`SPLINE`（按控制点折线化）、`TEXT`/`MTEXT`、`ATTDEF`、`INSERT`
（块展开，含比例/旋转/嵌套）、`POINT`、`SOLID`/`TRACE`/`3DFACE`、`LEADER`、
`DIMENSION`（仅当其匿名块可作为 INSERT 展开）、`HATCH`（实心、简单多边形
边界）。DWG 当前只解码
`LINE`/`CIRCLE`/`ARC`/`LWPOLYLINE`，`TEXT` 到 R2004 为止；其余 DWG 实体、
图层句柄和 R2007+ 文本流留到后续阶段。未知 DXF 实体显式计数并跳过。

## 2. 输出

- 文档模型：实体数、图层数、边界框、文本清单（内容、位置、字高、旋转、图层）。
- 栅格：RGBA8，按请求宽度等比渲染；线、圆、圆弧、椭圆、折线、实心多边形。
- SVG：每层一个 group，矢量路径/圆/椭圆和真实 `<text>` 元素，带图层名与颜色。
- CLI：`.dxf` 和 R13–R2018 `.dwg` 可转 PDF（A4 单页栅格）；两者都可用
  `--to txt` 输出文本清单；`--check` 验证解析与渲染。

## 3. 边界

- 栅格渲染暂不包含字体引擎：TEXT/MTEXT 在当前 PNG/PDF 路线中以
  “基线条 + 竖线”占位；需要可读文字时使用 `qw_cad_render_svg()`，或后续
  的字体接入阶段。
- 块属性（ATTRIB）暂按 TEXT 实体读取；HATCH 仅支持实心简单多边形边界，
  复杂边界（孔洞/圆弧/样条）、图案填充、标注文字、ACIS 实体、代理对象和
  3D 实体不做几何展开。
- 样条仅按控制点折线化，不做精确 NURBS 求值；椭圆弧参数按 DXF 约定读取。
- 资源限制：输入 256 MiB、实体 200000、点 2000000、文本累计 1 MiB、
  单次渲染 2000 万像素；超限返回 `RESOURCE_LIMIT`。
- DWG R2010–R2018 解码、CJK 字形和智能分图属于后续阶段，不在当前发布能力内；
  R13–R2018 当前只解码 LINE/CIRCLE/ARC/LWPOLYLINE；TEXT 到 R2004 为止，R2007+ TEXT 暂未接入。

## 4. 后续阶段

阶段 2 的目标是补上 DWG 解码，按容器代际分四步：

1. R13/R14/R2000：section locator、对象映射、句柄流和常用实体记录；
   **当前已完成 LINE/CIRCLE/ARC/LWPOLYLINE/TEXT 的读取与测试**，图层句柄
   仍在补齐；
2. R2004：分页 section map、页表和数据页重组；**当前已完成 LINE/CIRCLE/ARC/LWPOLYLINE/TEXT 与混合实体测试**；
3. R2007（RS 交织流 + R21）：**当前已完成 LINE/CIRCLE/ARC/LWPOLYLINE 与混合实体测试**；
4. R2010/R2013/R2018：UMC/OT 对象记录和更新的实体头编码；**当前已完成 LINE/CIRCLE/ARC/LWPOLYLINE 与混合实体测试**。

每步以 `unitedrhino/go-cad` 的测试语料（公开 LibreDWG 样本）做交叉验证；
不引入 Go、LibreDWG 或其他第三方运行库。HATCH、ACIS、标注文字、CJK 字形
和智能分图在 DWG 基础实体之后补齐。

## 5. 参考

- 参考能力与验证语料：<https://github.com/unitedrhino/go-cad>（Apache-2.0）。
- 本地测试：`quirewise-vector` 的 `quirewise_vector_cad_test`；应用 smoke 使用
  `app/testfile/cad/sample.dxf`、`line_2000.dwg`、`line_2004.dwg` 和
  `line_2007.dwg` 验证 DXF/DWG → PDF 与 `--check`。
