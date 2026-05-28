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

BRAZIL_BENCHMARK_PRIMARY = "BOVA11.SA"
BRAZIL_BENCHMARK_FALLBACK = "EWZ"

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
    "XLF",
    "EFA",
    "VNQ",
    BRAZIL_BENCHMARK_PRIMARY,
    BRAZIL_BENCHMARK_FALLBACK,
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


def _score_trend(df: pd.DataFrame | None, points_max: float) -> tuple[float, str]:  # MELHORIA
    """Retorna (score, note) onde score é 0–points_max proporcional à força da tendência."""  # MELHORIA
    if df is None or df.empty or "Close" not in df.columns:  # MELHORIA
        return 0.0, ""  # MELHORIA
    close = df["Close"].dropna()  # MELHORIA
    if len(close) < 60:  # MELHORIA
        return 0.0, ""  # MELHORIA
    last = close.iloc[-1]  # MELHORIA
    sma20 = close.rolling(20).mean().iloc[-1]  # MELHORIA
    sma50 = close.rolling(50).mean().iloc[-1]  # MELHORIA
    sma200 = close.rolling(200).mean().iloc[-1] if len(close) >= 200 else sma50  # MELHORIA
    score = 0.0  # MELHORIA
    if last > sma20:  # MELHORIA
        score += points_max * 0.4  # MELHORIA
    if sma20 > sma50:  # MELHORIA
        score += points_max * 0.3  # MELHORIA
    if last > sma200:  # MELHORIA
        score += points_max * 0.3  # MELHORIA
    return min(score, points_max), f"trend score {score:.1f}/{points_max}"  # MELHORIA


def _score_trend_falling(df: pd.DataFrame | None, points_max: float) -> tuple[float, str]:  # MELHORIA
    """Versão inversa: pontua quando o ativo está caindo (ex: VIX, yields)."""  # MELHORIA
    if df is None or df.empty or "Close" not in df.columns:  # MELHORIA
        return 0.0, ""  # MELHORIA
    close = df["Close"].dropna()  # MELHORIA
    if len(close) < 60:  # MELHORIA
        return 0.0, ""  # MELHORIA
    last = close.iloc[-1]  # MELHORIA
    sma20 = close.rolling(20).mean().iloc[-1]  # MELHORIA
    sma50 = close.rolling(50).mean().iloc[-1]  # MELHORIA
    sma200 = close.rolling(200).mean().iloc[-1] if len(close) >= 200 else sma50  # MELHORIA
    score = 0.0  # MELHORIA
    if last < sma20:  # MELHORIA
        score += points_max * 0.4  # MELHORIA
    if sma20 < sma50:  # MELHORIA
        score += points_max * 0.3  # MELHORIA
    if last < sma200:  # MELHORIA
        score += points_max * 0.3  # MELHORIA
    return min(score, points_max), f"falling trend score {score:.1f}/{points_max}"  # MELHORIA


