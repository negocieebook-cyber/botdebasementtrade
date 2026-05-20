from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.config import FRED_SERIES, MACRO_DIR, load_settings
from src.data_collector import FredCollector


@dataclass
class MacroSnapshot:
    score: float
    regime: str
    notes: list[str]


class MacroEngine:
    def analyze(self, fred_data: dict[str, pd.DataFrame] | None = None) -> MacroSnapshot:
        if not fred_data:
            series = ", ".join(FRED_SERIES)
            return MacroSnapshot(
                score=50.0,
                regime="neutral",
                notes=[
                    "Macro engine is in neutral mode because no FRED data was supplied.",
                    f"Configured FRED series: {series}.",
                ],
            )

        score = 50.0
        notes = []
        latest = _latest_values(fred_data)

        if "T10Y2Y" in latest:
            curve = latest["T10Y2Y"]
            if curve < 0:
                score -= 8.0
                notes.append(f"Yield curve is inverted: T10Y2Y={curve:.2f}.")
            else:
                score += 4.0
                notes.append(f"Yield curve is positive: T10Y2Y={curve:.2f}.")

        if "UNRATE" in fred_data:
            unemployment_trend = _change_over_last_points(fred_data["UNRATE"], 6)
            if unemployment_trend > 0.3:
                score -= 8.0
                notes.append(f"Unemployment is rising over recent observations: {unemployment_trend:.2f} pp.")
            else:
                notes.append(f"Unemployment trend is not materially deteriorating: {unemployment_trend:.2f} pp.")

        if "WALCL" in fred_data:
            balance_sheet_trend = _pct_change_over_last_points(fred_data["WALCL"], 12)
            if balance_sheet_trend > 0:
                score += 5.0
                notes.append(f"Fed balance sheet trend is expanding: {balance_sheet_trend:.2f}%.")
            else:
                score -= 3.0
                notes.append(f"Fed balance sheet trend is contracting: {balance_sheet_trend:.2f}%.")

        score = max(0.0, min(100.0, score))
        regime = "supportive" if score >= 60 else "hostile" if score <= 40 else "neutral/mixed"
        return MacroSnapshot(
            score=score,
            regime=regime,
            notes=notes or ["FRED data supplied, but no macro rules were triggered."],
        )


def fetch_fred_series(series_id: str) -> pd.DataFrame:
    settings = load_settings()
    cache_path = MACRO_DIR / f"{series_id.lower()}.csv"
    if not settings.fred_api_key:
        if cache_path.exists():
            return pd.read_csv(cache_path, parse_dates=["date"])
        return pd.DataFrame(columns=["date", "value", "series_id"])
    try:
        return FredCollector(settings.fred_api_key).fetch_series(series_id, settings.start_date)
    except Exception:
        if cache_path.exists():
            return pd.read_csv(cache_path, parse_dates=["date"])
        return pd.DataFrame(columns=["date", "value", "series_id"])


def get_macro_snapshot() -> dict:
    settings = load_settings()
    if not settings.fred_api_key:
        return {
            "available": False,
            "regime": "neutral",
            "score": 50.0,
            "macro_score": 0.0,
            "series": {},
            "trends": {},
            "notes": ["Macro not calculated: FRED_API_KEY is missing."],
        }

    fred_data = FredCollector(settings.fred_api_key).fetch_many(settings.start_date, FRED_SERIES)
    latest = _latest_values(fred_data)
    trends = _macro_trends(fred_data)
    macro = MacroEngine().analyze(fred_data)
    return {
        "available": True,
        "regime": macro.regime,
        "score": macro.score,
        "series": latest,
        "trends": trends,
        "notes": macro.notes,
    }


