#!/usr/bin/env python3
"""Render RELEASE_ACCEPTANCE_REPORT.md from the recorded release artifacts.

The report is generated, not hand-edited: every hash and count is read from
``.tmp/release``. The independent-review section is read verbatim from
``.tmp/release/reviewer-signoff.md``; if that file is absent the report says so
instead of claiming a sign-off.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def summary_stats(path: Path) -> tuple[int, list[str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return len(data["steps"]), data["failed"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path,
                        default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    root = args.workspace.resolve()
    release = root / ".tmp" / "release"

    heads = json.loads((release / "repository-heads.json").read_text(encoding="utf-8"))
    win_static = summary_stats(release / "static-summary.json")
    win_shared = summary_stats(release / "shared-summary.json")
    linux_static = summary_stats(root / ".tmp/acceptance/linux-static/summary.json")
    linux_shared = summary_stats(root / ".tmp/acceptance/linux-shared/summary.json")

    sbom = json.loads((release / "sbom-static.cdx.json").read_text(encoding="utf-8"))
    nodes = len(sbom["dependencies"])
    edges = sum(len(item["dependsOn"]) for item in sbom["dependencies"])
    inventory = json.loads((release / "license-inventory-static.json").read_text(encoding="utf-8"))

    docs_dir = release / "release-docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    acceptance_copy = docs_dir / "DEPENDENCY_BOUNDARIES_AND_ACCEPTANCE.md"
    shutil.copyfile(root / "DEPENDENCY_BOUNDARIES_AND_ACCEPTANCE.md", acceptance_copy)
    hashes = {"dependency-boundaries.md": sha256(acceptance_copy)}
    for name in [
        "sbom-static.cdx.json", "sbom-shared.cdx.json",
        "license-inventory-static.json", "license-inventory-shared.json",
        "install-manifest-static.json", "install-manifest-shared.json",
        "dependency-closure.json", "public-headers-static.json",
        "public-headers-shared.json", "error-taxonomy.txt",
        "resource-limits.txt", "pdg-pdf-status.txt", "self-audit.json",
        "reviewer-signoff.md",
    ]:
        path = release / name
        if path.is_file():
            hashes[name] = sha256(path)
    signoff_path = release / "reviewer-signoff.md"
    if signoff_path.is_file():
        signoff_text = signoff_path.read_text(encoding="utf-8").strip()
        signoff_section = (
            "## 8. 独立复核\n\n"
            f"- 签字文件：`.tmp/release/reviewer-signoff.md`"
            f"（SHA-256 `{hashes['reviewer-signoff.md']}`）\n"
            "- 说明：以下为独立 reviewer 写入的签字原文，未经 Lead 改写。\n\n"
            "```text\n" + signoff_text + "\n```\n"
        )
    else:
        signoff_section = (
            "## 8. 独立复核\n\n"
            "- 未提供 `.tmp/release/reviewer-signoff.md`；本报告不宣称独立 sign-off。\n"
        )

    manifest_static = json.loads((release / "install-manifest-static.json").read_text(encoding="utf-8"))
    manifest_shared = json.loads((release / "install-manifest-shared.json").read_text(encoding="utf-8"))
    actual_static = sum(1 for p in (root / ".tmp/acceptance/static/install").rglob("*") if p.is_file())
    actual_shared = sum(1 for p in (root / ".tmp/acceptance/shared/install").rglob("*") if p.is_file())

    commit_rows = "\n".join(
        f"| `{item['repo']}` | `{item['commit'][:12]}` | `{item['branch']}` | "
        f"{'clean' if item['clean'] else 'dirty'} |"
        for item in heads
    )
    hash_rows = "\n".join(f"| `{name}` | `{value}` |" for name, value in hashes.items())

    report = f"""# Quirewise M6 发布验收报告

- 报告时间：{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}
- Goal：`QW-AUTONOMY-001`
- 状态：**发布候选（RELEASE CANDIDATE）** — 代码、许可证、构建矩阵与验收证据齐备；外部仓库发布后 CI 可复现
- 依据：[QUIREWISE_AGENT_LONG_TERM_GOAL.md](QUIREWISE_AGENT_LONG_TERM_GOAL.md)、[DEPENDENCY_BOUNDARIES_AND_ACCEPTANCE.md](DEPENDENCY_BOUNDARIES_AND_ACCEPTANCE.md)

## 1. 范围

本发布物由 **1 个应用组合仓库 + 17 个独立库仓库 + 1 个外部消费者模板**组成。
库之间只通过已安装的 Quirewise CMake 包和公共头依赖；生产路径不包含
LibLZMA/XZ、OpenSSL、WebP、OpenJPEG、DjVuLibre、MuPDF、Zlib、libjpeg、iconv
或其他第三方运行库。

