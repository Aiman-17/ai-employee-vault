"""
.claude/hooks/stop.py — Ralph Wiggum Stop hook for the Digital FTE Agent.

Claude Code invokes this script when it tries to exit. This hook:
  1. Checks VAULT_PATH/In_Progress/claude/ for any active task state file.
  2. If a task state file exists AND the corresponding Done/ file does NOT exist,
     the task is still incomplete — re-inject the prompt and block exit.
  3. Increment the iteration counter in the state file.
  4. Allow exit when: counter exceeds MAX_ITERATIONS, or task moved to Done/.

State file format (VAULT_PATH/In_Progress/claude/<task_name>.json):
  {
    "task_name": "TASK_FILE.md",
    "prompt":    "Full prompt to re-inject when incomplete",
    "iteration": 0
  }

Exit codes:
  0 → Allow Claude Code to exit (task complete or max iterations reached)
  1 → Block exit and re-inject the original prompt (task still in progress)
"""

import json
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [ralph-wiggum] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────

VAULT_PATH = Path(os.getenv("VAULT_PATH", "."))
MAX_ITERATIONS = int(os.getenv("MAX_ITERATIONS", "10"))

IN_PROGRESS_DIR = VAULT_PATH / "In_Progress" / "claude"
DONE_DIR = VAULT_PATH / "Done"


def find_active_task() -> Path | None:
    """Return the first active task state file in In_Progress/claude/, or None."""
    if not IN_PROGRESS_DIR.exists():
        return None
    state_files = sorted(IN_PROGRESS_DIR.glob("*.json"))
    return state_files[0] if state_files else None


def read_state(state_file: Path) -> dict:
    """Read and parse a task state JSON file. Returns {} on error."""
    try:
        return json.loads(state_file.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Could not read state file %s: %s", state_file.name, exc)
        return {}


def write_state(state_file: Path, state: dict) -> None:
    """Persist updated task state to disk."""
    try:
        state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except Exception as exc:
        logger.warning("Could not write state file %s: %s", state_file.name, exc)


def task_is_done(state: dict) -> bool:
    """Check whether the task's done marker exists in Done/."""
    task_name = state.get("task_name", "")
    if not task_name:
        return False
    done_marker = DONE_DIR / task_name
    return done_marker.exists()


def _try_audit_log(action_type: str, target: str, parameters: dict, result: str) -> None:
    """Best-effort audit log. Silently skips if audit_logger unavailable."""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
        from src.audit import audit_logger
        audit_logger.log_action(
            action_type=action_type,
            actor="stop_hook",
            target=target,
            parameters=parameters,
            result=result,
        )
    except Exception:
        pass


def main() -> int:
    """
    Ralph Wiggum Stop hook entry point.

    Returns:
        0 — allow Claude Code to exit
        1 — block exit (re-inject prompt, keep working)
    """
    active = find_active_task()

    # No in-progress task → allow clean exit
    if active is None:
        logger.info("No active task in In_Progress/claude/ — allowing exit.")
        return 0

    state = read_state(active)
    iteration = state.get("iteration", 0) + 1
    state["iteration"] = iteration
    task_name = state.get("task_name", active.stem)
    prompt = state.get("prompt", "Continue working on the active task until it is complete.")

    # Task already moved to Done/ → allow exit
    if task_is_done(state):
        logger.info(
            "Task '%s' found in Done/ — allowing exit (completed in %d iterations).",
            task_name,
            iteration - 1,
        )
        _try_audit_log(
            action_type="ralph_wiggum_complete",
            target=task_name,
            parameters={"iterations": iteration - 1},
            result="success",
        )
        active.unlink(missing_ok=True)
        return 0

    # Max iterations ceiling reached → allow exit with warning
    if iteration > MAX_ITERATIONS:
        logger.warning(
            "Task '%s' reached MAX_ITERATIONS=%d — allowing exit to prevent infinite loop. "
            "Move the task file to Done/ to resolve this warning.",
            task_name,
            MAX_ITERATIONS,
        )
        _try_audit_log(
            action_type="ralph_wiggum_max_iterations",
            target=task_name,
            parameters={"iterations": iteration, "max": MAX_ITERATIONS},
            result="max_reached",
        )
        return 0

    # Task still in progress → update counter, re-inject prompt, block exit
    write_state(active, state)

    logger.info(
        "Task '%s' not yet in Done/ — blocking exit (iteration %d/%d). Re-injecting prompt.",
        task_name,
        iteration,
        MAX_ITERATIONS,
    )
    _try_audit_log(
        action_type="ralph_wiggum_loop",
        target=task_name,
        parameters={"iteration": iteration, "prompt_snippet": prompt[:80]},
        result="blocked",
    )

    # Print the re-injection prompt for Claude Code to pick up
    print(prompt, flush=True)
    return 1


if __name__ == "__main__":
    sys.exit(main())
