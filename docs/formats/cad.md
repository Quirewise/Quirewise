# CAD（DXF/DWG）

> **状态（2026-11-13）**：CAD 能力由 `quirewise-vector` 的 `quirewise/cad.h` 提供，
> 是纯 C、零第三方实现的读取与渲染层。CAD 解码参考 `unitedrhino/go-cad`
> 的能力边界，但本仓库没有链接或内置 Go 代码。第一阶段覆盖 DXF；DWG 只做
> 版本探测，解码尚未实现。

## 1. 输入

| 格式 | 当前能力 |
|---|---|
| DXF ASCII | 读取 `HEADER`、`TABLES/LAYER`、`BLOCKS`、`ENTITIES`；字符集按 `$ACADVER`/`$DWGCODEPAGE` 转换到 UTF-8。 |
| DXF binary（`AutoCAD Binary DXF`） | 与 ASCII 共用同一文档模型；支持字符串、double、int16/int32/int64、布尔和二进制块分组。 |
| DWG | `AC10xx` 版本头可探测；`qw_cad_parse` 返回稳定的 `QW_CAD_ERR_UNSUPPORTED`。 |

已映射的实体：`LINE`、`LWPOLYLINE`、`POLYLINE`+`VERTEX`、`CIRCLE`、`ARC`、
`ELLIPSE`、`SPLINE`（按控制点折线化）、`TEXT`/`MTEXT`、`ATTDEF`、`INSERT`
（块展开，含比例/旋转/嵌套）、`POINT`、`SOLID`/`TRACE`/`3DFACE`、`LEADER`、
`DIMENSION`（仅当其匿名块可作为 INSERT 展开）。未知实体显式计数并跳过。

## 2. 输出

- 文档模型：实体数、图层数、边界框、文本清单（内容、位置、字高、旋转、图层）。
- 栅格：RGBA8，按请求宽度等比渲染；线、圆、圆弧、椭圆、折线、实心多边形。
- SVG：每层一个 group，矢量路径/圆/椭圆和真实 `<text>` 元素，带图层名与颜色。
- CLI：`.dxf` 输入可转 PDF（A4 单页栅格）；`--to txt` 输出文本清单；`--check` 验证解析与渲染。

## 3. 边界

- 栅格渲染暂不包含字体引擎：TEXT/MTEXT 在当前 PNG/PDF 路线中以
  “基线条 + 竖线”占位；需要可读文字时使用 `qw_cad_render_svg()`，或后续
  的字体接入阶段。
- 块属性（ATTRIB）暂按 TEXT 实体读取；填充/图案（HATCH）、标注文字、
  ACIS 实体、代理对象和 3D 实体不做几何展开。
- 样条仅按控制点折线化，不做精确 NURBS 求值；椭圆弧参数按 DXF 约定读取。
- 资源限制：输入 256 MiB、实体 200000、点 2000000、文本累计 1 MiB、
  单次渲染 2000 万像素；超限返回 `RESOURCE_LIMIT`。
- DWG R13–R2018 解码、CJK 字形和智能分图属于后续阶段，不在当前发布能力内。

## 4. 参考

- 参考能力与验证语料：<https://github.com/unitedrhino/go-cad>（Apache-2.0）。
- 本地测试：`quirewise-vector` 的 `quirewise_vector_cad_test`；应用 smoke 使用
  `app/testfile/cad/sample.dxf` 验证 DXF → PDF 与 `--check`。
