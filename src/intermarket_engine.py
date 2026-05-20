from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import yfinance as yf

from src.config import START_DATE
from src.universe import Asset

DXY_PROXY = "UUP"
VIX_PROXY = "^VIX"
TREASURY_YIELD_10Y_PROXY = "^TNX"

REQUIRED_RELATIONS = {
    "TLT": ["DGS10"],
    "GLD": ["DXY", "UUP"],
    "BTC-USD": ["QQQ"],
    "BTC-USD_EXTENDED": ["DXY", "UUP"],
    "QQQ": ["DGS10"],
    "SPY": ["VIX", "^VIX"],
    "HYG": ["SPY"],
    "IWM": ["SPY"],
}

INTERMARKET_SYMBOLS = [
    "TLT",
    "GLD",
    "BTC-USD",
    "QQQ",
    "SPY",
    "IWM",
    "HYG",
    DXY_PROXY,
    VIX_PROXY,
    TREASURY_YIELD_10Y_PROXY,
]


@dataclass
class IntermarketSnapshot:
    score: float
    regime: str
    notes: list[str]


class IntermarketEngine:
    def analyze(self, asset: Asset, market_data: dict[str, pd.DataFrame]) -> IntermarketSnapshot:
        result = _calculate_intermarket_score_from_data(asset.symbol, asset.asset_class, market_data)
        score = result["intermarket_score"] * 10
        regime = "supportive" if result["intermarket_score"] >= 7 else "hostile" if result["intermarket_score"] <= 3 else "mixed"
        notes = result["notes"]
        return IntermarketSnapshot(score=score, regime=regime, notes=notes or ["Intermarket context unavailable."])


def calculate_intermarket_score(symbol: str, asset_class: str, start_date: str = START_DATE) -> dict:
    data = _fetch_intermarket_data(start_date)
    result = _calculate_intermarket_score_from_data(symbol, asset_class, data)
    pros = [note for note in result["notes"] if note.startswith("+")]
    cons = [] if pros else result["notes"]
    result["intermarket_summary"] = f"Intermarket {result['intermarket_regime']}, score {result['intermarket_score']:.0f}/10."
    result["intermarket_pros"] = pros
    result["intermarket_cons"] = cons
    return result


def _calculate_intermarket_score_from_data(symbol: str, asset_class: str, market_data: dict[str, pd.DataFrame]) -> dict:
    normalized_symbol = symbol.upper()
    notes: list[str] = []
    score = 0.0

    if not market_data:
        return _missing_intermarket_result(symbol, asset_class, "No intermarket data supplied.")

    if asset_class == "bonds":
        if not _has_usable_data(market_data, ["TLT", TREASURY_YIELD_10Y_PROXY]):
            return _missing_intermarket_result(symbol, asset_class, "Missing required intermarket data: TLT and/or ^TNX.")
        score += _rule(_is_rising(market_data.get("TLT")), 5, "TLT rising.", notes)
        score += _rule(_is_falling(market_data.get(TREASURY_YIELD_10Y_PROXY)), 5, "10Y yield proxy ^TNX falling.", notes)
    elif asset_class == "commodities" or normalized_symbol == "GLD":
        if not _has_usable_data(market_data, ["GLD", DXY_PROXY]):
            return _missing_intermarket_result(symbol, asset_class, "Missing required intermarket data: GLD and/or UUP.")
        score += _rule(_is_rising(market_data.get("GLD")), 5, "GLD rising.", notes)
        score += _rule(_is_falling(market_data.get(DXY_PROXY)), 5, "Dollar proxy UUP falling.", notes)
    elif asset_class == "crypto":
        if not _has_usable_data(market_data, ["BTC-USD", "QQQ", DXY_PROXY]):
            return _missing_intermarket_result(symbol, asset_class, "Missing required intermarket data: BTC-USD, QQQ and/or UUP.")
        score += _rule(_is_rising(market_data.get("BTC-USD")), 4, "BTC rising.", notes)
        score += _rule(_is_rising(market_data.get("QQQ")), 3, "QQQ rising.", notes)
        score += _rule(_is_falling(market_data.get(DXY_PROXY)), 3, "Dollar proxy UUP falling.", notes)
    elif asset_class in {"growth_stocks", "mega_caps"}:
        if not _has_usable_data(market_data, ["QQQ", TREASURY_YIELD_10Y_PROXY]):
            return _missing_intermarket_result(symbol, asset_class, "Missing required intermarket data: QQQ and/or ^TNX.")
        score += _rule(_is_rising(market_data.get("QQQ")), 5, "QQQ rising.", notes)
        score += _rule(_is_falling(market_data.get(TREASURY_YIELD_10Y_PROXY)), 5, "10Y yield proxy ^TNX falling.", notes)
    elif asset_class == "equity_indices":
        if not _has_usable_data(market_data, ["SPY", VIX_PROXY]):
            return _missing_intermarket_result(symbol, asset_class, "Missing required intermarket data: SPY and/or ^VIX.")
        score += _rule(_is_rising(market_data.get("SPY")), 5, "SPY rising.", notes)
        score += _rule(_is_falling(market_data.get(VIX_PROXY)), 5, "VIX proxy ^VIX falling.", notes)
    elif asset_class == "banks":
        notes.append("Banks curve/yield rule is intentionally neutral until specific bank data is configured.")
        score = 5.0
    elif asset_class == "emerging_markets":
        if not _has_usable_data(market_data, [DXY_PROXY]) or not (_has_usable_data(market_data, [normalized_symbol]) or _has_usable_data(market_data, ["EEM"])):
            return _missing_intermarket_result(symbol, asset_class, "Missing required intermarket data: EEM/KWEB proxy and/or UUP.")
        score += _rule(_is_rising(market_data.get(normalized_symbol)) or _is_rising(market_data.get("EEM")), 5, "EEM/KWEB proxy rising.", notes)
        score += _rule(_is_falling(market_data.get(DXY_PROXY)), 5, "Dollar proxy UUP falling.", notes)
    else:
        return _missing_intermarket_result(symbol, asset_class, f"No intermarket rule for asset_class={asset_class}.")

    if not notes:
        return _missing_intermarket_result(symbol, asset_class, "Required intermarket data missing or insufficient.")

    score = max(0.0, min(10.0, score))
    return {
        "symbol": symbol,
        "asset_class": asset_class,
        "intermarket_score": score,
        "intermarket_regime": "supportive" if score >= 7 else "neutral/mixed" if score >= 4 else "hostile/low_support",
        "notes": notes,
    }


