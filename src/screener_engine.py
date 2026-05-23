from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.config import (
    DAILY_ALERT_MAX_ASSETS,
    DAILY_ALERT_MIN_SCORE,
    DAILY_ALERT_PHASES,
    DAILY_ALERT_STRICT_MODE,
    MAX_TELEGRAM_ALERTS,
    MIN_NOTIFICATION_SCORE,
    MIN_TECHNICAL_CONFIRMATIONS,
    NOTIFICATION_PHASES,
    SAFETY_RULES,
    STRICT_MODE,
    load_settings,
)
from src.data_collector import FredCollector, MarketDataResult, YFinanceCollector
from src.data_quality import evaluate_data_quality
from src.intermarket_engine import INTERMARKET_SYMBOLS, IntermarketEngine, IntermarketSnapshot
from src.macro_engine import MacroEngine, MacroSnapshot
from src.market_groups import empty_group_stats, market_group_for_class
from src.narrative_engine import NarrativeEngine, NarrativeSnapshot
from src.scoring_engine import ScoreResult, ScoringEngine
from src.technical_engine import TechnicalEngine, TechnicalSnapshot
from src.thresholds import get_threshold
from src.universe import Asset, get_assets_by_symbols


@dataclass
class AssetAnalysis:
    asset: Asset
    technical: TechnicalSnapshot | None
    macro: MacroSnapshot
    intermarket: IntermarketSnapshot
    narrative: NarrativeSnapshot
    score: ScoreResult | None
    error: str | None = None
    thesis_phase: str = "Fora do padrao"
    approved: bool = False
    confirmation_point: str = ""
    invalidation_point: str = ""
    pros: list[str] | None = None
    cons: list[str] | None = None
    data_quality: dict | None = None

    def to_dict(self) -> dict:
        return analysis_to_dict(self)


class ScreenerEngine:
    def __init__(self) -> None:
        self.technical_engine = TechnicalEngine()
        self.macro_engine = MacroEngine()
        self.intermarket_engine = IntermarketEngine()
        self.narrative_engine = NarrativeEngine()
        self.scoring_engine = ScoringEngine()

    def run(
        self,
        results: list[MarketDataResult],
        fred_data: dict[str, pd.DataFrame] | None = None,
        intermarket_data: dict[str, pd.DataFrame] | None = None,
    ) -> list[AssetAnalysis]:
        macro = self.macro_engine.analyze(fred_data)
        market_data = {result.asset.symbol: result.data for result in results if result.error is None}
        if intermarket_data:
            market_data.update(intermarket_data)
        analyses: list[AssetAnalysis] = []

        for result in results:
            asset = result.asset
            data_quality = evaluate_data_quality(result.data, asset.symbol)
            intermarket = self.intermarket_engine.analyze(asset, market_data)
            narrative = self.narrative_engine.analyze(asset)
            if result.error:
                analyses.append(
                    AssetAnalysis(
                        asset,
                        None,
                        macro,
                        intermarket,
                        narrative,
                        None,
                        result.error,
                        cons=[f"Data error: {result.error}"],
                        data_quality=data_quality,
                    )
                )
                continue

            threshold = get_threshold(asset.asset_class)
            if len(result.data) < threshold.min_history_rows:
                analyses.append(
                    AssetAnalysis(
                        asset,
                        None,
                        macro,
                        intermarket,
                        narrative,
                        None,
                        "insufficient history",
                        cons=["Insufficient history for the class threshold."],
                        data_quality=data_quality,
                    )
                )
                continue

            technical = self.technical_engine.analyze(result.data, threshold, asset.asset_class)  # MELHORIA
            score = self.scoring_engine.score(technical, threshold, macro, intermarket, narrative, asset.asset_class)
            thesis_phase = score.classification
            pros, cons = build_pros_cons(technical, score, macro, intermarket, narrative, asset.asset_class)
            analyses.append(
                AssetAnalysis(
                    asset=asset,
                    technical=technical,
                    macro=macro,
                    intermarket=intermarket,
                    narrative=narrative,
                    score=score,
                    thesis_phase=thesis_phase,
                    approved=is_approved_phase(thesis_phase),
                    confirmation_point=create_confirmation_point(technical),
                    invalidation_point=create_invalidation_point(technical),
                    pros=pros,
                    cons=cons,
                    data_quality=data_quality,
                )
            )

        return sorted(analyses, key=lambda item: item.score.total_score if item.score else -1, reverse=True)


