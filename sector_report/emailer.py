from __future__ import annotations

import os
import smtplib
import ssl
import time
from email.message import EmailMessage
from email.utils import make_msgid
from pathlib import Path

from .config import EmailSettings


class EmailSender:
    def __init__(self, settings: EmailSettings):
        self.settings = settings

    def send_html(self, subject: str, html: str, images: dict[str, Path] | None = None, retries: int = 3) -> None:
        password = os.environ.get(self.settings.auth_env)
        if not password:
            raise RuntimeError(
                f"环境变量 {self.settings.auth_env} 未设置；请填写 126 邮箱客户端授权码，而不是网页登录密码"
            )
        message = self._build_message(subject, html, images or {})
        last_error: Exception | None = None
        for attempt in range(1, retries + 1):
            try:
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(
                    self.settings.smtp_host,
                    self.settings.smtp_port,
                    context=context,
                    timeout=30,
                ) as smtp:
                    smtp.login(self.settings.sender, password)
                    smtp.send_message(message)
                return
            except Exception as exc:
                last_error = exc
                if attempt < retries:
                    time.sleep(5 * attempt)
        raise RuntimeError(f"SMTP 连续 {retries} 次发送失败: {last_error}") from last_error

    def _build_message(self, subject: str, html: str, images: dict[str, Path]) -> EmailMessage:
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = self.settings.sender
        message["To"] = self.settings.recipient
        domain = self.settings.sender.split("@")[-1]
        message["Message-ID"] = make_msgid(domain=domain)
        message.set_content("本邮件包含 HTML 板块趋势报告，请使用支持 HTML 的邮件客户端查看。")
        message.add_alternative(html, subtype="html")
        html_part = message.get_payload()[-1]
        for cid, path in images.items():
            data = path.read_bytes()
            html_part.add_related(data, maintype="image", subtype="png", cid=f"<{cid}>", filename=path.name)
        return message

    def send_failure_alert(self, report_date: str, error: str) -> None:
        safe_error = (
            error.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")[:1500]
        )
        subject = f"[{self.settings.subject_prefix}·采集失败] {report_date}"
        html = f"""
        <html><body style="font-family:Microsoft YaHei,Arial,sans-serif">
        <h2 style="color:#b91c1c">板块趋势早报生成失败</h2>
        <p>日期：{report_date}</p>
        <pre style="white-space:pre-wrap;background:#f8fafc;padding:12px">{safe_error}</pre>
        <p style="color:#64748b">系统未使用旧行情生成正式报告，请检查网络、AKShare 或同花顺页面结构。</p>
        </body></html>
        """
        self.send_html(subject, html, images={}, retries=1)
