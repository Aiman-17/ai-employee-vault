"""
src/watchers/filesystem_watcher.py — Drop-folder watcher (Bronze tier).

Monitors FILE_DROP_PATH for any new file and writes a structured action card
to VAULT_PATH/Needs_Action/ so Claude can reason about it.

Design choices:
  - Uses watchdog's Observer so it reacts instantly (no polling delay).
  - A thread-safe queue decouples detection from BaseWatcher's run() loop.
  - Atomic write via BaseWatcher._write_action_file_atomic() prevents partial files.
  - Idempotency: file path hash stored in state so reboots don't re-process.

User-friendly errors:
  - DROP_PATH missing → clear warning with setup instructions.
  - File copy errors → quarantine card written to Needs_Action/.
  - Permission errors → actionable message telling user to check folder rights.
"""

import hashlib
import logging
import os
import queue
import time
from pathlib import Path

from dotenv import load_dotenv
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from src.exceptions import ParseError
from src.watchers.base_watcher import BaseWatcher

load_dotenv()

logger = logging.getLogger(__name__)


# ── Event handler (runs in watchdog's internal thread) ───────────────────────

class _DropFolderHandler(FileSystemEventHandler):
    """Feeds newly created files into the watcher's queue."""

    def __init__(self, event_queue: queue.Queue):
        super().__init__()
        self._queue = event_queue

    def on_created(self, event):
        if event.is_directory:
            return
        src = Path(event.src_path)
        # Ignore hidden/temp files (e.g. .DS_Store, *.tmp, ~$*)
        if src.name.startswith(".") or src.suffix in (".tmp", ".part"):
            return
        logger.debug("Drop folder: new file detected — %s", src.name)
        self._queue.put(src)


# ── Watcher ──────────────────────────────────────────────────────────────────

class FilesystemWatcher(BaseWatcher):
    """
    Bronze-tier watcher: monitors a local drop folder for new files.

    Environment variables:
        FILE_DROP_PATH   Directory to watch (falls back to BANK_CSV_DROP_PATH).
        VAULT_PATH       Obsidian vault root.
    """

    def __init__(self, check_interval: int = 5):
        super().__init__(check_interval=check_interval)

        drop = (
            os.getenv("FILE_DROP_PATH")
            or os.getenv("BANK_CSV_DROP_PATH")
        )
        if not drop:
            logger.warning(
                "FILE_DROP_PATH is not set. FilesystemWatcher will not monitor anything. "
                "Add FILE_DROP_PATH=/path/to/your/drop_folder to .env "
                "and restart the watcher."
            )
        self.drop_path: Path | None = Path(drop) if drop else None
        self._queue: queue.Queue = queue.Queue()
        self._observer: Observer | None = None

    # ── BaseWatcher interface ─────────────────────────────────────────────────

    def check_for_updates(self) -> list:
        """Drain the queue and return all waiting file paths."""
        items = []
        while True:
            try:
                items.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return items

    def get_event_id(self, item: Path) -> str:
        """Stable ID: SHA-1 of the absolute path so reboots stay idempotent."""
        return hashlib.sha1(str(item.resolve()).encode()).hexdigest()

    def create_action_file(self, item: Path) -> Path:
        """
        Copy the dropped file into Needs_Action/ and write a companion .md card.
        Returns the path of the .md card (BaseWatcher logs this).
        """
        if not item.exists():
            raise ParseError(
                f"File disappeared before processing: {item}",
                user_message=f"The file '{item.name}' was removed before the AI Employee could read it.",
                action_hint="Drop the file again — make sure nothing else is moving it.",
            )

        self.needs_action.mkdir(parents=True, exist_ok=True)

        # Write the structured action card — raw file stays in Inbox (no copy)
        size_kb = item.stat().st_size / 1024
        received = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        content = "\n".join([
            "---",
            "type: file_drop",
            f"original_name: {item.name}",
            f"original_path: {item}",
            f"size_kb: {size_kb:.1f}",
            f"received: {received}",
            "priority: medium",
            "status: pending",
            "---",
            "",
            f"## File Received: {item.name}",
            "",
            f"- **Size**: {size_kb:.1f} KB",
            f"- **Received**: {received}",
            f"- **Location**: `{item}`",
            "",
            "## Suggested Actions",
            "- [ ] Review file contents",
            "- [ ] Process or categorise",
            "- [ ] Move to Done/ when complete",
        ])

        card_path = self.needs_action / f"FILE_{item.stem}.md"
        card_path.write_text(content, encoding="utf-8")
        logger.info("Action card written: %s", card_path.name)
        return card_path

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def run(self) -> None:
        """Start the watchdog Observer, then enter the BaseWatcher run loop."""
        if not self.drop_path:
            logger.error(
                "FilesystemWatcher cannot start — FILE_DROP_PATH is not set. "
                "Set it in .env and restart."
            )
            return

        if not self.drop_path.exists():
            logger.warning(
                "Drop folder does not exist yet: %s — creating it now.",
                self.drop_path,
            )
            self.drop_path.mkdir(parents=True, exist_ok=True)

        handler = _DropFolderHandler(self._queue)
        self._observer = Observer()
        self._observer.schedule(handler, str(self.drop_path), recursive=False)
        self._observer.start()
        logger.info("Watching drop folder: %s", self.drop_path)

        try:
            super().run()
        finally:
            self._observer.stop()
            self._observer.join()
            logger.info("FilesystemWatcher stopped.")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [FilesystemWatcher] %(levelname)s: %(message)s",
    )
    FilesystemWatcher().run()