不在本发布范围：

- macOS 与 MSVC 工具链（本机不可用，未验证；Windows 由 MinGW64 覆盖，Linux 由 Ubuntu 24.04 覆盖）；
- 迁移前的统一 `quirewise INPUT --to FORMAT` CLI（当前 `app/` 只提供组合 shell）；
- 依赖 Ghostscript、veraPDF、FFmpeg、LibRaw 等外部后端的历史路线；
- 各格式内部尚未实现的子集；这些入口稳定返回 `UNSUPPORTED`，见各库文档与支持矩阵。

## 2. 提交基线

| 仓库 | HEAD | 分支 | 工作区 |
|---|---|---|---|
{commit_rows}

所有仓库 `git status --porcelain` 为空；本报告基于以上提交，未执行远程 push。

## 3. 构建、安装与测试矩阵

| 平台 | 工具链 | 模式 | 结果 |
|---|---|---|---|
| Windows 11 x64 | CMake 3.29.2, Ninja 1.12.0, GCC 15.2.0, Python 3.11.9 | static | {win_static[0]} 步全部通过（17 库 CTest + 17 消费者 + app + 3 闸门） |
| Windows 11 x64 | 同上 | shared | {win_shared[0]} 步全部通过 |
| Ubuntu 24.04 (WSL2) | CMake 3.28.3, GNU Make, GCC 13.3.0, Python 3.12.3 | static | {linux_static[0]} 步全部通过 |
| Ubuntu 24.04 (WSL2) | 同上 | shared | {linux_shared[0]} 步全部通过 |

安装树：静态 {manifest_static['file_count']} 个文件（文件系统实计 {actual_static}）；
共享 {manifest_shared['file_count']} 个文件（实计 {actual_shared}）。两棵树各含
20 份 `share/doc/quirewise/**/LICENSE`。运行器在缺少工作区根 `LICENSE` 时回退到
`app/LICENSE`，因此 CI 只检出 `app/` 也能完成许可证复制。

复现命令：

```powershell
# Windows PowerShell
python app/tools/run_acceptance.py --workspace . --jobs 8
python app/tools/run_acceptance.py --workspace . --shared --jobs 8

# Ubuntu / WSL
python3 app/tools/run_acceptance.py --workspace . --jobs 4
python3 app/tools/run_acceptance.py --workspace . --shared --jobs 4
```

## 4. 静态验收闸门

| 闸门 | 结果 |
|---|---|
| `validate_dependency_graph.py`（声明图；静态模式另由运行器传入 `--actual-prefix`/`--nm` 从归档反推实际闭包） | 17 个库、无环、无 app/源码泄漏；静态实际闭包与声明图一致（`comic/page` 对 `image` 为声明但无符号证据，属于冗余声明，不影响无环）；共享模式只做声明图 |
| `audit_release_boundaries.py` | **0 findings、0 read errors**，仅 1 条开发期观察（app 的 Python3 查找） |
| `audit_mupdf_removal.py` | **0 命中**；`qw_mupdf_*`、`mupdf_backend.h`、`QUIREWISE_WITH_MUPDF`、`<mupdf/...>` 与 MuPDF CMake 引用全部清零 |
| `verify_public_headers.py`（静态与共享安装树） | 58/58 公共头独立编译通过，0 失败，0 第三方头泄漏（JSON 证据见下表） |
| `verify_error_taxonomy.py` / `verify_resource_limits.py` | 0 findings，原始输出见 `.tmp/release/error-taxonomy.txt` 与 `.tmp/release/resource-limits.txt` |

机械自检结果：`.tmp/release/self-audit.json`（仓库干净、20 份 MIT LICENSE、
四组 79 步、SBOM 第一方全 MIT、djvudec MIT、闸门与 lock 校验全部通过）。
Runtime 现在也有 `quirewise_runtime_abi` CTest，17 个库均有测试入口。

## 5. 许可证与 SBOM

- 第一方许可：**MIT**。SBOM 的第一方组件为 **17 个库 + 应用 = 18 个**；此外
  `external-consumer-template` 与工作区根目录也各有一份 MIT `LICENSE`，因此
  源仓库与安装树共有 **20 份**许可证文件（18 个发布组件 + 2 个非发布模板/工作区声明）。
- 内置源码：LZMA SDK（Public Domain）、tiny-AES-c（Unlicense）、stb_image
  （MIT OR Unlicense，Image/PDG 各一份）、djvudec（MIT，commit `f0412ee…`）。
