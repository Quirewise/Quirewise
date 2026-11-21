# 发布证据与快照流程

本流程把“四套平台验收矩阵（另加可选 sanitizer 矩阵）”变成可复核的发布证据，并生成发布候选报告。所有命令在
工作区根目录执行；证据文件都在 `.tmp/` 下，不属于发布物。

## 1. 前置条件

- 20 个仓库（`app`、`external-consumer-template`、18 个 `libraries/quirewise-*`）
  已提交且工作区干净。SBOM、`repository-heads.json` 与 `release-lock.json` 都记录
  提交号，脏工作区会让证据自相矛盾。
- Windows 与 WSL/Linux 都能找到 `cmake`、`ninja`、`python`、`nm`（Windows 用
  MinGW 的 `nm.exe`）。未装 Ninja 的 Linux 主机可省略，`run_acceptance.py` 会退回
  默认 Makefile 生成器。
- 19 个库仓库与 `external-consumer-template` 目前都是公开仓库（2026-11-21 用
  `git ls-remote` 不带凭据验证），因此 `QUIREWISE_REPOS_TOKEN` 已不是 workspace
  fetch 的必要条件；只有仓库重新变为私有、或 Actions 触到匿名限流时才需要配置。
- CI 的 sanitizer job 用默认构建目录 `.tmp/acceptance/linux-static/install`
  作为 `CMAKE_PREFIX_PATH`（2026-11-21 修正，此前误写为不存在的
  `.tmp/acceptance/static/install`）。

## 2. 重建四套平台矩阵（另可选 sanitizer 矩阵）

```powershell
python app/tools/run_acceptance.py --workspace . --jobs 8 `
  --summary .tmp/acceptance/windows-static/summary.json
python app/tools/run_acceptance.py --workspace . --jobs 8 --shared `
  --summary .tmp/acceptance/windows-shared/summary.json
```

```bash
python app/tools/run_acceptance.py --workspace . --jobs 8 \
  --build-dir .tmp/acceptance/linux-static \
  --summary .tmp/acceptance/linux-static/summary.json
python app/tools/run_acceptance.py --workspace . --jobs 8 --shared \
  --build-dir .tmp/acceptance/linux-shared \
  --summary .tmp/acceptance/linux-shared/summary.json
```

四套平台矩阵默认都是 85 步；sanitizer 矩阵同样按 85 步运行。`failed` 必须为空。

可选的 sanitizer 矩阵（仅 Linux/WSL）：

```bash
python app/tools/run_acceptance.py --workspace . --jobs 8 --sanitize \
  --build-dir .tmp/acceptance/linux-static-asan \
  --summary .tmp/acceptance/linux-static-asan/summary.json
```

## 3. 重新固定 release-lock

```powershell
python app/tools/write_release_lock.py --workspace .
python app/tools/fetch_workspace.py --workspace . --verify-only
```

## 4. 生成证据

```powershell
python app/tools/release_evidence.py --workspace . `
  --release-dir .tmp/release/2026-11-12 `
  --static-summary .tmp/acceptance/windows-static/summary.json `
  --shared-summary .tmp/acceptance/windows-shared/summary.json `
  --linux-static-summary .tmp/acceptance/linux-static/summary.json `
  --linux-shared-summary .tmp/acceptance/linux-shared/summary.json `
  --sanitizer-summary .tmp/acceptance/linux-static-asan/summary.json `
  --static-prefix .tmp/acceptance/windows-static/install `
  --shared-prefix .tmp/acceptance/windows-shared/install `
  --nm C:\msys64\mingw64\bin\nm.exe
