# V4 — Momentum module: detecta compressão → explosão (não exige drawdown mínimo)
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class MomentumSnapshot:  # V4
    symbol: str  # V4
    asset_class: str  # V4
    momentum_score: float  # V4
    signal_type: str  # V4
    classification: str  # V4
    volatility_compression: bool  # V4
    volume_expansion: bool  # V4
    price_breakout: bool  # V4
    momentum_rsi: bool  # V4
    trend_alignment: bool  # V4
    nr7_or_inside: bool  # V4
    resistance_level: float  # V4
    stop_level: float  # V4
    close: float  # V4
    volume_ratio: float  # V4
    atr_compression_ratio: float  # V4
    rsi_14: float  # V4
    pros: list[str] = field(default_factory=list)  # V4
    cons: list[str] = field(default_factory=list)  # V4
    summary: str = ""  # V4
    alert_worthy: bool = False  # V4


def _calc_rsi(close: pd.Series, window: int = 14) -> float:  # V4
    if len(close) < window + 1:  # V4
        return 50.0  # V4
    delta = close.diff()  # V4
    gain = delta.clip(lower=0).rolling(window=window, min_periods=window).mean()  # V4
    loss = (-delta.clip(upper=0)).rolling(window=window, min_periods=window).mean()  # V4
    last_loss = float(loss.iloc[-1])  # V4
    last_gain = float(gain.iloc[-1])  # V4
    if np.isnan(last_loss) or np.isnan(last_gain):  # V4
        return 50.0  # V4
    if last_loss == 0:  # V4
        return 100.0  # V4
    rs = last_gain / last_loss  # V4
    return float(100 - (100 / (1 + rs)))  # V4


