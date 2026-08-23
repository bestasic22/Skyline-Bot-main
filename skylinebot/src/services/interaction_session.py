from __future__ import annotations

import asyncio
from typing import Awaitable, Callable


class IdleTimerSession:
    """Simple idle timer to drive interactive component state machines."""

    def __init__(self, timeout_seconds: int):
        self.initial_timeout = max(int(timeout_seconds), 1)
        self.remaining = self.initial_timeout
        self.cancelled = False

    def touch(self) -> None:
        self.remaining = self.initial_timeout

    def cancel(self) -> None:
        self.cancelled = True

    async def run_until_timeout(self, on_timeout: Callable[[], Awaitable[None]]) -> None:
        while not self.cancelled:
            if self.remaining <= 0:
                await on_timeout()
                break
            await asyncio.sleep(1)
            self.remaining -= 1
