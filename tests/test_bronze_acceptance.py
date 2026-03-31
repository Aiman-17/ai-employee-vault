"""
Bronze Tier Acceptance Tests — Digital FTE Agent
=================================================
Covers SC-001, SC-002, SC-003 from specs/001-digital-fte-agent/spec.md

Run:
    uv run python tests/test_bronze_acceptance.py

All tests use a *temporary* vault directory so they are safe to run without
a real Obsidian install.  VAULT_PATH in .env is NOT required; the test creates
its own temp vault.

Exit code:  0 = all PASS  |  1 = any FAIL
"""

from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

# ─── helpers ────────────────────────────────────────────────────────────────

TIMEOUT_SC001 = 60   # seconds — watcher must create action card


class Result:
    def __init__(self, sc: str) -> None:
        self.sc = sc
        self.passed = False
        self.message = ""

    def ok(self, msg: str) -> "Result":
        self.passed = True
        self.message = msg
        return self

    def fail(self, msg: str) -> "Result":
        self.passed = False
        self.message = msg
        return self

    def __str__(self) -> str:
        status = "PASS [OK]" if self.passed else "FAIL [!!]"
        return f"  [{self.sc}] {status}: {self.message}"


def _poll(condition_fn, timeout: float, interval: float = 0.5) -> bool:
    """Return True if condition_fn() becomes truthy before *timeout* seconds."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition_fn():
            return True
        time.sleep(interval)
    return False


def _yaml_front_matter(path: Path) -> dict:
    """Parse the YAML front-matter block between --- delimiters."""
    lines = path.read_text(encoding="utf-8").splitlines()
    in_block = False
    fields: dict = {}
    for line in lines:
        stripped = line.strip()
        if stripped == "---":
            if not in_block:
                in_block = True
                continue
            else:
                break
        if in_block and ":" in line:
            key, _, val = line.partition(":")
            fields[key.strip()] = val.strip()
    return fields


def _setup_vault(vault: Path) -> None:
    """Create the standard folder structure under *vault*."""
    for folder in (
        "Needs_Action", "In_Progress", "Done", "Plans",
        "Pending_Approval", "Approved", "Rejected",
        "Logs", "State", "Accounting", "Briefings", "Updates",
    ):
        (vault / folder).mkdir(parents=True, exist_ok=True)
    # Dashboard.md required by update_dashboard (it warns if missing)
    dashboard = vault / "Dashboard.md"
    dashboard.write_text(
        "# AI Employee Dashboard\n\n## Recent Activity\n",
        encoding="utf-8",
    )


# ─── SC-001: FilesystemWatcher creates an action card ───────────────────────

def run_sc001(vault: Path) -> Result:
    """
    SC-001 — Drop a .md file into FILE_DROP_PATH; within 60 s
    Needs_Action/FILE_<stem>.md must appear with correct YAML.
    """
    res = Result("SC-001")
    drop_dir = vault / "drop_inbox"
    drop_dir.mkdir(parents=True, exist_ok=True)

    # Set env vars BEFORE constructing the watcher (it reads them in __init__)
    os.environ["VAULT_PATH"] = str(vault)
    os.environ["FILE_DROP_PATH"] = str(drop_dir)
    # Use cloud mode to avoid fcntl issues on Windows
    os.environ["AGENT_MODE"] = "cloud"

    from src.watchers.filesystem_watcher import FilesystemWatcher

    watcher = FilesystemWatcher(check_interval=1)

    # Run watcher in a daemon thread so the test can continue
    t = threading.Thread(target=watcher.run, daemon=True)
    t.start()
    time.sleep(0.8)  # let watchdog Observer initialise

    # Drop the test file
    test_file = drop_dir / "test_item.md"
    test_file.write_text(
        "# Test item\nDropped by SC-001 acceptance test.\n",
        encoding="utf-8",
    )

    needs_action = vault / "Needs_Action"

    def action_card_exists() -> bool:
        if not needs_action.exists():
            return False
        return any(
            f.name.startswith("FILE_") and f.suffix == ".md"
            for f in needs_action.iterdir()
        )

    if not _poll(action_card_exists, timeout=TIMEOUT_SC001):
        watcher.stop()
        return res.fail(
            f"Needs_Action/FILE_*.md not created within {TIMEOUT_SC001}s. "
            "Check that VAULT_PATH and FILE_DROP_PATH are set correctly."
        )

    # Validate YAML front-matter
    action_cards = [
        f for f in needs_action.iterdir()
        if f.name.startswith("FILE_") and f.suffix == ".md"
    ]
    fm = _yaml_front_matter(action_cards[0])
    required_fields = {"type", "original_name", "received", "priority", "status"}
    missing = required_fields - set(fm.keys())
    if missing:
        watcher.stop()
        return res.fail(f"YAML front-matter missing fields: {missing}")

    if fm.get("type") != "file_drop":
        watcher.stop()
        return res.fail(f"Expected type=file_drop, got: {fm.get('type')!r}")

    watcher.stop()
    return res.ok(
        f"Action card '{action_cards[0].name}' created with valid YAML "
        f"(type={fm['type']}, priority={fm['priority']}) within {TIMEOUT_SC001}s"
    )


# ─── SC-002: claim_task + Plan.md + Pending_Approval created ────────────────

def run_sc002(vault: Path) -> Result:
    """
    SC-002 — Simulate the vault-monitor skill:
    Given a seeded file in Needs_Action/, use claim_task() to claim it
    atomically, then write Plan.md and Pending_Approval/.
    """
    res = Result("SC-002")
    needs_action = vault / "Needs_Action"
    plans = vault / "Plans"
    pending = vault / "Pending_Approval"
    in_progress_claude = vault / "In_Progress" / "claude"

    for d in (needs_action, plans, pending, in_progress_claude):
        d.mkdir(parents=True, exist_ok=True)

    os.environ["VAULT_PATH"] = str(vault)
    os.environ["AGENT_MODE"] = "cloud"  # avoid fcntl on Windows

    # Seed a realistic action card (as SC-001 would have produced)
    src_file = needs_action / "FILE_test_sc002.md"
    src_file.write_text(
        "---\n"
        "type: file_drop\n"
        "original_name: test_sc002.md\n"
        "size_kb: 0.1\n"
        "received: 2026-02-22T00:00:00Z\n"
        "priority: medium\n"
        "status: pending\n"
        "---\n\n"
        "## File Received: test_sc002.md\n\nTest file for SC-002.\n",
        encoding="utf-8",
    )

    from src.vault_utils import claim_task, create_pending_approval

    # Step 1 — Atomic claim (vault-monitor does this first)
    claimed = claim_task(vault, src_file, agent_id="claude")
    if not claimed:
        return res.fail("claim_task() returned False — file was not moved to In_Progress/")

    in_progress_file = in_progress_claude / "FILE_test_sc002.md"
    if not in_progress_file.exists():
        return res.fail(
            "FILE_test_sc002.md not found in In_Progress/claude/ after claim"
        )

    # Step 2 — vault-monitor writes Plan.md
    ts = time.strftime("%Y%m%d_%H%M%S")
    plan_name = f"PLAN_test_sc002_{ts}.md"
    plan_path = plans / plan_name
    plan_path.write_text(
        f"---\ncreated: {time.strftime('%Y-%m-%dT%H:%M:%SZ')}\n"
        f"status: pending_approval\nsource_file: FILE_test_sc002.md\n---\n\n"
        f"## Objective\nProcess dropped file test_sc002.md\n\n"
        f"## Steps\n- [x] Claim task\n- [ ] Approve action\n- [ ] Move to Done\n\n"
        f"## Approval Required\nFile move to Done/ requires user approval.\n",
        encoding="utf-8",
    )

    # Step 3 — vault-monitor writes Pending_Approval
    create_pending_approval(
        vault_path=vault,
        action_type="file_move",
        payload={
            "source_file": "FILE_test_sc002.md",
            "destination": "Done/",
        },
        plan_ref=plan_name,
    )

    # Verify
    plan_files = list(plans.glob("PLAN_test_sc002*.md"))
    all_approvals = list(pending.iterdir()) if pending.exists() else []

    if not plan_files:
        return res.fail("Plans/PLAN_test_sc002*.md not found")
    if not all_approvals:
        return res.fail("Pending_Approval/ is empty — approval card not created")

    return res.ok(
        f"Claim OK; Plan '{plan_files[0].name}' created; "
        f"Approval card '{all_approvals[0].name}' created"
    )


# ─── SC-003: Approved → Done + Dashboard updated ────────────────────────────

def run_sc003(vault: Path) -> Result:
    """
    SC-003 — Move an approval file into Approved/, call _process_approval()
    directly, then verify:
      - source file has moved to Done/
      - Dashboard.md or Updates/ contains an activity entry
    """
    res = Result("SC-003")

    approved_dir = vault / "Approved"
    done_dir = vault / "Done"
    in_progress_claude = vault / "In_Progress" / "claude"

    for d in (approved_dir, done_dir, in_progress_claude):
        d.mkdir(parents=True, exist_ok=True)

    os.environ["VAULT_PATH"] = str(vault)
    os.environ["AGENT_MODE"] = "cloud"  # write to Updates/ instead of fcntl lock

    # Source file already in In_Progress/ (claimed in SC-002 flow)
    source_name = "FILE_sc003_source.md"
    source_path = in_progress_claude / source_name
    source_path.write_text("# SC-003 source file\n", encoding="utf-8")

    # Write approval file directly into Approved/ (simulates user action)
    ts = time.strftime("%Y%m%d_%H%M%S")
    approval_name = f"FILE_MOVE_sc003_{ts}.md"
    approval_content = (
        "---\n"
        "type: approval_request\n"
        "action: file_move\n"
        f"source_file: {source_name}\n"
        "destination: Done/\n"
        "plan_ref: PLAN_sc003.md\n"
        "status: approved\n"
        f"created: {time.strftime('%Y-%m-%dT%H:%M:%SZ')}\n"
        "expires: 2099-12-31T00:00:00Z\n"
        "---\n\nApproved by SC-003 acceptance test.\n"
    )
    approval_path = approved_dir / approval_name
    approval_path.write_text(approval_content, encoding="utf-8")

    # Invoke ApprovalHandler synchronously (no background thread needed)
    from src.orchestrator.approval_handler import ApprovalHandler

    handler = ApprovalHandler()
    handler._process_approval(approval_path)

    # ── Check 1: source file moved to Done/
    done_files = list(done_dir.rglob(source_name))
    if not done_files:
        return res.fail(
            f"'{source_name}' not found under Done/ after approval. "
            "Check that ApprovalHandler._execute_file_move ran without errors."
        )

    # ── Check 2: Dashboard activity recorded
    # In cloud mode update_dashboard writes to Updates/ instead of Dashboard.md
    dashboard = vault / "Dashboard.md"
    updates_dir = vault / "Updates"

    dashboard_updated = (
        dashboard.exists()
        and "file_move" in dashboard.read_text(encoding="utf-8")
    )
    updates_written = (
        updates_dir.exists()
        and any(
            f.name.startswith("dashboard_update_")
            for f in updates_dir.iterdir()
        )
    )

    if not dashboard_updated and not updates_written:
        return res.fail(
            "No activity entry in Dashboard.md or Updates/ — "
            "update_dashboard() may have silently failed."
        )

    where = "Dashboard.md" if dashboard_updated else "Updates/"
    return res.ok(
        f"'{source_name}' moved to Done/; activity entry written to {where}"
    )


# ─── Main runner ────────────────────────────────────────────────────────────

def main() -> int:
    print("\n" + "=" * 64)
    print("  Digital FTE Agent — Bronze Tier Acceptance Tests")
    print("=" * 64)

    results: list[Result] = []

    with tempfile.TemporaryDirectory(prefix="fte_bronze_") as tmpdir:
        vault = Path(tmpdir) / "AI_Employee_Vault"
        vault.mkdir()
        _setup_vault(vault)

        print(f"\n  Temp vault: {vault}\n")

        # SC-001
        print("  Running SC-001: FilesystemWatcher -> Needs_Action ...")
        try:
            results.append(run_sc001(vault))
        except Exception as exc:
            r = Result("SC-001")
            results.append(r.fail(f"Unhandled exception: {exc}"))

        # SC-002
        print("  Running SC-002: claim_task + Plan.md + Pending_Approval ...")
        try:
            results.append(run_sc002(vault))
        except Exception as exc:
            r = Result("SC-002")
            results.append(r.fail(f"Unhandled exception: {exc}"))

        # SC-003
        print("  Running SC-003: Approved -> Done + Dashboard ...")
        try:
            results.append(run_sc003(vault))
        except Exception as exc:
            r = Result("SC-003")
            results.append(r.fail(f"Unhandled exception: {exc}"))

    print("\n" + "-" * 64)
    print("  Results:")
    for r in results:
        print(str(r))

    passed = sum(1 for r in results if r.passed)
    total = len(results)
    print("-" * 64)
    print(f"  {passed}/{total} passed\n")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
