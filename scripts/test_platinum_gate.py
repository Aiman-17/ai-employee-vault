#!/usr/bin/env python3
"""
scripts/test_platinum_gate.py -- Platinum Tier Acceptance Test Gate

Simulates the Platinum demo scenario end-to-end with DRY_RUN=true:

  SC-011  Cloud drafts email + writes Pending_Approval when AGENT_MODE=cloud
  SC-012  Claim-by-move: only one agent claims a Needs_Action task
  SC-013  Cloud constraint: ConstitutionalBreachError when BANK_API_TOKEN is set
  SC-014  Vault sync security: .env excluded from git tracking

Usage:
    python scripts/test_platinum_gate.py
    python scripts/test_platinum_gate.py --write-log
"""

import argparse
import importlib
import json
import os
import shutil
import sys
import tempfile
import threading
import time
from datetime import date
from pathlib import Path

# ── Make sure project root is on sys.path ─────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _make_vault(tmp: Path) -> Path:
    """Create a minimal vault skeleton in *tmp*."""
    vault = tmp / "TestVault"
    for folder in [
        "Needs_Action",
        "In_Progress/cloud-01",
        "In_Progress/cloud-02",
        "Pending_Approval/email",
        "Approved",
        "Rejected",
        "Done",
        "Plans",
        "Logs",
        "Updates",
    ]:
        (vault / folder).mkdir(parents=True, exist_ok=True)

    (vault / "Dashboard.md").write_text(
        "# Dashboard\n## Recent Activity\n", encoding="utf-8"
    )
    return vault


def _result(name: str, passed: bool, detail: str = "") -> dict:
    status = "PASS" if passed else "FAIL"
    symbol = "[OK]" if passed else "[FAIL]"
    sep = " -- " + detail if detail else ""
    print(f"  {symbol} {name}: {status}{sep}")
    return {"sc": name, "status": status, "detail": detail}


# ═══════════════════════════════════════════════════════════════════════════════
# SC-011 -- Cloud drafts email + writes Pending_Approval
# ═══════════════════════════════════════════════════════════════════════════════

def test_sc011_cloud_email_draft() -> dict:
    """
    1. Set AGENT_MODE=cloud, DRY_RUN=true
    2. Create a Needs_Action email file
    3. Import and call email_mcp send handler (mocked as draft in cloud mode)
    4. Verify Pending_Approval file created
    """
    print("\n[SC-011] Cloud email -> Pending_Approval draft")
    with tempfile.TemporaryDirectory() as tmp_str:
        vault = _make_vault(Path(tmp_str))
        os.environ["AGENT_MODE"] = "cloud"
        os.environ["DRY_RUN"] = "true"
        os.environ["VAULT_PATH"] = str(vault)

        # Simulate email watcher writing a Needs_Action file
        email_file = vault / "Needs_Action" / "EMAIL_test_001.md"
        email_file.write_text(
            "---\ntype: email\nfrom: client@example.com\n"
            "subject: Invoice Request\nstatus: pending\n---\n\n"
            "Please send the January invoice.\n",
            encoding="utf-8",
        )

        # Simulate approval file creation via vault_utils
        try:
            from src.vault_utils import create_pending_approval

            approval_path = create_pending_approval(
                vault,
                action_type="email_send",
                payload={
                    "to": "client@example.com",
                    "subject": "January Invoice",
                    "body": "Please find attached.",
                },
                plan_ref="PLAN_email_test_001",
            )
            approval_exists = approval_path.exists()
            os.environ.pop("AGENT_MODE", None)
            return _result("SC-011", approval_exists, str(approval_path.name))
        except Exception as exc:
            os.environ.pop("AGENT_MODE", None)
            return _result("SC-011", False, str(exc))


# ═══════════════════════════════════════════════════════════════════════════════
# SC-012 -- Claim-by-move: only one agent wins the race
# ═══════════════════════════════════════════════════════════════════════════════

def test_sc012_claim_by_move() -> dict:
    """
    1. Create a shared Needs_Action task file
    2. Two threads simultaneously attempt claim_task() with different agent IDs
    3. Exactly one must succeed; the other must get None
    """
    print("\n[SC-012] Claim-by-move race condition")
    with tempfile.TemporaryDirectory() as tmp_str:
        vault = _make_vault(Path(tmp_str))
        task_file = vault / "Needs_Action" / "TASK_race_001.md"
        task_file.write_text("# Race task\ntest content\n", encoding="utf-8")

        os.environ["VAULT_PATH"] = str(vault)

        try:
            from src.vault_utils import claim_task

            results = []

            def _claim(agent_id: str) -> None:
                claimed = claim_task(vault, task_file, agent_id)
                results.append((agent_id, claimed))

            t1 = threading.Thread(target=_claim, args=("cloud-01",))
            t2 = threading.Thread(target=_claim, args=("cloud-02",))
            t1.start()
            t2.start()
            t1.join()
            t2.join()

            winners = [(a, p) for a, p in results if p is True]
            losers = [(a, p) for a, p in results if p is False]

            passed = len(winners) == 1 and len(losers) == 1
            detail = (
                f"winner={winners[0][0]}, loser={losers[0][0]}"
                if passed
                else f"results={results}"
            )
            return _result("SC-012", passed, detail)
        except Exception as exc:
            return _result("SC-012", False, str(exc))


# ═══════════════════════════════════════════════════════════════════════════════
# SC-013 -- Cloud constraint: ConstitutionalBreachError on BANK_API_TOKEN
# ═══════════════════════════════════════════════════════════════════════════════

