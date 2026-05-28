from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ClassThreshold:
    relevant_drawdown_pct: float
    strong_drawdown_pct: float
    extreme_drawdown_pct: float
    capitulation_rsi: float
    support_distance_pct: float
    volatility_compression_ratio: float
    min_history_rows: int = 180


THRESHOLDS = {
    "bonds": {
        "relevant_drawdown": 0.15,
        "strong_drawdown": 0.25,
        "extreme_drawdown": 0.35,
    },
    "equity_indices": {
        "relevant_drawdown": 0.20,
        "strong_drawdown": 0.30,
        "extreme_drawdown": 0.40,
    },
    "sectors": {
        "relevant_drawdown": 0.20,
        "strong_drawdown": 0.35,
        "extreme_drawdown": 0.50,
    },
    "growth_stocks": {
        "relevant_drawdown": 0.40,
        "strong_drawdown": 0.60,
        "extreme_drawdown": 0.75,
    },
    "mega_caps": {
        "relevant_drawdown": 0.25,
        "strong_drawdown": 0.40,
        "extreme_drawdown": 0.55,
    },
    "us_core_stocks": {
        "relevant_drawdown": 0.30,
        "strong_drawdown": 0.45,
        "extreme_drawdown": 0.60,
    },
    "banks": {
        "relevant_drawdown": 0.25,
        "strong_drawdown": 0.40,
        "extreme_drawdown": 0.60,
    },
    "emerging_markets": {
        "relevant_drawdown": 0.30,
        "strong_drawdown": 0.45,
        "extreme_drawdown": 0.60,
    },
    "commodities": {
        "relevant_drawdown": 0.30,
        "strong_drawdown": 0.50,
        "extreme_drawdown": 0.65,
    },
    "crypto": {
        "relevant_drawdown": 0.50,
        "strong_drawdown": 0.70,
        "extreme_drawdown": 0.85,
    },
    "defensive_dividends": {
        "relevant_drawdown": 0.20,
        "strong_drawdown": 0.35,
        "extreme_drawdown": 0.50,
    },
    "developed_international": {
        "relevant_drawdown": 0.25,
        "strong_drawdown": 0.40,
        "extreme_drawdown": 0.55,
    },
    "reits": {
        "relevant_drawdown": 0.25,
        "strong_drawdown": 0.40,
        "extreme_drawdown": 0.60,
    },
    "brazil_indices": {
        "relevant_drawdown": 0.20,
        "strong_drawdown": 0.35,
        "extreme_drawdown": 0.50,
    },
    "brazil_etfs": {
        "relevant_drawdown": 0.20,
        "strong_drawdown": 0.35,
        "extreme_drawdown": 0.50,
    },
    "brazil_stocks": {
        "relevant_drawdown": 0.35,
        "strong_drawdown": 0.55,
        "extreme_drawdown": 0.70,
    },
    "brazil_all_stocks": {
        "relevant_drawdown": 0.35,
        "strong_drawdown": 0.55,
        "extreme_drawdown": 0.70,
    },
    "brazil_banks": {
        "relevant_drawdown": 0.25,
        "strong_drawdown": 0.40,
        "extreme_drawdown": 0.60,
    },
    "brazil_commodities": {
        "relevant_drawdown": 0.30,
        "strong_drawdown": 0.50,
        "extreme_drawdown": 0.65,
    },
    "brazil_utilities": {
        "relevant_drawdown": 0.20,
        "strong_drawdown": 0.35,
        "extreme_drawdown": 0.50,
    },
    "brazil_reits": {
        "relevant_drawdown": 0.20,
        "strong_drawdown": 0.35,
        "extreme_drawdown": 0.50,
    },
}


