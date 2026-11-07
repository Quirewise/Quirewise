#!/usr/bin/env python3
"""Mechanical read-only self-audit of the M6 release evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(repo), *args],
                            capture_output=True, text=True, check=False)
    return result.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path,
                        default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    root = args.workspace.resolve()
    release = root / ".tmp" / "release"
    repos = [root / "app", root / "external-consumer-template"] + [
        root / "libraries" / p.name
        for p in sorted((root / "libraries").glob("quirewise-*"))
    ]
    checks: dict[str, object] = {}

    checks["repositories_clean"] = all(
        not git(repo, "status", "--porcelain") for repo in repos)
    checks["head_count"] = len(repos)
    checks["app_head"] = git(root / "app", "rev-parse", "HEAD")

    licenses = [root / "LICENSE"] + [repo / "LICENSE" for repo in repos]
    bodies = {path.read_bytes() for path in licenses if path.is_file()}
    checks["license_files"] = sum(1 for path in licenses if path.is_file())
    checks["license_identical_mit"] = (
        len(bodies) == 1 and next(iter(bodies)).startswith(b"MIT License"))
    checks["installed_licenses_static"] = sum(
        1 for _ in (root / ".tmp/acceptance/static/install/share/doc/quirewise").rglob("LICENSE"))
    checks["installed_licenses_shared"] = sum(
        1 for _ in (root / ".tmp/acceptance/shared/install/share/doc/quirewise").rglob("LICENSE"))

    summaries = {
        "windows_static": release / "static-summary.json",
        "windows_shared": release / "shared-summary.json",
        "linux_static": root / ".tmp/acceptance/linux-static/summary.json",
        "linux_shared": root / ".tmp/acceptance/linux-shared/summary.json",
    }
    checks["summaries"] = {}
    for name, path in summaries.items():
        data = json.loads(path.read_text(encoding="utf-8"))
        checks["summaries"][name] = {
            "steps": len(data["steps"]),
            "failed": data["failed"],
            "ok": not data["failed"] and len(data["steps"]) == 79,
        }

    sbom = json.loads((release / "sbom-static.cdx.json").read_text(encoding="utf-8"))
    inventory = json.loads((release / "license-inventory-static.json").read_text(encoding="utf-8"))
    checks["sbom_components"] = len(sbom["components"])
    checks["sbom_dependency_nodes"] = len(sbom["dependencies"])
    checks["sbom_depends_on_edges"] = sum(
        len(item["dependsOn"]) for item in sbom["dependencies"])
    checks["first_party_entries"] = len(inventory["first_party"])
    checks["first_party_all_mit"] = all(
        item["license"] == "MIT" for item in inventory["first_party"])
    checks["bundled_djvudec"] = any(
        item["component"] == "djvudec" and item["license"] == "MIT"
        for item in inventory["bundled"])

    manifests = {}
    for name in ["install-manifest-static.json", "install-manifest-shared.json"]:
        manifest = json.loads((release / name).read_text(encoding="utf-8"))
        manifests[name] = manifest["file_count"]
    checks["manifest_file_counts"] = manifests
    checks["manifest_recount_ok"] = (
        sum(1 for p in (root / ".tmp/acceptance/static/install").rglob("*") if p.is_file())
        == manifests["install-manifest-static.json"]
        and sum(1 for p in (root / ".tmp/acceptance/shared/install").rglob("*") if p.is_file())
        == manifests["install-manifest-shared.json"]
    )

    gate = subprocess.run(
        ["python", "app/tools/audit_mupdf_removal.py", "--workspace", "."],
        cwd=root, capture_output=True, text=True)
    checks["mupdf_gate_exit"] = gate.returncode
    checks["mupdf_gate_output"] = gate.stdout.strip()
    boundary = subprocess.run(
        ["python", "app/tools/audit_release_boundaries.py", "--workspace", "."],
        cwd=root, capture_output=True, text=True)
    checks["boundary_gate_exit"] = boundary.returncode
    checks["boundary_gate_output"] = boundary.stdout.strip()
    lock_verify = subprocess.run(
        ["python", "app/tools/fetch_workspace.py", "--workspace", ".", "--verify-only"],
        cwd=root, capture_output=True, text=True)
    checks["lock_verify_exit"] = lock_verify.returncode

    signoff = release / "reviewer-signoff.md"
    checks["reviewer_signoff"] = signoff.is_file()
    checks["reviewer_signoff_sha256"] = (
        hashlib.sha256(signoff.read_bytes()).hexdigest() if signoff.is_file() else None)
    report = root / "RELEASE_ACCEPTANCE_REPORT.md"
    if report.is_file() and signoff.is_file():
        checks["report_contains_signoff_hash"] = (
            checks["reviewer_signoff_sha256"]
            in report.read_text(encoding="utf-8"))
    else:
        checks["report_contains_signoff_hash"] = False

    checks["workflow"] = (root / "app/.github/workflows/ci.yml").is_file()
    checks["report"] = report.is_file()
    checks["app_tmp_removed"] = not (root / "app/.tmp").exists()
    checks["stray_tmp_removed"] = not (root / " .tmp").exists()
    checks["empty_to_delete_removed"] = not (root / ".to_delete").exists()
    checks["legacy_install_prefix_removed"] = not (root / ".tmp/quirewise-agent-install").exists()
    checks["evidence_build_retained"] = (root / ".tmp/quirewise-agent-build").is_dir()
    checks["runtime_ctest_present"] = any(
        "quirewise_runtime_abi" in p.read_text(encoding="utf-8", errors="replace")
        for p in (root / ".tmp/acceptance/static/logs").glob("quirewise-runtime.ctest.log"))

    ok = (
        checks["repositories_clean"]
        and checks["license_identical_mit"]
        and checks["installed_licenses_static"] == 20
        and checks["installed_licenses_shared"] == 20
        and all(item["ok"] for item in checks["summaries"].values())
        and checks["first_party_all_mit"]
        and checks["bundled_djvudec"]
        and checks["manifest_recount_ok"]
        and checks["mupdf_gate_exit"] == 0
        and checks["boundary_gate_exit"] == 0
        and checks["lock_verify_exit"] == 0
        and checks["reviewer_signoff"]
        and checks["report_contains_signoff_hash"]
        and checks["workflow"]
        and checks["report"]
        and checks["app_tmp_removed"]
        and checks["stray_tmp_removed"]
        and checks["empty_to_delete_removed"]
        and checks["legacy_install_prefix_removed"]
        and checks["evidence_build_retained"]
        and checks["runtime_ctest_present"]
    )
    checks["overall"] = "PASS" if ok else "FAIL"
    (release / "self-audit.json").write_text(
        json.dumps(checks, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    display = {k: v for k, v in checks.items() if k != "summaries"}
    print(json.dumps(display, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
