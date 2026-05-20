from __future__ import annotations

from dataclasses import dataclass

from src.universe import Asset

MONITORED_THEMES = [
    "fed rate cuts",
    "inflation cooling",
    "recession risk",
    "treasury yields",
    "bond market rally",
    "dollar weakness",
    "gold breakout",
    "bitcoin ETF",
    "liquidity",
    "quantitative tightening",
    "quantitative easing",
    "banking crisis",
]


@dataclass
class NarrativeSnapshot:
    score: float
    tone: str
    notes: list[str]


class NarrativeEngine:
    def analyze(self, asset: Asset) -> NarrativeSnapshot:
        result = calculate_narrative_score(asset.symbol, asset.asset_class)
        return NarrativeSnapshot(
            score=result["narrative_score"] * 10,
            tone=result["narrative_regime"],
            notes=result["notes"],
        )


def calculate_narrative_score(symbol: str, asset_class: str) -> dict:
    return {
        "symbol": symbol,
        "asset_class": asset_class,
        "narrative_score": 0.0,
        "narrative_regime": "not_calculated",
        "narrative_summary": "Narrativa ainda não implementada.",
        "narrative_pros": [],
        "narrative_cons": [],
        "themes": MONITORED_THEMES,
        "notes": ["Narrative not implemented yet."],
    }
