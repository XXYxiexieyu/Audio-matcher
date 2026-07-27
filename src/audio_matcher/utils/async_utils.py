"""Async utility helpers."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any, Optional, TypeVar

T = TypeVar("T")


async def gather_limited(
    *coros: Coroutine[Any, Any, T],
    limit: int = 4,
    desc: Optional[str] = None,
) -> list[T | Exception]:
    """Run coroutines with a concurrency limit, returning results in order.

    Exceptions are captured and returned as values (never raised).
    """
    semaphore = asyncio.Semaphore(limit)
    total = len(coros)
    completed = 0

    async def _worker(idx: int, coro: Coroutine[Any, Any, T]) -> tuple[int, T | Exception]:
        nonlocal completed
        async with semaphore:
            try:
                result = await coro
            except Exception as exc:
                result = exc
            completed += 1
            if desc:
                from tqdm import tqdm
                # Progress is handled externally in the pipeline.
                pass
            return idx, result

    tasks = [_worker(i, c) for i, c in enumerate(coros)]

    if desc:
        from tqdm.asyncio import tqdm_asyncio
        raw_results = await tqdm_asyncio.gather(*tasks, desc=desc, total=total)
    else:
        raw_results = await asyncio.gather(*tasks)

    # Sort by original index and unwrap.
    sorted_results = sorted(raw_results, key=lambda x: x[0])
    return [r[1] for r in sorted_results]
