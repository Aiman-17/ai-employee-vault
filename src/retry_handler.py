"""
src/retry_handler.py — Exponential backoff retry decorator.

Only retries transient errors (NetworkError, RateLimitError).
All other exceptions propagate immediately so the caller can handle them
or let the orchestrator route them to the appropriate recovery path.
"""

import time
import logging
import functools
from typing import Callable, Type

from src.exceptions import NetworkError, RateLimitError, WatcherError

logger = logging.getLogger(__name__)

# Errors that are safe to retry automatically
_RETRYABLE = (NetworkError, RateLimitError)


def with_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    retryable: tuple[Type[Exception], ...] = _RETRYABLE,
) -> Callable:
    """
    Decorator: retry the wrapped function on transient failures.

    Args:
        max_attempts:  Total attempts before giving up (default 3).
        base_delay:    Initial wait in seconds (doubles each attempt).
        max_delay:     Cap on wait time in seconds.
        retryable:     Exception types that trigger a retry.

    Behaviour:
        - Attempt 1: runs immediately.
        - On retryable error: waits base_delay * 2^(attempt-1), capped at max_delay.
        - For RateLimitError: respects `retry_after` if larger than the calculated delay.
        - After max_attempts: re-raises the last exception.
        - Non-retryable exceptions are raised immediately (no retry).
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_error: Exception | None = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)

                except retryable as exc:
                    last_error = exc
                    if attempt == max_attempts:
                        logger.error(
                            "Giving up after %d attempts on %s: %s",
                            max_attempts,
                            func.__qualname__,
                            exc.user_message if isinstance(exc, WatcherError) else exc,
                        )
                        raise

                    # Calculate wait time
                    delay = min(base_delay * (2 ** (attempt - 1)), max_delay)

                    # Honour Retry-After for rate limits
                    if isinstance(exc, RateLimitError) and exc.retry_after > delay:
                        delay = exc.retry_after

                    logger.warning(
                        "Attempt %d/%d failed for %s — retrying in %.1fs. Reason: %s",
                        attempt,
                        max_attempts,
                        func.__qualname__,
                        delay,
                        exc.user_message if isinstance(exc, WatcherError) else exc,
                    )
                    time.sleep(delay)

            raise last_error  # unreachable but satisfies type checkers

        return wrapper
    return decorator