```

该脚本会重新生成 SBOM、许可证清单、安装清单、公共头隔离、依赖闭包、错误分类、
资源上限、头所有权、边界/vendored/MuPDF/私有头副本闸门、消费者覆盖率、
`repository-heads.json` 与 `toolchain-*.json`。任一步失败返回非零。

## 5. 独立复核

复核者只读证据（不修改仓库），把签字原文写到快照目录：

```
.tmp/release/2026-11-12/reviewer-signoff.md
```

签字应列出：快照提交号、四套平台（及 sanitizer）矩阵步数与失败项、关键闸门输出、未验证项
（CI、macOS/MSVC）、以及签字的 SHA-256 自述。没有签字时报告会明确写“未提供
独立 sign-off”，不得对外声称已复核。

## 6. 渲染报告与机械自检

```powershell
python app/tools/render_release_report.py --workspace . `
  --release-dir .tmp/release/2026-11-12 `
  --static-prefix .tmp/acceptance/windows-static/install `
  --shared-prefix .tmp/acceptance/windows-shared/install `
  --out RELEASE_ACCEPTANCE_REPORT_2026-11-12.md

python app/tools/release_self_audit.py --workspace . `
  --release-dir .tmp/release/2026-11-12 `
  --static-prefix .tmp/acceptance/windows-static/install `
  --shared-prefix .tmp/acceptance/windows-shared/install `
  --report RELEASE_ACCEPTANCE_REPORT_2026-11-12.md `
  --require-sanitizer
```

独立复核尚未签字时，加 `--allow-pending-signoff` 只跑机械检查；结论会显示
`pending_signoff_allowed: true`，不能当作已签字发布。

## 7. Tag 与推送

只有在以下条件同时满足后才创建 tag：

1. 四套矩阵全绿，`release_self_audit.py` 在**不**带 `--allow-pending-signoff` 时
   返回 0；
2. `reviewer-signoff.md` 已存在且报告包含其 SHA-256；
3. CI 已实际执行且 `Build, test and audit` 步骤通过（见第 8 节）。

tag 名沿用 `v0.2.1-rc1` 风格，在每个仓库的同一提交上创建并推送。用工具执行，
它会把第 7 节的三个条件连同"工作区干净 / 锁一致 / HEAD 已推送 / 五套矩阵全绿"
一起复检，任一失败就拒绝打 tag：

```powershell
# 预演：只报告将会创建什么，不写任何 tag
python app/tools/tag_release.py --workspace . --version v0.3.0-rc1 `
  --release-dir .tmp/release/2026-11-21 `
  --report docs/reports/RELEASE_ACCEPTANCE_REPORT_2026-11-21.md

# 全部门禁通过后：本地创建并推送（push 失败会重试 5 次）
python app/tools/tag_release.py --workspace . --version v0.3.0-rc1 `
  --release-dir .tmp/release/2026-11-21 `
  --report docs/reports/RELEASE_ACCEPTANCE_REPORT_2026-11-21.md --push
```

手工等价命令（仅当工具不可用时）：

```powershell
git -C app tag -a v0.3.0-rc1 -m "Quirewise v0.3.0-rc1"
git -C app push origin v0.3.0-rc1
# 其余 19 个仓库同理
```

## 8. 观察 GitHub Actions

公开仓库的 run 列表与 job 步骤无需 token 即可读取：

```sh
curl -s -H "User-Agent: quirewise" \
  "https://api.github.com/repos/Quirewise/Quirewise/actions/runs?per_page=5" |
  python -c "import json,sys; [print(r['run_number'], r['head_sha'][:7], r['conclusion']) for r in json.load(sys.stdin)['workflow_runs']]"

curl -s -H "User-Agent: quirewise" \
  "https://api.github.com/repos/Quirewise/Quirewise/actions/runs/<run_id>/jobs" |
  python -c "import json,sys; [print(j['name'], j['conclusion'], [s['name'] for s in j['steps'] if s['conclusion']=='failure']) for j in json.load(sys.stdin)['jobs']]"
```

2026-11-21 的观察：推送 `app@3775a7c`、`app@c4ab034` 触发的 run #61、#62 都在
“Check out the pinned library repositories” 步骤失败——当时 `quirewise-subtitle` 的
修复提交尚未推送，`release-lock.json` 指向的提交在远端不存在。全部本地提交推送后才应
重新触发（任意 `app` 提交即可），并且在 `Build, test and audit` 与 sanitizer job 通过前
不得打 tag。

