from __future__ import annotations

import logging
import os
import traceback
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

from .analytics import calculate_report_rows, market_temperature
from .charts import create_charts
from .config import Settings
from .data_source import AkshareDataSource
from .db import Database
from .emailer import EmailSender
from .report import render_report, write_preview

LOGGER = logging.getLogger(__name__)


def configure_logging(settings: Settings, verbose: bool = False) -> None:
    log_path = settings.app.database.parent / "sector_report.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    handlers.append(logging.FileHandler(log_path, encoding="utf-8"))
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
        handlers=handlers,
        force=True,
    )


def sync_history(
    db: Database,
    source: AkshareDataSource,
    settings: Settings,
    end_date: date,
    full_backfill: bool = False,
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for index, sector in enumerate(settings.sectors, 1):
        latest = None if full_backfill else db.latest_history_date(sector)
        if latest is None:
            start_date = end_date - timedelta(days=settings.app.history_days)
        else:
            # 回看 10 天可修复临时缺口，并覆盖上游可能修订的数据。
            start_date = latest - timedelta(days=10)
        LOGGER.info("同步历史 %d/%d：%s（%s 至 %s）", index, len(settings.sectors), sector, start_date, end_date)
        frame = source.industry_history(sector, start_date, end_date)
        counts[sector] = db.upsert_history(sector, frame)
    return counts


def run_report(
    settings: Settings,
    *,
    send: bool,
    force: bool = False,
    now: datetime | None = None,
    source: AkshareDataSource | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(settings.tz)
    if now.tzinfo is None:
        now = now.replace(tzinfo=settings.tz)
    report_date = now.date()
    mode = "send" if send else "dry-run"
    db = Database(settings.app.database)
    run_id = db.start_run(report_date, now, mode)
    source = source or AkshareDataSource(settings.app)
    emailer = EmailSender(settings.email)

    try:
        if not force and not source.is_trading_day(report_date):
            LOGGER.info("%s 不是 A 股交易日，不生成邮件", report_date)
            db.finish_run(run_id, datetime.now(settings.tz), "skipped_non_trading_day")
            return {"status": "skipped_non_trading_day", "date": report_date.isoformat()}

        if send and not force:
            scheduled = datetime.combine(report_date, time(11, 0), tzinfo=settings.tz)
            if now > scheduled + timedelta(minutes=settings.app.max_late_minutes):
                LOGGER.warning("当前时间已超过补发时限，不发送过时早报")
                db.finish_run(run_id, datetime.now(settings.tz), "skipped_too_late")
                return {"status": "skipped_too_late", "date": report_date.isoformat()}
            if db.was_sent(report_date):
                LOGGER.info("%s 的正式报告已经发送，跳过重复发送", report_date)
                db.finish_run(run_id, datetime.now(settings.tz), "skipped_duplicate")
                return {"status": "skipped_duplicate", "date": report_date.isoformat()}

        # 先抓取盘中快照，避免 20 个历史请求令采集时点明显后移。
        summary = source.industry_summary()
        captured_at = datetime.now(settings.tz) if now is None else now
        sync_history(db, source, settings, report_date, full_backfill=False)
        market = market_temperature(summary)
        rows, trends = calculate_report_rows(summary, db, settings, report_date)
        db.save_snapshots(report_date, captured_at, rows)

        report_dir = settings.app.output_dir / report_date.isoformat()
        charts = create_charts(rows, trends, settings.sector_groups, report_dir)
        preview_html = render_report(
            captured_at=captured_at,
            rows=rows,
            market=market,
            heatmap_src=charts["heatmap"].name,
            trends_src=charts["trends"].name,
        )
        email_html = render_report(
            captured_at=captured_at,
            rows=rows,
            market=market,
            heatmap_src="cid:heatmap",
            trends_src="cid:trends",
        )
        preview_path = report_dir / "report.html"
        email_path = report_dir / "report_email.html"
        write_preview(preview_html, preview_path)
        write_preview(email_html, email_path)

        strongest = max(rows, key=lambda row: row.get("current_pct") if row.get("current_pct") is not None else -999)
        strongest_pct = strongest.get("current_pct")
        pct_text = "--" if strongest_pct is None else f"{strongest_pct:+.2f}%"
        subject = (
            f"[{settings.email.subject_prefix}] {report_date.isoformat()} 11:00 | "
            f"最强：{strongest['sector_name']} {pct_text}"
        )

        completed_at = datetime.now(settings.tz)
        if send:
            emailer.send_html(subject, email_html, {"heatmap": charts["heatmap"], "trends": charts["trends"]})
            sent_at = datetime.now(settings.tz)
            db.finish_run(run_id, sent_at, "sent", subject, preview_path, sent_at=sent_at)
            LOGGER.info("报告已发送至 %s", settings.email.recipient)
            status = "sent"
        else:
            db.finish_run(run_id, completed_at, "generated", subject, preview_path)
            LOGGER.info("dry-run 完成：%s", preview_path)
            status = "generated"
        return {
            "status": status,
            "date": report_date.isoformat(),
            "subject": subject,
            "preview": str(preview_path),
            "charts": {key: str(value) for key, value in charts.items()},
        }
    except Exception as exc:
        error_text = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        LOGGER.error("报告任务失败：%s", exc, exc_info=True)
        db.finish_run(run_id, datetime.now(settings.tz), "failed", error_message=error_text)
        if send and os.environ.get(settings.email.auth_env):
            try:
                emailer.send_failure_alert(report_date.isoformat(), str(exc))
            except Exception:
                LOGGER.error("失败告警邮件也未能发送", exc_info=True)
        raise


def backfill_history(settings: Settings, *, end_date: date | None = None) -> dict[str, int]:
    source = AkshareDataSource(settings.app)
    db = Database(settings.app.database)
    end_date = end_date or datetime.now(settings.tz).date()
    counts = sync_history(db, source, settings, end_date, full_backfill=True)
    LOGGER.info("历史回填完成，共写入/更新 %d 行", sum(counts.values()))
    return counts