def _fetch_intermarket_data(start_date: str = START_DATE) -> dict[str, pd.DataFrame]:
    data = {}
    for symbol in INTERMARKET_SYMBOLS:
        try:
            df = yf.download(
                tickers=symbol,
                start=start_date,
                interval="1d",
                auto_adjust=True,
                progress=False,
                threads=False,
            )
        except Exception:
            continue
        if not df.empty:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            data[symbol] = df.rename(columns=str.title).dropna(subset=["Close"])
    return data


def _missing_intermarket_result(symbol: str, asset_class: str, warning: str) -> dict:
    return {
        "symbol": symbol,
        "asset_class": asset_class,
        "intermarket_score": 0.0,
        "intermarket_regime": "not_calculated",
        "notes": [warning],
    }


def _has_usable_data(market_data: dict[str, pd.DataFrame], symbols: list[str]) -> bool:
    for symbol in symbols:
        df = market_data.get(symbol)
        if df is None or df.empty or "Close" not in df.columns or len(df["Close"].dropna()) < 60:
            return False
    return True


def _rule(condition: bool | None, points: float, note: str, notes: list[str]) -> float:
    if condition:
        notes.append(f"+{points:.0f}: {note}")
        return points
    return 0.0


def _is_rising(df: pd.DataFrame | None) -> bool | None:
    trend = _trend_direction(df)
    return None if trend is None else trend > 0


def _is_falling(df: pd.DataFrame | None) -> bool | None:
    trend = _trend_direction(df)
    return None if trend is None else trend < 0


def _trend_direction(df: pd.DataFrame | None) -> float | None:
    if df is None or df.empty or "Close" not in df.columns or len(df) < 60:
        return None
    close = df["Close"].dropna()
    if len(close) < 60:
        return None
    sma_20 = close.rolling(20).mean().iloc[-1]
    sma_50 = close.rolling(50).mean().iloc[-1]
    last = close.iloc[-1]
    return float((last / sma_20 - 1) + (sma_20 / sma_50 - 1))


def _trend_score(df: pd.DataFrame) -> float:
    close = df["Close"].dropna()
    if len(close) < 120:
        return 50.0
    sma_50 = close.rolling(50).mean().iloc[-1]
    sma_100 = close.rolling(100).mean().iloc[-1]
    last = close.iloc[-1]
    score = 50.0
    if last > sma_50:
        score += 15.0
    if sma_50 > sma_100:
        score += 15.0
    return max(0.0, min(100.0, score))
