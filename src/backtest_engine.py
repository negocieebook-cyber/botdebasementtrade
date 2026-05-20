from __future__ import annotations

import pandas as pd

from src.config import REPORTS_DIR, START_DATE
from src.data_collector import get_price_data
from src.signal_history import load_signal_history
from src.utils import write_text


def run_simple_forward_test(symbol: str, asset_class: str, signal_date: str, horizons=[30, 90, 180, 365]) -> dict:
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
    }
    for horizon in horizons:
        if len(future) > horizon:
            future_price = float(future.iloc[horizon]["close"])
            result[f"return_{horizon}d"] = ((future_price / signal_price) - 1) * 100
        else:
            result[f"return_{horizon}d"] = None

    drawdowns = (future["close"] / signal_price - 1) * 100
    result["max_drawdown_after_signal"] = float(drawdowns.min()) if not drawdowns.empty else None
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
            )
        )
    summary = pd.DataFrame(rows)
    _save_backtest_summary(summary)
    return summary


def _save_backtest_summary(summary: pd.DataFrame) -> None:
    if summary.empty:
        content = "# Backtest Summary\n\nNo historical notified signals available yet.\n"
    else:
        try:
            table = summary.to_markdown(index=False)
        except ImportError:
            table = summary.to_csv(index=False)
        content = "\n".join(
            [
                "# Backtest Summary",
                "",
                table,
                "",
            ]
        )
    write_text(REPORTS_DIR / "backtest_summary.md", content)


class BacktestEngine:
    def run(self, symbol, asset_class, start_date, end_date):
        return run_simple_forward_test(symbol, asset_class, start_date)
