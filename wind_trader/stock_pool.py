from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

import pandas as pd

CODE_PATTERN = re.compile(r"^\d{6}\.(SH|SZ|BJ)$", re.IGNORECASE)


@dataclass
class StockPoolLoader:
    excel_path: Path
    invalid_log_path: Path
    logger: logging.Logger = logging.getLogger("StockPoolLoader")

    def load(self) -> List[str]:
        """Load stock codes from Excel and return a clean list."""
        if not self.excel_path.exists():
            raise FileNotFoundError(f"Stock pool file not found: {self.excel_path}")
        df = pd.read_excel(self.excel_path, dtype=str, engine="openpyxl")
        if df.empty:
            self.logger.warning("Stock pool is empty: %s", self.excel_path)
            return []

        candidate_series = self._select_code_series(df)
        valid_codes: List[str] = []
        invalid_entries: List[str] = []

        for raw in candidate_series:
            normalized = self._normalize_code(raw)
            if not normalized:
                continue
            if CODE_PATTERN.match(normalized):
                valid_codes.append(normalized.upper())
            else:
                invalid_entries.append(normalized)

        self._log_invalid(invalid_entries)
        self.logger.info(
            "Loaded %s valid codes (%s invalid).",
            len(valid_codes),
            len(invalid_entries),
        )
        return valid_codes

    def _select_code_series(self, df: pd.DataFrame) -> Iterable[str]:
        code_columns = [
            col
            for col in df.columns
            if isinstance(col, str) and "code" in col.lower()
        ]
        if code_columns:
            return df[code_columns[0]].astype(str).tolist()
        # fallback to first column
        first_col = df.columns[0]
        return df[first_col].astype(str).tolist()

    def _normalize_code(self, raw: str | float | int | None) -> str | None:
        if raw is None:
            return None
        if isinstance(raw, float) and pd.isna(raw):
            return None
        code = str(raw).strip().upper()
        if not code or code in {"NAN", "NONE"}:
            return None
        return code

    def _log_invalid(self, entries: Iterable[str]) -> None:
        entries = list(entries)
        if not entries:
            return
        self.invalid_log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.invalid_log_path.open("a", encoding="utf-8") as fh:
            for entry in entries:
                fh.write(f"{entry}\n")
        self.logger.warning("Recorded %s invalid codes.", len(entries))