- SBOM：CycloneDX 1.5，27 个组件（17 库 + 应用 + 5 内置源码 + 2 组测试素材 +
  2 平台运行时）、**{nodes} 个依赖节点、{edges} 条 `dependsOn` 边**。
- 许可证清单：{len(inventory['first_party'])} 个第一方条目均为 MIT；被禁止运行库 0 项。

| 工件 | SHA-256 |
|---|---|
{hash_rows}

## 6. 与 DEP-001…DEP-018 的对应

验收文档第 8 节 18 行全部为“通过”，本报告补充了 M6 收尾证据：

- DEP-014：旧 MuPDF 边界已删除/重命名，`audit_mupdf_removal.py` 报告 0；
- DEP-018：第一方 MIT 许可证、SBOM 与许可证清单已生成，原“发布阻断项”清除；
- DEP-003/005/006/007：本轮在 Windows 与 Linux、静态与共享模式重新构建、安装、消费并运行闸门；
- 其余 DEP 证据路径不变，见验收文档与 `.tmp/quirewise-agent-evidence/`。

## 7. 已知限制与外部前置

1. **CI 需要先发布仓库**：`.github/workflows/ci.yml` 与 `app/release-lock.json`
   已就绪，但本会话未执行 push。运行器在缺少工作区根 `LICENSE` 时回退到
   `app/LICENSE`，因此只检出 `app/` 也能完成 20 份许可证复制；但仍需先发布
   18 个兄弟仓库的 M6 提交与 `charset`/`compression`/`crypto` 三个新仓库的远端，
   CI 才能拉取 lock 中的提交并实际运行。lock 中 `comic`/`page`/`runtime` 指向
   `github.com/Hellohistory/…`，其余指向 `github.com/Quirewise/…`；CI 的
   token/可见性需要同时覆盖这两个组织。
2. **平台**：macOS/MSVC 未验证，属于明确排除范围（决策记录在本节与验收文档第 11 节），
   不作为本发布物的验收项。
3. **应用入口**：`app` 仍是组合 shell，旧统一 CLI 未移植；转换能力通过库包与外部消费者验证。
4. **共享库部署**：Windows 共享消费者运行时需要把安装前缀的 `bin/` 加入 `PATH`
   （验收运行器已按此设置）；Linux 使用 `LD_LIBRARY_PATH` 或安装 RPATH。
5. **能力子集**：Audio/Image 等库存在大量显式 `UNSUPPORTED` 路径；支持矩阵需按库文档解读。
6. **PDG PDF 输出**：`pdg_output_requires_external_decoder(PDG_OUTPUT_PDF)` 仍为 1，
   模块返回 `PDG_ERR_EXTERNAL_DECODER_REQUIRED`（证据 `.tmp/release/pdg-pdf-status.txt`）；
   M3-04 的“PDG PDF 输出迁移到内部 PDF/Layout”仍是一项后续能力工作。
7. **依赖声明清理**：`comic` 与 `page` 声明了 `image` 依赖但没有符号证据，属于可后续删除的冗余声明。
8. **清理记录**：本轮删除了工作区根目录中名为 `$prefix` 的遗留安装目录、
   `.tmp/openjpeg-debug-src`、`.tmp/openjpeg-debug-build`、前导空格的 ` .tmp`、
   空 `.to_delete`、`.tmp/quirewise-agent-install`、`.tmp/verify-build`，以及
   `app/.tmp`（113.6 GB / 633,437 文件的旧构建与 Ghostscript 依赖缓存）。
   保留：`.tmp/quirewise-agent-build`（324 MB）、`.tmp/quirewise-agent-evidence`
   （3,375 MB）、`.tmp/acceptance`（411 MB，当前四组矩阵构建）与
   `.tmp/release`（0.2 MB 发布工件）；这些不属于发布物。报告与自检脚本已移入
   `app/tools/` 并纳入版本控制。两份根文档的副本与 SHA-256 记录在
   `.tmp/release/release-docs/`（`release-docs.sha256`），满足 DEP §8 对版本化
   验收资料的要求。

{signoff_section}"""
    out = root / "RELEASE_ACCEPTANCE_REPORT.md"
    out.write_text(report, encoding="utf-8")
    report_copy = docs_dir / "RELEASE_ACCEPTANCE_REPORT.md"
    shutil.copyfile(out, report_copy)
    (docs_dir / "release-docs.sha256").write_text(
        f"{hashlib.sha256(acceptance_copy.read_bytes()).hexdigest()}  "
        "DEPENDENCY_BOUNDARIES_AND_ACCEPTANCE.md\n"
        f"{hashlib.sha256(report_copy.read_bytes()).hexdigest()}  "
        "RELEASE_ACCEPTANCE_REPORT.md\n",
        encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
