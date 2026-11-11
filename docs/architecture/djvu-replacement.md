# DjVu 自写替换设计

> 状态：D1–D5 完成（2026-11-10）：`vendor/` 已删除，公共 API（页数、页信息、
> 渲染、文本）已切换到第一方实现；DJVM 多页、TXTz、JB2/IW44 合成均通过参考图验证。
> 已知边界见文末。

## 1. 现状

- 第一方实现位置：`libraries/quirewise-page/src/formats/djvu/`：
  `djvu_iff.c`（IFF 表单/块）、`djvu_parser.c`（INFO/页枚举）、`djvu_bzz.c`、
  `djvu_jb2.c`、`djvu_iw44.c`、`djvu_doc.c`（页面层与渲染/文本）、
  `djvu_api.c`（公共 API 适配），以及生成的数据表 `djvu_zp_table.c`、
  `djvu_iw44_zigzag.c`。原 `vendor/`（vendored MIT `djvudec`）已删除。
- 调用方：公共头 `quirewise/djvu.h` 暴露 `qw_djvu_get_page_info`、
  `qw_djvu_render_page`、`qw_djvu_extract_text` 与 `qw_format_djvu` 描述符。
- 现有夹具（`page/tests/data/djvu`）：

| 夹具 | 规模 | 参考输出 |
|---|---|---|
| `bitonal.djvu` | 单页 JB2 二值 | `bitonal.ref.pgm`（3,085 B） |
| `photo.djvu` | 单页 IW44 彩色 | `photo.ref.ppm`（9,229 B） |
| `multipage.djvu` | DJVM 两页 | `multi.p1.ref.ppm`、`multi.p2.ref.pgm` |
| `text.djvu` | JB2 + TXTz 文本 | 文本断言 `Hello DjVu` |

现有 `tests/djvu_decode_test.c` 已按字节比较参考图，是替换的天然 oracle。

## 2. 目标结构

```
page/src/formats/djvu/
  djvu_iff.c       IFF 容器：FORM/DJVM/DIRM/INFO/INCL/THUM 解析与成员定位
  djvu_zp.c        ZP 算术解码器（BZZ 与 IW44 共用）
  djvu_bzz.c       BZZ：MTF + Huffman（字典/文本层解压）
  djvu_jb2.c       JB2：位图算术解码、符号字典、文本区域、模板
  djvu_iw44.c      IW44：小波、渐进、颜色变换
  djvu_palette.c   FGbz/FG44 调色板与索引色
  djvu_text.c      TXTz 文本层与坐标
  djvu_render.c    图层合成、背景、缩放与旋转
  djvu_page.c      页面级编排（替换现有 vendor 调用点）
```

预估 6,000–8,500 行；全部为 `static` 内部函数，仅经既有公共头对外。

## 3. 解码流水线

1. **容器**：读取 `FORM:DJVU` / `FORM:DJVM`，DJVM 下按 `DIRM` 的成员表定位页面；
   `INFO` 提供宽高、版本、分辨率；`INCL` 递归共享字典。
2. **页面块**：收集 `INFO`、`Sjbz`、`BG44`/`FG44`/`FGbz`、`TXTz`、`Smmr`、`Djbz` 等块。
3. **位图**：`Sjbz` 走 JB2（共享字典优先），`Smmr` 走 MMR（复用现有 CCITT G4 解码）。
4. **颜色**：`BG44`/`FG44` 走 IW44（渐进层叠加），`FGbz` 提供调色板。
5. **文本**：`TXTz` 经 BZZ 解压后解析坐标与字符串。
6. **渲染**：按缩放因子合成前景/背景/掩码，输出 RGB24 或 GRAY8。

## 4. 内部数据结构（草案）

```c
typedef struct { const uint8_t *data; size_t size; } QwDjvuChunk;
typedef struct { uint32_t width, height; uint16_t dpi; uint8_t version; } QwDjvuInfo;
typedef struct { QwDjvuInfo info; QwDjvuChunk sjbz, bg44, fg44, fgbz, txtz, smmr; } QwDjvuPage;

typedef struct {                 /* ZP 算术解码器 */
    const uint8_t *data; size_t size, pos;
    uint32_t low, range; int bitpos; int eof;
} QwZpDecoder;

typedef struct {                 /* JB2 上下文 */
    QwZpDecoder zp;
    struct QwJb2Shape *symbols; size_t symbol_count;
    uint32_t width, height;
} QwJb2Context;

typedef struct {                 /* IW44 平面 */
    int32_t *coeff;              /* 小波系数 */
    uint32_t width, height, levels;
} QwIw44Plane;
```

