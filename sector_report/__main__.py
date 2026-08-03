from __future__ import annotations

import argparse
import json
import sys
from datetime import date

from .app import backfill_history, configure_logging, run_report
from .config import load_settings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="同花顺行业板块趋势早报")
    parser.add_argument("--config", default="config.yaml", help="YAML 配置文件路径")
    parser.add_argument("--verbose", action="store_true", help="输出调试日志")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="生成或发送报告")
    mode = run.add_mutually_exclusive_group(required=True)
    mode.add_argument("--send", action="store_true", help="生成并发送邮件")
    mode.add_argument("--dry-run", action="store_true", help="只生成本地预览")
    run.add_argument("--force", action="store_true", help="测试用：忽略交易日、过时和重复发送检查")

    backfill = subparsers.add_parser("backfill", help="回填行业历史指数")
    backfill.add_argument("--end-date", help="回填截止日期，格式 YYYY-MM-DD，默认今天")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = load_settings(args.config)
    configure_logging(settings, args.verbose)
    try:
        if args.command == "run":
            result = run_report(settings, send=args.send, force=args.force)
        else:
            end_date = date.fromisoformat(args.end_date) if args.end_date else None
            result = {"status": "backfilled", "rows": sum(backfill_history(settings, end_date=end_date).values())}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