def _build_engine_inputs(  # MELHORIA
    assets: list,
    settings,
    use_macro: bool,
    use_intermarket: bool,
    start_date: str,
) -> tuple:
    """Retorna (market_results, fred_data, intermarket_data) — elimina duplicação entre run_screener e run_screener_with_metadata."""  # MELHORIA
    collector = YFinanceCollector()  # MELHORIA
    market_results = collector.fetch_universe(  # MELHORIA
        assets, period=settings.period, interval=settings.interval, start_date=start_date  # MELHORIA
    )  # MELHORIA
    fred_data = None  # MELHORIA
    if use_macro and settings.fred_api_key:  # MELHORIA
        fred_data = FredCollector(settings.fred_api_key).fetch_many(start_date=start_date)  # MELHORIA
    intermarket_data = None  # MELHORIA
    if use_intermarket:  # MELHORIA
        intermarket_assets = [Asset(symbol=s, name=s, asset_class="intermarket") for s in INTERMARKET_SYMBOLS]  # MELHORIA
        intermarket_results = collector.fetch_universe(  # MELHORIA
            intermarket_assets, period=settings.period, interval=settings.interval, start_date=start_date  # MELHORIA
        )  # MELHORIA
        intermarket_data = {r.asset.symbol: r.data for r in intermarket_results if r.error is None}  # MELHORIA
    return market_results, fred_data, intermarket_data  # MELHORIA


def run_screener(
    universe: list,
    start_date: str,
    use_macro=True,
    use_intermarket=True,
    use_narrative=False,
    as_dict=False,
) -> list:
    settings = load_settings()
    assets = _coerce_universe(universe)
    market_results, fred_data, intermarket_data = _build_engine_inputs(  # MELHORIA
        assets, settings, use_macro, use_intermarket, start_date  # MELHORIA
    )  # MELHORIA
    engine = ScreenerEngine()
    if use_narrative:
        engine.narrative_engine = NarrativeEngine()
    analyses = engine.run(market_results, fred_data=fred_data, intermarket_data=intermarket_data)
    approved = filter_approved_assets(analyses)
    return analyses_to_dicts(approved) if as_dict else approved


def run_screener_with_metadata(
    universe: list,
    start_date: str,
    use_macro=True,
    use_intermarket=True,
    use_narrative=False,
    as_dict=True,
    mode_note: str = "",
) -> dict:
    settings = load_settings()
    assets = _coerce_universe(universe)
    market_results, fred_data, intermarket_data = _build_engine_inputs(  # MELHORIA
        assets, settings, use_macro, use_intermarket, start_date  # MELHORIA
    )  # MELHORIA
    engine = ScreenerEngine()
    if use_narrative:
        engine.narrative_engine = NarrativeEngine()
    analyses = engine.run(market_results, fred_data=fred_data, intermarket_data=intermarket_data)
    approved = filter_approved_assets(analyses)
    rejected = [analysis for analysis in analyses if not analysis.approved]
    brazil_assets = [asset for asset in assets if _is_brazil_asset(asset)]
    brazil_analyses = [analysis for analysis in analyses if _is_brazil_asset(analysis.asset)]
    approved_brazil = [analysis for analysis in approved if _is_brazil_asset(analysis.asset)]
    brazil_errors = [
        {"ticker": analysis.asset.symbol, "reason": str(analysis.error)}
        for analysis in brazil_analyses
        if analysis.error
    ]
    groups = _group_metadata(assets, analyses, approved)
    rejected_by_phase: dict[str, int] = {
        "Fora do padrão": 0,
        "Queda extrema, mas sem fundo": 0,
    }
    for analysis in rejected:
        phase = _display_phase(analysis.thesis_phase)
        if phase in rejected_by_phase:
            rejected_by_phase[phase] += 1

    return {
        "planned_count": len(assets),
        "analyzed_count": len(analyses),
        "approved_count": len(approved),
        "rejected_count": len(rejected),
        "planned_brazil_count": len(brazil_assets),
        "analyzed_brazil_count": len(brazil_analyses) - len(brazil_errors),
        "approved_brazil_count": len(approved_brazil),
        "brazil_error_count": len(brazil_errors),
        "brazil_errors": brazil_errors,
        "groups": groups,
        "results": analyses_to_dicts(approved) if as_dict else approved,
        "all_results": analyses_to_dicts(analyses) if as_dict else analyses,
        "rejected_by_phase": rejected_by_phase,
        "mode_note": mode_note,
        "start_date": start_date,
    }


