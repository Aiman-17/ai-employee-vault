# Contract: Watcher Interface

**Branch**: `001-digital-fte-agent` | **Date**: 2026-02-22

All Watchers MUST extend `BaseWatcher` and implement the abstract methods below.
No Watcher may perform MCP actions — they are perception-only components.
All output goes to the vault via filesystem writes.

---

## BaseWatcher Abstract Interface

```python
from abc import ABC, abstractmethod
from pathlib import Path


class BaseWatcher(ABC):
    """
    Abstract base class for all Digital FTE Watchers.

    Lifecycle:
      1. __init__: load vault paths + state from /State/<name>.json
      2. run(): infinite loop — check_for_updates() → create_action_file() → sleep
      3. On crash: PM2 restarts within restart_delay; state resumes from /State/

    Contract:
      - MUST be idempotent: same event MUST NOT produce duplicate action files
      - MUST persist state to /State/<watcher_name>.json after each poll cycle
      - MUST apply exponential backoff on API errors (1s → 2s → 4s ... 60s cap)
      - MUST write ALERT file on critical failures (auth expiry, uncoverable errors)
      - MUST NOT call MCP servers
      - MUST NOT store secrets in vault files
    """

    # --- Required class attributes ---
    WATCHER_NAME: str          # e.g., "gmail_watcher"
    DEFAULT_INTERVAL: int      # poll interval in seconds

    def __init__(self, vault_path: str, check_interval: int | None = None) -> None:
        self.vault_path = Path(vault_path)
        self.needs_action = self.vault_path / "Needs_Action"
        self.state_dir = self.vault_path / "State"
        self.logs_dir = self.vault_path / "Logs"
        self.check_interval = check_interval or self.DEFAULT_INTERVAL

        # Loaded from /State/<WATCHER_NAME>.json
        self.processed_ids: set[str] = set()
        self.error_count: int = 0
        self.backoff_seconds: float = 1.0

        self._load_state()

    # --- Abstract methods (MUST implement) ---

    @abstractmethod
    def check_for_updates(self) -> list[dict]:
        """
        Poll the external source for new events.
        Returns a list of raw event dicts (source-specific format).
        Must be idempotent — filter out already-processed IDs.
        May raise: AuthExpiredError, RateLimitError, NetworkError.
        """
        pass

    @abstractmethod
    def create_action_file(self, event: dict) -> Path:
        """
        Transform one event into a vault Action Item file.
        Writes to /Needs_Action/<TYPE>_<ID>_<TS>.md atomically.
        Marks event ID as processed (add to self.processed_ids).
        Returns the absolute path of the created file.
        """
        pass

    @abstractmethod
    def get_event_id(self, event: dict) -> str:
        """
        Extract the unique source ID from an event dict.
        Used for idempotency checking.
        """
        pass

    # --- Provided concrete methods ---

    def run(self) -> None:
        """Main polling loop. Managed by PM2."""
        while True:
            try:
                events = self.check_for_updates()
                for event in events:
                    event_id = self.get_event_id(event)
                    if event_id not in self.processed_ids:
                        self.create_action_file(event)
                        self.processed_ids.add(event_id)
                self.backoff_seconds = 1.0  # reset on success
                self.error_count = 0
                self._save_state()
            except RateLimitError:
                self._handle_rate_limit()
            except AuthExpiredError:
                self._handle_auth_expiry()
            except NetworkError:
                self._handle_transient_error()
            except Exception as e:
                self._handle_critical_error(e)

            time.sleep(self.check_interval)

    def _handle_rate_limit(self) -> None:
        """Exponential backoff: 1s → 2s → 4s … 60s cap. Write ALERT. Resume automatically."""
        self.backoff_seconds = min(self.backoff_seconds * 2, 60.0)
        self._write_alert("rate_limit", severity="warning", email_sent=False)
        time.sleep(self.backoff_seconds)

    def _handle_auth_expiry(self) -> None:
        """Write CRITICAL alert + email flag. Pause polling. Human must re-authenticate."""
        self._write_alert("auth_expiry", severity="critical", email_sent=True)
        time.sleep(300)  # pause 5 min before retry check

    def _handle_transient_error(self) -> None:
        """Retry up to 3 times with 10s backoff; escalate if persistent."""
        self.error_count += 1
        if self.error_count >= 3:
            self._write_alert("watcher_crash", severity="warning", email_sent=True)
            self.error_count = 0
        time.sleep(10)

    def _handle_critical_error(self, error: Exception) -> None:
        """Unhandled exception — log + ALERT. PM2 will restart on exit."""
        self._write_alert("watcher_crash", severity="critical", email_sent=True)
        raise  # allow PM2 to restart

    def _write_alert(self, alert_type: str, severity: str, email_sent: bool) -> Path:
        """Create /Needs_Action/ALERT_<type>_<ts>.md atomically."""
        ...  # implementation required

    def _write_action_file_atomic(self, content: str, filename: str) -> Path:
        """Write to <filename>.tmp, then rename. Returns final path."""
        ...  # implementation required

    def _load_state(self) -> None:
        """Load processed_ids from /State/<WATCHER_NAME>.json."""
        ...

    def _save_state(self) -> None:
        """Write current state to /State/<WATCHER_NAME>.json atomically."""
        ...

    def _compact_state(self) -> None:
        """Remove IDs older than 30 days when processed_ids > 10,000."""
        ...
```

