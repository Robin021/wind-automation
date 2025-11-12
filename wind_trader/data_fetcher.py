from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Sequence

import pandas as pd

from .config import StrategyConfig
from .wind_client import WindClient, WindClientError
from .retry import retry_call


logger = logging.getLogger("DataFetcher")


DEFAULT_FIELDS = [
    "OPEN",
    "HIGH",
    "LOW",
    "CLOSE",
    "VOLUME",
    "TURN",
    "CHO",
    "MACHO",
]


class DataFetcher:
    """Fetch historical data from WindPy and persist to CSV."""

    def __init__(
        self,
        client: WindClient,
        strategy: StrategyConfig,
        fields: Optional[Sequence[str]] = None,
    ):
        self.client = client
        self.strategy = strategy
        self.fields = list(fields or DEFAULT_FIELDS)

    def fetch_history(
        self,
        code: str,
        days: Optional[int] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        days = days or self.strategy.min_history_days
        if end_date is None:
            end_date = datetime.today().strftime("%Y-%m-%d")
        start_date = (datetime.strptime(end_date, "%Y-%m-%d") - timedelta(days=days * 2)).strftime("%Y-%m-%d")

        logger.info("Fetching %s from %s to %s", code, start_date, end_date)
        response = retry_call(
            lambda: self.client.wsd(
                code,
                ",".join(self.fields),
                start_date,
                end_date,
                "Days=Trading;Fill=Previous",
                usedf=True,
            ),
            attempts=3,
            delays=[1, 2, 4],
            exceptions=(WindClientError, RuntimeError),
            logger=logger,
            operation=f"wsd {code}",
        )
        df = self._parse_response(response)
        df["code"] = code
        df["update_time"] = datetime.utcnow().isoformat()
        df = df.reset_index().rename(columns={"index": "date"})
        return df

    def save_history(self, df: pd.DataFrame, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            existing = pd.read_csv(path, parse_dates=["date"])
            combined = (
                pd.concat([existing, df], ignore_index=True)
                .drop_duplicates(subset=["date"])
                .sort_values("date")
            )
        else:
            combined = df.sort_values("date")
        combined.to_csv(path, index=False)
        logger.info("Saved history to %s (%s rows)", path, len(combined))

    def _parse_response(self, response):
        if isinstance(response, tuple):
            error_code, data = response
            if error_code != 0:
                raise WindClientError(f"WindPy wsd error: {error_code}")
            if isinstance(data, pd.DataFrame):
                return data
            raise WindClientError("Unexpected data type from WindPy (expected DataFrame).")
        error_code = getattr(response, "ErrorCode", None)
        if error_code and error_code != 0:
            raise WindClientError(f"WindPy wsd error: {error_code}")
        df = getattr(response, "Data", None)
        if isinstance(df, pd.DataFrame):
            return df
        raise WindClientError("Unsupported response format from WindPy.")
