from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd


def evaluate_data_quality(df: pd.DataFrame, symbol: str) -> dict:
    issues: list[str] = []
    if df is None or df.empty:
        return {
            "confidence_score": 0,
            "confidence_level": "Baixa",
            "issues": ["Sem dados de preço."],
            "has_enough_history": False,
            "has_volume": False,
            "missing_values_pct": 100.0,
            "last_date": "",
            "source": "yfinance/cache",
        }

    work = df.copy()
    has_enough_history = len(work) >= 250
    if not has_enough_history:
        issues.append("Histórico inferior a 250 candles.")

    volume_column = "Volume" if "Volume" in work.columns else "volume" if "volume" in work.columns else None
    has_volume = bool(volume_column and work[volume_column].notna().any())
    if not has_volume:
        issues.append("Volume ausente.")

    missing_values_pct = float(work.isna().mean().mean() * 100)
    if missing_values_pct > 5:
        issues.append(f"Dados ausentes acima de 5% ({missing_values_pct:.2f}%).")

    last_index = work.index[-1]
    if "Date" in work.columns:
        last_index = work["Date"].iloc[-1]
    last_date = pd.to_datetime(last_index, errors="coerce")
    last_date_str = "" if pd.isna(last_date) else last_date.strftime("%Y-%m-%d")

    is_updated = True
    if not pd.isna(last_date):
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        age_days = (now - last_date.to_pydatetime().replace(tzinfo=None)).days
        if age_days > 7:
            is_updated = False
            issues.append(f"Última data disponível parece antiga: {last_date_str}.")

    gaps = 0
    if isinstance(work.index, pd.DatetimeIndex) and len(work.index) > 2:
        gaps = int((work.index.to_series().diff().dt.days > 10).sum())
        if gaps > 0:
            issues.append(f"Foram encontrados {gaps} gaps grandes.")

    score = 100
    if not has_enough_history:
        score -= 30
    if not has_volume:
        score -= 20
    if missing_values_pct > 5:
        score -= min(25, int(missing_values_pct))
    if not is_updated:
        score -= 20
    if gaps > 0:
        score -= min(15, gaps * 3)
    score = max(0, min(100, score))

    level = "Alta" if score >= 80 else "Média" if score >= 50 else "Baixa"
    return {
        "confidence_score": score,
        "confidence_level": level,
        "issues": issues,
        "has_enough_history": has_enough_history,
        "has_volume": has_volume,
        "missing_values_pct": missing_values_pct,
        "last_date": last_date_str,
        "source": "yfinance/cache",
    }
