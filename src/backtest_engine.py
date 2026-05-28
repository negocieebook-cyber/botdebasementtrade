from __future__ import annotations

import pandas as pd

from src.config import REPORTS_DIR, START_DATE
from src.data_collector import get_price_data
from src.signal_history import load_signal_history
from src.utils import write_text


def run_simple_forward_test(
    symbol: str,
    asset_class: str,
    signal_date: str,
    horizons=[30, 90, 180, 365],
    signal_score: float = 0.0,  # V3
) -> dict:
    df = get_price_data(symbol, START_DATE)
    if df.empty:
        return {"symbol": symbol, "asset_class": asset_class, "signal_date": signal_date, "error": "no price data"}

    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    signal_dt = pd.to_datetime(signal_date)
    future = df[df["date"] >= signal_dt].reset_index(drop=True)
    if future.empty:
        return {"symbol": symbol, "asset_class": asset_class, "signal_date": signal_date, "error": "signal date unavailable"}

    signal_price = float(future.iloc[0]["close"])
    result = {
        "symbol": symbol,
        "asset_class": asset_class,
        "signal_date": signal_date,
        "signal_price": signal_price,
        "signal_score": signal_score,  # V3
    }
    for horizon in horizons:
        if len(future) > horizon:
            future_price = float(future.iloc[horizon]["close"])
            ret = ((future_price / signal_price) - 1) * 100
            result[f"return_{horizon}d"] = ret
            result[f"win_{horizon}d"] = ret > 0  # V3
        else:
            result[f"return_{horizon}d"] = None
            result[f"win_{horizon}d"] = None  # V3

    gains = (future["close"] / signal_price - 1) * 100
    result["max_drawdown_after_signal"] = float(gains.min()) if not gains.empty else None
    result["max_gain_after_signal"] = float(gains.max()) if not gains.empty else None  # V3
    # V3 — payoff ratio: best gain divided by max drawdown magnitude
    max_gain = result.get("max_gain_after_signal") or 0.0  # V3
    max_dd = abs(result.get("max_drawdown_after_signal") or 0.0)  # V3
    result["payoff_ratio"] = round(max_gain / max_dd, 2) if max_dd > 0 else None  # V3
    return result


def evaluate_signal_history() -> pd.DataFrame:
    history = load_signal_history()
    if history.empty:
        summary = pd.DataFrame()
        _save_backtest_summary(summary)
        return summary

    rows = []
    notified = history[history.get("was_notified", False).astype(str).str.lower().isin(["true", "1", "yes"])]
    for _, row in notified.iterrows():
        rows.append(
            run_simple_forward_test(
                symbol=str(row.get("symbol", "")),
                asset_class=str(row.get("asset_class", "")),
                signal_date=str(row.get("date", "")),
                signal_score=float(row.get("score", 0) or 0),  # V3
            )
        )
    summary = pd.DataFrame(rows)
    _save_backtest_summary(summary)
    return summary


def _save_backtest_summary(summary: pd.DataFrame) -> None:
    if summary.empty:
        content = "# Backtest Summary\n\nNo historical notified signals available yet.\n"
        write_text(REPORTS_DIR / "backtest_summary.md", content)
        return

    lines = ["# Backtest Summary", ""]

    # V3 — hit rates by horizon
    lines.append("## Hit Rates by Horizon")  # V3
    for horizon in [30, 90, 180, 365]:  # V3
        col = f"win_{horizon}d"  # V3
        if col in summary.columns:  # V3
            valid = summary[col].dropna()  # V3
            if len(valid) > 0:  # V3
                hit_rate = valid.mean() * 100  # V3
                lines.append(f"- {horizon}d: {hit_rate:.1f}% ({int(valid.sum())}/{len(valid)} signals)")  # V3
    lines.append("")  # V3

    # V3 — average and median returns by horizon
    lines.append("## Returns by Horizon")  # V3
    for horizon in [30, 90, 180, 365]:  # V3
        col = f"return_{horizon}d"  # V3
        if col in summary.columns:  # V3
            valid = summary[col].dropna()  # V3
            if len(valid) > 0:  # V3
                avg = valid.mean()  # V3
                median = valid.median()  # V3
                lines.append(f"- {horizon}d: avg={avg:.1f}%, median={median:.1f}%")  # V3
    lines.append("")  # V3

    # V3 — payoff ratio summary
    if "payoff_ratio" in summary.columns:  # V3
        valid_pr = summary["payoff_ratio"].dropna()  # V3
        if len(valid_pr) > 0:  # V3
            lines.append(f"## Payoff Ratio (avg): {valid_pr.mean():.2f}")  # V3
            lines.append("")  # V3

    # V3 — score comparison: high-score vs low-score signals
    score_col = "signal_score" if "signal_score" in summary.columns else None  # V3
    if score_col:  # V3
        median_score = summary[score_col].median()  # V3
        high_group = summary[summary[score_col] >= median_score]  # V3
        low_group = summary[summary[score_col] < median_score]  # V3
        lines.append(f"## Score Comparison (split at {median_score:.0f})")  # V3
        for horizon in [30, 90]:  # V3
            col = f"return_{horizon}d"  # V3
            if col in summary.columns:  # V3
                high_avg = high_group[col].dropna().mean() if not high_group.empty else float("nan")  # V3
                low_avg = low_group[col].dropna().mean() if not low_group.empty else float("nan")  # V3
                lines.append(f"- {horizon}d: high-score avg={high_avg:.1f}%, low-score avg={low_avg:.1f}%")  # V3
        lines.append("")  # V3

    try:
        table = summary.to_markdown(index=False)
    except ImportError:
        table = summary.to_csv(index=False)
    lines.append("## All Signals")
    lines.append("")
    lines.append(table)
    lines.append("")

    write_text(REPORTS_DIR / "backtest_summary.md", "\n".join(lines))


class BacktestEngine:
    def run(self, symbol, asset_class, start_date, end_date):
        return run_simple_forward_test(symbol, asset_class, start_date)