def analyze_single_asset(
    symbol,
    asset_class,
    start_date,
    use_macro=True,
    use_intermarket=True,
    use_narrative=False,
) -> dict:
    asset = Asset(symbol=symbol, name=symbol, asset_class=asset_class)
    settings = load_settings()
    collector = YFinanceCollector()
    market_results = collector.fetch_universe(
        [asset],
        period=settings.period,
        interval=settings.interval,
        start_date=start_date,
    )

    fred_data = None
    if use_macro and settings.fred_api_key:
        fred_data = FredCollector(settings.fred_api_key).fetch_many(start_date=start_date)

    intermarket_data = None
    if use_intermarket:
        intermarket_assets = [Asset(symbol=item, name=item, asset_class="intermarket") for item in INTERMARKET_SYMBOLS]
        intermarket_results = collector.fetch_universe(
            intermarket_assets,
            period=settings.period,
            interval=settings.interval,
            start_date=start_date,
        )
        intermarket_data = {result.asset.symbol: result.data for result in intermarket_results if result.error is None}

    engine = ScreenerEngine()
    if use_narrative:
        engine.narrative_engine = NarrativeEngine()
    analyses = engine.run(market_results, fred_data=fred_data, intermarket_data=intermarket_data)
    if not analyses:
        return {
            "symbol": symbol,
            "asset_class": asset_class,
            "date": "",
            "phase": "Fora do padrao",
            "score": 0,
            "classification": "error",
            "close": 0,
            "confirmation_trigger": "",
            "invalidation_level": "",
            "why_on_radar": "Not on radar: analysis unavailable.",
            "pros": [],
            "cons": ["Analysis unavailable."],
            "macro": {},
            "intermarket": {},
            "narrative": {},
            "data_quality": {"has_price_data": False, "error": "analysis unavailable", "approved": False},
        }
    return analysis_to_dict(analyses[0])


def _coerce_universe(universe: list) -> list[Asset]:
    if not universe:
        return []
    if isinstance(universe[0], Asset):
        return universe
    return get_assets_by_symbols([str(symbol) for symbol in universe])


def _is_brazil_asset(asset: Asset) -> bool:
    return asset.region == "brazil" or asset.asset_class.startswith("brazil_") or asset.symbol.upper().endswith(".SA")


def _group_metadata(assets: list[Asset], analyses: list[AssetAnalysis], approved: list[AssetAnalysis]) -> dict[str, dict[str, int]]:
    groups = empty_group_stats()
    for asset in assets:
        groups[market_group_for_class(asset.asset_class, asset.symbol)]["planned"] += 1
    for analysis in analyses:
        group = market_group_for_class(analysis.asset.asset_class, analysis.asset.symbol)
        if analysis.error:
            groups[group]["errors"] += 1
        else:
            groups[group]["analyzed"] += 1
    for analysis in approved:
        groups[market_group_for_class(analysis.asset.asset_class, analysis.asset.symbol)]["approved"] += 1
    return groups


APPROVED_PHASES = {
    "Possivel estabilizacao",
    "Possível estabilização",
    "Acumulacao inicial",
    "Acumulação inicial",
    "Acumulacao avancada",
    "Acumulação avançada",
    "Rompimento inicial",
    "Tese forte",
}

REJECTED_PHASES = {
    "Fora do padrao",
    "Queda extrema, mas sem fundo",
}


def is_approved_phase(thesis_phase: str) -> bool:
    return thesis_phase in APPROVED_PHASES


def filter_approved_assets(analyses: list[AssetAnalysis]) -> list[AssetAnalysis]:
    return [analysis for analysis in analyses if analysis.approved]


