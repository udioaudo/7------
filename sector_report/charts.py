from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.colors import Normalize
from matplotlib.patches import Rectangle
import numpy as np


THEME_COLORS = {
    "消费": "#d97706",
    "科技": "#2563eb",
    "医疗": "#059669",
    "光电新能源": "#7c3aed",
    "传统能源": "#475569",
}


def configure_chinese_font() -> None:
    candidates = ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "Arial Unicode MS"]
    installed = {font.name for font in font_manager.fontManager.ttflist}
    for name in candidates:
        if name in installed:
            plt.rcParams["font.sans-serif"] = [name]
            break
    plt.rcParams["axes.unicode_minus"] = False


def create_charts(rows: list[dict], trend_series: dict, sector_groups: dict[str, list[str]], output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    configure_chinese_font()
    heatmap_path = output_dir / "sector_heatmap.png"
    trends_path = output_dir / "sector_trends.png"
    create_heatmap(rows, heatmap_path)
    create_trend_chart(trend_series, sector_groups, trends_path)
    return {"heatmap": heatmap_path, "trends": trends_path}


def create_heatmap(rows: list[dict], path: Path) -> None:
    ordered = sorted(rows, key=lambda row: (row.get("current_pct") is None, -(row.get("current_pct") or -999)))
    cols = 4
    cell_w, cell_h = 1.0, 0.72
    rows_count = int(np.ceil(len(ordered) / cols))
    fig, ax = plt.subplots(figsize=(10, max(4.2, rows_count * 1.28)))
    values = [abs(row.get("current_pct") or 0) for row in ordered]
    scale = max(1.0, max(values, default=1.0))
    norm = Normalize(vmin=-scale, vmax=scale)
    cmap = matplotlib.colors.LinearSegmentedColormap.from_list("cn_market", ["#169b62", "#f8fafc", "#dc2626"])

    for index, row in enumerate(ordered):
        grid_row, grid_col = divmod(index, cols)
        x, y = grid_col * cell_w, (rows_count - 1 - grid_row) * cell_h
        value = row.get("current_pct")
        color = cmap(norm(value or 0))
        ax.add_patch(Rectangle((x, y), cell_w - 0.025, cell_h - 0.025, facecolor=color, edgecolor="white", linewidth=1.5))
        text_color = "white" if value is not None and abs(value) >= scale * 0.45 else "#172033"
        ax.text(x + 0.5, y + 0.43, row["sector_name"], ha="center", va="center", fontsize=10, color=text_color, weight="bold")
        ax.text(x + 0.5, y + 0.19, _pct(value), ha="center", va="center", fontsize=11, color=text_color)

    ax.set_xlim(0, cols * cell_w)
    ax.set_ylim(0, rows_count * cell_h)
    ax.axis("off")
    ax.set_title("重点板块 11:00 涨跌热力图", loc="left", fontsize=16, weight="bold", pad=14, color="#172033")
    fig.tight_layout(pad=0.8)
    fig.savefig(path, dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def create_trend_chart(trend_series: dict, sector_groups: dict[str, list[str]], path: Path) -> None:
    group_count = len(sector_groups)
    fig, axes = plt.subplots(group_count, 1, figsize=(10, 3.0 * group_count), squeeze=False)
    for ax, (theme, sectors) in zip(axes.flat, sector_groups.items()):
        colors = plt.cm.tab10(np.linspace(0, 1, max(len(sectors), 2)))
        plotted = False
        for color, sector in zip(colors, sectors):
            frame = trend_series.get(sector)
            if frame is None or frame.empty:
                continue
            ax.plot(frame["date"], frame["normalized"], label=sector, linewidth=1.8, color=color)
            plotted = True
        ax.axhline(100, color="#94a3b8", linewidth=0.8, linestyle="--")
        ax.grid(axis="y", color="#e2e8f0", linewidth=0.8)
        ax.set_title(theme, loc="left", fontsize=13, weight="bold", color=THEME_COLORS.get(theme, "#172033"))
        ax.set_ylabel("起点=100", color="#64748b", fontsize=9)
        ax.tick_params(axis="x", labelsize=8, colors="#64748b")
        ax.tick_params(axis="y", labelsize=8, colors="#64748b")
        for spine in ax.spines.values():
            spine.set_visible(False)
        if plotted:
            ax.legend(loc="upper left", ncol=min(3, len(sectors)), fontsize=8, frameon=False)
        else:
            ax.text(0.5, 0.5, "历史数据积累中", transform=ax.transAxes, ha="center", va="center", color="#94a3b8")
    fig.suptitle("近 20 个交易日趋势（含当日 11:00 估算点）", x=0.08, ha="left", fontsize=16, weight="bold", color="#172033")
    fig.tight_layout(rect=(0, 0, 1, 0.98), h_pad=1.4)
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def _pct(value: float | None) -> str:
    return "--" if value is None else f"{value:+.2f}%"
