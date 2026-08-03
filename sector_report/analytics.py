from __future__ import annotations

import math
from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from .config import Settings
from .db import Database


def market_temperature(summary: pd.DataFrame) -> dict[str, Any]:
    valid = summary.dropna(subset=["涨跌幅"]).copy()
    ordered = valid.sort_values("涨跌幅", ascending=False)
    return {
        "up_count": int((valid["涨跌幅"] > 0).sum()),
        "down_count": int((valid["涨跌幅"] < 0).sum()),
        "flat_count": int((valid["涨跌幅"] == 0).sum()),
        "median_pct": float(valid["涨跌幅"].median()),
        "top": [(str(row["板块"]), float(row["涨跌幅"])) for _, row in ordered.head(5).iterrows()],
        "bottom": [(str(row["板块"]), float(row["涨跌幅"])) for _, row in ordered.tail(5).sort_values("涨跌幅").iterrows()],
        "total": int(len(valid)),
    }


def calculate_report_rows(
    summary: pd.DataFrame,
    db: Database,
    settings: Settings,
    report_date: date,
) -> tuple[list[dict[str, Any]], dict[str, pd.DataFrame]]:
    by_name = summary.set_index("板块", drop=False)
    missing = [name for name in settings.sectors if name not in by_name.index]
    if missing:
        raise ValueError(f"行业汇总缺少配置中的板块: {', '.join(missing)}")

    total_industries = len(summary)
    strong_rank_limit = max(1, math.ceil(total_industries * settings.signals.strong_rank_quantile))
    rows: list[dict[str, Any]] = []
    trend_series: dict[str, pd.DataFrame] = {}

    for sector_name in settings.sectors:
        source = by_name.loc[sector_name]
        if isinstance(source, pd.DataFrame):
            source = source.iloc[0]
        current_pct = _safe_float(source["涨跌幅"])
        rank = int(source["市场排名"])
        up_count = _safe_int(source["上涨家数"])
        down_count = _safe_int(source["下跌家数"])
        breadth = None
        if up_count is not None and down_count is not None and up_count + down_count > 0:
            breadth = up_count / (up_count + down_count)

        history = db.get_history(sector_name, before=report_date)
        latest_close = _last_value(history, "close")
        estimated = latest_close * (1 + current_pct / 100) if latest_close is not None and current_pct is not None else None
        return_5d = _period_return(history, estimated, 5)
        return_20d = _period_return(history, estimated, 20)
        previous_rank = db.previous_snapshot_rank(sector_name, report_date)
        signals = classify_signals(
            current_pct=current_pct,
            return_5d=return_5d,
            return_20d=return_20d,
            breadth=breadth,
            net_inflow=_safe_float(source["净流入"]),
            current_rank=rank,
            previous_rank=previous_rank,
            strong_rank_limit=strong_rank_limit,
            broad_threshold=settings.signals.broad_strength_threshold,
            leader_threshold=settings.signals.leader_only_threshold,
        )
        rows.append({
            "sector_name": sector_name,
            "theme": settings.sector_theme[sector_name],
            "current_pct": current_pct,
            "market_rank": rank,
            "amount": _safe_float(source["总成交额"]),
            "net_inflow": _safe_float(source["净流入"]),
            "up_count": up_count,
            "down_count": down_count,
            "breadth": breadth,
            "avg_price": _safe_float(source["均价"]),
            "leader_name": str(source["领涨股"]) if pd.notna(source["领涨股"]) else "--",
            "leader_price": _safe_float(source["领涨股-最新价"]),
            "leader_pct": _safe_float(source["领涨股-涨跌幅"]),
            "estimated_index": estimated,
            "return_5d": return_5d,
            "return_20d": return_20d,
            "previous_rank": previous_rank,
            "signals": signals,
        })
        trend_series[sector_name] = build_normalized_trend(history, estimated, report_date)
    return rows, trend_series


def classify_signals(
    *, current_pct: float | None, return_5d: float | None, return_20d: float | None,
    breadth: float | None, net_inflow: float | None, current_rank: int,
    previous_rank: int | None, strong_rank_limit: int, broad_threshold: float,
    leader_threshold: float,
) -> list[str]:
    signals: list[str] = []
    if all(value is not None and value > 0 for value in (current_pct, return_5d, return_20d)):
        signals.append("多周期走强")
    if current_pct is not None and current_pct > 0 and breadth is not None:
        if breadth >= broad_threshold:
            signals.append("普涨走强")
        elif breadth < leader_threshold:
            signals.append("龙头独涨")
    if current_pct is not None and net_inflow is not None and current_pct * net_inflow < 0:
        signals.append("资金背离")
    if previous_rank is not None and current_rank <= strong_rank_limit and previous_rank <= strong_rank_limit:
        signals.append("连续强势")
    if not signals:
        signals.append("暂无明确信号" if previous_rank is not None else "连续性数据积累中")
    return signals


def build_normalized_trend(history: pd.DataFrame, estimated: float | None, report_date: date) -> pd.DataFrame:
    if history.empty:
        return pd.DataFrame(columns=["date", "normalized"])
    data = history[["trade_date", "close"]].dropna().tail(20).copy()
    data.columns = ["date", "value"]
    if estimated is not None:
        data = pd.concat([
            data,
            pd.DataFrame({"date": [pd.Timestamp(report_date)], "value": [estimated]}),
        ], ignore_index=True)
    if data.empty or data.iloc[0]["value"] == 0:
        return pd.DataFrame(columns=["date", "normalized"])
    data["normalized"] = data["value"] / float(data.iloc[0]["value"]) * 100.0
    return data[["date", "normalized"]]


def _period_return(history: pd.DataFrame, estimated: float | None, sessions: int) -> float | None:
    if estimated is None or len(history) < sessions:
        return None
    base = _safe_float(history.iloc[-sessions]["close"])
    if base in (None, 0):
        return None
    return (estimated / base - 1.0) * 100.0


def _last_value(frame: pd.DataFrame, column: str) -> float | None:
    if frame.empty:
        return None
    return _safe_float(frame.iloc[-1][column])


def _safe_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    value = float(value)
    return value if np.isfinite(value) else None


def _safe_int(value) -> int | None:
    number = _safe_float(value)
    return int(number) if number is not None else None