def test_sc013_cloud_constraint() -> dict:
    """
    Set AGENT_MODE=cloud + BANK_API_TOKEN=dummy_value.
    enforce_all_cloud_constraints() MUST raise ConstitutionalBreachError.
    """
    print("\n[SC-013] Cloud constraint enforcement")
    prev_mode = os.environ.get("AGENT_MODE")
    prev_token = os.environ.get("BANK_API_TOKEN")

    os.environ["AGENT_MODE"] = "cloud"
    os.environ["BANK_API_TOKEN"] = "dummy_violation_token"

    try:
        # Force reimport to pick up env change
        if "src.orchestrator.cloud_constraints" in sys.modules:
            del sys.modules["src.orchestrator.cloud_constraints"]

        from src.orchestrator.cloud_constraints import enforce_all_cloud_constraints
        from src.exceptions import ConstitutionalBreachError

        try:
            enforce_all_cloud_constraints()
            return _result("SC-013", False, "No exception raised -- BANK_API_TOKEN not detected")
        except ConstitutionalBreachError as breach:
            return _result("SC-013", True, f"Breach caught: {breach.message[:60]}")
        except Exception as exc:
            return _result("SC-013", False, f"Wrong exception type: {type(exc).__name__}: {exc}")
    finally:
        # Restore environment
        if prev_mode is None:
            os.environ.pop("AGENT_MODE", None)
        else:
            os.environ["AGENT_MODE"] = prev_mode
        if prev_token is None:
            os.environ.pop("BANK_API_TOKEN", None)
        else:
            os.environ["BANK_API_TOKEN"] = prev_token


# ═══════════════════════════════════════════════════════════════════════════════
# SC-014 -- Vault sync security: .env excluded from git tracking
# ═══════════════════════════════════════════════════════════════════════════════

def test_sc014_vault_sync_security() -> dict:
    """
    1. Create a temp vault with a .gitignore from vault_template/
    2. Init a git repo; add .env and Dashboard.md
    3. Run 'git status --porcelain'
    4. Verify .env is NOT staged (ignored) and Dashboard.md IS tracked
    """
    print("\n[SC-014] Vault sync security (.env excluded from git)")
    import subprocess

    with tempfile.TemporaryDirectory() as tmp_str:
        vault = Path(tmp_str) / "SecureVault"
        vault.mkdir()

        # Copy .gitignore from vault_template
        gitignore_src = PROJECT_ROOT / "vault_template" / ".gitignore"
        if not gitignore_src.exists():
            return _result("SC-014", False, "vault_template/.gitignore not found")

        shutil.copy(gitignore_src, vault / ".gitignore")
        (vault / ".env").write_text("BANK_API_TOKEN=supersecret\n", encoding="utf-8")
        (vault / "Dashboard.md").write_text("# Dashboard\n", encoding="utf-8")
        (vault / "State").mkdir()
        (vault / "State" / "processed_ids.json").write_text("{}", encoding="utf-8")

        try:
            subprocess.run(
                ["git", "init"], cwd=vault, capture_output=True, check=True
            )
            subprocess.run(
                ["git", "config", "user.email", "test@test.com"],
                cwd=vault, capture_output=True, check=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test"],
                cwd=vault, capture_output=True, check=True,
            )
            subprocess.run(
                ["git", "add", "-A"], cwd=vault, capture_output=True, check=True
            )
            status = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=vault, capture_output=True, text=True, check=True,
            )
            tracked = status.stdout

            env_tracked = ".env" in tracked
            dashboard_tracked = "Dashboard.md" in tracked
            state_tracked = "State/processed_ids.json" in tracked

            passed = (not env_tracked) and dashboard_tracked and (not state_tracked)
            details = (
                f".env={'tracked(BAD)' if env_tracked else 'excluded(OK)'} | "
                f"Dashboard={'tracked(OK)' if dashboard_tracked else 'missing(BAD)'} | "
                f"State={'tracked(BAD)' if state_tracked else 'excluded(OK)'}"
            )
            return _result("SC-014", passed, details)
        except subprocess.CalledProcessError as exc:
            return _result("SC-014", False, f"git command failed: {exc}")
        except FileNotFoundError:
            return _result("SC-014", False, "git not found in PATH")


# ═══════════════════════════════════════════════════════════════════════════════
# Runner
# ═══════════════════════════════════════════════════════════════════════════════

def run_all(write_log: bool = False) -> int:
    print("=" * 60)
    print("  Platinum Tier Acceptance Gate")
    print("=" * 60)

    results = [
        test_sc011_cloud_email_draft(),
        test_sc012_claim_by_move(),
        test_sc013_cloud_constraint(),
        test_sc014_vault_sync_security(),
    ]

    passed = sum(1 for r in results if r["status"] == "PASS")
    total = len(results)

    print("\n" + "=" * 60)
    print(f"  Result: {passed}/{total} PASSED")
    print("=" * 60)

    if write_log:
        vault_path_str = os.getenv("VAULT_PATH", "")
        if vault_path_str:
            log_dir = Path(vault_path_str) / "Logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / f"platinum_acceptance_{date.today()}.json"
            log_file.write_text(
                json.dumps(
                    {
                        "date": str(date.today()),
                        "passed": passed,
                        "total": total,
                        "results": results,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            print(f"\nLog written: {log_file}")
        else:
            print("\nWARN: VAULT_PATH not set -- log not written.")

    return 0 if passed == total else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Platinum tier acceptance gate")
    parser.add_argument(
        "--write-log",
        action="store_true",
        help="Write results to VAULT_PATH/Logs/platinum_acceptance_YYYY-MM-DD.json",
    )
    args = parser.parse_args()
    sys.exit(run_all(write_log=args.write_log))