---

## Watcher-Specific Contracts

### GmailWatcher

```
WATCHER_NAME = "gmail_watcher"
DEFAULT_INTERVAL = 120  # seconds
Event ID source: Gmail message ID (e.g., "18a3f2e91b3c4d5e")
Output file pattern: EMAIL_<message_id[:16]>_<TS>.md
Raises: AuthExpiredError (token.json expired), RateLimitError (429)
```

### WhatsAppWatcher

```
WATCHER_NAME = "whatsapp_watcher"
DEFAULT_INTERVAL = 30  # seconds
Event ID source: chat_id + message_timestamp concatenated
Output file pattern: WHATSAPP_<chat_slug>_<TS>.md
Raises: SessionInvalidError (treated as AuthExpiredError), NetworkError
Special: On SessionInvalidError, stop polling; write wa_session_loss ALERT
```

### FilesystemWatcher

```
WATCHER_NAME = "filesystem_watcher"
DEFAULT_INTERVAL = N/A  # event-driven via watchdog.Observer
Event ID source: filepath + file modification time (inode-independent)
Output file pattern: FILE_<filename_slug>_<TS>.md
Raises: NetworkError (for remote shares)
Note: Uses watchdog.FileSystemEventHandler; run() starts Observer thread
```

### FinanceWatcher

```
WATCHER_NAME = "finance_watcher"
DEFAULT_INTERVAL = 60  # seconds (polls /Accounting/ for new .csv files)
Event ID source: CSV filename + file hash (SHA-256 first 8 bytes)
Output file pattern: FINANCE_<csv_slug>_<TS>.md
Target folder: /Accounting/
Writes parsed transactions to: /Accounting/Current_Month.md (append mode)
Raises: ParseError (malformed CSV — log, skip file, write warning)
```

---

## Custom Exceptions

```python
class WatcherError(Exception):
    """Base exception for all Watcher errors."""

class AuthExpiredError(WatcherError):
    """OAuth token or session has expired; human intervention required."""

class RateLimitError(WatcherError):
    """API rate limit hit; exponential backoff and auto-resume."""

class NetworkError(WatcherError):
    """Transient network failure; retry with backoff."""

class SessionInvalidError(AuthExpiredError):
    """WhatsApp Web session invalidated; stop polling, alert human."""

class ParseError(WatcherError):
    """Data parsing failure (e.g., malformed CSV); log and skip."""
```

---

## Idempotency Contract

Every Watcher MUST guarantee that calling `check_for_updates()` + `create_action_file()`
multiple times for the same source event produces EXACTLY ONE action file in the vault.

**Implementation requirement**:
1. On startup: load `processed_ids` set from `/State/<name>.json`
2. Before creating action file: check `event_id in self.processed_ids`
3. After creating action file: add `event_id` to set; write state file
4. State file write MUST be atomic (tmp + rename)

**Compaction**: When `len(processed_ids) > 10_000`, remove entries with timestamps
older than 30 days to prevent unbounded growth.

---

## Output File Atomicity Contract

All action files MUST be written using the tmp-rename pattern:

```python
def _write_action_file_atomic(self, content: str, filename: str) -> Path:
    final_path = self.needs_action / filename
    tmp_path = self.needs_action / f".{filename}.tmp"
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.rename(final_path)  # atomic on POSIX + NTFS
    return final_path
```

This prevents partial files from being picked up by the Orchestrator or Claude.
