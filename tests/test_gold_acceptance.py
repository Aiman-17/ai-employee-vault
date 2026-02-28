"""
tests/test_gold_acceptance.py — Gold tier acceptance tests (SC-007, SC-008, SC-009).

SC-007: CEO Briefing — generate_briefing() produces a valid Briefings/YYYY-MM-DD_Monday_Briefing.md
        within the reporting period, containing all required sections and subscription cards.

SC-008: Ralph Wiggum Stop hook — when a task state file exists in In_Progress/claude/
        and the corresponding Done/ file is absent, the hook blocks exit (returns 1).

SC-009: Ralph Wiggum completion — when the Done/ file is present, the hook allows exit (returns 0).

These tests run fully offline using a temporary vault; no real credentials are required.

Usage:
    uv run pytest tests/test_gold_acceptance.py -v
"""

import importlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_vault(tmp_path: Path) -> Path:
    """Create a minimal vault structure for testing."""
    (tmp_path / "Done").mkdir(parents=True)
    (tmp_path / "In_Progress" / "claude").mkdir(parents=True)
    (tmp_path / "Briefings").mkdir(parents=True)
    (tmp_path / "Accounting").mkdir(parents=True)
    (tmp_path / "Pending_Approval").mkdir(parents=True)
    (tmp_path / "State").mkdir(parents=True)

    # Business_Goals.md — monthly goal $5,000, MTD $1,500
    (tmp_path / "Business_Goals.md").write_text(
        "# Business Goals\n\nMonthly goal: $5000\nCurrent MTD: $1500\n",
        encoding="utf-8",
    )

    # Accounting/Current_Month.md — two transactions in the past week
    today = date.today()
    tx1 = (today - timedelta(days=3)).isoformat()
    tx2 = (today - timedelta(days=1)).isoformat()
    (tmp_path / "Accounting" / "Current_Month.md").write_text(
        "| Date | Amount | Description |\n"
        "|------|--------|-------------|\n"
        f"| {tx1} | 500.00 | Client A payment |\n"
        f"| {tx2} | 250.00 | Client B deposit |\n",
        encoding="utf-8",
    )

    # Done/ — one task completed this week
    done_file = tmp_path / "Done" / "PLAN_invoice_client_a.md"
    done_file.write_text("# Invoice Client A\n\nCompleted.\n", encoding="utf-8")

    return tmp_path


# ---------------------------------------------------------------------------
# SC-007: CEO Briefing
# ---------------------------------------------------------------------------

