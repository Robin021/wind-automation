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
    # CHO/MACHO are computed locally; do not request via WSD
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
                # Ensure trading-day series with backfilled previous value; use back-adjusted prices
                "Days=Trading;Fill=Previous;PriceAdj=B",
                usedf=True,
            ),
            attempts=3,
            delays=[1, 2, 4],
            exceptions=(WindClientError, RuntimeError),
            logger=logger,
            operation=f"wsd {code}",
        )
        df = self._parse_response(response)
        # Compute CHO/MACHO locally to avoid relying on Wind built-ins
        df = self._compute_cho_macho(df)
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

    def _compute_cho_macho(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute CHO and MACHO based on OHLCV.

        Formula (aligned with project requirements):
          MID := cumulative sum of VOLUME * (2*MATCH - HIGH - LOW) / (HIGH + LOW)
          CHO := SMA(MID, short) - SMA(MID, long)
          MACHO := SMA(CHO, n)

        MATCH is approximated using VWAP if available; otherwise CLOSE.
        """
        required = ["HIGH", "LOW", "CLOSE", "VOLUME"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            # If core columns are missing, return as-is; caller will log/handle later
            logger.warning("Missing columns for CHO/MACHO calculation: %s", ",".join(missing))
            return df

        price = df["VWAP"] if "VWAP" in df.columns else df["CLOSE"]
        high = df["HIGH"]
        low = df["LOW"]
        vol = df["VOLUME"].fillna(0.0)

        # Avoid invalid divisions; when denominator is zero or NaN, treat multiplier as 0
        denom = (high + low)
        with pd.option_context("mode.use_inf_as_na", True):
            multiplier = (2 * price - high - low) / denom
            multiplier = multiplier.fillna(0.0)
        money_flow = multiplier * vol
        mid = money_flow.cumsum()

        short_w = max(1, int(self.strategy.short))
        long_w = max(1, int(self.strategy.long))
        n_w = max(1, int(self.strategy.n))

        cho = mid.rolling(window=short_w, min_periods=1).mean() - mid.rolling(window=long_w, min_periods=1).mean()
        macho = cho.rolling(window=n_w, min_periods=1).mean()

        df["CHO"] = cho
        df["MACHO"] = macho
        return df