生命周期：`QwDjvuContext` 持有解码缓冲，页面渲染后统一释放；所有分配经现有
`qw_*` 资源上限检查，失败路径保持幂等。

## 5. 里程碑与门禁

| 里程碑 | 内容 | 门禁 | 预估 |
|---|---|---|---|
| **D1 容器+ZP+BZZ** | IFF 解析、DJVM 成员、ZP 算术解码、BZZ 解压 | `text.djvu` 的 TXTz 解压结果与替换前基线**逐字节一致**（66 字节）；4 个夹具的 chunk 结构断言通过 | 4–5 人日（已完成） |
| **D2 JB2** | 位图算术解码、符号字典、文本区域、模板、多页顺序 | `bitonal.djvu` 与 ref.pgm **逐字节一致**（已完成）；`multipage.djvu` 页面选择与 `text.djvu` 文本提取归入 D4 集成 | 4–5 人日（位图/符号库已完成） |
| **D3 IW44** | 小波逆变换、渐进层、颜色变换、FGbz/FG44 调色板 | `photo.djvu` 与 photo.ref.ppm **逐字节一致**（已完成，灰阶 profile）；彩色 Cb/Cr 路径已实现但仓库暂无语料，D5 前补合成/外部语料 | 4–6 人日（灰阶已完成） |
| **D4 合成与边界** | 图层合成、DJVM 多页选择、TXTz 文本区域、资源上限、错误分类 | page CTest 8/8；`multipage` 两页与 refs 一致；`text.djvu` 提取 `Hello DjVu` | 2–3 人日（已完成） |
| **D5 删除 vendor** | 删除 vendor 目录与许可证文件、更新文档、门禁白名单 | `vendor/` 0 文件；门禁白名单从 53 减到 35 条；四套矩阵待 Phase 5 重跑 | 1–2 人日（已完成） |

D1/D2/D3 各自独立可回滚；未被 D1–D4 覆盖的行为列出清单，与现实现保持一致
（不支持项继续返回 `UNSUPPORTED`，不得画出错误页）。

## 6. 测试与差分

- **逐字节回归**：现有 4 组参考图 + 2×/4× 缩放参考（替换前用当前实现生成并提交）。
- **结构测试**：新增 `djvu_iff_test`、`djvu_bzz_test`、`djvu_jb2_test`、`djvu_iw44_test`、
  `djvu_text_test`，覆盖截断/越界/超限输入与错误码。
- **差分脚本**：`app/tools/` 下临时脚本对当前实现逐页渲染并记录 SHA-256，替换后复算。
- **模糊测试**：扩展现有 `page_fuzz_smoke` 语料与轮次，ASan/UBSan/LSan 0 诊断。
- **资源上限**：最大页面尺寸、像素预算、字典大小、图层数上限，超限返回
  `QW_PAGE_ERR_RESOURCE_LIMIT` 且不发布输出。

## 7. 非目标

- 不实现 DjVu 编码器（现有实现也只解码）；
- 不新增公共 API 或改动 `quirewise/djvu.h`；
- 不改变包依赖：Page 仍不依赖 Image/Document；
- 不追求覆盖 DjVu 规范中现实现未支持的特性（如某些 JB2 refinement 变体），
  差异清单在 D5 更新到包 README。

## 8. D5 后的实现边界

**已验证可用：** IFF/DJVM 容器与多页、INFO、JB2（直接编码、交叉细化、符号库、
文本区域位图）、IW44（灰阶 profile、渐进切片）、TXTz/TXTa 文本提取、
`subsample` 下采样、资源上限与错误分类。四组参考图（bitonal/photo/multipage×2）
与 `Hello DjVu` 文本均与替换前逐字节一致。

**已知差异（后续补齐）：**

1. `FGbz`/`FG44` 前景调色板尚未参与合成；当前夹具没有该层。遇到时按
   “背景 + 黑色掩码”近似，需要带调色板的语料来验证。
2. 彩色 IW44（`crcbdelay >= 0`）路径已实现但仓库内没有彩色语料。
3. INFO 的 `rotation` 已解析并通过公共 API 返回，渲染端尚未应用旋转
   （现有夹具均为 0°）。
4. `subsample > 1` 使用最近邻采样，不是参考实现的缩放滤波器；现有测试只用 1×。
5. JB2 的 inherited dictionary（`Djbz` 共享字典）未实现：页面引用共享字典时
   解码失败并返回错误，不会画出错误页。
6. 文本层只返回整页字符串（公共 API 的契约），不暴露区域坐标。
