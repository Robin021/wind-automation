from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

import pandas as pd

from .config import AppConfig
from .models import PendingOrder
from .storage import PositionStore


class Dashboard:
    """Lightweight dashboard generator (console + HTML)."""

    def __init__(self, config: AppConfig):
        self.config = config

    def load_pending(self, trade_date: str) -> List[PendingOrder]:
        path = self.config.paths.pending_orders_dir / f"{trade_date}.json"
        if not path.exists():
            return []
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        return [PendingOrder(**item) for item in data]

    def load_trades_df(self, trade_date: str) -> pd.DataFrame | None:
        csv_path = self.config.paths.trades_dir / f"{trade_date}.csv"
        if not csv_path.exists():
            return None
        return pd.read_csv(csv_path)

    def build_console_summary(self, trade_date: str) -> Tuple[str, Path | None]:
        store = PositionStore(self.config.paths.data_root / "trading.db")
        try:
            positions = store.list_all()
        finally:
            store.close()

        pos_df = pd.DataFrame([asdict(p) for p in positions]) if positions else pd.DataFrame()
        pending = self.load_pending(trade_date)
        pend_df = pd.DataFrame([asdict(p) for p in pending]) if pending else pd.DataFrame()
        trades_df = self.load_trades_df(trade_date)

        lines: List[str] = []
        lines.append(f"=== Dashboard {trade_date} ===")

        # Positions summary
        total_pos = len(pos_df) if not pos_df.empty else 0
        holding = int((pos_df["status"] == 1).sum()) if not pos_df.empty else 0
        flat = int((pos_df["status"] == 0).sum()) if not pos_df.empty else 0
        lines.append(f"Positions: total={total_pos}, holding={holding}, flat={flat}")

        # Pending orders summary
        total_pend = len(pend_df) if not pend_df.empty else 0
        if total_pend:
            by_status = pend_df.groupby("status").size().to_dict()
        else:
            by_status = {}
        lines.append(
            "Pending orders: "
            + (", ".join([f"{k}={v}" for k, v in by_status.items()]) if by_status else "none")
        )

        # Needs check: failed orders + positions with pending_sell_since
        needs_check_codes: List[str] = []
        if not pend_df.empty:
            needs_check_codes += pend_df.loc[pend_df["status"] == "Failed", "code"].astype(str).tolist()
        if not pos_df.empty:
            needs_check_codes += pos_df.loc[pos_df["pending_sell_since"].notna(), "code"].astype(str).tolist()
        needs_check_codes = sorted(list(dict.fromkeys(needs_check_codes)))
        if needs_check_codes:
            lines.append("Needs check: " + ", ".join(needs_check_codes[:10]) + (" ..." if len(needs_check_codes) > 10 else ""))
        else:
            lines.append("Needs check: none")

        # Top tables (limited rows for console)
        if not pend_df.empty:
            view = pend_df[["code", "side", "limit_price", "status", "request_id"]].head(10)
            lines.append("\nPending (top 10):\n" + view.to_string(index=False))
        if not pos_df.empty:
            view = pos_df[["code", "status", "hold_volume", "last_signal_time", "pending_sell_since"]].head(10)
            lines.append("\nPositions (top 10):\n" + view.to_string(index=False))
        if trades_df is not None and not trades_df.empty:
            view = trades_df[["code", "side", "status", "traded_volume", "traded_price"]].head(10)
            lines.append("\nTrades (top 10):\n" + view.to_string(index=False))

        # Also write HTML report
        html_path = self.write_html(trade_date, pos_df, pend_df, trades_df)
        lines.append(f"\nHTML report: {html_path}")
        return "\n".join(lines), html_path

    def write_html(
        self,
        trade_date: str,
        pos_df: pd.DataFrame,
        pend_df: pd.DataFrame,
        trades_df: pd.DataFrame | None,
    ) -> Path:
        self.config.paths.reports_dir.mkdir(parents=True, exist_ok=True)
        html_path = self.config.paths.reports_dir / f"dashboard_{trade_date}.html"
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        def _status_tag(text: str, kind: str) -> str:
            return f"<span class='tag status-{kind}'>{text}</span>"

        def _decorate_pending(df: pd.DataFrame) -> pd.DataFrame:
            if df is None or df.empty:
                return df
            df = df.copy()
            df["status"] = df["status"].fillna("")
            df["status"] = df["status"].apply(lambda s: _status_tag(s, s.lower() or "unknown"))
            cols = ["code", "side", "limit_price", "status", "request_id", "notes"]
            return df[[c for c in cols if c in df.columns]]

        def _decorate_positions(df: pd.DataFrame) -> pd.DataFrame:
            if df is None or df.empty:
                return df
            df = df.copy()
            def map_status(x: int | float | str) -> str:
                try:
                    v = int(x)
                except Exception:
                    return _status_tag("Unknown", "unknown")
                label = "Holding" if v == 1 else "Flat" if v == 0 else "Sold" if v == 2 else "Unknown"
                kind = label.lower()
                return _status_tag(label, kind)

            df["status"] = df["status"].apply(map_status)
            cols = ["code", "status", "hold_volume", "last_signal_time", "pending_sell_since", "update_time"]
            return df[[c for c in cols if c in df.columns]]

        def _decorate_trades(df: pd.DataFrame | None) -> pd.DataFrame | None:
            if df is None or df.empty:
                return df
            df = df.copy()
            df["status"] = df["status"].astype(str)
            df["status"] = df["status"].apply(lambda s: _status_tag(s, ("ok" if s.lower().startswith("success") else "warn" if s.lower().startswith("queryerror") else s.lower())))
            cols = ["code", "side", "status", "traded_price", "traded_volume", "request_id"]
            return df[[c for c in cols if c in df.columns]]

        def section(title: str, df: pd.DataFrame | None) -> str:
            if df is None or df.empty:
                return f"<h2>{title}</h2><p>No data</p>"
            # Mark tables filterable and allow HTML contents in cells
            return f"<h2>{title}</h2>" + df.to_html(index=False, border=0, classes=["table", "filterable"], escape=False)

        styles = """
        <style>
        body { font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Helvetica, Arial, sans-serif; margin: 24px; }
        h1 { font-size: 20px; }
        h2 { font-size: 16px; margin-top: 24px; }
        .meta { color: #666; font-size: 12px; }
        table.table { border-collapse: collapse; width: 100%; }
        table.table th, table.table td { border: 1px solid #ddd; padding: 6px 8px; }
        table.table th { background: #f6f8fa; text-align: left; }
        .controls { margin: 12px 0 20px; }
        .tag { display: inline-block; padding: 2px 6px; border-radius: 999px; font-size: 12px; }
        .status-pending { background:#fff7e6; color:#ad6800; border:1px solid #ffd591; }
        .status-submitted, .status-ok { background:#f6ffed; color:#237804; border:1px solid #b7eb8f; }
        .status-failed, .status-warn { background:#fff1f0; color:#a8071a; border:1px solid #ffa39e; }
        .status-unknown { background:#f0f0f0; color:#595959; border:1px solid #d9d9d9; }
        </style>
        """

        summary_rows = []
        if not pos_df.empty:
            summary_rows.append({
                "metric": "positions_total",
                "value": len(pos_df),
            })
            summary_rows.append({
                "metric": "positions_holding",
                "value": int((pos_df["status"] == 1).sum()),
            })
            summary_rows.append({
                "metric": "positions_flat",
                "value": int((pos_df["status"] == 0).sum()),
            })
        if not pend_df.empty:
            for k, v in pend_df.groupby("status").size().to_dict().items():
                summary_rows.append({"metric": f"pending_{k}", "value": int(v)})
        summary_df = pd.DataFrame(summary_rows) if summary_rows else pd.DataFrame(columns=["metric", "value"])

        # Decorate dataframes for nicer rendering
        pend_view = _decorate_pending(pend_df)
        pos_view = _decorate_positions(pos_df)
        trade_view = _decorate_trades(trades_df)

        html = [
            "<html><head><meta charset='utf-8'>",
            styles,
            "</head><body>",
            f"<h1>Wind Dashboard {trade_date}</h1>",
            f"<div class='meta'>Generated at {ts}</div>",
            "<div class='controls'><label>Filter by code: <input id='filter' type='search' placeholder='e.g. 600000.SH' oninput='filterTables()'></label></div>",
            section("Summary", summary_df),
            section("Pending Orders", pend_view),
            section("Positions", pos_view),
            section("Trades", trade_view),
            "<script>\nfunction filterTables(){\n  const q=(document.getElementById('filter').value||'').toLowerCase();\n  document.querySelectorAll('table.filterable').forEach(tbl=>{\n    const rows=tbl.tBodies[0]?Array.from(tbl.tBodies[0].rows):[];\n    rows.forEach(r=>{\n      const code=(r.cells[0]?.textContent||'').toLowerCase();\n      r.style.display = code.includes(q) ? '' : 'none';\n    });\n  });\n}\n</script>",
            "</body></html>",
        ]
        with html_path.open("w", encoding="utf-8") as fh:
            fh.write("\n".join(html))
        return html_path