def analysis_to_dict(analysis: AssetAnalysis) -> dict:
    technical = analysis.technical
    score = analysis.score
    return {
        "symbol": analysis.asset.symbol,
        "asset_class": analysis.asset.asset_class,
        "market_group": market_group_for_class(analysis.asset.asset_class, analysis.asset.symbol),
        "date": _analysis_date(technical),
        "phase": _display_phase(analysis.thesis_phase),
        "score": score.total_score if score else 0,
        "classification": score.classification if score else "error",
        "risk": score.risk if score else "n/a",
        "close": technical.last_close if technical else 0,
        "confirmation_trigger": analysis.confirmation_point,
        "invalidation_level": analysis.invalidation_point,
        "confirmation_trigger_value": technical.trigger_level if technical else None,
        "invalidation_level_value": technical.invalidation_level if technical else None,
        "why_on_radar": _why_on_radar(analysis),
        "what_to_watch_now": _what_to_watch_now(analysis),
        "technical": _technical_dict(technical, analysis.asset.asset_class),
        "pros": analysis.pros or [],
        "cons": analysis.cons or [],
        "macro": {
            "score": analysis.macro.score,
            "regime": analysis.macro.regime,
            "notes": analysis.macro.notes,
        },
        "intermarket": {
            "score": analysis.intermarket.score,
            "regime": analysis.intermarket.regime,
            "notes": analysis.intermarket.notes,
        },
        "narrative": {
            "score": analysis.narrative.score,
            "tone": analysis.narrative.tone,
            "notes": analysis.narrative.notes,
        },
        "data_quality": {
            "has_price_data": technical is not None,
            "error": analysis.error,
            "approved": analysis.approved,
            **(analysis.data_quality or {}),
        },
        "safety": {
            "not_financial_advice": True,
            "rules": SAFETY_RULES,
        },
    }


def should_notify_asset(result: dict) -> tuple[bool, str]:
    phase = result.get("phase", "")
    score = float(result.get("score", 0) or 0)
    technical = result.get("technical", {}) or {}
    data_quality = result.get("data_quality", {}) or {}

    min_score = 70 if STRICT_MODE else MIN_NOTIFICATION_SCORE
    allowed_phases = ["Rompimento inicial", "Tese forte"] if STRICT_MODE else NOTIFICATION_PHASES
    min_confirmations = 4 if STRICT_MODE else MIN_TECHNICAL_CONFIRMATIONS

    if not data_quality.get("has_price_data", False) or data_quality.get("error"):
        return False, "Dados insuficientes ou falha de dados."
    if data_quality.get("confidence_level") == "Baixa":
        return False, "Confiança dos dados baixa."
    if phase in {"Queda extrema, mas sem fundo", "Fora do padrão", "Fora do padrao"}:
        return False, f"Fase {phase} não passa na régua de alerta."
    if score < min_score:
        return False, f"Score {score:.0f}/100 abaixo do mínimo de {min_score}."
    if phase not in allowed_phases:
        return False, f"Score bom, mas fase {phase} ainda não é avançada o suficiente."

    severe_risks = _technical_severe_risks(technical, phase)
    if severe_risks:
        return False, "Risco técnico grave: " + "; ".join(severe_risks) + "."

    confirmations = _technical_confirmations(technical)
    if STRICT_MODE:
        if not technical.get("close_above_sma_50", False):
            return False, "Modo rígido: preço ainda não está acima da SMA 50."
        if not technical.get("rsi_above_50", False):
            return False, "Modo rígido: RSI ainda não está acima de 50."
    if not technical.get("liquidity_acceptable", False):
        return False, "Liquidez fraca para alerta."

    if confirmations < min_confirmations:
        return False, f"Apenas {confirmations} confirmações técnicas; mínimo exigido é {min_confirmations}."

    return True, f"Score acima de {min_score}, fase {phase} e {confirmations} confirmações técnicas."


def filter_notification_candidates(results: list) -> list:
    candidates = []
    for result in results:
        should_notify, reason = should_notify_asset(result)
        if should_notify:
            enriched = dict(result)
            enriched["notification_reason"] = reason
            candidates.append(enriched)
    return sorted(candidates, key=lambda item: item.get("score", 0), reverse=True)[:MAX_TELEGRAM_ALERTS]


