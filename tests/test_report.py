from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from sector_report.report import render_report


def test_report_renders_cid_and_escapes():
    row = {
        "theme": "科技", "sector_name": "半导体", "current_pct": 1.2,
        "market_rank": 2, "return_5d": 3.4, "return_20d": None,
        "net_inflow": 5.6, "amount": 100.0, "breadth": 0.75,
        "leader_name": "测试<股>", "leader_pct": 10.0,
        "signals": ["普涨走强"],
    }
    market = {
        "up_count": 50, "down_count": 30, "flat_count": 10, "median_pct": 0.2,
        "top": [("甲", 2.0)], "bottom": [("乙", -1.0)], "total": 90,
    }
    html = render_report(
        captured_at=datetime(2026, 8, 3, 11, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        rows=[row], market=market, heatmap_src="cid:heatmap", trends_src="cid:trends",
    )
    assert "cid:heatmap" in html
    assert "测试&lt;股&gt;" in html
    assert "+1.20%" in html
    assert "本报告为上午 11:00 左右的盘中快照" not in html
    assert "不构成投资建议" not in html
    assert "background:#fff7ed" not in html