def calculate_macro_score(asset_class: str, snapshot: dict) -> dict:
    if not snapshot.get("available", False):
        return {
            "asset_class": asset_class,
            "macro_score": 0.0,
            "macro_regime": "not_calculated",
            "macro_summary": "Macro não calculado.",
            "macro_pros": [],
            "macro_cons": [],
            "warning": "Macro não calculado: FRED_API_KEY ausente.",
            "notes": ["Macro not calculated: FRED_API_KEY is missing."],
        }

    trends = snapshot.get("trends", {})
    score = 0.0
    notes: list[str] = []
    pros: list[str] = []
    cons: list[str] = []

    if asset_class == "bonds":
        score += _macro_rule(trends.get("inflation_decelerating"), 3, "Inflação desacelerando.", pros, cons)
        score += _macro_rule(trends.get("yield_10y_falling"), 3, "Yield de 10 anos caindo.", pros, cons)
        score += _macro_rule(trends.get("yield_2y_falling"), 2, "Yield de 2 anos caindo.", pros, cons)
        score += _macro_rule(trends.get("curve_disinverting"), 2, "Curva desinvertendo.", pros, cons)
        score += _macro_rule(trends.get("m2_stabilizing_or_rising"), 2, "M2 estabilizando/subindo.", pros, cons)
        score += _macro_rule(trends.get("fed_funds_no_recent_hikes"), 2, "Fed Funds sem novas altas recentes.", pros, cons)
        score += _macro_rule(trends.get("fed_balance_sheet_stabilizing_or_rising"), 1, "Balanço do Fed estabilizando/subindo.", pros, cons)

    elif asset_class in {"commodities", "emerging_markets"}:
        score += _macro_rule(trends.get("yield_10y_falling") or trends.get("yield_2y_falling"), 3, "Yields caindo.", pros, cons)
        score += _add_rule(
            trends.get("inflation_relevant_or_decelerating_without_new_tightening"),
            3,
            "Inflation relevant or decelerating without new tightening.",
            notes,
        )
        score += _add_rule(trends.get("macro_risk_elevated"), 2, "Macro risk elevated.", notes)
        score += _add_rule(trends.get("m2_stabilizing_or_rising"), 2, "M2 stabilizing or rising.", notes)
        score += _add_rule(trends.get("fed_less_restrictive"), 2, "Fed less restrictive.", notes)

    elif asset_class in {"crypto", "growth_stocks", "mega_caps"}:
        score += _add_rule(trends.get("yield_10y_falling") or trends.get("yield_2y_falling"), 3, "Yields falling.", notes)
        score += _add_rule(trends.get("fed_less_restrictive"), 3, "Fed less restrictive.", notes)
        score += _add_rule(trends.get("liquidity_stabilizing_or_rising"), 3, "Liquidity stabilizing or rising.", notes)
        score += _add_rule(False, 2, "Weak dollar rule unavailable: no dollar index series configured.", notes)
        notes.append("Nasdaq/QQQ improvement is intentionally left to the intermarket engine.")
        score += _add_rule(trends.get("inflation_decelerating"), 2, "Inflation decelerating.", notes)
        score += _add_rule(
            trends.get("unemployment_rising_moderately"),
            2,
            "Unemployment rising moderately, suggesting possible end of tightening.",
            notes,
        )

    else:
        score += _add_rule(trends.get("inflation_decelerating"), 3, "Inflation decelerating.", notes)
        score += _add_rule(trends.get("yield_10y_falling"), 3, "10Y yield falling.", notes)
        score += _add_rule(trends.get("m2_stabilizing_or_rising"), 2, "M2 stabilizing or rising.", notes)
        notes.append(f"No specific macro rule set for asset_class={asset_class}; applied generic rules.")

    score = max(0.0, min(15.0, score))
    regime = "supportive" if score >= 10 else "neutral/mixed" if score >= 5 else "hostile/low_support"
    return {
        "asset_class": asset_class,
        "macro_score": score,
        "macro_regime": regime,
        "macro_summary": f"Macro {regime}, score {score:.0f}/15.",
        "macro_pros": pros or [note for note in notes if note.startswith("+")],
        "macro_cons": cons,
        "warning": None,
        "notes": notes,
    }


def _latest_values(fred_data: dict[str, pd.DataFrame]) -> dict[str, float]:
    values = {}
    for series_id, df in fred_data.items():
        if not df.empty and "value" in df.columns:
            values[series_id] = float(df["value"].iloc[-1])
    return values


def _change_over_last_points(df: pd.DataFrame, points: int) -> float:
    if df.empty or len(df) <= points:
        return 0.0
    return float(df["value"].iloc[-1] - df["value"].iloc[-points])


def _pct_change_over_last_points(df: pd.DataFrame, points: int) -> float:
    if df.empty or len(df) <= points:
        return 0.0
    previous = float(df["value"].iloc[-points])
    latest = float(df["value"].iloc[-1])
    return ((latest / previous) - 1) * 100 if previous else 0.0


