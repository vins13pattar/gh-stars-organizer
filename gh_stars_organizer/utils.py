from __future__ import annotations

import time
from collections.abc import Callable
from functools import wraps
from threading import Lock
from typing import TypeVar

T = TypeVar("T")


class RateLimiter:
    def __init__(self, requests_per_minute: int) -> None:
        self.requests_per_minute = max(1, requests_per_minute)
        self._interval = 60.0 / self.requests_per_minute
        self._lock = Lock()
        self._last_call = 0.0

    def wait(self) -> None:
        with self._lock:
            now = time.time()
            elapsed = now - self._last_call
            if elapsed < self._interval:
                time.sleep(self._interval - elapsed)
            self._last_call = time.time()


def retry(max_attempts: int = 3, base_delay: float = 0.6) -> Callable[[Callable[..., T]], Callable[..., T]]:
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:
                    last_exception = exc
                    if attempt >= max_attempts:
                        break
                    time.sleep(base_delay * (2 ** (attempt - 1)))
            raise last_exception

        return wrapper

    return decorator

