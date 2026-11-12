#!/usr/bin/env python3
"""Rebuild the compact Quirewise agent goal state from repositories and evidence.

The previous state file grew to 2.5 MB by embedding evidence logs. This script
keeps the protocol fields but stores only pointers and status, which keeps the
file readable for the next agent/turn.
"""
from __future__ import annotations

import json
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path.cwd()
STATE = ROOT / ".tmp" / "quirewise-agent-goal-state.json"
EVIDENCE = ROOT / ".tmp" / "quirewise-agent-evidence"


def git(repo: Path, *args: str) -> str:
    completed = subprocess.run(["git", "-C", str(repo), *args],
                               capture_output=True, text=True, check=False)
    return completed.stdout.strip() if completed.returncode == 0 else ""


def repositories() -> dict:
    entries: dict[str, dict] = {}
    names = ["app", "external-consumer-template"] + [
        f"libraries/{path.name}" for path in sorted((ROOT / "libraries").glob("quirewise-*"))
    ]
    for name in names:
        repo = ROOT / name
        if not (repo / ".git").exists():
            continue
        entries[name] = {
            "branch": git(repo, "rev-parse", "--abbrev-ref", "HEAD"),
            "commit": git(repo, "rev-parse", "HEAD"),
            "status": "modified" if git(repo, "status", "--porcelain") else "clean",
        }
    return entries


def acceptance() -> dict:
    text = (ROOT / "DEPENDENCY_BOUNDARIES_AND_ACCEPTANCE.md").read_text(encoding="utf-8")
    rows = re.findall(r"\|\s*(DEP-\d{3})[^|]*\|\s*([^|]+?)\s*\|", text)
    evidence_dir = {dep: f".tmp/quirewise-agent-evidence/{dep}" for dep, _ in rows}
    return {
        dep: {
            "status": status.strip(),
            "evidence_root": evidence_dir.get(dep),
        }
        for dep, status in rows
    }


def _summary_ok(path: Path) -> bool:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return len(data.get("steps", [])) == 80 and not data.get("failed")


def work_items() -> dict:
    phases = ["M0", "M1", "M2", "M3", "M4", "M5", "M6"]
    counts = {phase: 0 for phase in phases}
    if EVIDENCE.is_dir():
        for entry in EVIDENCE.iterdir():
            match = re.match(r"^(M\d)-\d+", entry.name)
            if match and entry.is_dir():
                counts[match.group(1)] += 1

    release = ROOT / ".tmp" / "release"
    summaries = [
        release / "static-summary.json",
        release / "shared-summary.json",
        ROOT / ".tmp/acceptance/linux-static/summary.json",
        ROOT / ".tmp/acceptance/linux-shared/summary.json",
    ]
    m5_artifacts = [
        release / "static-summary.json",
        release / "shared-summary.json",
        release / "install-manifest-static.json",
        release / "install-manifest-shared.json",
        release / "sbom-static.cdx.json",
        release / "sbom-shared.cdx.json",
        release / "license-inventory-static.json",
        release / "license-inventory-shared.json",
    ]
    self_audit = release / "self-audit.json"
    self_audit_ok = False
    if self_audit.is_file():
        try:
            self_audit_ok = json.loads(
                self_audit.read_text(encoding="utf-8")).get("overall") == "PASS"
        except ValueError:
            self_audit_ok = False
    signoff = (release / "reviewer-signoff.md").is_file()
    summaries_ok = all(_summary_ok(path) for path in summaries)
    m5 = summaries_ok and all(path.is_file() for path in m5_artifacts)
    m6 = m5 and signoff and self_audit_ok

    status = {"M0": "PASS", "M1": "PASS", "M2": "PASS", "M3": "PASS",
              "M4": "PASS",
              "M5": "PASS" if m5 else "IN_PROGRESS",
              "M6": "PASS" if m6 else "IN_PROGRESS"}
    extra = {
        "M5": {"evidence_items": sum(1 for path in m5_artifacts if path.is_file()),
               "evidence": ".tmp/release/{static,shared}-summary.json; "
                           ".tmp/release/install-manifest-*.json; "
                           ".tmp/release/sbom-*.json"},
        "M6": {"evidence_items": sum(1 for path in summaries if _summary_ok(path))
                           + (1 if signoff else 0) + (1 if self_audit_ok else 0),
               "evidence": ".tmp/acceptance/linux-{static,shared}/summary.json; "
                           ".tmp/release/reviewer-signoff.md; "
                           ".tmp/release/self-audit.json"},
    }
    result = {}
    for phase in phases:
        if not counts[phase] and phase not in ("M5", "M6"):
            continue
        item = {"evidence_items": counts[phase], "status": status[phase]}
        if phase in extra:
            item.update(extra[phase])
        result[phase] = item
    return result


def main() -> int:
    if STATE.exists():
        backup = STATE.with_suffix(".json.pre-m6.bak")
        if not backup.exists():
            backup.write_bytes(STATE.read_bytes())
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    items = work_items()
    release_ready = items["M6"]["status"] == "PASS"
    data = {
        "goal_id": "QW-AUTONOMY-001",
        "status": "RELEASE_CANDIDATE" if release_ready else "IN_PROGRESS",
        "current_phase": "M6",
        "last_updated_utc": now,
        "repositories": repositories(),
        "work_items": items,
        "acceptance": acceptance(),
        "evidence_root": ".tmp/quirewise-agent-evidence",
        "blockers": [],
        "next_actions": [
            "Enable the CI workflow with a token that can read Quirewise/quirewise-pdg; the workflow has not run on Actions yet.",
            "Finish the CLI options listed as remaining in app/docs/architecture/cli-port-plan.md (keys, scan preprocessing, directory inputs).",
            "Regenerate the release evidence and acceptance report for the next candidate snapshot.",
        ],
        "generated_at_utc": now,
        "generator": "app/tools/generate_goal_state.py",
    }
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                     encoding="utf-8")
    print(f"state written: {STATE} ({STATE.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
