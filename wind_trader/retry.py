from __future__ import annotations

import logging
import time
from typing import Callable, Iterable, Sequence, Tuple, Type, TypeVar

T = TypeVar("T")


def retry_call(
    func: Callable[[], T],
    attempts: int,
    delays: Sequence[float],
    exceptions: Tuple[Type[BaseException], ...] = (Exception,),
    logger: logging.Logger | None = None,
    operation: str | None = None,
) -> T:
    """Retry helper with exponential backoff.

    Args:
        func: callable with no arguments returning result.
        attempts: max attempts.
        delays: sequence of delays (seconds). Last value reused if attempts exceed length.
        exceptions: exception tuple that should trigger retry.
        logger: optional logger for warning output.
        operation: human readable operation name.
    """

    if attempts < 1:
        raise ValueError("attempts must be >= 1")
    if not delays:
        delays = [0]

    last_exc: BaseException | None = None
    for attempt in range(1, attempts + 1):
        try:
            return func()
        except exceptions as exc:  # type: ignore
            last_exc = exc
            if attempt == attempts:
                break
            delay_idx = min(attempt - 1, len(delays) - 1)
            delay = delays[delay_idx]
            if logger:
                logger.warning(
                    "%s failed (attempt %s/%s): %s. Retrying in %.1fs",
                    operation or "Operation",
                    attempt,
                    attempts,
                    exc,
                    delay,
                )
            time.sleep(delay)
    assert last_exc is not None
    raise last_exc