class SC007CEOBriefingTest:
    """
    SC-007: generate_briefing() produces a valid Monday Briefing Markdown file
    within 5 seconds for a small vault.

    PASS: Briefings/YYYY-MM-DD_Monday_Briefing.md is created and contains
          all mandatory sections with non-empty content.
    """

    def test_briefing_file_created(self, tmp_path):
        """Briefing file appears in Briefings/ after generate_briefing()."""
        vault = _make_vault(tmp_path)
        os.environ["VAULT_PATH"] = str(vault)
        os.environ["DRY_RUN"] = "true"  # skip subscription card writes

        from src.audit.ceo_briefing import generate_briefing

        period_end = date.today()
        period_start = period_end - timedelta(days=7)

        briefing_path = generate_briefing(vault, period_start, period_end)

        assert briefing_path.exists(), (
            f"[SC-007 FAIL] Briefing file not found: {briefing_path}"
        )
        assert briefing_path.suffix == ".md", "[SC-007 FAIL] Briefing file must be .md"
        assert briefing_path.parent.name == "Briefings", (
            "[SC-007 FAIL] Briefing must be inside Briefings/"
        )

    def test_briefing_required_sections(self, tmp_path):
        """Generated briefing contains all mandatory sections."""
        vault = _make_vault(tmp_path)
        os.environ["VAULT_PATH"] = str(vault)
        os.environ["DRY_RUN"] = "true"

        from src.audit.ceo_briefing import generate_briefing

        period_end = date.today()
        period_start = period_end - timedelta(days=7)

        briefing_path = generate_briefing(vault, period_start, period_end)
        text = briefing_path.read_text(encoding="utf-8")

        required_sections = [
            "# Monday Morning CEO Briefing",
            "## Executive Summary",
            "## Revenue",
            "## Completed Tasks",
            "## Bottlenecks",
            "## Cost Optimization",
        ]
        for section in required_sections:
            assert section in text, f"[SC-007 FAIL] Missing section: '{section}'"

    def test_briefing_contains_revenue_data(self, tmp_path):
        """Briefing revenue section shows parsed transaction total."""
        vault = _make_vault(tmp_path)
        os.environ["VAULT_PATH"] = str(vault)
        os.environ["DRY_RUN"] = "true"

        from src.audit.ceo_briefing import generate_briefing

        period_end = date.today()
        period_start = period_end - timedelta(days=7)

        briefing_path = generate_briefing(vault, period_start, period_end)
        text = briefing_path.read_text(encoding="utf-8")

        # The two transactions sum to 750.00
        assert "750.00" in text, (
            "[SC-007 FAIL] Expected revenue $750.00 not found in briefing."
        )

    def test_briefing_yaml_frontmatter(self, tmp_path):
        """Briefing starts with YAML frontmatter containing generated and period fields."""
        vault = _make_vault(tmp_path)
        os.environ["VAULT_PATH"] = str(vault)
        os.environ["DRY_RUN"] = "true"

        from src.audit.ceo_briefing import generate_briefing

        briefing_path = generate_briefing(vault, date.today() - timedelta(7), date.today())
        text = briefing_path.read_text(encoding="utf-8")

        assert text.startswith("---"), "[SC-007 FAIL] Briefing must start with YAML front-matter."
        assert "generated:" in text, "[SC-007 FAIL] Missing 'generated:' in front-matter."
        assert "period:" in text, "[SC-007 FAIL] Missing 'period:' in front-matter."

    def test_subscription_card_written_when_dry_run_false(self, tmp_path):
        """When DRY_RUN=false, subscription cards are written for flagged transactions."""
        vault = _make_vault(tmp_path)
        os.environ["VAULT_PATH"] = str(vault)
        os.environ["DRY_RUN"] = "false"

        # Add a transaction that matches a known subscription pattern
        today = date.today()
        acct_file = vault / "Accounting" / "Current_Month.md"
        existing = acct_file.read_text(encoding="utf-8")
        acct_file.write_text(
            existing + f"| {today.isoformat()} | -15.00 | notion.so monthly charge |\n",
            encoding="utf-8",
        )

        from src.audit.ceo_briefing import generate_briefing

        generate_briefing(vault, today - timedelta(7), today)

        approval_dir = vault / "Pending_Approval"
        subscription_cards = list(approval_dir.glob("SUBSCRIPTION_notion_*.md"))
        assert subscription_cards, (
            "[SC-007 FAIL] Expected SUBSCRIPTION_notion_*.md in Pending_Approval/ "
            "but none were found."
        )

        # Validate card content
        card_text = subscription_cards[0].read_text(encoding="utf-8")
        assert "type: subscription_review" in card_text, (
            "[SC-007 FAIL] Card missing 'type: subscription_review'."
        )
        assert "status: pending" in card_text, (
            "[SC-007 FAIL] Card missing 'status: pending'."
        )


# ---------------------------------------------------------------------------
# SC-008 / SC-009: Ralph Wiggum Stop hook
# ---------------------------------------------------------------------------

