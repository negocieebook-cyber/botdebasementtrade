from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.signal import argrelmin  # MELHORIA

from src.thresholds import ClassThreshold


@dataclass
class TechnicalSnapshot:
    date: str
    last_close: float
    drawdown_pct: float
    drawdown_ath_pct: float
    drawdown_52w_pct: float
    return_1m_pct: float
    return_3m_pct: float
    return_6m_pct: float
    return_12m_pct: float
    volatility_30d_pct: float
    volatility_90d_pct: float
    avg_volume_30d: float
    avg_dollar_volume_30d: float
    volume_ratio_30d: float
    rsi_14: float
    macd: float
    macd_signal: float
    atr_14_pct: float
    atr_compression_ratio: float
    sma_20: float
    sma_50: float
    sma_100: float
    sma_200: float
    rolling_high_60d: float
    rolling_low_60d: float
    rolling_high_120d: float
    rolling_low_120d: float
    range_position_60d: float
    range_position_120d: float
    support_90d: float
    support_distance_pct: float
    high_252d: float
    low_252d: float
    structure_recovery: bool
    confirmation: bool
    defended_support: bool
    lateralization: bool
    volatility_compression: bool
    exhaustion: bool
    invalidation_level: float
    trigger_level: float
    trigger_volume_confirmed: bool = False   # MELHORIA — True se volume no dia do trigger >= média 30d
    rsi_bullish_divergence: bool = False     # MELHORIA — preço mínima < anterior, RSI não confirma
    macd_bullish_divergence: bool = False    # MELHORIA — mesmo critério com MACD
    pattern_snapshot: object = None          # MELHORIA — PatternSnapshot do pattern_engine


def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window, min_periods=window).mean()


