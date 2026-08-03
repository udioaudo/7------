from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

import pandas as pd


SCHEMA = """
CREATE TABLE IF NOT EXISTS daily_history (
    sector_name TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL NOT NULL,
    volume REAL,
    amount REAL,
    PRIMARY KEY (sector_name, trade_date)
);
CREATE INDEX IF NOT EXISTS idx_daily_history_date ON daily_history(trade_date);

CREATE TABLE IF NOT EXISTS snapshots (
    report_date TEXT NOT NULL,
    captured_at TEXT NOT NULL,
    sector_name TEXT NOT NULL,
    theme TEXT NOT NULL,
    current_pct REAL,
    market_rank INTEGER,
    amount REAL,
    net_inflow REAL,
    up_count INTEGER,
    down_count INTEGER,
    breadth REAL,
    avg_price REAL,
    leader_name TEXT,
    leader_price REAL,
    leader_pct REAL,
    estimated_index REAL,
    return_5d REAL,
    return_20d REAL,
    signals TEXT,
    PRIMARY KEY (report_date, sector_name)
);
CREATE INDEX IF NOT EXISTS idx_snapshots_date ON snapshots(report_date);

CREATE TABLE IF NOT EXISTS report_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_date TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    mode TEXT NOT NULL,
    status TEXT NOT NULL,
    subject TEXT,
    output_path TEXT,
    error_message TEXT,
    sent_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_report_runs_date ON report_runs(report_date, mode, status);
"""


class Database:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def upsert_history(self, sector_name: str, frame: pd.DataFrame) -> int:
        if frame.empty:
            return 0
        rows = [
            (
                sector_name,
                pd.Timestamp(row["日期"]).date().isoformat(),
                _float(row.get("开盘价")),
                _float(row.get("最高价")),
                _float(row.get("最低价")),
                _float(row.get("收盘价")),
                _float(row.get("成交量")),
                _float(row.get("成交额")),
            )
            for _, row in frame.iterrows()
            if pd.notna(row.get("收盘价"))
        ]
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT INTO daily_history
                (sector_name, trade_date, open, high, low, close, volume, amount)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(sector_name, trade_date) DO UPDATE SET
                    open=excluded.open, high=excluded.high, low=excluded.low,
                    close=excluded.close, volume=excluded.volume, amount=excluded.amount
                """,
                rows,
            )
        return len(rows)

    def latest_history_date(self, sector_name: str) -> date | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT MAX(trade_date) AS d FROM daily_history WHERE sector_name=?",
                (sector_name,),
            ).fetchone()
        return date.fromisoformat(row["d"]) if row and row["d"] else None

    def get_history(self, sector_name: str, before: date | None = None) -> pd.DataFrame:
        sql = "SELECT trade_date, open, high, low, close, volume, amount FROM daily_history WHERE sector_name=?"
        params: list[object] = [sector_name]
        if before is not None:
            sql += " AND trade_date < ?"
            params.append(before.isoformat())
        sql += " ORDER BY trade_date"
        with self.connect() as conn:
            frame = pd.read_sql_query(sql, conn, params=params)
        if not frame.empty:
            frame["trade_date"] = pd.to_datetime(frame["trade_date"])
        return frame

    def previous_snapshot_rank(self, sector_name: str, before: date) -> int | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT market_rank FROM snapshots
                WHERE sector_name=? AND report_date < ?
                ORDER BY report_date DESC LIMIT 1
                """,
                (sector_name, before.isoformat()),
            ).fetchone()
        return int(row["market_rank"]) if row and row["market_rank"] is not None else None

    def save_snapshots(self, report_date: date, captured_at: datetime, rows: Iterable[dict]) -> None:
        payload = []
        for row in rows:
            payload.append((
                report_date.isoformat(), captured_at.isoformat(), row["sector_name"], row["theme"],
                _float(row.get("current_pct")), row.get("market_rank"), _float(row.get("amount")),
                _float(row.get("net_inflow")), row.get("up_count"), row.get("down_count"),
                _float(row.get("breadth")), _float(row.get("avg_price")), row.get("leader_name"),
                _float(row.get("leader_price")), _float(row.get("leader_pct")),
                _float(row.get("estimated_index")), _float(row.get("return_5d")),
                _float(row.get("return_20d")), "、".join(row.get("signals", [])),
            ))
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT INTO snapshots VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(report_date, sector_name) DO UPDATE SET
                    captured_at=excluded.captured_at, theme=excluded.theme,
                    current_pct=excluded.current_pct, market_rank=excluded.market_rank,
                    amount=excluded.amount, net_inflow=excluded.net_inflow,
                    up_count=excluded.up_count, down_count=excluded.down_count,
                    breadth=excluded.breadth, avg_price=excluded.avg_price,
                    leader_name=excluded.leader_name, leader_price=excluded.leader_price,
                    leader_pct=excluded.leader_pct, estimated_index=excluded.estimated_index,
                    return_5d=excluded.return_5d, return_20d=excluded.return_20d,
                    signals=excluded.signals
                """,
                payload,
            )

    def was_sent(self, report_date: date) -> bool:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM report_runs WHERE report_date=? AND mode='send' AND status='sent' LIMIT 1",
                (report_date.isoformat(),),
            ).fetchone()
        return row is not None

    def start_run(self, report_date: date, started_at: datetime, mode: str) -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                "INSERT INTO report_runs(report_date, started_at, mode, status) VALUES (?, ?, ?, 'running')",
                (report_date.isoformat(), started_at.isoformat(), mode),
            )
            return int(cursor.lastrowid)

    def finish_run(
        self, run_id: int, completed_at: datetime, status: str, subject: str | None = None,
        output_path: Path | None = None, error_message: str | None = None, sent_at: datetime | None = None,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """UPDATE report_runs SET completed_at=?, status=?, subject=?, output_path=?,
                   error_message=?, sent_at=? WHERE id=?""",
                (
                    completed_at.isoformat(), status, subject, str(output_path) if output_path else None,
                    error_message[:2000] if error_message else None,
                    sent_at.isoformat() if sent_at else None, run_id,
                ),
            )


def _float(value):
    if value is None or pd.isna(value):
        return None
    return float(value)
