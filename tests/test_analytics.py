from __future__ import annotations

from datetime import date

import pandas as pd

from sector_report.analytics import (
    _period_return,
    build_normalized_trend,
    classify_signals,
    market_temperature,
)


def test_period_returns_and_normalized_trend():
    history = pd.DataFrame({
        "trade_date": pd.date_range("2026-07-01", periods=20, freq="B"),
        "close": [100 + i for i in range(20)],
    })
    estimated = 122.0
    assert round(_period_return(history, estimated, 5), 6) == round((122 / 115 - 1) * 100, 6)
    assert round(_period_return(history, estimated, 20), 6) == 22.0
    trend = build_normalized_trend(history, estimated, date(2026, 8, 3))
    assert len(trend) == 21
    assert trend.iloc[0]["normalized"] == 100
    assert round(trend.iloc[-1]["normalized"], 6) == 122


def test_signal_rules():
    signals = classify_signals(
        current_pct=1.2,
        return_5d=3.0,
        return_20d=8.0,
        breadth=0.75,
        net_inflow=2.0,
        current_rank=3,
        previous_rank=5,
        strong_rank_limit=10,
        broad_threshold=0.6,
        leader_threshold=0.4,
    )
    assert signals == ["多周期走强", "普涨走强", "连续强势"]


def test_divergence_and_leader_only():
    signals = classify_signals(
        current_pct=0.8,
        return_5d=-1.0,
        return_20d=-2.0,
        breadth=0.3,
        net_inflow=-0.5,
        current_rank=30,
        previous_rank=None,
        strong_rank_limit=10,
        broad_threshold=0.6,
        leader_threshold=0.4,
    )
    assert "龙头独涨" in signals
    assert "资金背离" in signals


def test_market_temperature():
    frame = pd.DataFrame({"板块": ["甲", "乙", "丙"], "涨跌幅": [2.0, 0.0, -1.0]})
    value = market_temperature(frame)
    assert value["up_count"] == 1
    assert value["down_count"] == 1
    assert value["flat_count"] == 1
    assert value["top"][0] == ("甲", 2.0)
