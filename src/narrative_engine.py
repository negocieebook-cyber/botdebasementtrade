from __future__ import annotations

import xml.etree.ElementTree as ET  # V3
from dataclasses import dataclass

import requests  # V3

from src.universe import Asset

CLASS_THEMES: dict[str, list[str]] = {  # V3
    "equity_indices": ["stock market", "s&p 500", "nasdaq", "dow jones", "federal reserve", "inflation", "recession"],  # V3
    "sectors": ["sector rotation", "earnings", "economic data", "s&p 500", "federal reserve"],  # V3
    "growth_stocks": ["tech stocks", "nasdaq", "earnings", "interest rates", "artificial intelligence", "growth"],  # V3
    "mega_caps": ["big tech", "earnings", "nasdaq", "apple", "microsoft", "google", "amazon", "meta"],  # V3
    "banks": ["bank", "interest rate", "federal reserve", "yield curve", "credit", "lending", "deposits"],  # V3
    "emerging_markets": ["emerging markets", "dollar", "china", "developing economies", "em"],  # V3
    "commodities": ["oil", "gold", "commodity", "inflation", "dollar", "energy", "metals"],  # V3
    "crypto": ["bitcoin", "crypto", "ethereum", "blockchain", "defi", "digital assets", "btc"],  # V3
    "defensive_dividends": ["dividend", "defensive", "consumer staples", "utilities", "yield", "income"],  # V3
    "reits": ["real estate", "reit", "property", "interest rate", "housing", "mortgage"],  # V3
    "developed_international": ["europe", "japan", "international", "dollar", "global", "eurozone"],  # V3
    "bonds": ["treasury", "fed rate", "inflation", "yield curve", "interest rates", "bond", "debt"],  # V3
    "brazil_indices": ["brazil", "bovespa", "ibovespa", "petrobras", "real", "selic"],  # V3
    "brazil_stocks": ["brazil", "bovespa", "earnings", "petrobras", "vale", "selic"],  # V3
    "brazil_banks": ["brazil", "bank", "interest rate", "selic", "lending", "bradesco", "itau"],  # V3
    "brazil_commodities": ["brazil", "commodity", "petrobras", "vale", "soybean", "iron ore"],  # V3
    "brazil_etfs": ["brazil", "etf", "bovespa", "ibovespa"],  # V3
    "brazil_utilities": ["brazil", "utilities", "energy", "electricity", "eletrobras"],  # V3
    "brazil_reits": ["brazil", "fii", "real estate", "property", "fundos imobiliarios"],  # V3
}  # V3

POSITIVE_WORDS: frozenset[str] = frozenset({  # V3
    "rally", "breakout", "surge", "gains", "recovery", "upgrade", "bullish",  # V3
    "beat", "outperform", "strong", "growth", "rising", "positive", "optimism",  # V3
    "rebound", "momentum", "upside", "buy", "accumulate", "record",  # V3
    "expansion", "boost", "support", "confident", "soar", "jump",  # V3
})  # V3

NEGATIVE_WORDS: frozenset[str] = frozenset({  # V3
    "crash", "selloff", "plunge", "losses", "recession", "fear", "downgrade",  # V3
    "bearish", "miss", "underperform", "weak", "falling", "negative", "concern",  # V3
    "decline", "drop", "correction", "downturn", "risk", "warning",  # V3
    "contraction", "slowdown", "pressure", "uncertainty", "tumble", "slump",  # V3
})  # V3

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


def _fetch_rss_headlines(symbol: str, max_items: int = 20) -> list[str]:  # V3
    """Busca headlines do Yahoo Finance RSS para o símbolo informado."""  # V3
    url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={symbol}&region=US&lang=en-US"  # V3
    try:  # V3
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})  # V3
        resp.raise_for_status()  # V3
        root = ET.fromstring(resp.content)  # V3
        headlines: list[str] = []  # V3
        for item in root.iter("item"):  # V3
            title = item.findtext("title") or ""  # V3
            desc = item.findtext("description") or ""  # V3
            headlines.append(f"{title} {desc}".lower())  # V3
            if len(headlines) >= max_items:  # V3
                break  # V3
        return headlines  # V3
    except Exception:  # V3
        return []  # V3


def _score_headlines(headlines: list[str], themes: list[str]) -> tuple[float, list[str]]:  # V3
    """Pontua 0–10 com base em palavras positivas/negativas e relevância temática."""  # V3
    if not headlines:  # V3
        return 0.0, []  # V3
    pos = sum(1 for h in headlines for w in POSITIVE_WORDS if w in h)  # V3
    neg = sum(1 for h in headlines for w in NEGATIVE_WORDS if w in h)  # V3
    theme_hits = sum(1 for h in headlines if any(t in h for t in themes))  # V3
    total_signals = pos + neg  # V3
    sentiment = (pos - neg) / total_signals if total_signals > 0 else 0.0  # V3
    theme_relevance = min(theme_hits / max(len(headlines), 1), 1.0)  # V3
    score = 5.0 + sentiment * 3.0 + theme_relevance * 2.0  # V3
    score = max(0.0, min(10.0, round(score, 2)))  # V3
    notes: list[str] = []  # V3
    if pos > 0:  # V3
        notes.append(f"+{pos} positive signals in {len(headlines)} headlines")  # V3
    if neg > 0:  # V3
        notes.append(f"-{neg} negative signals in {len(headlines)} headlines")  # V3
    if theme_hits > 0:  # V3
        notes.append(f"{theme_hits}/{len(headlines)} theme-relevant headlines found")  # V3
    return score, notes  # V3


def calculate_narrative_score(symbol: str, asset_class: str) -> dict:
    themes = CLASS_THEMES.get(asset_class, CLASS_THEMES.get("equity_indices", []))  # V3
    headlines = _fetch_rss_headlines(symbol)  # V3

    if not headlines:  # V3
        return {  # V3
            "symbol": symbol,  # V3
            "asset_class": asset_class,  # V3
            "narrative_score": 0.0,  # V3
            "narrative_regime": "not_calculated",  # V3
            "narrative_summary": "Narrativa não calculada: headlines indisponíveis.",  # V3
            "narrative_pros": [],  # V3
            "narrative_cons": [],  # V3
            "themes": themes,  # V3
            "notes": ["No headlines available for this symbol."],  # V3
        }  # V3

    score, notes = _score_headlines(headlines, themes)  # V3
    regime = "bullish" if score >= 6.5 else "bearish" if score < 3.5 else "neutral"  # V3

    return {  # V3
        "symbol": symbol,  # V3
        "asset_class": asset_class,  # V3
        "narrative_score": score,  # V3
        "narrative_regime": regime,  # V3
        "narrative_summary": f"Narrativa {regime}: score {score:.1f}/10 com base em {len(headlines)} headlines.",  # V3
        "narrative_pros": [n for n in notes if n.startswith("+")],  # V3
        "narrative_cons": [n for n in notes if n.startswith("-")],  # V3
        "themes": themes,  # V3
        "notes": notes or [f"Score {score:.1f}/10, regime {regime}."],  # V3
    }  # V3
