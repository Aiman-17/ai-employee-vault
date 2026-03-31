"""
src/state_manager.py — Idempotent watcher state persistence.

Each watcher stores a JSON state file under VAULT_PATH/State/<watcher_name>.json.
Atomic writes (tmp-rename) prevent corruption on crash mid-write.
"""

import json
import logging
import os
import tempfile
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def _state_dir() -> Path:
    vault = os.getenv("VAULT_PATH", "")
    if not vault:
        # Graceful fallback: use a local .state/ dir so watchers still work
        # even if the vault isn't configured yet
        fallback = Path(".state")
        fallback.mkdir(exist_ok=True)
        logger.warning(
            "VAULT_PATH is not set. Storing state in %s (temporary). "
            "Set VAULT_PATH in .env and run scripts/setup_vault.py to fix this.",
            fallback.resolve(),
        )
        return fallback
    return Path(vault) / "State"


def _state_file(watcher_name: str) -> Path:
    return _state_dir() / f"{watcher_name}.json"


def load_state(watcher_name: str) -> dict:
    """
    Load persisted state for *watcher_name*.

    Returns an empty dict if no state file exists yet — first run is always safe.
    Logs a clear warning (not a crash) if the file is corrupted so the watcher
    can continue with a fresh state rather than dying.
    """
    path = _state_file(watcher_name)
    if not path.exists():
        logger.debug("No state file for %r — starting fresh.", watcher_name)
        return {}

    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        logger.debug("Loaded state for %r (%d keys).", watcher_name, len(data))
        return data
    except json.JSONDecodeError as exc:
        logger.warning(
            "State file for %r is corrupted (%s). "
            "Starting with a clean state to avoid a crash. "
            "The corrupt file is at: %s",
            watcher_name,
            exc,
            path,
        )
        return {}
    except OSError as exc:
        logger.warning(
            "Could not read state file for %r (%s). Starting fresh.",
            watcher_name,
            exc,
        )
        return {}


def save_state(watcher_name: str, state: dict) -> None:
    """
    Atomically persist *state* for *watcher_name*.

    Uses a tmp-rename pattern so a crash mid-write never leaves a half-written
    or empty state file — the previous good file survives.
    """
    dir_ = _state_dir()
    try:
        dir_.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.error(
            "Cannot create State/ directory at %s: %s. "
            "State will NOT be saved this cycle — watcher may re-process items on restart.",
            dir_,
            exc,
        )
        return

    target = _state_file(watcher_name)

    try:
        # Write to a temp file in the same directory, then atomically rename
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=dir_,
            suffix=".tmp",
            delete=False,
        ) as tmp:
            json.dump(state, tmp, ensure_ascii=False, indent=2)
            tmp_path = Path(tmp.name)

        os.replace(tmp_path, target)
        logger.debug("State saved for %r.", watcher_name)

    except OSError as exc:
        logger.error(
            "Failed to save state for %r: %s. "
            "Items processed this cycle may be duplicated on the next run.",
            watcher_name,
            exc,
        )
        # Clean up orphaned tmp file if it exists
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass
