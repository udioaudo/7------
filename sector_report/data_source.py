from __future__ import annotations

import logging
import random
import time
from datetime import date
from typing import Callable, TypeVar

import pandas as pd

from .config import AppSettings

T = TypeVar("T")
LOGGER = logging.getLogger(__name__)

SUMMARY_COLUMNS = {
    "板块", "涨跌幅", "总成交额", "净流入", "上涨家数", "下跌家数",
    "均价", "领涨股", "领涨股-最新价", "领涨股-涨跌幅",
}
HISTORY_COLUMNS = {"日期", "开盘价", "最高价", "最低价", "收盘价", "成交量", "成交额"}


class AkshareDataSource:
    def __init__(self, settings: AppSettings):
        self.settings = settings
        import akshare as ak
        self.ak = ak
        LOGGER.info("使用 AKShare %s", getattr(ak, "__version__", "unknown"))

    def _retry(self, label: str, call: Callable[[], T]) -> T:
        last_error: Exception | None = None
        for attempt in range(1, self.settings.request_retries + 1):
            try:
                value = call()
                if attempt > 1:
                    LOGGER.info("%s 第 %d 次尝试成功", label, attempt)
                return value
            except Exception as exc:  # 网络/上游页面异常类型不稳定
                last_error = exc
                if attempt >= self.settings.request_retries:
                    break
                delay = min(60.0, (2 ** (attempt - 1)) * 5.0 + random.uniform(0.2, 1.0))
                LOGGER.warning("%s 失败（%d/%d）：%s；%.1f 秒后重试", label, attempt,
                               self.settings.request_retries, exc, delay)
                time.sleep(delay)
        raise RuntimeError(f"{label} 连续 {self.settings.request_retries} 次失败: {last_error}") from last_error

    def trading_dates(self) -> set[date]:
        frame = self._retry("获取 A 股交易日历", self.ak.tool_trade_date_hist_sina)
        if frame.empty or "trade_date" not in frame.columns:
            raise ValueError("交易日历为空或字段结构已变化")
        return {pd.Timestamp(value).date() for value in frame["trade_date"].dropna()}

    def is_trading_day(self, day: date) -> bool:
        return day in self.trading_dates()

    def industry_summary(self) -> pd.DataFrame:
        frame = self._retry("获取同花顺行业盘中汇总", self.ak.stock_board_industry_summary_ths)
        missing = SUMMARY_COLUMNS.difference(frame.columns)
        if missing:
            raise ValueError(f"行业汇总字段结构已变化，缺少: {', '.join(sorted(missing))}")
        if frame.empty:
            raise ValueError("行业汇总为空")
        frame = frame.copy()
        numeric = ["涨跌幅", "总成交额", "净流入", "上涨家数", "下跌家数", "均价", "领涨股-最新价", "领涨股-涨跌幅"]
        for column in numeric:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        if frame["板块"].isna().any() or frame["涨跌幅"].notna().sum() < 50:
            raise ValueError("行业汇总有效板块不足，拒绝生成可能误导的报告")
        frame["市场排名"] = frame["涨跌幅"].rank(method="min", ascending=False, na_option="bottom").astype(int)
        return frame

    def industry_history(self, sector_name: str, start_date: date, end_date: date) -> pd.DataFrame:
        def fetch():
            return self.ak.stock_board_industry_index_ths(
                symbol=sector_name,
                start_date=start_date.strftime("%Y%m%d"),
                end_date=end_date.strftime("%Y%m%d"),
            )

        frame = self._retry(f"获取 {sector_name} 历史指数", fetch)
        missing = HISTORY_COLUMNS.difference(frame.columns)
        if missing:
            raise ValueError(f"{sector_name} 历史指数字段结构已变化，缺少: {', '.join(sorted(missing))}")
        frame = frame.copy()
        frame["日期"] = pd.to_datetime(frame["日期"], errors="coerce")
        for column in HISTORY_COLUMNS - {"日期"}:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        frame = frame.dropna(subset=["日期", "收盘价"]).sort_values("日期")
        # 同花顺日线接口偶尔可能出现当天未收盘数据；早报只保存完整交易日。
        frame = frame[frame["日期"].dt.date < end_date]
        time.sleep(max(0.0, self.settings.request_interval_seconds))
        return frame