def should_send_daily_alert(result: dict) -> tuple[bool, str]:
    phase = result.get("phase", "")
    score = float(result.get("score", 0) or 0)
    technical = result.get("technical", {}) or {}
    data_quality = result.get("data_quality", {}) or {}

    if not data_quality.get("has_price_data", False) or data_quality.get("error"):
        return False, "Dados insuficientes ou falha de dados."
    if data_quality.get("confidence_level") == "Baixa":
        return False, "Confiança dos dados baixa."

    blocked_phases = {
        "Fora do padrão",
        "Fora do padrao",
        "Queda extrema, mas sem fundo",
        "Possível estabilização",
        "Possivel estabilizacao",
        "Acumulação inicial",
        "Acumulacao inicial",
    }
    if phase in blocked_phases:
        return False, "Score abaixo de 70 ou fase ainda inicial."

    if score < DAILY_ALERT_MIN_SCORE or phase not in DAILY_ALERT_PHASES:
        return False, "Score abaixo de 70 ou fase ainda inicial."

    severe_risks = _daily_alert_severe_risks(technical, phase)
    if severe_risks:
        return False, "Risco técnico grave: " + "; ".join(severe_risks) + "."

    required_confirmations = [
        technical.get("close_above_sma_50", False),
        technical.get("rsi_above_50", False),
        technical.get("macd_above_signal", False),
    ]
    if not all(required_confirmations):
        return False, "Ainda falta confirmação técnica: close acima da SMA 50, RSI > 50 e MACD confirmado."
    if not technical.get("liquidity_acceptable", False):
        return False, "Liquidez fraca para alerta diário."

    if DAILY_ALERT_STRICT_MODE:
        confirmations = _technical_confirmations(technical)
        if confirmations < 4:
            return False, f"Modo rígido: apenas {confirmations} confirmações técnicas."

    return True, f"Score >= {DAILY_ALERT_MIN_SCORE}, fase {phase} e confirmações técnicas suficientes."


def filter_daily_alerts(results: list) -> list:
    grouped_alerts: dict[str, list[dict]] = {}
    for result in results:
        should_send, reason = should_send_daily_alert(result)
        if should_send:
            enriched = dict(result)
            enriched["daily_alert_reason"] = reason
            group = enriched.get("market_group") or market_group_for_class(enriched.get("asset_class", ""), enriched.get("symbol", ""))
            grouped_alerts.setdefault(group, []).append(enriched)
    alerts = []
    for group_items in grouped_alerts.values():
        alerts.extend(sorted(group_items, key=lambda item: item.get("score", 0), reverse=True)[:5])
    return sorted(alerts, key=lambda item: item.get("score", 0), reverse=True)[:20]


def analyses_to_dicts(analyses: list[AssetAnalysis]) -> list[dict]:
    return [analysis_to_dict(analysis) for analysis in analyses]


def _analysis_date(technical: TechnicalSnapshot | None) -> str:
    return "" if technical is None else technical.date


def _why_on_radar(analysis: AssetAnalysis) -> str:
    if analysis.error:
        return f"Not on radar: {analysis.error}."
    if not analysis.score:
        return "Not on radar: score unavailable."
    if analysis.approved:
        tech = analysis.technical
        if tech:
            return (
                f"Entrou no radar como {_display_phase(analysis.thesis_phase)} porque combina queda relevante para a classe, "
                f"score {analysis.score.total_score:.0f}/100 e sinais técnicos como suporte, médias, RSI, MACD ou compressão de volatilidade."
            )
        return f"Entrou no radar como {_display_phase(analysis.thesis_phase)} com score {analysis.score.total_score:.0f}/100."
    return f"Rejeitado nesta leitura: {_display_phase(analysis.thesis_phase)}."


def _what_to_watch_now(analysis: AssetAnalysis) -> str:
    if not analysis.technical:
        return "Aguardar dados suficientes para análise."
    if not _is_valid_technical_level(analysis.technical.trigger_level):
        return "Aguardar gatilho técnico mais confiável."
    if not _is_valid_technical_level(analysis.technical.invalidation_level):
        return f"Observar fechamento acima de {analysis.technical.trigger_level:.2f} com volume melhor que a média."
    return (
        f"Observar fechamento acima de {analysis.technical.trigger_level:.2f} com volume melhor que a média; "
        f"a tese perde qualidade abaixo de {analysis.technical.invalidation_level:.2f}."
    )