def _calculate_intermarket_score_from_data(symbol: str, asset_class: str, market_data: dict[str, pd.DataFrame]) -> dict:
    normalized_symbol = symbol.upper()
    notes: list[str] = []
    score = 0.0

    if not market_data:
        return _missing_intermarket_result(symbol, asset_class, "No intermarket data supplied.")

    if asset_class == "bonds":
        if not _has_usable_data(market_data, ["TLT", TREASURY_YIELD_10Y_PROXY]):
            return _missing_intermarket_result(symbol, asset_class, "Missing required intermarket data: TLT and/or ^TNX.")
        s1, n1 = _score_trend(market_data.get("TLT"), 5)  # MELHORIA
        s2, n2 = _score_trend_falling(market_data.get(TREASURY_YIELD_10Y_PROXY), 5)  # MELHORIA
        score += s1; score += s2  # MELHORIA
        if n1: notes.append(f"+{s1:.1f}: TLT rising ({n1}).")  # MELHORIA
        if n2: notes.append(f"+{s2:.1f}: 10Y yield proxy ^TNX falling ({n2}).")  # MELHORIA
    elif asset_class == "commodities" or normalized_symbol == "GLD":
        if not _has_usable_data(market_data, ["GLD", DXY_PROXY]):
            return _missing_intermarket_result(symbol, asset_class, "Missing required intermarket data: GLD and/or UUP.")
        s1, n1 = _score_trend(market_data.get("GLD"), 5)  # MELHORIA
        s2, n2 = _score_trend_falling(market_data.get(DXY_PROXY), 5)  # MELHORIA
        score += s1; score += s2  # MELHORIA
        if n1: notes.append(f"+{s1:.1f}: GLD rising ({n1}).")  # MELHORIA
        if n2: notes.append(f"+{s2:.1f}: Dollar proxy UUP falling ({n2}).")  # MELHORIA
    elif asset_class == "crypto":
        if not _has_usable_data(market_data, ["BTC-USD", "QQQ", DXY_PROXY]):
            return _missing_intermarket_result(symbol, asset_class, "Missing required intermarket data: BTC-USD, QQQ and/or UUP.")
        s1, n1 = _score_trend(market_data.get("BTC-USD"), 4)  # MELHORIA
        s2, n2 = _score_trend(market_data.get("QQQ"), 3)  # MELHORIA
        s3, n3 = _score_trend_falling(market_data.get(DXY_PROXY), 3)  # MELHORIA
        score += s1; score += s2; score += s3  # MELHORIA
        if n1: notes.append(f"+{s1:.1f}: BTC rising ({n1}).")  # MELHORIA
        if n2: notes.append(f"+{s2:.1f}: QQQ rising ({n2}).")  # MELHORIA
        if n3: notes.append(f"+{s3:.1f}: Dollar proxy UUP falling ({n3}).")  # MELHORIA
    elif asset_class in {"growth_stocks", "mega_caps"}:
        if not _has_usable_data(market_data, ["QQQ", TREASURY_YIELD_10Y_PROXY]):
            return _missing_intermarket_result(symbol, asset_class, "Missing required intermarket data: QQQ and/or ^TNX.")
        s1, n1 = _score_trend(market_data.get("QQQ"), 5)  # MELHORIA
        s2, n2 = _score_trend_falling(market_data.get(TREASURY_YIELD_10Y_PROXY), 5)  # MELHORIA
        score += s1; score += s2  # MELHORIA
        if n1: notes.append(f"+{s1:.1f}: QQQ rising ({n1}).")  # MELHORIA
        if n2: notes.append(f"+{s2:.1f}: 10Y yield proxy ^TNX falling ({n2}).")  # MELHORIA
    elif asset_class == "equity_indices":
        if not _has_usable_data(market_data, ["SPY", VIX_PROXY]):
            return _missing_intermarket_result(symbol, asset_class, "Missing required intermarket data: SPY and/or ^VIX.")
        s1, n1 = _score_trend(market_data.get("SPY"), 5)  # MELHORIA
        s2, n2 = _score_trend_falling(market_data.get(VIX_PROXY), 5)  # MELHORIA
        score += s1; score += s2  # MELHORIA
        if n1: notes.append(f"+{s1:.1f}: SPY rising ({n1}).")  # MELHORIA
        if n2: notes.append(f"+{s2:.1f}: VIX proxy ^VIX falling ({n2}).")  # MELHORIA
    elif asset_class in {"sectors", "defensive_dividends"}:  # V3
        if not _has_usable_data(market_data, ["SPY", VIX_PROXY]):  # V3
            return _missing_intermarket_result(symbol, asset_class, "Missing required intermarket data: SPY and/or ^VIX.")  # V3
        s1, n1 = _score_trend(market_data.get("SPY"), 5)  # V3
        s2, n2 = _score_trend_falling(market_data.get(VIX_PROXY), 5)  # V3
        score += s1; score += s2  # V3
        if n1: notes.append(f"+{s1:.1f}: SPY rising ({n1}).")  # V3
        if n2: notes.append(f"+{s2:.1f}: VIX proxy ^VIX falling ({n2}).")  # V3
    elif asset_class == "reits":  # V3
        vnq_df = market_data.get("VNQ")  # V3
        tlt_df = market_data.get("TLT")  # V3
        if vnq_df is None and tlt_df is None:  # V3
            return _missing_intermarket_result(symbol, asset_class, "Missing required intermarket data: VNQ and TLT.")  # V3
        s1, n1 = _score_trend(vnq_df, 5)  # V3
        s2, n2 = _score_trend_falling(market_data.get(TREASURY_YIELD_10Y_PROXY), 5)  # V3
        score += s1; score += s2  # V3
        if n1: notes.append(f"+{s1:.1f}: VNQ rising ({n1}).")  # V3
        if n2: notes.append(f"+{s2:.1f}: 10Y yield ^TNX falling favors REITs ({n2}).")  # V3
    elif asset_class == "developed_international":  # V3
        efa_df = market_data.get("EFA")  # V3
        if efa_df is None:  # V3
            return _missing_intermarket_result(symbol, asset_class, "Missing required intermarket data: EFA and/or UUP.")  # V3
        s1, n1 = _score_trend(efa_df, 5)  # V3
        s2, n2 = _score_trend_falling(market_data.get(DXY_PROXY), 5)  # V3
        score += s1; score += s2  # V3
        if n1: notes.append(f"+{s1:.1f}: EFA rising ({n1}).")  # V3
        if n2: notes.append(f"+{s2:.1f}: Dollar proxy UUP falling favors international ({n2}).")  # V3
    elif asset_class == "banks":  # V3 — replaced fixed 5.0 with XLF + yield trend
        xlf_df = market_data.get("XLF")  # V3
        tnx_df = market_data.get(TREASURY_YIELD_10Y_PROXY)  # V3
        if xlf_df is None and tnx_df is None:  # V3
            return _missing_intermarket_result(symbol, asset_class, "Missing required intermarket data: XLF and/or ^TNX.")  # V3
        s1, n1 = _score_trend(xlf_df, 5)  # V3
        s2, n2 = _score_trend(tnx_df, 5)  # V3 — banks benefit from rising yields
        score += s1; score += s2  # V3
        if n1: notes.append(f"+{s1:.1f}: XLF (banks ETF) rising ({n1}).")  # V3
        if n2: notes.append(f"+{s2:.1f}: 10Y yield ^TNX rising supports bank margins ({n2}).")  # V3
    elif asset_class == "emerging_markets":
        if not _has_usable_data(market_data, [DXY_PROXY]) or not (_has_usable_data(market_data, [normalized_symbol]) or _has_usable_data(market_data, ["EEM"])):
            return _missing_intermarket_result(symbol, asset_class, "Missing required intermarket data: EEM/KWEB proxy and/or UUP.")
        em_df = market_data.get(normalized_symbol)
        if em_df is None or (hasattr(em_df, "empty") and em_df.empty):
            em_df = market_data.get("EEM")
        s1, n1 = _score_trend(em_df, 5)  # MELHORIA
        s2, n2 = _score_trend_falling(market_data.get(DXY_PROXY), 5)  # MELHORIA
        score += s1; score += s2  # MELHORIA
        if n1: notes.append(f"+{s1:.1f}: EEM/KWEB proxy rising ({n1}).")  # MELHORIA
        if n2: notes.append(f"+{s2:.1f}: Dollar proxy UUP falling ({n2}).")  # MELHORIA
    elif asset_class.startswith("brazil_"):
        bova_df = market_data.get(BRAZIL_BENCHMARK_PRIMARY) or market_data.get(BRAZIL_BENCHMARK_FALLBACK)
        bench_label = BRAZIL_BENCHMARK_PRIMARY if market_data.get(BRAZIL_BENCHMARK_PRIMARY) is not None else BRAZIL_BENCHMARK_FALLBACK
        if bova_df is None:
            return _missing_intermarket_result(symbol, asset_class, f"Missing required intermarket data: {BRAZIL_BENCHMARK_PRIMARY}/{BRAZIL_BENCHMARK_FALLBACK} and/or UUP.")
        s1, n1 = _score_trend(bova_df, 6)
        s2, n2 = _score_trend_falling(market_data.get(DXY_PROXY), 4)
        score += s1; score += s2
        if n1: notes.append(f"+{s1:.1f}: {bench_label} (Ibovespa proxy) rising ({n1}).")
        if n2: notes.append(f"+{s2:.1f}: Dollar proxy UUP falling favors Brazil assets ({n2}).")
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
