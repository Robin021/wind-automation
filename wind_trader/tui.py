from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Optional

import pandas as pd

from .config import AppConfig
from .dashboard import Dashboard
from .storage import PositionStore


def _load_frames(config: AppConfig, trade_date: str) -> tuple[pd.DataFrame, pd.DataFrame, Optional[pd.DataFrame]]:
    dash = Dashboard(config)
    # positions
    store = PositionStore(config.paths.data_root / "trading.db")
    try:
        positions = store.list_all()
    finally:
        store.close()
    pos_df = pd.DataFrame([asdict(p) for p in positions]) if positions else pd.DataFrame()
    # pending
    pending = dash.load_pending(trade_date)
    pend_df = pd.DataFrame([asdict(p) for p in pending]) if pending else pd.DataFrame()
    # trades
    trades_df = dash.load_trades_df(trade_date)
    return pos_df, pend_df, trades_df


def render_tui(
    config: AppConfig,
    trade_date: str,
    filter_text: str | None = None,
    max_rows: int = 30,
) -> None:
    try:
        from rich.console import Console
        from rich.table import Table
        from rich.panel import Panel
        from rich.text import Text
    except Exception:  # pragma: no cover - optional dependency
        print("'rich' not installed. Please: pip install rich")
        return

    console = Console()
    pos_df, pend_df, trades_df = _load_frames(config, trade_date)

    # Filtering
    if filter_text:
        ft = filter_text.lower()
        if not pend_df.empty:
            pend_df = pend_df[pend_df["code"].astype(str).str.lower().str.contains(ft)]
        if not pos_df.empty:
            pos_df = pos_df[pos_df["code"].astype(str).str.lower().str.contains(ft)]
        if trades_df is not None and not trades_df.empty:
            trades_df = trades_df[trades_df["code"].astype(str).str.lower().str.contains(ft)]

    # Header
    console.print(Panel.fit(Text(f"Wind TUI Dashboard {trade_date}", style="bold cyan")))

    # Summary
    total_pos = len(pos_df) if not pos_df.empty else 0
    holding = int((pos_df["status"] == 1).sum()) if not pos_df.empty else 0
    flat = int((pos_df["status"] == 0).sum()) if not pos_df.empty else 0
    pend_counts = {} if pend_df.empty else pend_df.groupby("status").size().to_dict()
    summary = Table(show_header=False, box=None)
    summary.add_row("Positions", f"total={total_pos}, holding={holding}, flat={flat}")
    summary.add_row("Pending", ", ".join([f"{k}={v}" for k, v in pend_counts.items()]) if pend_counts else "none")
    console.print(summary)

    # Pending table
    if not pend_df.empty:
        t = Table(title="Pending Orders", expand=True)
        for col in ["code", "side", "limit_price", "status", "request_id", "notes"]:
            if col in pend_df.columns:
                t.add_column(col)
        for _, row in pend_df.head(max_rows).iterrows():
            t.add_row(
                str(row.get("code", "")),
                str(row.get("side", "")),
                str(row.get("limit_price", "")),
                str(row.get("status", "")),
                str(row.get("request_id", "")),
                str(row.get("notes", "")),
            )
        console.print(t)

    # Positions table
    if not pos_df.empty:
        t = Table(title="Positions", expand=True)
        cols = ["code", "status", "hold_volume", "last_signal_time", "pending_sell_since", "update_time"]
        for col in cols:
            if col in pos_df.columns:
                t.add_column(col)
        for _, row in pos_df.head(max_rows).iterrows():
            status_val = int(row.get("status", 0)) if pd.notna(row.get("status")) else 0
            status_label = "Holding" if status_val == 1 else "Flat" if status_val == 0 else "Sold" if status_val == 2 else "Unknown"
            t.add_row(
                str(row.get("code", "")),
                status_label,
                str(row.get("hold_volume", "")),
                str(row.get("last_signal_time", "")),
                str(row.get("pending_sell_since", "")),
                str(row.get("update_time", "")),
            )
        console.print(t)

    # Trades table
    if trades_df is not None and not trades_df.empty:
        t = Table(title="Trades", expand=True)
        for col in ["code", "side", "status", "traded_price", "traded_volume", "request_id"]:
            if col in trades_df.columns:
                t.add_column(col)
        for _, row in trades_df.head(max_rows).iterrows():
            t.add_row(
                str(row.get("code", "")),
                str(row.get("side", "")),
                str(row.get("status", "")),
                str(row.get("traded_price", "")),
                str(row.get("traded_volume", "")),
                str(row.get("request_id", "")),
            )
        console.print(t)
