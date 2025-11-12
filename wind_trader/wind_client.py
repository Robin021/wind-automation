from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Dict, Optional

try:
    from WindPy import w as wind_api
except ImportError:  # pragma: no cover - WindPy not available on non-Windows
    wind_api = None  # type: ignore


logger = logging.getLogger("WindClient")


class WindClientError(RuntimeError):
    pass


class WindClient:
    """Thin wrapper around WindPy API with start/stop lifecycle."""

    def __init__(self, wait_time: int = 60):
        self.wait_time = wait_time
        self._connected = False

    def ensure_api(self) -> None:
        if wind_api is None:
            raise WindClientError("WindPy is not available in current environment.")

    def start(self) -> None:
        self.ensure_api()
        if not self._connected:
            wind_api.start(waitTime=self.wait_time)
            if not wind_api.isconnected():
                raise WindClientError("Failed to connect to WindPy.")
            self._connected = True
            logger.info("WindPy session started.")

    def stop(self) -> None:
        if wind_api and self._connected:
            wind_api.stop()
            self._connected = False
            logger.info("WindPy session stopped.")

    def wsd(self, *args: Any, **kwargs: Any) -> Any:
        self.ensure_api()
        return wind_api.wsd(*args, **kwargs)

    def tlogon(self, *args: Any, **kwargs: Any) -> Any:
        self.ensure_api()
        result = wind_api.tlogon(*args, **kwargs)
        self._check_response(result, "tlogon")
        return result

    def tlogout(self, *args: Any, **kwargs: Any) -> Any:
        self.ensure_api()
        result = wind_api.tlogout(*args, **kwargs)
        self._check_response(result, "tlogout")
        return result

    def torder(self, *args: Any, **kwargs: Any) -> Any:
        self.ensure_api()
        result = wind_api.torder(*args, **kwargs)
        self._check_response(result, "torder")
        return result

    def tquery(self, *args: Any, **kwargs: Any) -> Any:
        self.ensure_api()
        result = wind_api.tquery(*args, **kwargs)
        self._check_response(result, "tquery")
        return result

    @contextmanager
    def session(self) -> "WindClient":
        """Context manager ensuring start/stop lifecycle."""
        self.start()
        try:
            yield self
        finally:
            self.stop()

    def _check_response(self, result: Any, operation: str) -> None:
        error_code = getattr(result, "ErrorCode", 0)
        if error_code:
            error_msg = getattr(result, "Data", None) or getattr(result, "ErrorMsg", "")
            raise WindClientError(f"{operation} failed: {error_code} {error_msg}")