def _calc_atr(df: pd.DataFrame, window: int) -> float:  # V4
    if len(df) < 2:  # V4
        return float(df["High"].iloc[-1] - df["Low"].iloc[-1]) if len(df) > 0 else 0.0  # V4
    high_low = df["High"] - df["Low"]  # V4
    high_close = (df["High"] - df["Close"].shift()).abs()  # V4
    low_close = (df["Low"] - df["Close"].shift()).abs()  # V4
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)  # V4
    result = true_range.rolling(window=window, min_periods=max(1, window // 2)).mean().iloc[-1]  # V4
    return float(result) if not np.isnan(result) else 0.0  # V4


class MomentumEngine:  # V4
    def analyze(self, df: pd.DataFrame, symbol: str, asset_class: str) -> MomentumSnapshot:  # V4
        col_map = {"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}  # V4
        work = df.rename(columns={c: col_map.get(str(c).lower(), c) for c in df.columns}).copy()  # V4

        if work.empty or len(work) < 60:  # V4
            return _empty_snapshot(symbol, asset_class)  # V4

        close = work["Close"].dropna()  # V4
        high = work["High"].dropna()  # V4
        low = work["Low"].dropna()  # V4
        has_volume = "Volume" in work.columns  # V4
        volume = work["Volume"].dropna() if has_volume else pd.Series(dtype=float)  # V4

        # Resistance (max High 20d) and stop (min Low 10d)
        resistance = float(high.tail(20).max())  # V4
        stop = float(low.tail(10).min())  # V4
        last_close = float(close.iloc[-1])  # V4

        # ATR compression ratio: 10d mean vs 40d mean
        atr_10 = _calc_atr(work.tail(50), 10)  # V4
        atr_40 = _calc_atr(work.tail(100), 40)  # V4
        atr_ratio = float(atr_10 / atr_40) if atr_40 > 0 else 1.0  # V4
        volatility_compression = atr_ratio <= 0.75  # V4

        # Volume expansion: last bar vs 30d average
        avg_vol_30 = float(volume.tail(30).mean()) if len(volume) >= 20 else 0.0  # V4
        last_vol = float(volume.iloc[-1]) if len(volume) > 0 else 0.0  # V4
        volume_ratio = float(last_vol / avg_vol_30) if avg_vol_30 > 0 else 0.0  # V4
        volume_expansion = volume_ratio >= 1.8  # V4

        # Price breakout: close >= resistance × 0.995
        price_breakout = last_close >= resistance * 0.995  # V4

        # RSI 14
        rsi_val = _calc_rsi(close, 14)  # V4
        momentum_rsi = rsi_val >= 55  # V4

        # Trend alignment: close > SMA50
        sma_50_series = close.rolling(50, min_periods=30).mean()  # V4
        sma_50 = float(sma_50_series.iloc[-1]) if not np.isnan(sma_50_series.iloc[-1]) else float(close.mean())  # V4
        trend_alignment = last_close > sma_50  # V4

        # NR7: last bar range is the smallest of the 7
        last_7 = work.tail(7)  # V4
        if len(last_7) >= 7:  # V4
            ranges_7 = (last_7["High"] - last_7["Low"]).values  # V4
            nr7 = bool(float(ranges_7[-1]) <= float(ranges_7[:-1].min()))  # V4
        else:  # V4
            nr7 = False  # V4
        # Inside bar: high < prev high AND low > prev low
        if len(work) >= 2:  # V4
            prev_bar = work.iloc[-2]  # V4
            last_bar = work.iloc[-1]  # V4
            inside = bool(last_bar["High"] < prev_bar["High"] and last_bar["Low"] > prev_bar["Low"])  # V4
        else:  # V4
            inside = False  # V4
        nr7_or_inside = nr7 or inside  # V4

        # Score weights
        score = 0.0  # V4
        if volatility_compression:  # V4
            score += 20  # V4
        if volume_expansion:  # V4
            score += 25  # V4
        if price_breakout:  # V4
            score += 25  # V4
        if momentum_rsi:  # V4
            score += 15  # V4
        if trend_alignment:  # V4
            score += 10  # V4
        if nr7_or_inside:  # V4
            score += 5  # V4
        score = float(min(score, 100.0))  # V4

        # Classification
        if score >= 75 and price_breakout and volume_expansion:  # V4
            signal_type = "breakout"  # V4
            classification = "Breakout confirmado com volume"  # V4
            alert_worthy = True  # V4
        elif score >= 55 and volatility_compression and (price_breakout or volume_expansion):  # V4
            signal_type = "pre_breakout"  # V4
            classification = "Pre-breakout — setup em formacao"  # V4
            alert_worthy = True  # V4
        elif score >= 35 and volatility_compression:  # V4
            signal_type = "accumulation"  # V4
            classification = "Acumulacao em andamento"  # V4
            alert_worthy = False  # V4
        else:  # V4
            signal_type = "no_signal"  # V4
            classification = "Sem sinal de momentum"  # V4
            alert_worthy = False  # V4

        # Build pros and cons
        pros: list[str] = []  # V4
        cons: list[str] = []  # V4
        if volatility_compression:  # V4
            pros.append(f"Volatilidade comprimida (ATR ratio {atr_ratio:.2f}).")  # V4
        else:  # V4
            cons.append(f"Volatilidade ainda expandida (ATR ratio {atr_ratio:.2f}).")  # V4
        if volume_expansion:  # V4
            pros.append(f"Volume expandindo ({volume_ratio:.1f}x a media de 30d).")  # V4
        else:  # V4
            cons.append(f"Volume fraco ({volume_ratio:.1f}x a media de 30d).")  # V4
        if price_breakout:  # V4
            pros.append(f"Preco rompendo resistencia de 20d ({resistance:.2f}).")  # V4
        else:  # V4
            cons.append(f"Preco ainda abaixo da resistencia de 20d ({resistance:.2f}).")  # V4
        if momentum_rsi:  # V4
            pros.append(f"RSI em zona de momentum ({rsi_val:.1f} >= 55).")  # V4
        else:  # V4
            cons.append(f"RSI fraco para momentum ({rsi_val:.1f} < 55).")  # V4
        if trend_alignment:  # V4
            pros.append(f"Preco acima da SMA50 ({sma_50:.2f}).")  # V4
        else:  # V4
            cons.append(f"Preco abaixo da SMA50 ({sma_50:.2f}).")  # V4
        if nr7_or_inside:  # V4
            pros.append("NR7 ou Inside Bar: setup de compressao pre-breakout.")  # V4

        summary = (  # V4
            f"{symbol} | {classification} | Score {score:.0f}/100 "  # V4
            f"| Resistencia {resistance:.2f} | Stop {stop:.2f}"  # V4
        )  # V4

        return MomentumSnapshot(  # V4
            symbol=symbol,  # V4
            asset_class=asset_class,  # V4
            momentum_score=score,  # V4
            signal_type=signal_type,  # V4
            classification=classification,  # V4
            volatility_compression=volatility_compression,  # V4
            volume_expansion=volume_expansion,  # V4
            price_breakout=price_breakout,  # V4
            momentum_rsi=momentum_rsi,  # V4
            trend_alignment=trend_alignment,  # V4
            nr7_or_inside=nr7_or_inside,  # V4
            resistance_level=resistance,  # V4
            stop_level=stop,  # V4
            close=last_close,  # V4
            volume_ratio=volume_ratio,  # V4
            atr_compression_ratio=atr_ratio,  # V4
            rsi_14=rsi_val,  # V4
            pros=pros,  # V4
            cons=cons,  # V4
            summary=summary,  # V4
            alert_worthy=alert_worthy,  # V4
        )  # V4


def _empty_snapshot(symbol: str, asset_class: str) -> MomentumSnapshot:  # V4
    return MomentumSnapshot(  # V4
        symbol=symbol,  # V4
        asset_class=asset_class,  # V4
        momentum_score=0.0,  # V4
        signal_type="no_signal",  # V4
        classification="Dados insuficientes",  # V4
        volatility_compression=False,  # V4
        volume_expansion=False,  # V4
        price_breakout=False,  # V4
        momentum_rsi=False,  # V4
        trend_alignment=False,  # V4
        nr7_or_inside=False,  # V4
        resistance_level=0.0,  # V4
        stop_level=0.0,  # V4
        close=0.0,  # V4
        volume_ratio=0.0,  # V4
        atr_compression_ratio=1.0,  # V4
        rsi_14=50.0,  # V4
        pros=[],  # V4
        cons=["Dados insuficientes (menos de 60 barras)."],  # V4
        summary=f"{symbol} | Dados insuficientes",  # V4
        alert_worthy=False,  # V4
    )  # V4