class SC008SC009RalphWiggumTest:
    """
    SC-008: Stop hook blocks exit (exit code 1) when a task state file exists
            in In_Progress/claude/ and the corresponding Done/ file is absent.

    SC-009: Stop hook allows exit (exit code 0) when the task's Done/ marker
            file is present, cleaning up the state file.
    """

    def _write_state(self, vault: Path, task_name: str, prompt: str, iteration: int = 0) -> Path:
        """Write a task state JSON file to In_Progress/claude/."""
        state_dir = vault / "In_Progress" / "claude"
        state_dir.mkdir(parents=True, exist_ok=True)
        state_file = state_dir / f"{task_name}.json"
        state_file.write_text(
            json.dumps({"task_name": task_name, "prompt": prompt, "iteration": iteration}),
            encoding="utf-8",
        )
        return state_file

    def _run_hook(self, vault: Path) -> subprocess.CompletedProcess:
        """Run the Stop hook as a subprocess and return the result."""
        hook_path = Path(__file__).parent.parent / ".claude" / "hooks" / "stop.py"
        return subprocess.run(
            [sys.executable, str(hook_path)],
            capture_output=True,
            text=True,
            env={**os.environ, "VAULT_PATH": str(vault), "MAX_ITERATIONS": "10"},
        )

    def test_sc008_hook_blocks_when_task_in_progress(self, tmp_path):
        """
        SC-008 PASS: Hook returns exit code 1 and re-injects the prompt when
        the task state file exists but Done/ marker is absent.
        """
        vault = _make_vault(tmp_path)
        task_name = "TEST_TASK.md"
        prompt = "Continue working on TEST_TASK until complete."

        self._write_state(vault, task_name, prompt, iteration=0)

        result = self._run_hook(vault)

        assert result.returncode == 1, (
            f"[SC-008 FAIL] Expected exit code 1 (block exit), got {result.returncode}.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert prompt in result.stdout, (
            f"[SC-008 FAIL] Expected re-injected prompt in stdout.\n"
            f"stdout: {result.stdout}"
        )

    def test_sc009_hook_allows_exit_when_task_done(self, tmp_path):
        """
        SC-009 PASS: Hook returns exit code 0 and removes the state file when
        the Done/ marker exists.
        """
        vault = _make_vault(tmp_path)
        task_name = "TEST_TASK.md"
        prompt = "Continue working on TEST_TASK until complete."

        state_file = self._write_state(vault, task_name, prompt, iteration=1)

        # Create the Done/ marker
        (vault / "Done" / task_name).write_text("# TEST_TASK\n\nDone.\n", encoding="utf-8")

        result = self._run_hook(vault)

        assert result.returncode == 0, (
            f"[SC-009 FAIL] Expected exit code 0 (allow exit), got {result.returncode}.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        # State file should be cleaned up
        assert not state_file.exists(), (
            f"[SC-009 FAIL] State file should be deleted after task completion: {state_file}"
        )

    def test_hook_allows_exit_when_no_active_task(self, tmp_path):
        """Hook returns 0 immediately when no state files exist in In_Progress/claude/."""
        vault = _make_vault(tmp_path)
        result = self._run_hook(vault)
        assert result.returncode == 0, (
            f"[SC-008/SC-009] Expected exit code 0 (no active task), got {result.returncode}."
        )

    def test_hook_allows_exit_at_max_iterations(self, tmp_path):
        """Hook returns 0 (not 1) when iteration ceiling is reached, preventing infinite loops."""
        vault = _make_vault(tmp_path)
        task_name = "RUNAWAY_TASK.md"

        # Set iteration to MAX_ITERATIONS (so iteration+1 > MAX_ITERATIONS)
        self._write_state(vault, task_name, "Keep going.", iteration=10)

        result = subprocess.run(
            [sys.executable, str(Path(__file__).parent.parent / ".claude" / "hooks" / "stop.py")],
            capture_output=True,
            text=True,
            env={**os.environ, "VAULT_PATH": str(vault), "MAX_ITERATIONS": "10"},
        )
        assert result.returncode == 0, (
            f"[SC-009] Hook must allow exit at MAX_ITERATIONS ceiling to prevent infinite loop. "
            f"Got exit code {result.returncode}."
        )

    def test_hook_increments_iteration_counter(self, tmp_path):
        """State file iteration counter is incremented on each block."""
        vault = _make_vault(tmp_path)
        task_name = "COUNTER_TASK.md"

        state_file = self._write_state(vault, task_name, "Keep working.", iteration=2)

        self._run_hook(vault)

        updated = json.loads(state_file.read_text(encoding="utf-8"))
        assert updated["iteration"] == 3, (
            f"[SC-008] Expected iteration=3 after one hook call, got {updated['iteration']}."
        )
