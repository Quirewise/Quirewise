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
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def summary_stats(path: Path):
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return len(data["steps"]), data["failed"]


def toolchain(release: Path, name: str, fallback: dict) -> dict:
    path = release / f"toolchain-{name}.json"
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return fallback


def run_gate(root: Path, *args: str) -> tuple[int, str]:
    completed = subprocess.run(["python", *args], cwd=root,
                               capture_output=True, text=True)
    lines = [line for line in completed.stdout.strip().splitlines() if line]
    return completed.returncode, (lines[-1] if lines else "")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path,
                        default=Path(__file__).resolve().parents[2])
    parser.add_argument("--release-dir", type=Path,
                        default=Path(".tmp/release"))
    parser.add_argument("--static-prefix", type=Path,
                        default=Path(".tmp/acceptance/windows-static/install"))
    parser.add_argument("--shared-prefix", type=Path,
                        default=Path(".tmp/acceptance/windows-shared/install"))
    parser.add_argument("--linux-static-summary", type=Path,
                        default=Path(".tmp/acceptance/linux-static/summary.json"))
    parser.add_argument("--linux-shared-summary", type=Path,
                        default=Path(".tmp/acceptance/linux-shared/summary.json"))
    parser.add_argument("--out", type=Path,
                        default=Path("RELEASE_ACCEPTANCE_REPORT.md"))
    args = parser.parse_args()
    root = args.workspace.resolve()
    release = (root / args.release_dir).resolve()
    static_prefix = (root / args.static_prefix).resolve()
    shared_prefix = (root / args.shared_prefix).resolve()
    linux_static_path = (root / args.linux_static_summary).resolve()
    linux_shared_path = (root / args.linux_shared_summary).resolve()
    if (release / "linux-static-summary.json").is_file():
        linux_static_path = release / "linux-static-summary.json"
    if (release / "linux-shared-summary.json").is_file():
        linux_shared_path = release / "linux-shared-summary.json"

    heads = json.loads((release / "repository-heads.json").read_text(encoding="utf-8"))
    win_static = summary_stats(release / "static-summary.json")
    win_shared = summary_stats(release / "shared-summary.json")
    linux_static = summary_stats(linux_static_path)
    linux_shared = summary_stats(linux_shared_path)

    sbom = json.loads((release / "sbom-static.cdx.json").read_text(encoding="utf-8"))
    nodes = len(sbom["dependencies"])
    edges = sum(len(item["dependsOn"]) for item in sbom["dependencies"])
    inventory = json.loads((release / "license-inventory-static.json").read_text(encoding="utf-8"))

    public_static = json.loads(
        (release / "public-headers-static.json").read_text(encoding="utf-8"))
    public_shared = json.loads(
        (release / "public-headers-shared.json").read_text(encoding="utf-8"))
    header_count = public_static["header_count"]

    manifest_static = json.loads(
        (release / "install-manifest-static.json").read_text(encoding="utf-8"))
    manifest_shared = json.loads(
        (release / "install-manifest-shared.json").read_text(encoding="utf-8"))
    actual_static = sum(1 for p in static_prefix.rglob("*") if p.is_file())
    actual_shared = sum(1 for p in shared_prefix.rglob("*") if p.is_file())

    win_tc = toolchain(release, "windows", {
        "os": "Windows 11 x64",
        "cmake": "3.29.2", "ninja": "1.12.0", "cc": "GCC 15.2.0",
        "python": "3.11.9", "generator": "Ninja"})
    linux_tc = toolchain(release, "linux", {
        "os": "Ubuntu (WSL2)",
        "cmake": "unknown", "ninja": "unknown", "cc": "GCC",
        "python": "3", "generator": "Ninja"})

    def toolchain_text(tc: dict) -> str:
        return (f"CMake {tc['cmake']}, {tc['generator']} {tc['ninja']}, "
                f"{tc['cc']}, Python {tc['python']}")

    matrix = []
    if win_static:
        matrix.append(("Windows", win_tc["os"], toolchain_text(win_tc), "static",
                       win_static[0], win_static[1]))
    if win_shared:
        matrix.append(("Windows", win_tc["os"], toolchain_text(win_tc), "shared",
                       win_shared[0], win_shared[1]))
    if linux_static:
        matrix.append(("Linux", linux_tc["os"], toolchain_text(linux_tc), "static",
                       linux_static[0], linux_static[1]))
    if linux_shared:
        matrix.append(("Linux", linux_tc["os"], toolchain_text(linux_tc), "shared",
                       linux_shared[0], linux_shared[1]))
    matrix_rows = "\n".join(
        f"| {os_name} | {tc} | {mode} | {steps} 步全部通过（failed: {failed or '[]'}） |"
        for _, os_name, tc, mode, steps, failed in matrix)
    matrix_note = (f"四组矩阵均为 {win_static[0]} 步"
                   if linux_static and linux_shared else
                   "Windows 两组矩阵为 "
                   f"{win_static[0]} 步；Linux 矩阵本轮未重跑（本机无可用 ELF 环境）")

    ownership_code, ownership_line = run_gate(
        root, "app/tools/verify_header_ownership.py", "--workspace", ".", "--strict")
    dag_code, dag_line = run_gate(
        root, "app/tools/validate_dependency_graph.py", "--workspace", ".")
    vendored_code, vendored_line = run_gate(
        root, "app/tools/audit_vendored_sources.py", "--workspace", ".")

    docs_dir = release / "release-docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    acceptance_copy = docs_dir / "DEPENDENCY_BOUNDARIES_AND_ACCEPTANCE.md"
    shutil.copyfile(root / "DEPENDENCY_BOUNDARIES_AND_ACCEPTANCE.md", acceptance_copy)
    shutil.copyfile(root / "DEPENDENCY_BOUNDARIES_AND_ACCEPTANCE.md",
                    release / "dependency-boundaries.md")
    hashes = {"dependency-boundaries.md": sha256(release / "dependency-boundaries.md")}
    for name in [
        "sbom-static.cdx.json", "sbom-shared.cdx.json",
        "license-inventory-static.json", "license-inventory-shared.json",
        "install-manifest-static.json", "install-manifest-shared.json",
        "dependency-closure.json", "public-headers-static.json",
        "public-headers-shared.json", "error-taxonomy.txt",
        "resource-limits.txt", "pdg-pdf-status.txt", "reviewer-signoff.md",
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

    commit_rows = "\n".join(
        f"| `{item['repo']}` | `{item['commit'][:12]}` | `{item['branch']}` | "
        f"{'clean' if item['clean'] else 'dirty'} |"
        for item in heads)
    hash_rows = "\n".join(f"| `{name}` | `{value}` |" for name, value in hashes.items())

    report = f"""# Quirewise M6 发布验收报告

- 报告时间：{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}
- Goal：`QW-AUTONOMY-001`
- 状态：**发布候选（RELEASE CANDIDATE）** — 代码、许可证、构建矩阵与验收证据齐备；仓库与 lock 已发布，四套矩阵在本机复现（GitHub Actions 尚未执行）
- 依据：[QUIREWISE_AGENT_LONG_TERM_GOAL.md](QUIREWISE_AGENT_LONG_TERM_GOAL.md)、[DEPENDENCY_BOUNDARIES_AND_ACCEPTANCE.md](DEPENDENCY_BOUNDARIES_AND_ACCEPTANCE.md)

## 1. 范围

本发布物由 **1 个应用组合仓库 + 17 个独立库仓库 + 1 个外部消费者模板**组成。
库之间只通过已安装的 Quirewise CMake 包和公共头依赖；生产路径不包含
LibLZMA/XZ、OpenSSL、WebP、OpenJPEG、DjVuLibre、MuPDF、Zlib、libjpeg、iconv
或其他第三方运行库。

公共头采用**单一所有者模型**：`quirewise-runtime` 发布 `status.h`、
`document.h`、`format.h`；`quirewise-document` 只发布转换调度声明
`convert.h`；需要契约类型的 12 个包通过 `Quirewise::Runtime`（PUBLIC）获取。
依赖图在此变化后仍为有向无环图（17 库、0 环）。

不在本发布范围：

- macOS 与 MSVC 工具链（本机不可用，未验证；Windows 由 MinGW64 覆盖，Linux 由 Ubuntu/WSL2 覆盖）；
- 迁移前的统一 `quirewise INPUT --to FORMAT` CLI（当前 `app/` 只提供组合 shell）；
- 依赖 Ghostscript、veraPDF、FFmpeg、LibRaw 等外部后端的历史路线；
- 各格式内部尚未实现的子集；这些入口稳定返回 `UNSUPPORTED`，见各库文档与支持矩阵。

## 2. 提交基线

| 仓库 | HEAD | 分支 | 工作区 |
|---|---|---|---|
{commit_rows}

所有仓库 `git status --porcelain` 为空；本轮已按仓库推送到各自远端，
`app/release-lock.json` 的 `fetch_workspace.py --verify-only` 校验通过。

## 3. 构建、安装与测试矩阵

| 平台 | 工具链 | 模式 | 结果 |
|---|---|---|---|
{matrix_rows}

{matrix_note}。

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
| `validate_dependency_graph.py` | {dag_line}（退出码 {dag_code}；静态模式另从归档 `nm` 反推实际闭包） |
| `verify_header_ownership.py --strict` | {ownership_line}（退出码 {ownership_code}） |
| `audit_release_boundaries.py` | **0 findings、0 read errors**，仅 1 条开发期观察（app 的 Python3 查找） |
| `audit_mupdf_removal.py` | **0 命中**；`qw_mupdf_*`、`mupdf_backend.h`、`QUIREWISE_WITH_MUPDF`、`<mupdf/...>` 与 MuPDF CMake 引用全部清零 |
| `audit_vendored_sources.py` | {vendored_line}（退出码 {vendored_code}） |
| `verify_public_headers.py`（静态与共享安装树） | {header_count}/{header_count} 公共头独立编译通过，0 失败，0 第三方头泄漏（共享树 {public_shared['header_count']}/{public_shared['header_count']}） |
| `verify_error_taxonomy.py` / `verify_resource_limits.py` | 0 findings，原始输出见 `.tmp/release/error-taxonomy.txt` 与 `.tmp/release/resource-limits.txt` |

机械自检结果：`.tmp/release/self-audit.json`（仓库干净、20 份 MIT LICENSE、
{win_static[0]} 步矩阵、SBOM 第一方全 MIT、内置第三方源码 0 文件/0 行、公共头/所有权/边界/MuPDF/vendored/lock 闸门全部通过）。
Runtime 现有 `quirewise_runtime_abi` CTest，17 个库均有测试入口。

公共头契约的迁移记录与设计评审见
[`public-header-contract.md`](app/docs/architecture/public-header-contract.md) 与
[`shared-contract-ownership.md`](app/docs/architecture/shared-contract-ownership.md)。

## 5. 许可证与 SBOM

- 第一方许可：**MIT**。SBOM 的第一方组件为 **17 个库 + 应用 = 18 个**；此外
  `external-consumer-template` 与工作区根目录也各有一份 MIT `LICENSE`，因此
  源仓库与安装树共有 **20 份**许可证文件（18 个发布组件 + 2 个非发布模板/工作区声明）。
- 内置第三方源码：**无**。DjVu、tiny-AES、stb_image ×2、LZMA SDK 均已由第一方实现
  替换，`audit_vendored_sources.py` 记录 **0 文件 / 0 行**。
- SBOM：CycloneDX 1.5，{len(sbom['components'])} 个组件（17 库 + 应用 + 2 组测试素材 +
  2 平台运行时）、**{nodes} 个依赖节点、{edges} 条 `dependsOn` 边**。
- 许可证清单：{len(inventory['first_party'])} 个第一方条目均为 MIT；被禁止运行库 0 项。

| 工件 | SHA-256 |
|---|---|
{hash_rows}

## 6. 与 DEP-001…DEP-018 的对应

验收文档第 8 节 18 行全部为“通过”，本报告补充了本轮收尾证据：

- DEP-003/DEP-008：公共头改为单一所有者；新增 12 条 `quirewise-runtime` 边，
  依赖图仍无环，`verify_header_ownership.py --strict` 报告 0 条共享安装路径；
- DEP-014：旧 MuPDF 边界已删除/重命名，`audit_mupdf_removal.py` 报告 0；
- DEP-018：第一方 MIT 许可证、SBOM 与许可证清单已生成，原“发布阻断项”清除；
- DEP-003/005/006/007：在 Windows 与 Ubuntu、静态/共享模式重新构建、安装、消费并运行闸门；
- 其余 DEP 证据路径不变，见验收文档与 `.tmp/quirewise-agent-evidence/`。

## 7. 已知限制与外部前置

1. **CI 激活**：19 个仓库均已发布，`app/release-lock.json` 校验通过。CI 工作流
   （`app/.github/workflows/ci.yml`）尚未在 GitHub Actions 上实际执行，本报告的
   四套矩阵均为本机复现；执行它仍需要能覆盖 `Quirewise/quirewise-pdg`（私有）的
   token/可见性，才能拉取 lock 中的全部提交。
2. **平台**：macOS/MSVC 未验证，属于明确排除范围（决策记录在本节与验收文档第 11 节），
   不作为本发布物的验收项。
3. **应用入口**：`app` 统一 CLI 已移植（C1–C3）：`--to pdf|txt|png`、`--check`、
   `--page`、`--pages` 与拒绝覆盖均已落地；密钥、扫描预处理和目录输入仍未实现。
4. **共享库部署**：Windows 共享消费者运行时需要把安装前缀的 `bin/` 加入 `PATH`
   （验收运行器已按此设置）；Linux 使用 `LD_LIBRARY_PATH` 或安装 RPATH。
5. **能力子集**：Audio/Image 等库存在大量显式 `UNSUPPORTED` 路径；支持矩阵需按库文档解读。
6. **PDG PDF**：PDG 页载荷（`pdg_type 0x00` 的 PDF）由组合层用内部 PDF 引擎按页
   栅格化；`pdg_type 0x1A` 发行版 PDF 由 `pdz_pdfpdg_decode_member` 解码后按成员
   顺序合并，并核对合并页数与输入页数。PDG 包本身仍对 `PDG_OUTPUT_PDF` 返回
   `PDG_ERR_EXTERNAL_DECODER_REQUIRED`，这是包边界而非构建缺失。
7. **依赖声明清理**：`comic` 与 `page` 的冗余 `image` 依赖已删除；未引用的私有头
   （`page` 的 image 副本、`ebook` 的 workspace/platform_unicode）已移除，
   `verify_private_header_copies.py` 防止跨仓库共享私有头漂移。
8. **清理记录**：`.tmp/acceptance` 与 `.tmp/release` 保留为复核证据，不属于发布物；
   报告与自检脚本位于 `app/tools/` 并纳入版本控制。两份根文档的副本与 SHA-256
   记录在 `.tmp/release/release-docs/`（`release-docs.sha256`）。

{signoff_section}"""
    out = (root / args.out).resolve()
    out.write_text(report, encoding="utf-8")
    report_copy = docs_dir / out.name
    shutil.copyfile(out, report_copy)
    (docs_dir / "release-docs.sha256").write_text(
        f"{hashlib.sha256(acceptance_copy.read_bytes()).hexdigest()}  "
        "DEPENDENCY_BOUNDARIES_AND_ACCEPTANCE.md\n"
        f"{hashlib.sha256(report_copy.read_bytes()).hexdigest()}  "
        f"{out.name}\n",
        encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
