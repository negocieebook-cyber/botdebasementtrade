# V4 — Momentum screener: coleta dados, analisa com MomentumEngine, formata alertas Telegram
from __future__ import annotations

from src.data_collector import YFinanceCollector  # V4
from src.momentum_engine import MomentumEngine, MomentumSnapshot  # V4
from src.universe import get_momentum_universe  # V4


def run_momentum_screener(  # V4
    start_date: str,  # V4
    min_score: float = 55.0,  # V4
    alert_only: bool = True,  # V4
) -> list[MomentumSnapshot]:  # V4
    universe = get_momentum_universe()  # V4
    collector = YFinanceCollector()  # V4
    engine = MomentumEngine()  # V4
    results: list[MomentumSnapshot] = []  # V4

    market_data = collector.fetch_universe(  # V4
        universe=universe,  # V4
        period="1y",  # V4
        interval="1d",  # V4
        start_date=start_date,  # V4
    )  # V4

    for result in market_data:  # V4
        if result.data is None or result.data.empty:  # V4
            continue  # V4
        snap = engine.analyze(result.data, result.asset.symbol, result.asset.asset_class)  # V4
        if snap.momentum_score < min_score:  # V4
            continue  # V4
        if alert_only and not snap.alert_worthy:  # V4
            continue  # V4
        results.append(snap)  # V4

    results.sort(key=lambda s: s.momentum_score, reverse=True)  # V4
    return results  # V4


def format_momentum_alert(snap: MomentumSnapshot) -> str:  # V4
    prefix = "🚀" if snap.signal_type == "breakout" else "⚡"  # V4
    pros_text = "\n".join(f"  + {p}" for p in snap.pros[:4])  # V4
    lines = [  # V4
        f"{prefix} *{snap.symbol}* — {snap.asset_class}",  # V4
        f"Score: {snap.momentum_score:.0f}/100 | Sinal: {snap.signal_type}",  # V4
        f"Preco: {snap.close:.2f} | Resistencia: {snap.resistance_level:.2f} | Stop: {snap.stop_level:.2f}",  # V4
        f"Volume ratio: {snap.volume_ratio:.1f}x | ATR ratio: {snap.atr_compression_ratio:.2f} | RSI: {snap.rsi_14:.1f}",  # V4
        "",  # V4
        pros_text,  # V4
        "",  # V4
        "_Aviso: este alerta e apenas para estudo. Nao e recomendacao de investimento._",  # V4
    ]  # V4
    return "\n".join(lines)  # V4
