# 命令行使用

> **迁移状态（2026-11-07）**：本页描述的是目标/旧版统一 CLI。当前 `app/` 仓库
> 的可执行文件只实现 `--version`、`--libraries` 和 `--help`；转换入口尚未移植，
> 库级能力与验收方式见 `app/README.md` 和 `app/tools/run_acceptance.py`。

## 统一转换入口

基本形式：

    quirewise INPUT [-o OUTPUT] [--to FORMAT]

默认输出格式为 PDF；未指定输出路径时，使用输入文件名并替换为目标扩展名。使用 --to 指定目标格式。输入格式优先由内容识别；部分路径格式还使用扩展名或目录上下文。

示例：

    quirewise book.container -o book.pdf --key BOOKKEY
    quirewise scan.page -o scan.pdf --binarize wolf --deskew --crop
    quirewise report.xlsx --to csv -o report.csv
    quirewise track.flac --to opus -o track.opus --audio-track 2
    quirewise document.pdf --to txt -o document.txt
    quirewise document.pdf --check

文件输出默认不覆盖已有路径。发生错误时，命令返回非零状态并提供错误类别和可用的路线说明。

## 常用选项

| 选项 | 用途 |
|---|---|
| --to FORMAT | 选择输出格式。 |
| -o FILE、--out FILE | 设置输出文件；默认使用输入名称和目标扩展名。 |
| --check | 检查当前支持路线能否读取输入，不创建输出文件。 |
| --quiet | 正常转换只输出目标路径；检查成功时输出 OK。 |
| --key STRING | CONTAINER 成员密钥；默认可执行离线 SSCT bookkey 解析。 |
| --pages RULE | CONTAINER 页面规则：auto、body、body+att 或 all。 |
| --page MODE | 图像页页面尺寸：a4 或 image。 |
| --archive-password TEXT | 加密 CBZ/CB7 归档密码。 |
| --zip-password TEXT | --archive-password 的兼容别名。 |
| --audio-track N | 选择从 1 开始的音轨序号；默认使用最佳音轨。 |
| --ekey STRING | QMC 所需 EKey，或 KGM v5 的匹配歌曲 EKey。 |
| --ekey-db PATH | QMC STag/MusicEx 使用的 player_process_db。 |
| --kgm-key PATH | KGM v3/v4 公钥文件；默认使用随程序提供的密钥。 |
| --kgm-db PATH | KGM v5 本地歌曲密钥数据库。 |
| --pdfa LEVEL | 输出 PDF/A-1b、2b 或 3b。 |
| --optimize | PDF/A 转换时使用 Ghostscript /ebook profile。 |

## 扫描页选项

扫描处理仅作用于可提供图像像素的页面路线，默认关闭。

| 选项 | 参数与效果 |
|---|---|
| --illumination | 校正纸张照度不均。 |
| --perspective | 在页面四边形检测可信时校正透视。 |
| --deskew | 校正最多约 5 度的页面倾斜。 |
| --split-double | 按检测到的中缝输出左右两页。 |
| --dewarp | 在检测可靠时展平弯曲文本行。 |
| --crop | 裁切页面外边距。 |
| --crop-padding N | 内容边缘保留像素，默认 12，最大 512。 |
| --binarize MODE | 使用 otsu 或 wolf 二值化。 |
| --wolf-window N | Wolf 局部奇数窗口，3–255，默认 31。 |
| --despeckle N | 删除小于阈值的 8 连通斑点；须启用二值化。 |
| --ccitt-g4 | 使用 Group 4 编码最终二值页面；须启用二值化。 |

原生 PDF 页面路线只提供 PDF 字节，不提供可处理的扫描像素；扫描预处理参数用于 PAGE、图像页 CONTAINER、UVZ 等像素路线。

## 只读检查

--check 检查的是 Quirewise 当前读取路径，不是格式规范认证，也不创建输出文件。PDF 会逐页打开并渲染；其它文档通常完整走 PDF 转换路线；音频会转换为内存 FLAC 后释放。内存需求可能接近转换本身。

## 专用工具

- **container_extract**：读取 CONTAINER bookkey、列出成员或提取成员文件。
- **container2pdf**：专用 CONTAINER→PDF 路线，可接受输入 CONTAINER 或 PAGE 目录。
- **page_batch**：批量处理目录中的 PAGE 文件，可设置并行任务数。

专用工具的参数范围以各自的 --help 输出为准。

## 输出格式名称

输出格式包括 PDF、PS/EPS、SVG/SVGZ、TXT/TXTz、JSON/JSONL/YAML/TOML/XML/vCard、CSV/TSV、常见字幕与标记文本、XLS/XLT/XLSX/XLTX/ODS/OTS/FODS、HTML/EPUB/HWPX/EML、CBZ/CBT、注册的图像格式和注册的音频格式。目标是否可用以及具体限制，以[格式能力总览](../formats/support-matrix.md)和对应分类文档为准。
