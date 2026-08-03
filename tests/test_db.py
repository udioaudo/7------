from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from sector_report.db import Database


def test_database_history_and_send_dedup(tmp_path: Path):
    db = Database(tmp_path / "test.db")
    frame = pd.DataFrame({
        "日期": pd.to_datetime(["2026-07-30", "2026-07-31"]),
        "开盘价": [10, 11], "最高价": [12, 13], "最低价": [9, 10],
        "收盘价": [11, 12], "成交量": [100, 120], "成交额": [1000, 1200],
    })
    assert db.upsert_history("白酒", frame) == 2
    loaded = db.get_history("白酒", before=date(2026, 8, 3))
    assert list(loaded["close"]) == [11.0, 12.0]

    tz = ZoneInfo("Asia/Shanghai")
    now = datetime(2026, 8, 3, 11, 1, tzinfo=tz)
    run_id = db.start_run(now.date(), now, "send")
    assert not db.was_sent(now.date())
    db.finish_run(run_id, now, "sent", sent_at=now)
    assert db.was_sent(now.date())


def test_snapshot_previous_rank(tmp_path: Path):
    db = Database(tmp_path / "test.db")
    captured = datetime(2026, 7, 31, 11, 0)
    db.save_snapshots(date(2026, 7, 31), captured, [{
        "sector_name": "半导体", "theme": "科技", "current_pct": 1.0,
        "market_rank": 4, "amount": 10, "net_inflow": 1,
        "up_count": 20, "down_count": 5, "breadth": 0.8,
        "avg_price": 10, "leader_name": "测试", "leader_price": 20,
        "leader_pct": 10, "estimated_index": 100, "return_5d": 2,
        "return_20d": 5, "signals": ["普涨走强"],
    }])
    assert db.previous_snapshot_rank("半导体", date(2026, 8, 3)) == 4
