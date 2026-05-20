from __future__ import annotations

from dataclasses import dataclass

from src.intermarket_engine import IntermarketSnapshot
from src.macro_engine import MacroSnapshot
from src.narrative_engine import NarrativeSnapshot
from src.technical_engine import TechnicalSnapshot
from src.thresholds import ClassThreshold
from src.thresholds import get_threshold as get_class_threshold
from src.utils import clamp


RAW_TOTAL_WEIGHT = 95.0


@dataclass
class ThesisPhase:
    name: str
    passed: bool
    score: float
    detail: str


@dataclass
class ScoreResult:
    total_score: float
    classification: str
    risk: str
    phases: list[ThesisPhase]


class ScoringEngine:
    def score(
        self,
        technical: TechnicalSnapshot,
        threshold: ClassThreshold,
        macro: MacroSnapshot,
        intermarket: IntermarketSnapshot,
        narrative: NarrativeSnapshot,
        asset_class: str = "equity_indices",
    ) -> ScoreResult:
        snapshot = _snapshot_from_technical(technical)
        snapshot["asset_class"] = asset_class
        macro_result = {"macro_score": _scale(macro.score, 100, 15), "macro_regime": macro.regime}
        intermarket_result = {"intermarket_score": _scale(intermarket.score, 100, 10), "intermarket_regime": intermarket.regime}
        narrative_result = {
            "narrative_score": 0.0 if narrative.tone == "not_calculated" else _scale(narrative.score, 100, 5),
            "narrative_regime": narrative.tone,
        }
        drawdown_score = score_drawdown(snapshot, asset_class)
        accumulation_score = score_accumulation(snapshot)
        confirmation_score = score_technical_confirmation(snapshot)
        macro_score = score_macro(macro_result)
        intermarket_score = score_intermarket(intermarket_result)
        narrative_score = score_narrative(narrative_result)
        liquidity_score = score_liquidity(snapshot)

        phases = [
            ThesisPhase(
                "Drawdown",
                technical.drawdown_pct <= threshold.relevant_drawdown_pct,
                drawdown_score,
                (
                    f"Drawdown {technical.drawdown_pct:.2f}% vs relevant {threshold.relevant_drawdown_pct:.2f}%, "
                    f"strong {threshold.strong_drawdown_pct:.2f}%, extreme {threshold.extreme_drawdown_pct:.2f}%."
                ),
            ),
            ThesisPhase(
                "Accumulation/lateralization",
                accumulation_score >= 10,
                accumulation_score,
                "Scores lateralization, support defense, volatility compression and range position.",
            ),
            ThesisPhase(
                "Technical confirmation",
                confirmation_score >= 10,
                confirmation_score,
                "Scores SMA50 recovery, RSI > 50, MACD above signal and 60D resistance proximity.",
            ),
            ThesisPhase(
                "Macro",
                macro_score >= 7,
                macro_score,
                f"Macro regime: {macro.regime}.",
            ),
            ThesisPhase(
                "Intermarket",
                intermarket_score >= 5,
                intermarket_score,
                f"Intermarket regime: {intermarket.regime}.",
            ),
            ThesisPhase(
                "Narrative",
                narrative_score >= 3,
                narrative_score,
                f"Narrative regime: {narrative.tone}.",
            ),
            ThesisPhase(
                "Liquidity",
                liquidity_score >= 3,
                liquidity_score,
                f"30D volume ratio: {technical.volume_ratio_30d:.2f}.",
            ),
        ]

        total = calculate_total_score(snapshot, asset_class, macro_result, intermarket_result, narrative_result)
        classification = classify_asset(total, snapshot, asset_class, macro_result, intermarket_result, narrative_result)
        risk = _risk(technical, threshold, macro, intermarket)
        return ScoreResult(total_score=total, classification=classification, risk=risk, phases=phases)