def rsi(series: pd.Series, window: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(window=window).mean()
    loss = (-delta.clip(upper=0)).rolling(window=window).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def atr(df: pd.DataFrame, window: int = 14) -> pd.Series:
    high_low = df["High"] - df["Low"]
    high_close = (df["High"] - df["Close"].shift()).abs()
    low_close = (df["Low"] - df["Close"].shift()).abs()
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return true_range.rolling(window=window, min_periods=window).mean()


def add_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    work = _normalize_ohlcv_columns(df)
    close = work["Close"]
    high = work["High"]
    low = work["Low"]
    volume = work["Volume"] if "Volume" in work.columns else pd.Series(np.nan, index=work.index)
    daily_returns = close.pct_change()

    work["SMA20"] = sma(close, 20)
    work["SMA50"] = sma(close, 50)
    work["SMA100"] = sma(close, 100)
    work["SMA200"] = sma(close, 200)
    work["RSI14"] = rsi(close, 14)

    ema_12 = close.ewm(span=12, adjust=False, min_periods=12).mean()
    ema_26 = close.ewm(span=26, adjust=False, min_periods=26).mean()
    work["MACD"] = ema_12 - ema_26
    work["MACDSignal"] = work["MACD"].ewm(span=9, adjust=False, min_periods=9).mean()
    work["ATR14"] = atr(work, 14)

    historical_high = close.cummax()
    rolling_high_52w = close.rolling(window=252, min_periods=1).max()
    work["DrawdownATHPct"] = ((close / historical_high) - 1) * 100
    work["Drawdown52WPct"] = ((close / rolling_high_52w) - 1) * 100
    work["Return1MPct"] = close.pct_change(21) * 100
    work["Return3MPct"] = close.pct_change(63) * 100
    work["Return6MPct"] = close.pct_change(126) * 100
    work["Return12MPct"] = close.pct_change(252) * 100
    work["Volatility30DPct"] = daily_returns.rolling(window=30, min_periods=20).std() * np.sqrt(252) * 100
    work["Volatility90DPct"] = daily_returns.rolling(window=90, min_periods=60).std() * np.sqrt(252) * 100
    work["AvgVolume30D"] = volume.rolling(window=30, min_periods=20).mean()
    work["AvgDollarVolume30D"] = work["AvgVolume30D"] * close
    work["VolumeRatio30D"] = volume / work["AvgVolume30D"]

    work["RollingHigh60D"] = high.rolling(window=60, min_periods=20).max()
    work["RollingLow60D"] = low.rolling(window=60, min_periods=20).min()
    work["RollingHigh120D"] = high.rolling(window=120, min_periods=40).max()
    work["RollingLow120D"] = low.rolling(window=120, min_periods=40).min()
    work["RangePosition60D"] = _range_position(close, work["RollingLow60D"], work["RollingHigh60D"])
    work["RangePosition120D"] = _range_position(close, work["RollingLow120D"], work["RollingHigh120D"])

    atr_14_pct = (work["ATR14"] / close) * 100
    recent_atr_pct = atr_14_pct.rolling(window=20, min_periods=10).mean()
    prior_atr_pct = atr_14_pct.rolling(window=90, min_periods=60).mean()
    work["VolatilityCompression"] = recent_atr_pct / prior_atr_pct
    return work


def _normalize_ohlcv_columns(df: pd.DataFrame) -> pd.DataFrame:
    column_map = {
        "date": "Date",
        "open": "Open",
        "high": "High",
        "low": "Low",
        "close": "Close",
        "adj_close": "Adj Close",
        "volume": "Volume",
    }
    work = df.rename(columns={column: column_map.get(str(column), column) for column in df.columns}).copy()
    if "Date" in work.columns:
        work = work.set_index("Date", drop=False)
    return work


def _range_position(close: pd.Series, rolling_low: pd.Series, rolling_high: pd.Series) -> pd.Series:
    range_width = (rolling_high - rolling_low).replace(0, np.nan)
    return ((close - rolling_low) / range_width) * 100


def _last_float(row: pd.Series, column: str) -> float:
    value = row[column] if column in row and pd.notna(row[column]) else np.nan
    return float(value)


def _find_support_level(df: pd.DataFrame, window: int = 90) -> float:  # MELHORIA
    """Suporte como zona de preço com mais toques nos últimos `window` dias (fallback: mínimo)."""  # MELHORIA
    tail = df.tail(window)  # MELHORIA
    lows = tail["Low"].dropna().values  # MELHORIA
    if len(lows) < 10:  # MELHORIA
        return float(np.min(lows))  # MELHORIA
    idx = argrelmin(lows, order=3)[0]  # MELHORIA
    if len(idx) < 2:  # MELHORIA
        return float(np.min(lows))  # MELHORIA
    local_lows = lows[idx]  # MELHORIA
    best_level = float(np.min(local_lows))  # MELHORIA
    best_count = 0  # MELHORIA
    for level in local_lows:  # MELHORIA
        count = int(np.sum(np.abs(local_lows / level - 1) <= 0.02))  # MELHORIA
        if count > best_count:  # MELHORIA
            best_count = count  # MELHORIA
            best_level = float(level)  # MELHORIA
    return best_level  # MELHORIA


def _detect_bullish_divergence(close: pd.Series, indicator: pd.Series, window: int = 60) -> bool:  # MELHORIA
    """True se divergência bullish: preço faz mínima mais baixa mas indicador não confirma."""  # MELHORIA
    c = close.tail(window).dropna()  # MELHORIA
    ind = indicator.tail(window).dropna()  # MELHORIA
    if len(c) < 20 or len(ind) < 20:  # MELHORIA
        return False  # MELHORIA
    mid = len(c) // 2  # MELHORIA
    price_first_low = c.iloc[:mid].min()  # MELHORIA
    price_second_low = c.iloc[mid:].min()  # MELHORIA
    ind_first_low = ind.iloc[:mid].min()  # MELHORIA
    ind_second_low = ind.iloc[mid:].min()  # MELHORIA
    return bool(price_second_low < price_first_low and ind_second_low > ind_first_low)  # MELHORIA


class TechnicalEngine:
    def analyze(self, df: pd.DataFrame, threshold: ClassThreshold, asset_class: str = "equity_indices") -> TechnicalSnapshot:  # MELHORIA
        work = add_technical_indicators(df)
        close = work["Close"]

        tail_252 = work.tail(252)
        tail_90 = work.tail(90)
        last = work.iloc[-1]
        last_date = work.index[-1]
        last_close = float(last["Close"])
        high_252d = float(tail_252["Close"].max())
        low_252d = float(tail_252["Close"].min())
        drawdown_pct = _last_float(last, "Drawdown52WPct")
        support_90d = _find_support_level(work, window=90)  # MELHORIA — zona de suporte com mais toques
        support_distance_pct = ((last_close / support_90d) - 1) * 100 if support_90d else 0.0

        atr_14 = _last_float(last, "ATR14")
        atr_14_pct = (atr_14 / last_close) * 100 if last_close else np.nan
        atr_compression_ratio = _last_float(last, "VolatilityCompression")

        last_rsi = _last_float(last, "RSI14")
        sma_20 = _last_float(last, "SMA20")
        sma_50 = _last_float(last, "SMA50")
        sma_100 = _last_float(last, "SMA100")
        sma_200 = _last_float(last, "SMA200")
        twenty_high = float(work["High"].tail(20).max())
        ten_low = float(work["Low"].tail(10).min())

        defended_support = 0 <= support_distance_pct <= threshold.support_distance_pct
        volatility_compression = atr_compression_ratio <= threshold.volatility_compression_ratio
        exhaustion = drawdown_pct <= threshold.extreme_drawdown_pct and last_rsi >= threshold.capitulation_rsi
        lateral_range_pct = ((tail_90["High"].max() / tail_90["Low"].min()) - 1) * 100
        lateralization = lateral_range_pct <= abs(threshold.extreme_drawdown_pct) * 0.75
        structure_recovery = last_close > sma_50 and sma_50 >= work["SMA50"].tail(20).mean()
        confirmation = last_close >= twenty_high * 0.995 or (last_close > sma_50 and last_rsi >= 50)

        # MELHORIA — volume confirmação do trigger
        last_20 = work.tail(20)
        high_idx = last_20["High"].idxmax()
        volume_at_high = float(work.loc[high_idx, "Volume"]) if "Volume" in work.columns else 0.0
        avg_vol_30 = float(work["Volume"].tail(30).mean()) if "Volume" in work.columns else 0.0
        trigger_volume_confirmed = volume_at_high >= avg_vol_30 * 0.8 if avg_vol_30 > 0 else False  # MELHORIA

        # MELHORIA — divergências bullish RSI e MACD
        rsi_bullish_divergence = _detect_bullish_divergence(close, work["RSI14"], window=60)  # MELHORIA
        macd_divergence_series = work["MACD"].fillna(0)  # MELHORIA
        macd_bullish_divergence = _detect_bullish_divergence(close, macd_divergence_series, window=60)  # MELHORIA

        # MELHORIA — padrões gráficos via PatternEngine
        pattern_snapshot = None  # MELHORIA
        try:  # MELHORIA
            from src.pattern_engine import PatternEngine as _PatternEngine  # MELHORIA
            pattern_snapshot = _PatternEngine().analyze(df, asset_class)  # MELHORIA
        except Exception:  # MELHORIA
            pass  # MELHORIA

        return TechnicalSnapshot(
            date=str(last_date.date() if hasattr(last_date, "date") else last_date),
            last_close=last_close,
            drawdown_pct=float(drawdown_pct),
            drawdown_ath_pct=_last_float(last, "DrawdownATHPct"),
            drawdown_52w_pct=_last_float(last, "Drawdown52WPct"),
            return_1m_pct=_last_float(last, "Return1MPct"),
            return_3m_pct=_last_float(last, "Return3MPct"),
            return_6m_pct=_last_float(last, "Return6MPct"),
            return_12m_pct=_last_float(last, "Return12MPct"),
            volatility_30d_pct=_last_float(last, "Volatility30DPct"),
            volatility_90d_pct=_last_float(last, "Volatility90DPct"),
            avg_volume_30d=_last_float(last, "AvgVolume30D"),
            avg_dollar_volume_30d=_last_float(last, "AvgDollarVolume30D"),
            volume_ratio_30d=_last_float(last, "VolumeRatio30D"),
            rsi_14=last_rsi,
            macd=_last_float(last, "MACD"),
            macd_signal=_last_float(last, "MACDSignal"),
            atr_14_pct=float(atr_14_pct),
            atr_compression_ratio=atr_compression_ratio,
            sma_20=sma_20,
            sma_50=sma_50,
            sma_100=sma_100,
            sma_200=sma_200,
            rolling_high_60d=_last_float(last, "RollingHigh60D"),
            rolling_low_60d=_last_float(last, "RollingLow60D"),
            rolling_high_120d=_last_float(last, "RollingHigh120D"),
            rolling_low_120d=_last_float(last, "RollingLow120D"),
            range_position_60d=_last_float(last, "RangePosition60D"),
            range_position_120d=_last_float(last, "RangePosition120D"),
            support_90d=support_90d,
            support_distance_pct=float(support_distance_pct),
            high_252d=high_252d,
            low_252d=low_252d,
            structure_recovery=bool(structure_recovery),
            confirmation=bool(confirmation),
            defended_support=bool(defended_support),
            lateralization=bool(lateralization),
            volatility_compression=bool(volatility_compression),
            exhaustion=bool(exhaustion),
            invalidation_level=float(min(ten_low, support_90d)),
            trigger_level=twenty_high,
            trigger_volume_confirmed=bool(trigger_volume_confirmed),   # MELHORIA
            rsi_bullish_divergence=bool(rsi_bullish_divergence),       # MELHORIA
            macd_bullish_divergence=bool(macd_bullish_divergence),     # MELHORIA
            pattern_snapshot=pattern_snapshot,                         # MELHORIA
        )
