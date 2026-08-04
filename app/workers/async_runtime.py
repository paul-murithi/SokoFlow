import asyncio
from typing import Any, Coroutine, TypeVar

# type variable for the coroutines return value
T = TypeVar("T")

_loop: asyncio.AbstractEventLoop | None = None


def initialize() -> None:
    global _loop
    _loop = asyncio.new_event_loop()


def run(coro: Coroutine[Any, Any, T]) -> T:
    if _loop is None:
        raise RuntimeError("Worker event loop not initialized")
    return _loop.run_until_complete(coro)