def score_drawdown(snapshot, asset_class) -> int:
    threshold = get_class_threshold(asset_class)
    drawdown_pct = _value(snapshot, "drawdown_52w_pct", _value(snapshot, "drawdown_pct", 0.0))
    if drawdown_pct <= threshold.extreme_drawdown_pct:
        return 20
    if drawdown_pct <= threshold.strong_drawdown_pct:
        return 14
    if drawdown_pct <= threshold.relevant_drawdown_pct:
        return 8
    return 0


def score_accumulation(snapshot) -> int:
    score = 0
    score += 5 if _value(snapshot, "lateralization", False) else 0
    score += 5 if _value(snapshot, "volatility_compression", False) else 0
    score += 4 if _value(snapshot, "defended_support", False) else 0
    score += 3 if 25 <= _value(snapshot, "range_position_60d", 50) <= 75 else 0
    score += 3 if _value(snapshot, "atr_compression_ratio", 1.0) <= 0.85 else 0
    return int(clamp(score, 0, 20))


def score_technical_confirmation(snapshot) -> int:
    score = 0
    last_close = _value(snapshot, "last_close", 0.0)
    sma_50 = _value(snapshot, "sma_50", 0.0)
    macd = _value(snapshot, "macd", 0.0)
    macd_signal = _value(snapshot, "macd_signal", 0.0)
    rolling_high_60d = _value(snapshot, "rolling_high_60d", 0.0)

    score += 5 if last_close > sma_50 > 0 else 0
    score += 4 if _value(snapshot, "rsi_14", 0.0) > 50 else 0
    score += 4 if macd > macd_signal else 0
    score += 4 if _value(snapshot, "structure_recovery", False) else 0
    score += 3 if rolling_high_60d and last_close >= rolling_high_60d * 0.97 else 0
    return int(clamp(score, 0, 20))


def score_macro(macro_result) -> int:
    return int(clamp(_value(macro_result, "macro_score", 0.0), 0, 15))


def score_intermarket(intermarket_result) -> int:
    return int(clamp(_value(intermarket_result, "intermarket_score", 0.0), 0, 10))


def score_narrative(narrative_result) -> int:
    return int(clamp(_value(narrative_result, "narrative_score", 0.0), 0, 5))


def score_liquidity(snapshot) -> int:
    avg_volume = _value(snapshot, "avg_volume_30d", 0.0)
    avg_dollar_volume = _value(snapshot, "avg_dollar_volume_30d", 0.0)
    volume_ratio = _value(snapshot, "volume_ratio_30d", 0.0)
    asset_class = _value(snapshot, "asset_class", "")
    if asset_class == "crypto" and avg_dollar_volume <= 0:
        return 2
    if avg_dollar_volume >= 50_000_000:
        return 5
    if avg_dollar_volume >= 20_000_000:
        return 4
    if avg_dollar_volume >= 5_000_000:
        return 3
    if avg_volume <= 0:
        return 0
    if volume_ratio >= 1.0:
        return 5
    if volume_ratio >= 0.75:
        return 3
    return 1


def calculate_total_score(
    snapshot,
    asset_class,
    macro_result=None,
    intermarket_result=None,
    narrative_result=None,
) -> int:
    raw_score = (
        score_drawdown(snapshot, asset_class)
        + score_accumulation(snapshot)
        + score_technical_confirmation(snapshot)
        + score_macro(macro_result or {})
        + score_intermarket(intermarket_result or {})
        + score_narrative(narrative_result or {})
        + score_liquidity(snapshot)
    )
    return int(round(clamp((raw_score / RAW_TOTAL_WEIGHT) * 100, 0, 100)))


def classify_asset(
    total_score,
    snapshot,
    asset_class,
    macro_result=None,
    intermarket_result=None,
    narrative_result=None,
) -> str:
    if _is_invalidated(snapshot):
        return "Tese invalidada"
    if _is_strong_thesis(total_score, snapshot, asset_class):
        return "Tese forte"
    if total_score >= 70:
        return "Rompimento inicial"
    if total_score >= 60:
        return "Acumulacao avancada"
    if total_score >= 50:
        return "Acumulacao inicial"
    if total_score >= 35:
        return "Possivel estabilizacao"
    if score_drawdown(snapshot, asset_class) > 0:
        return "Queda extrema, mas sem fundo"
    return "Fora do padrao"


