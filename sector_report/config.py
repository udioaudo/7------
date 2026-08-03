from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml


@dataclass(frozen=True)
class AppSettings:
    timezone: str
    database: Path
    output_dir: Path
    history_days: int = 90
    request_interval_seconds: float = 0.8
    request_retries: int = 3
    max_late_minutes: int = 90


@dataclass(frozen=True)
class EmailSettings:
    sender: str
    recipients: tuple[str, ...]
    smtp_host: str
    smtp_port: int
    auth_env: str
    subject_prefix: str


@dataclass(frozen=True)
class SignalSettings:
    broad_strength_threshold: float = 0.60
    leader_only_threshold: float = 0.40
    strong_rank_quantile: float = 0.25


@dataclass(frozen=True)
class Settings:
    app: AppSettings
    email: EmailSettings
    signals: SignalSettings
    sector_groups: dict[str, list[str]]
    config_path: Path

    @property
    def sectors(self) -> list[str]:
        return [name for names in self.sector_groups.values() for name in names]

    @property
    def sector_theme(self) -> dict[str, str]:
        return {name: theme for theme, names in self.sector_groups.items() for name in names}

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.app.timezone)


def _required(mapping: dict[str, Any], key: str) -> Any:
    if key not in mapping:
        raise ValueError(f"配置缺少字段: {key}")
    return mapping[key]


def load_settings(path: str | Path = "config.yaml") -> Settings:
    config_path = Path(path).expanduser().resolve()
    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    base = config_path.parent
    app_raw = _required(raw, "app")
    email_raw = _required(raw, "email")
    signal_raw = raw.get("signals", {})
    groups = _required(raw, "sector_groups")

    if not isinstance(groups, dict) or not groups:
        raise ValueError("sector_groups 必须是非空映射")
    normalized_groups: dict[str, list[str]] = {}
    seen: set[str] = set()
    for theme, names in groups.items():
        if not isinstance(names, list) or not names:
            raise ValueError(f"板块分组 {theme} 必须包含至少一个板块")
        clean = [str(name).strip() for name in names if str(name).strip()]
        duplicates = seen.intersection(clean)
        if duplicates:
            raise ValueError(f"板块不能重复分组: {', '.join(sorted(duplicates))}")
        seen.update(clean)
        normalized_groups[str(theme)] = clean

    database = Path(_required(app_raw, "database"))
    output_dir = Path(_required(app_raw, "output_dir"))
    if not database.is_absolute():
        database = (base / database).resolve()
    if not output_dir.is_absolute():
        output_dir = (base / output_dir).resolve()

    if "recipients" in email_raw:
        raw_recipients = email_raw["recipients"]
        if not isinstance(raw_recipients, list):
            raise ValueError("email.recipients 必须是非空列表")
    else:
        # 兼容旧版单收件人配置。
        raw_recipients = [_required(email_raw, "recipient")]
    recipients = tuple(dict.fromkeys(
        str(recipient).strip() for recipient in raw_recipients if str(recipient).strip()
    ))
    if not recipients:
        raise ValueError("email.recipients 必须包含至少一个收件邮箱")

    settings = Settings(
        app=AppSettings(
            timezone=str(app_raw.get("timezone", "Asia/Shanghai")),
            database=database,
            output_dir=output_dir,
            history_days=int(app_raw.get("history_days", 90)),
            request_interval_seconds=float(app_raw.get("request_interval_seconds", 0.8)),
            request_retries=int(app_raw.get("request_retries", 3)),
            max_late_minutes=int(app_raw.get("max_late_minutes", 90)),
        ),
        email=EmailSettings(
            sender=str(_required(email_raw, "sender")),
            recipients=recipients,
            smtp_host=str(email_raw.get("smtp_host", "smtp.126.com")),
            smtp_port=int(email_raw.get("smtp_port", 465)),
            auth_env=str(email_raw.get("auth_env", "SMTP_AUTH_CODE")),
            subject_prefix=str(email_raw.get("subject_prefix", "板块趋势早报")),
        ),
        signals=SignalSettings(
            broad_strength_threshold=float(signal_raw.get("broad_strength_threshold", 0.60)),
            leader_only_threshold=float(signal_raw.get("leader_only_threshold", 0.40)),
            strong_rank_quantile=float(signal_raw.get("strong_rank_quantile", 0.25)),
        ),
        sector_groups=normalized_groups,
        config_path=config_path,
    )
    _ = settings.tz  # 立即验证时区名称
    return settings
