"""
tests/test_foundation.py — Smoke tests for Phase 2 foundation modules.

Run with:  uv run pytest tests/test_foundation.py -v
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


# ── Helpers ───────────────────────────────────────────────────────────────────

def tmp_vault(tmp_path: Path) -> Path:
    """Create a minimal vault structure inside tmp_path."""
    for d in ("State", "Logs", "Needs_Action", "In_Progress/test_agent"):
        (tmp_path / d).mkdir(parents=True, exist_ok=True)
    return tmp_path


# ── state_manager ─────────────────────────────────────────────────────────────

class TestStateManager:
    def test_roundtrip(self, tmp_path):
        """Saved state can be loaded back unchanged."""
        with patch.dict(os.environ, {"VAULT_PATH": str(tmp_path)}):
            from src import state_manager

            state = {"processed_ids": ["abc", "def"], "count": 3}
            state_manager.save_state("test_watcher", state)
            loaded = state_manager.load_state("test_watcher")
            assert loaded["processed_ids"] == ["abc", "def"]
            assert loaded["count"] == 3

    def test_missing_file_returns_empty(self, tmp_path):
        """Loading a non-existent state file returns {} without crashing."""
        with patch.dict(os.environ, {"VAULT_PATH": str(tmp_path)}):
            from src import state_manager

            result = state_manager.load_state("nonexistent_watcher")
            assert result == {}

    def test_corrupted_file_returns_empty(self, tmp_path):
        """A corrupted JSON file is handled gracefully — no crash."""
        with patch.dict(os.environ, {"VAULT_PATH": str(tmp_path)}):
            from src import state_manager

            state_dir = tmp_path / "State"
            state_dir.mkdir(exist_ok=True)
            (state_dir / "bad_watcher.json").write_text("not valid json{{{")

            result = state_manager.load_state("bad_watcher")
            assert result == {}


# ── retry_handler ─────────────────────────────────────────────────────────────

class TestRetryHandler:
    def test_succeeds_first_try(self):
        from src.retry_handler import with_retry

        calls = []

        @with_retry(max_attempts=3)
        def always_ok():
            calls.append(1)
            return "ok"

        assert always_ok() == "ok"
        assert len(calls) == 1

    def test_retries_on_network_error(self):
        from src.exceptions import NetworkError
        from src.retry_handler import with_retry

        calls = []

        @with_retry(max_attempts=3, base_delay=0)
        def flaky():
            calls.append(1)
            if len(calls) < 3:
                raise NetworkError("timeout")
            return "recovered"

        assert flaky() == "recovered"
        assert len(calls) == 3

    def test_does_not_retry_auth_error(self):
        from src.exceptions import AuthExpiredError
        from src.retry_handler import with_retry

        calls = []

        @with_retry(max_attempts=3, base_delay=0)
        def auth_fail():
            calls.append(1)
            raise AuthExpiredError("token expired")

        with pytest.raises(AuthExpiredError):
            auth_fail()

        assert len(calls) == 1  # No retry

    def test_gives_up_after_max_attempts(self):
        from src.exceptions import NetworkError
        from src.retry_handler import with_retry

        calls = []

        @with_retry(max_attempts=3, base_delay=0)
        def always_fails():
            calls.append(1)
            raise NetworkError("always down")

        with pytest.raises(NetworkError):
            always_fails()

        assert len(calls) == 3


# ── audit_logger ──────────────────────────────────────────────────────────────

class TestAuditLogger:
    def test_writes_json_entry(self, tmp_path):
        """log_action creates a log file with a valid JSON line."""
        with patch.dict(os.environ, {"VAULT_PATH": str(tmp_path)}):
            # Re-import to pick up patched env
            import importlib
            from src.audit import audit_logger as al
            importlib.reload(al)

            al.log_action(
                action_type="email_send",
                actor="test_actor",
                target="user@example.com",
                parameters={"subject": "Hello"},
                result="success",
            )

            log_files = list((tmp_path / "Logs").glob("*.json"))
            assert len(log_files) == 1

            entries = [json.loads(line) for line in log_files[0].read_text().splitlines() if line.strip()]
            assert len(entries) == 1
            entry = entries[0]
            assert entry["action_type"] == "email_send"
            assert entry["actor"] == "test_actor"
            assert entry["result"] == "success"

    def test_does_not_crash_on_bad_vault_path(self, tmp_path):
        """If the log directory can't be created, log_action logs to stderr — no crash."""
        with patch.dict(os.environ, {"VAULT_PATH": "/nonexistent/path/xyz123"}):
            import importlib
            from src.audit import audit_logger as al
            importlib.reload(al)

            # Should not raise
            al.log_action("test", "actor", "target")


# ── vault_utils: claim_task ───────────────────────────────────────────────────

class TestVaultUtils:
    def test_claim_task_atomic(self, tmp_path):
        """First claim succeeds; second claim on the same file returns False."""
        vault = tmp_vault(tmp_path)
        task = vault / "Needs_Action" / "task_001.md"
        task.write_text("# Task")

        with patch.dict(os.environ, {"VAULT_PATH": str(vault)}):
            from src import vault_utils

            first = vault_utils.claim_task(vault, task, "agent_a")
            second = vault_utils.claim_task(vault, task, "agent_b")

            assert first is True
            assert second is False
            assert (vault / "In_Progress" / "agent_a" / "task_001.md").exists()

    def test_create_pending_approval(self, tmp_path):
        """create_pending_approval writes a well-formed approval card."""
        vault = tmp_vault(tmp_path)

        with patch.dict(os.environ, {"VAULT_PATH": str(vault)}):
            from src import vault_utils

            path = vault_utils.create_pending_approval(
                vault,
                action_type="payment",
                payload={"amount": "$500", "recipient": "Client A"},
            )

            assert path.exists()
            content = path.read_text()
            assert "type: approval_request" in content
            assert "amount" in content
            assert "Approved/" in content
