from __future__ import annotations

import argparse
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

# Local imports via sys.path adjustment if running as script
BASE = Path(__file__).resolve().parents[1]
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from wind_trader.config import ConfigManager, AppConfig
from wind_trader.dashboard import Dashboard
from wind_trader.storage import PositionStore


def parse_args(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--config", default=str(BASE / "config.yml"))
    p.add_argument("--trade-date", default=datetime.today().strftime("%Y%m%d"))
    return p.parse_args(argv)


def load_frames(config: AppConfig, trade_date: str):
    dash = Dashboard(config)
    store = PositionStore(config.paths.data_root / "trading.db")
    try:
        positions = store.list_all()
    finally:
        store.close()
    pos_df = pd.DataFrame([asdict(p) for p in positions]) if positions else pd.DataFrame()
    pend = dash.load_pending(trade_date)
    pend_df = pd.DataFrame([asdict(p) for p in pend]) if pend else pd.DataFrame()
    trades_df = dash.load_trades_df(trade_date)
    return pos_df, pend_df, trades_df


def main():
    args = parse_args(sys.argv[1:])
    cfg = ConfigManager(args.config).get()

    st.set_page_config(page_title="Wind 仪表盘", layout="wide")
    st.title("Wind 仪表盘")
    st.caption(f"交易日期：{args.trade_date}")

    pos_df, pend_df, trades_df = load_frames(cfg, args.trade_date)

    # Filters
    code_filter = st.text_input("按代码过滤（包含）", "")
    if code_filter:
        q = code_filter.lower()
        if not pos_df.empty:
            pos_df = pos_df[pos_df["code"].str.lower().str.contains(q)]
        if not pend_df.empty:
            pend_df = pend_df[pend_df["code"].str.lower().str.contains(q)]
        if trades_df is not None and not trades_df.empty:
            trades_df = trades_df[trades_df["code"].str.lower().str.contains(q)]

    # Summary
    col1, col2, col3 = st.columns(3)
    with col1:
        total_pos = 0 if pos_df.empty else len(pos_df)
        holding = 0 if pos_df.empty else int((pos_df["status"] == 1).sum())
        st.metric("持仓（持有 / 总数）", f"{holding} / {total_pos}")
    with col2:
        total_pend = 0 if pend_df.empty else len(pend_df)
        submitted = 0 if pend_df.empty else int((pend_df["status"] == "Submitted").sum())
        failed = 0 if pend_df.empty else int((pend_df["status"] == "Failed").sum())
        st.metric("待下单（已提交 / 失败）", f"{submitted} / {failed}")
    with col3:
        total_trades = 0 if (trades_df is None or trades_df.empty) else len(trades_df)
        st.metric("成交记录（行数）", f"{total_trades}")

    # Tables
    st.subheader("待下单（Pending Orders）")
    st.dataframe(pend_df, use_container_width=True)

    st.subheader("持仓（Positions）")
    st.dataframe(pos_df, use_container_width=True)

    st.subheader("成交（Trades）")
    if trades_df is not None:
        st.dataframe(trades_df, use_container_width=True)
    else:
        st.info("该日期没有交易记录 CSV。")


if __name__ == "__main__":
    main()
