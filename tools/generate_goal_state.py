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


def work_items() -> dict:
    phases = ["M0", "M1", "M2", "M3", "M4", "M5", "M6"]
    counts = {phase: 0 for phase in phases}
    if EVIDENCE.is_dir():
        for entry in EVIDENCE.iterdir():
            match = re.match(r"^(M\d)-\d+", entry.name)
            if match and entry.is_dir():
                counts[match.group(1)] += 1
    status = {"M0": "PASS", "M1": "PASS", "M2": "PASS", "M3": "PASS",
              "M4": "PASS", "M5": "IN_PROGRESS", "M6": "IN_PROGRESS"}
    return {phase: {"evidence_items": counts[phase], "status": status[phase]}
            for phase in phases if counts[phase] or phase in ("M5", "M6")}


def main() -> int:
    if STATE.exists():
        backup = STATE.with_suffix(".json.pre-m6.bak")
        if not backup.exists():
            backup.write_bytes(STATE.read_bytes())
    data = {
        "goal_id": "QW-AUTONOMY-001",
        "status": "ACTIVE",
        "current_phase": "M6",
        "last_updated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "repositories": repositories(),
        "work_items": work_items(),
        "acceptance": acceptance(),
        "evidence_root": ".tmp/quirewise-agent-evidence",
        "blockers": [],
        "next_actions": [
            "Run the full static and shared acceptance matrix on Windows and Ubuntu.",
            "Generate the release manifest, SBOM and license inventory from the installed prefix.",
            "Record the independent reviewer sign-off and final commit hashes in the release report.",
            "Decide and document whether macOS/MSVC are in scope for this release.",
        ],
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generator": "app/tools/generate_goal_state.py",
    }
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                     encoding="utf-8")
    print(f"state written: {STATE} ({STATE.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