def _macro_trends(fred_data: dict[str, pd.DataFrame]) -> dict[str, bool]:
    cpi_yoy_now = _yoy(fred_data.get("CPIAUCSL"))
    cpi_yoy_prior = _yoy(fred_data.get("CPIAUCSL"), offset=6)
    core_cpi_yoy_now = _yoy(fred_data.get("CPILFESL"))
    core_cpi_yoy_prior = _yoy(fred_data.get("CPILFESL"), offset=6)
    pce_yoy_now = _yoy(fred_data.get("PCEPI"))
    pce_yoy_prior = _yoy(fred_data.get("PCEPI"), offset=6)

    inflation_now = _mean_available([cpi_yoy_now, core_cpi_yoy_now, pce_yoy_now])
    inflation_prior = _mean_available([cpi_yoy_prior, core_cpi_yoy_prior, pce_yoy_prior])
    inflation_decelerating = inflation_now is not None and inflation_prior is not None and inflation_now < inflation_prior
    inflation_relevant = inflation_now is not None and inflation_now >= 2.5

    yield_10y_change = _change_over_last_points(fred_data.get("DGS10", pd.DataFrame()), 20)
    yield_2y_change = _change_over_last_points(fred_data.get("DGS2", pd.DataFrame()), 20)
    curve_change = _change_over_last_points(fred_data.get("T10Y2Y", pd.DataFrame()), 20)
    unemployment_change = _change_over_last_points(fred_data.get("UNRATE", pd.DataFrame()), 6)
    fed_funds_change = _change_over_last_points(fred_data.get("FEDFUNDS", pd.DataFrame()), 3)
    m2_change = _pct_change_over_last_points(fred_data.get("M2SL", pd.DataFrame()), 6)
    walcl_change = _pct_change_over_last_points(fred_data.get("WALCL", pd.DataFrame()), 12)

    fed_funds_no_recent_hikes = fed_funds_change <= 0.10
    fed_less_restrictive = fed_funds_no_recent_hikes and (yield_2y_change < 0 or yield_10y_change < 0)
    m2_stabilizing_or_rising = m2_change >= -0.50
    fed_balance_sheet_stabilizing_or_rising = walcl_change >= -0.50

    return {
        "inflation_decelerating": inflation_decelerating,
        "yield_10y_falling": yield_10y_change < 0,
        "yield_2y_falling": yield_2y_change < 0,
        "curve_disinverting": curve_change > 0,
        "m2_stabilizing_or_rising": m2_stabilizing_or_rising,
        "fed_funds_no_recent_hikes": fed_funds_no_recent_hikes,
        "fed_balance_sheet_stabilizing_or_rising": fed_balance_sheet_stabilizing_or_rising,
        "inflation_relevant_or_decelerating_without_new_tightening": (inflation_relevant or inflation_decelerating)
        and fed_funds_no_recent_hikes,
        "macro_risk_elevated": unemployment_change > 0.30 or curve_change < 0,
        "fed_less_restrictive": fed_less_restrictive,
        "liquidity_stabilizing_or_rising": m2_stabilizing_or_rising or fed_balance_sheet_stabilizing_or_rising,
        "unemployment_rising_moderately": 0.10 <= unemployment_change <= 0.50,
    }


def _yoy(df: pd.DataFrame | None, offset: int = 0) -> float | None:
    if df is None or df.empty or len(df) < 13 + offset:
        return None
    latest_index = -1 - offset
    prior_index = latest_index - 12
    latest = float(df["value"].iloc[latest_index])
    prior = float(df["value"].iloc[prior_index])
    return ((latest / prior) - 1) * 100 if prior else None


def _mean_available(values: list[float | None]) -> float | None:
    clean_values = [value for value in values if value is not None]
    if not clean_values:
        return None
    return sum(clean_values) / len(clean_values)


def _add_rule(condition: bool | None, points: float, note: str, notes: list[str]) -> float:
    if condition:
        notes.append(f"+{points:.0f}: {note}")
        return points
    return 0.0


def _macro_rule(condition: bool | None, points: float, note: str, pros: list[str], cons: list[str]) -> float:
    if condition:
        pros.append(f"+{points:.0f}: {note}")
        return points
    cons.append(f"0: {note}")
    return 0.0
