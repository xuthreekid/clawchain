"""重试工具"""

from __future__ import annotations

import asyncio
import random
import logging
from typing import Awaitable, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


async def retry_async(
    fn: Callable[[], Awaitable[T]],
    *,
    attempts: int = 3,
    min_delay_ms: int = 500,
    max_delay_ms: int = 5000,
    jitter: float = 0.2,
    should_retry: Callable[[Exception, int], bool] | None = None,
) -> T:
    """异步重试，指数退避 + jitter。

    - attempts=3, minDelayMs=500, maxDelayMs=5000, jitter=0.2
    - AbortError 不重试（由 should_retry 控制）
    """
    last_err: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return await fn()
        except Exception as e:
            last_err = e
            if attempt >= attempts:
                break
            if should_retry is not None and not should_retry(e, attempt):
                raise
            # AbortError 不重试
            if type(e).__name__ == "AbortError":
                raise

            delay = min(min_delay_ms * (2 ** (attempt - 1)), max_delay_ms)
            if jitter > 0:
                offset = (random.random() * 2 - 1) * jitter
                delay = max(0, int(delay * (1 + offset)))
            delay = min(max(delay, min_delay_ms), max_delay_ms)

            logger.debug(f"Retry attempt {attempt}/{attempts} after {delay}ms: {e}")
            await asyncio.sleep(delay / 1000)

    raise last_err or RuntimeError("Retry failed")