def _technical_dict(technical: TechnicalSnapshot | None, asset_class: str) -> dict:
    if technical is None:
        return {}
    threshold = get_threshold(asset_class)
    drawdown_relevant = technical.drawdown_52w_pct <= threshold.relevant_drawdown_pct
    range_upper_half = technical.range_position_60d >= 50 if technical.range_position_60d == technical.range_position_60d else False
    return {
        "last_close": technical.last_close,
        "sma_50": technical.sma_50,
        "sma_200": technical.sma_200,
        "rsi_14": technical.rsi_14,
        "macd": technical.macd,
        "macd_signal": technical.macd_signal,
        "rolling_high_60d": technical.rolling_high_60d,
        "rolling_low_60d": technical.rolling_low_60d,
        "range_position_60d": technical.range_position_60d,
        "volatility_compression": technical.volatility_compression,
        "volume_ratio_30d": technical.volume_ratio_30d,
        "avg_dollar_volume_30d": technical.avg_dollar_volume_30d,
        "drawdown_52w_pct": technical.drawdown_52w_pct,
        "drawdown_relevant": drawdown_relevant,
        "close_above_sma_50": technical.last_close > technical.sma_50,
        "close_above_sma_200": technical.last_close > technical.sma_200,
        "rsi_above_50": technical.rsi_14 > 50,
        "macd_above_signal": technical.macd > technical.macd_signal,
        "range_upper_half": range_upper_half,
        "liquidity_acceptable": technical.avg_dollar_volume_30d >= 5_000_000 or (asset_class == "crypto" and technical.volume_ratio_30d >= 0.75),
        "near_breakout": bool(technical.rolling_high_60d and technical.last_close >= technical.rolling_high_60d * 0.97),
    }


def _technical_confirmations(technical: dict) -> int:
    checks = [
        technical.get("drawdown_relevant", False),
        technical.get("close_above_sma_50", False),
        technical.get("rsi_above_50", False),
        technical.get("macd_above_signal", False),
        technical.get("range_upper_half", False),
        technical.get("volatility_compression", False),
        technical.get("liquidity_acceptable", False),
    ]
    return sum(1 for item in checks if item)


def _technical_severe_risks(technical: dict, phase: str) -> list[str]:
    risks = []
    close = float(technical.get("last_close", 0) or 0)
    sma_50 = float(technical.get("sma_50", 0) or 0)
    rolling_low_60d = float(technical.get("rolling_low_60d", 0) or 0)
    rsi = float(technical.get("rsi_14", 0) or 0)
    volume_ratio = float(technical.get("volume_ratio_30d", 0) or 0)

    if rolling_low_60d and close < rolling_low_60d:
        risks.append("preço abaixo da mínima de 60 dias")
    if rsi and rsi < 45:
        risks.append("RSI abaixo de 45")
    if sma_50 and close < sma_50 * 0.95:
        risks.append("preço muito abaixo da SMA 50")
    if volume_ratio and volume_ratio < 0.50:
        risks.append("volume muito fraco")
    if phase in {"Queda extrema, mas sem fundo", "Fora do padrão", "Fora do padrao"}:
        risks.append(f"fase {phase}")
    return risks


def _daily_alert_severe_risks(technical: dict, phase: str) -> list[str]:
    risks = []
    close = float(technical.get("last_close", 0) or 0)
    sma_50 = float(technical.get("sma_50", 0) or 0)
    rolling_low_60d = float(technical.get("rolling_low_60d", 0) or 0)
    rsi = float(technical.get("rsi_14", 0) or 0)
    volume_ratio = float(technical.get("volume_ratio_30d", 0) or 0)

    if rolling_low_60d and close < rolling_low_60d:
        risks.append("preço abaixo da mínima de 60 dias")
    if rsi and rsi < 45:
        risks.append("RSI abaixo de 45")
    if sma_50 and close < sma_50:
        risks.append("preço abaixo da SMA 50")
    if volume_ratio and volume_ratio < 0.50:
        risks.append("volume muito fraco")
    if phase in {
        "Fora do padrão",
        "Fora do padrao",
        "Queda extrema, mas sem fundo",
        "Possível estabilização",
        "Possivel estabilizacao",
        "Acumulação inicial",
        "Acumulacao inicial",
    }:
        risks.append(f"fase {phase}")
    return risks



def create_confirmation_point(technical: TechnicalSnapshot) -> str:
    if not _is_valid_technical_level(technical.trigger_level):
        return "Gatilho nao definido com seguranca."
    return (
        f"Confirmacao acima de {technical.trigger_level:.2f}, idealmente com fechamento sustentado "
        f"e volume igual ou acima da media de 30 dias."
    )


def create_invalidation_point(technical: TechnicalSnapshot) -> str:
    if not _is_valid_technical_level(technical.invalidation_level):
        return "Nivel de invalidacao nao definido com seguranca."
    return f"Invalidacao abaixo de {technical.invalidation_level:.2f}."


