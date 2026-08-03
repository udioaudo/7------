from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, BaseLoader, select_autoescape


HTML_TEMPLATE = r"""<!doctype html>
<html lang="zh-CN">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body style="margin:0;background:#f1f5f9;font-family:'Microsoft YaHei','PingFang SC',Arial,sans-serif;color:#172033;">
<div style="display:none;max-height:0;overflow:hidden;">{{ preheader }}</div>
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#f1f5f9;"><tr><td align="center">
<table role="presentation" width="760" cellspacing="0" cellpadding="0" border="0" style="width:100%;max-width:760px;background:#ffffff;margin:18px auto;">
<tr><td style="padding:30px 30px 20px;background:#172033;color:white;">
  <div style="font-size:13px;letter-spacing:1px;color:#93c5fd;">SECTOR PULSE · 盘中观察</div>
  <h1 style="font-size:26px;margin:8px 0 6px;">同花顺板块趋势早报</h1>
  <div style="font-size:14px;color:#cbd5e1;">{{ captured_at }} · 北京时间</div>
</td></tr>
<tr><td style="padding:26px 30px 6px;">
  <h2 style="font-size:18px;margin:0 0 14px;">市场温度</h2>
  <table role="presentation" width="100%" cellspacing="8" cellpadding="0"><tr>
    <td style="padding:15px;background:#fef2f2;text-align:center;border-radius:8px;"><div style="font-size:12px;color:#64748b;">上涨行业</div><div style="font-size:24px;font-weight:bold;color:#dc2626;">{{ market.up_count }}</div></td>
    <td style="padding:15px;background:#f0fdf4;text-align:center;border-radius:8px;"><div style="font-size:12px;color:#64748b;">下跌行业</div><div style="font-size:24px;font-weight:bold;color:#169b62;">{{ market.down_count }}</div></td>
    <td style="padding:15px;background:#f8fafc;text-align:center;border-radius:8px;"><div style="font-size:12px;color:#64748b;">涨幅中位数</div><div style="font-size:24px;font-weight:bold;color:{{ pct_color(market.median_pct) }};">{{ pct(market.median_pct) }}</div></td>
  </tr></table>
</td></tr>
<tr><td style="padding:10px 30px 22px;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0"><tr>
    <td width="50%" valign="top" style="padding-right:10px;"><div style="font-size:13px;font-weight:bold;margin-bottom:8px;color:#dc2626;">全市场 TOP 5</div>{% for name,value in market.top %}<div style="font-size:13px;padding:5px 0;border-bottom:1px solid #f1f5f9;">{{ loop.index }}. {{ name }} <span style="float:right;color:{{ pct_color(value) }};font-weight:bold;">{{ pct(value) }}</span></div>{% endfor %}</td>
    <td width="50%" valign="top" style="padding-left:10px;"><div style="font-size:13px;font-weight:bold;margin-bottom:8px;color:#169b62;">全市场 BOTTOM 5</div>{% for name,value in market.bottom %}<div style="font-size:13px;padding:5px 0;border-bottom:1px solid #f1f5f9;">{{ loop.index }}. {{ name }} <span style="float:right;color:{{ pct_color(value) }};font-weight:bold;">{{ pct(value) }}</span></div>{% endfor %}</td>
  </tr></table>
</td></tr>
<tr><td style="padding:4px 20px 22px;text-align:center;"><img src="{{ heatmap_src }}" alt="板块热力图" style="display:block;width:100%;max-width:720px;height:auto;border:0;"></td></tr>
<tr><td style="padding:8px 20px 14px;">
  <h2 style="font-size:18px;margin:0 10px 14px;">重点板块明细</h2>
  <div style="overflow-x:auto;">
  <table width="100%" cellspacing="0" cellpadding="7" border="0" style="border-collapse:collapse;font-size:12px;min-width:720px;">
    <thead><tr style="background:#172033;color:white;text-align:right;">
      <th style="text-align:left;">板块</th><th>当日</th><th>排名</th><th>5日</th><th>20日</th><th>净流入</th><th>成交额</th><th>上涨占比</th><th style="text-align:left;">领涨股</th><th style="text-align:left;">信号</th>
    </tr></thead>
    <tbody>{% for row in rows %}<tr style="background:{{ '#f8fafc' if loop.index is even else '#ffffff' }};border-bottom:1px solid #e2e8f0;text-align:right;">
      <td style="text-align:left;font-weight:bold;white-space:nowrap;"><span style="display:block;font-size:10px;color:#64748b;">{{ row.theme }}</span>{{ row.sector_name }}</td>
      <td style="color:{{ pct_color(row.current_pct) }};font-weight:bold;">{{ pct(row.current_pct) }}</td>
      <td>{{ row.market_rank }}/{{ market.total }}</td>
      <td style="color:{{ pct_color(row.return_5d) }};">{{ pct(row.return_5d) }}</td>
      <td style="color:{{ pct_color(row.return_20d) }};">{{ pct(row.return_20d) }}</td>
      <td style="color:{{ pct_color(row.net_inflow) }};">{{ number(row.net_inflow) }}亿</td>
      <td>{{ number(row.amount) }}亿</td>
      <td>{{ ratio(row.breadth) }}</td>
      <td style="text-align:left;white-space:nowrap;">{{ row.leader_name }}<br><span style="color:{{ pct_color(row.leader_pct) }};">{{ pct(row.leader_pct) }}</span></td>
      <td style="text-align:left;line-height:1.5;">{{ row.signals|join(' · ') }}</td>
    </tr>{% endfor %}</tbody>
  </table></div>
</td></tr>
<tr><td style="padding:10px 20px 24px;text-align:center;"><img src="{{ trends_src }}" alt="20日趋势图" style="display:block;width:100%;max-width:720px;height:auto;border:0;"></td></tr>
<tr><td style="padding:20px 30px;background:#f8fafc;color:#64748b;font-size:11px;line-height:1.7;border-top:1px solid #e2e8f0;">
  数据来源：AKShare / 同花顺公开行情页面。盘中资金流与成交额均为采集时点快照。<br>
  本邮件由本机自动生成；如出现“数据积累中”，表示尚无足够的历史快照，不代表中性判断。
</td></tr>
</table></td></tr></table>
</body></html>"""


def render_report(
    *, captured_at: datetime, rows: list[dict], market: dict[str, Any],
    heatmap_src: str, trends_src: str,
) -> str:
    env = Environment(loader=BaseLoader(), autoescape=select_autoescape(default=True))
    env.globals.update(pct=_pct, number=_number, ratio=_ratio, pct_color=_pct_color)
    strongest = max(rows, key=lambda item: item.get("current_pct") if item.get("current_pct") is not None else -999)
    return env.from_string(HTML_TEMPLATE).render(
        captured_at=captured_at.strftime("%Y-%m-%d %H:%M:%S"),
        rows=rows,
        market=market,
        heatmap_src=heatmap_src,
        trends_src=trends_src,
        preheader=f"当前重点板块最强：{strongest['sector_name']} {_pct(strongest.get('current_pct'))}",
    )


def write_preview(html: str, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")


def _pct(value: float | None) -> str:
    return "--" if value is None else f"{value:+.2f}%"


def _number(value: float | None) -> str:
    return "--" if value is None else f"{value:,.2f}"


def _ratio(value: float | None) -> str:
    return "--" if value is None else f"{value * 100:.1f}%"


def _pct_color(value: float | None) -> str:
    if value is None or value == 0:
        return "#64748b"
    return "#dc2626" if value > 0 else "#169b62"
