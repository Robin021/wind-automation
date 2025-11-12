from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional


@dataclass
class Position:
    code: str
    status: int
    hold_volume: int = 0
    last_buy_price: Optional[float] = None
    last_sell_price: Optional[float] = None
    pending_sell_since: Optional[str] = None
    last_signal_time: Optional[str] = None
    update_time: Optional[str] = None


class PositionStore:
    """Lightweight SQLite storage for position state."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._ensure_schema()

    def close(self) -> None:
        if self._conn:
            self._conn.close()

    def _ensure_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS positions (
                code TEXT PRIMARY KEY,
                status INTEGER NOT NULL,
                hold_volume INTEGER DEFAULT 0,
                last_buy_price REAL,
                last_sell_price REAL,
                pending_sell_since TEXT,
                last_signal_time TEXT,
                update_time TEXT NOT NULL
            );
            """
        )
        self._conn.commit()

    def upsert(self, position: Position) -> None:
        self._conn.execute(
            """
            INSERT INTO positions (code, status, hold_volume, last_buy_price, last_sell_price,
                                   pending_sell_since, last_signal_time, update_time)
            VALUES (:code, :status, :hold_volume, :last_buy_price, :last_sell_price,
                    :pending_sell_since, :last_signal_time, COALESCE(:update_time, CURRENT_TIMESTAMP))
            ON CONFLICT(code) DO UPDATE SET
                status=excluded.status,
                hold_volume=excluded.hold_volume,
                last_buy_price=excluded.last_buy_price,
                last_sell_price=excluded.last_sell_price,
                pending_sell_since=excluded.pending_sell_since,
                last_signal_time=excluded.last_signal_time,
                update_time=excluded.update_time;
            """,
            position.__dict__,
        )
        self._conn.commit()

    def get(self, code: str) -> Optional[Position]:
        row = self._conn.execute(
            "SELECT * FROM positions WHERE code = ?", (code,)
        ).fetchone()
        if not row:
            return None
        return self._row_to_position(row)

    def list_all(self) -> List[Position]:
        rows = self._conn.execute("SELECT * FROM positions").fetchall()
        return [self._row_to_position(r) for r in rows]

    def delete(self, code: str) -> None:
        self._conn.execute("DELETE FROM positions WHERE code = ?", (code,))
        self._conn.commit()

    def bulk_upsert(self, positions: Iterable[Position]) -> None:
        with self._conn:
            for pos in positions:
                self._conn.execute(
                    """
                    INSERT INTO positions (code, status, hold_volume, last_buy_price, last_sell_price,
                                           pending_sell_since, last_signal_time, update_time)
                    VALUES (:code, :status, :hold_volume, :last_buy_price, :last_sell_price,
                            :pending_sell_since, :last_signal_time, COALESCE(:update_time, CURRENT_TIMESTAMP))
                    ON CONFLICT(code) DO UPDATE SET
                        status=excluded.status,
                        hold_volume=excluded.hold_volume,
                        last_buy_price=excluded.last_buy_price,
                        last_sell_price=excluded.last_sell_price,
                        pending_sell_since=excluded.pending_sell_since,
                        last_signal_time=excluded.last_signal_time,
                        update_time=excluded.update_time;
                    """,
                    pos.__dict__,
                )

    def _row_to_position(self, row: sqlite3.Row) -> Position:
        return Position(
            code=row["code"],
            status=row["status"],
            hold_volume=row["hold_volume"],
            last_buy_price=row["last_buy_price"],
            last_sell_price=row["last_sell_price"],
            pending_sell_since=row["pending_sell_since"],
            last_signal_time=row["last_signal_time"],
            update_time=row["update_time"],
        )
