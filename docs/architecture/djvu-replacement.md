# DjVu 自写替换设计

> 状态：D1 完成（IFF/ZP/BZZ，2026-11-10），D2（JB2）待开工。目标：删除
> `page/src/formats/djvu/vendor`（18 文件 / 9,230 行），用第一方实现替换，
> 公共 API 与行为保持不变。

## 1. 现状

- 实现位置：`libraries/quirewise-page/src/formats/djvu/vendor/`（vendored MIT
  `djvudec`，上游 commit `f0412ee…`，见 `PROVENANCE.md` 与 `LICENSE.djvudec.md`）。
- 调用方：`page/src/formats/djvu/djvu_page.c` 等，通过公共头
  `quirewise/djvu.h` 暴露 `qw_djvu_get_page_info`、`qw_djvu_render_page`、
  `qw_djvu_extract_text` 与 `qw_format_djvu` 描述符。
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
| **D2 JB2** | 位图算术解码、符号字典、文本区域、模板、多页顺序 | `bitonal.djvu` 与 ref.pgm **逐字节一致**；`multipage.djvu` 两页与 refs 一致；`text.djvu` 提取 `Hello DjVu` | 4–5 人日 |
| **D3 IW44** | 小波逆变换、渐进层、颜色变换、FGbz/FG44 调色板 | `photo.djvu` 与 photo.ref.ppm 逐字节一致；灰度/彩色 | 4–6 人日 |
| **D4 合成与边界** | 图层合成、缩放、旋转、背景色、资源上限、错误分类 | page 现有 4 项 CTest 全绿；新增边界用例 | 2–3 人日 |
| **D5 删除 vendor** | 删除 vendor 目录与许可证文件、更新文档、fuzz/ASan | 门禁白名单删除 18 条；四套矩阵全绿 | 1–2 人日 |

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