def _drawdown_score(drawdown_pct: float, threshold: ClassThreshold) -> float:
    if drawdown_pct <= threshold.extreme_drawdown_pct:
        return 12.0
    if drawdown_pct <= threshold.strong_drawdown_pct:
        return 8.0
    if drawdown_pct <= threshold.relevant_drawdown_pct:
        return 5.0
    return 0.0


def _classification(score: float) -> str:
    if score >= 80:
        return "advanced watchlist candidate"
    if score >= 65:
        return "developing thesis"
    if score >= 50:
        return "early watchlist"
    return "not qualified"


def _is_invalidated(snapshot) -> bool:
    invalidation = _value(snapshot, "invalidation_level", 0.0)
    last_close = _value(snapshot, "last_close", 0.0)
    return bool(invalidation and last_close and last_close < invalidation)


def _is_strong_thesis(total_score, snapshot, asset_class) -> bool:
    threshold = get_class_threshold(asset_class)
    drawdown_pct = _value(snapshot, "drawdown_52w_pct", _value(snapshot, "drawdown_pct", 0.0))
    last_close = _value(snapshot, "last_close", 0.0)
    sma_50 = _value(snapshot, "sma_50", 0.0)
    rolling_high_60d = _value(snapshot, "rolling_high_60d", 0.0)
    near_resistance = bool(rolling_high_60d and last_close >= rolling_high_60d * 0.97)
    return (
        total_score > 70
        and drawdown_pct <= threshold.relevant_drawdown_pct
        and last_close > sma_50 > 0
        and _value(snapshot, "rsi_14", 0.0) > 50
        and _value(snapshot, "macd", 0.0) > _value(snapshot, "macd_signal", 0.0)
        and near_resistance
        and score_liquidity(snapshot) >= 3
    )


def _snapshot_from_technical(technical: TechnicalSnapshot) -> dict:
    return {
        "asset_class": getattr(technical, "asset_class", "equity_indices"),
        "date": technical.date,
        "last_close": technical.last_close,
        "drawdown_pct": technical.drawdown_pct,
        "drawdown_52w_pct": technical.drawdown_52w_pct,
        "rsi_14": technical.rsi_14,
        "macd": technical.macd,
        "macd_signal": technical.macd_signal,
        "atr_compression_ratio": technical.atr_compression_ratio,
        "sma_50": technical.sma_50,
        "range_position_60d": technical.range_position_60d,
        "rolling_high_60d": technical.rolling_high_60d,
        "avg_volume_30d": technical.avg_volume_30d,
        "avg_dollar_volume_30d": technical.avg_dollar_volume_30d,
        "volume_ratio_30d": technical.volume_ratio_30d,
        "structure_recovery": technical.structure_recovery,
        "confirmation": technical.confirmation,
        "defended_support": technical.defended_support,
        "lateralization": technical.lateralization,
        "volatility_compression": technical.volatility_compression,
        "invalidation_level": technical.invalidation_level,
    }


def _value(source, key: str, default=0.0):
    if source is None:
        return default
    if isinstance(source, dict):
        return source.get(key, default)
    return getattr(source, key, default)


def _scale(value: float, old_max: float, new_max: float) -> float:
    return clamp((value / old_max) * new_max, 0, new_max)


def _risk(
    technical: TechnicalSnapshot,
    threshold: ClassThreshold,
    macro: MacroSnapshot,
    intermarket: IntermarketSnapshot,
) -> str:
    if technical.drawdown_pct <= threshold.extreme_drawdown_pct * 1.6 or macro.score < 35 or intermarket.score < 35:
        return "high"
    if technical.confirmation and technical.structure_recovery and intermarket.score >= 50:
        return "moderate"
    return "elevated"
