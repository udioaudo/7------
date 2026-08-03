from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sector_report.config import EmailSettings, load_settings
from sector_report.emailer import EmailSender


BASE_CONFIG = """
app:
  timezone: Asia/Shanghai
  database: data/test.db
  output_dir: output
email:
  sender: sender@126.com
  smtp_host: smtp.126.com
  smtp_port: 465
  auth_env: SMTP_AUTH_CODE
  subject_prefix: 测试
sector_groups:
  测试组:
    - 测试板块
"""


def _write_config(tmp_path: Path, email_recipient_lines: str) -> Path:
    path = tmp_path / "config.yaml"
    path.write_text(
        BASE_CONFIG.replace(
            "  sender: sender@126.com\n",
            f"  sender: sender@126.com\n{email_recipient_lines}",
        ),
        encoding="utf-8",
    )
    return path


def test_loads_multiple_recipients(tmp_path: Path):
    path = _write_config(
        tmp_path,
        "  recipients:\n    - first@example.com\n    - second@example.com\n",
    )
    assert load_settings(path).email.recipients == (
        "first@example.com",
        "second@example.com",
    )


def test_legacy_single_recipient_is_supported(tmp_path: Path):
    path = _write_config(tmp_path, "  recipient: legacy@example.com\n")
    assert load_settings(path).email.recipients == ("legacy@example.com",)


def test_empty_recipients_are_rejected(tmp_path: Path):
    path = _write_config(tmp_path, "  recipients: []\n")
    with pytest.raises(ValueError, match="至少一个收件邮箱"):
        load_settings(path)


def test_message_and_smtp_envelope_include_all_recipients(monkeypatch):
    settings = EmailSettings(
        sender="sender@126.com",
        recipients=("first@example.com", "second@example.com"),
        smtp_host="smtp.126.com",
        smtp_port=465,
        auth_env="SMTP_AUTH_CODE",
        subject_prefix="测试",
    )
    monkeypatch.setenv("SMTP_AUTH_CODE", "test-auth-code")
    smtp = MagicMock()
    smtp.__enter__.return_value = smtp
    with patch("sector_report.emailer.smtplib.SMTP_SSL", return_value=smtp):
        EmailSender(settings).send_html("主题", "<p>正文</p>", retries=1)

    message = smtp.send_message.call_args.args[0]
    assert message["To"] == "first@example.com, second@example.com"
    assert smtp.send_message.call_args.kwargs == {
        "from_addr": "sender@126.com",
        "to_addrs": ["first@example.com", "second@example.com"],
    }