CLASS_PARAMETERS = {
    "bonds": {"capitulation_rsi": 40.0, "support_distance_pct": 5.0, "volatility_compression_ratio": 0.80},
    "equity_indices": {"capitulation_rsi": 38.0, "support_distance_pct": 6.0, "volatility_compression_ratio": 0.75},
    "sectors": {"capitulation_rsi": 38.0, "support_distance_pct": 8.0, "volatility_compression_ratio": 0.75},
    "growth_stocks": {"capitulation_rsi": 40.0, "support_distance_pct": 12.0, "volatility_compression_ratio": 0.70},
    "mega_caps": {"capitulation_rsi": 38.0, "support_distance_pct": 8.0, "volatility_compression_ratio": 0.75},
    "us_core_stocks": {"capitulation_rsi": 38.0, "support_distance_pct": 9.0, "volatility_compression_ratio": 0.75},
    "banks": {"capitulation_rsi": 38.0, "support_distance_pct": 9.0, "volatility_compression_ratio": 0.75},
    "emerging_markets": {"capitulation_rsi": 38.0, "support_distance_pct": 10.0, "volatility_compression_ratio": 0.75},
    "commodities": {"capitulation_rsi": 38.0, "support_distance_pct": 10.0, "volatility_compression_ratio": 0.80},
    "crypto": {"capitulation_rsi": 40.0, "support_distance_pct": 12.0, "volatility_compression_ratio": 0.70},
    "defensive_dividends": {"capitulation_rsi": 38.0, "support_distance_pct": 7.0, "volatility_compression_ratio": 0.78},
    "developed_international": {"capitulation_rsi": 38.0, "support_distance_pct": 8.0, "volatility_compression_ratio": 0.76},
    "reits": {"capitulation_rsi": 38.0, "support_distance_pct": 8.0, "volatility_compression_ratio": 0.78},
    "brazil_indices": {"capitulation_rsi": 38.0, "support_distance_pct": 8.0, "volatility_compression_ratio": 0.76},
    "brazil_etfs": {"capitulation_rsi": 38.0, "support_distance_pct": 8.0, "volatility_compression_ratio": 0.76},
    "brazil_stocks": {"capitulation_rsi": 40.0, "support_distance_pct": 12.0, "volatility_compression_ratio": 0.70},
    "brazil_all_stocks": {"capitulation_rsi": 40.0, "support_distance_pct": 12.0, "volatility_compression_ratio": 0.70},
    "brazil_banks": {"capitulation_rsi": 38.0, "support_distance_pct": 9.0, "volatility_compression_ratio": 0.75},
    "brazil_commodities": {"capitulation_rsi": 38.0, "support_distance_pct": 10.0, "volatility_compression_ratio": 0.80},
    "brazil_utilities": {"capitulation_rsi": 38.0, "support_distance_pct": 7.0, "volatility_compression_ratio": 0.78},
    "brazil_reits": {"capitulation_rsi": 38.0, "support_distance_pct": 8.0, "volatility_compression_ratio": 0.78},
}


DEFAULT_THRESHOLD = ClassThreshold(-0.20 * 100, -0.30 * 100, -0.40 * 100, 38.0, 8.0, 0.75)


def get_threshold(asset_class: str) -> ClassThreshold:
    drawdowns = THRESHOLDS.get(asset_class)
    if drawdowns is None:
        return DEFAULT_THRESHOLD

    parameters = CLASS_PARAMETERS.get(asset_class, CLASS_PARAMETERS["equity_indices"])
    return ClassThreshold(
        relevant_drawdown_pct=-drawdowns["relevant_drawdown"] * 100,
        strong_drawdown_pct=-drawdowns["strong_drawdown"] * 100,
        extreme_drawdown_pct=-drawdowns["extreme_drawdown"] * 100,
        capitulation_rsi=parameters["capitulation_rsi"],
        support_distance_pct=parameters["support_distance_pct"],
        volatility_compression_ratio=parameters["volatility_compression_ratio"],
    )


def get_thresholds(asset_class: str) -> dict[str, float]:
    return THRESHOLDS.get(asset_class, THRESHOLDS["equity_indices"])