def _is_valid_technical_level(value: float | int | None) -> bool:
    if value is None:
        return False
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return False
    return numeric == numeric and numeric > 0


def build_pros_cons(
    technical: TechnicalSnapshot,
    score: ScoreResult,
    macro: MacroSnapshot,
    intermarket: IntermarketSnapshot,
    narrative: NarrativeSnapshot,
    asset_class: str,
) -> tuple[list[str], list[str]]:
    pros: list[str] = []
    cons: list[str] = []
    threshold = get_threshold(asset_class)

    if technical.drawdown_52w_pct <= threshold.relevant_drawdown_pct:
        pros.append("Drawdown relevante para a classe do ativo.")
    else:
        cons.append("Drawdown ainda não é relevante para a classe.")

    if technical.last_close > technical.sma_50:
        pros.append("Preço acima da SMA 50.")
    else:
        cons.append("Preço abaixo da SMA 50.")

    if technical.last_close > technical.sma_200:
        pros.append("Preço acima da SMA 200.")
    else:
        cons.append("Abaixo da SMA 200.")

    if technical.rsi_14 > 50:
        pros.append("RSI acima de 50.")
    else:
        cons.append("RSI ainda fraco.")

    if technical.macd > technical.macd_signal:
        pros.append("MACD confirmou acima da linha de sinal.")
    else:
        cons.append("MACD não confirmou.")

    if technical.rolling_high_60d and technical.last_close >= technical.rolling_high_60d * 0.97:
        pros.append("Perto de rompimento da resistência de 60 dias.")
    else:
        cons.append("Muito distante da resistência de 60 dias.")

    if technical.volatility_compression:
        pros.append("Volatilidade comprimida.")
    else:
        cons.append("Volatilidade ainda sem compressão clara.")

    if technical.volume_ratio_30d >= 1:
        pros.append("Volume relativo acima da média de 30 dias.")
    else:
        cons.append("Volume fraco ou abaixo da média.")

    if technical.defended_support:
        pros.append("Suporte recente foi defendido.")
    else:
        cons.append("Risco de perder suporte.")

    if technical.confirmation:
        pros.append("Confirmação técnica já presente.")
    else:
        cons.append("Confirmação técnica ainda pendente.")

    if not _is_valid_technical_level(technical.invalidation_level):
        cons.append("Nível de invalidação técnico não está confiável.")
    elif technical.invalidation_level < technical.last_close:
        pros.append(create_invalidation_point(technical))
    else:
        cons.append("Ponto de invalidação não está claramente abaixo do preço atual.")

    if macro.regime in {"supportive", "neutral/mixed", "neutral"}:
        pros.append(f"Regime macro: {macro.regime}.")
    else:
        cons.append(f"Regime macro: {macro.regime}.")

    if intermarket.regime == "supportive":
        pros.append("Intermarket favorável.")
    elif intermarket.regime == "mixed":
        cons.append("Intermarket misto.")
    else:
        cons.append("Intermarket fraco ou não calculado.")

    if narrative.tone == "not_calculated":
        cons.append("Narrativa não calculada nesta execução.")

    return pros, cons


def _display_phase(phase: str) -> str:
    return {
        "Fora do padrao": "Fora do padrão",
        "Possivel estabilizacao": "Possível estabilização",
        "Acumulacao inicial": "Acumulação inicial",
        "Acumulacao avancada": "Acumulação avançada",
    }.get(phase, phase)


def ranking_frame(analyses: list[AssetAnalysis]) -> pd.DataFrame:
    rows = []
    for item in analyses:
        rows.append(
            {
                "symbol": item.asset.symbol,
                "name": item.asset.name,
                "class": item.asset.asset_class,
                "score": item.score.total_score if item.score else None,
                "classification": item.score.classification if item.score else "error",
                "approved": item.approved,
                "risk": item.score.risk if item.score else "n/a",
                "drawdown_pct": item.technical.drawdown_pct if item.technical else None,
                "trigger": item.technical.trigger_level if item.technical else None,
                "invalidation": item.technical.invalidation_level if item.technical else None,
                "confirmation_point": item.confirmation_point,
                "invalidation_point": item.invalidation_point,
                "error": item.error,
            }
        )
    return pd.DataFrame(rows)
