from __future__ import annotations


MARKET_GROUPS = {
    "us_equities": {
        "growth_stocks",
        "mega_caps",
        "us_core_stocks",
        "us_core_momentum",
        "banks",
        "sectors",
        "equity_indices",
    },
    "crypto": {"crypto"},
    "brazil": {
        "brazil_indices",
        "brazil_etfs",
        "brazil_stocks",
        "brazil_all_stocks",
        "brazil_banks",
        "brazil_commodities",
        "brazil_utilities",
        "brazil_reits",
    },
    "bonds_commodities_others": {
        "bonds",
        "commodities",
        "emerging_markets",
        "international_developed",
        "developed_markets",
        "developed_international",
        "reits",
        "defensive_dividends",
    },
}

GROUP_ORDER = ["us_equities", "crypto", "brazil", "bonds_commodities_others"]


def market_group_for_class(asset_class: str, symbol: str = "") -> str:
    normalized_class = str(asset_class or "")
    normalized_symbol = str(symbol or "").upper()
    if normalized_symbol.endswith(".SA") or normalized_class.startswith("brazil_"):
        return "brazil"
    for group, classes in MARKET_GROUPS.items():
        if normalized_class in classes:
            return group
    return "bonds_commodities_others"


def empty_group_stats() -> dict[str, dict[str, int]]:
    return {
        group: {"planned": 0, "analyzed": 0, "approved": 0, "alerts": 0, "errors": 0}
        for group in GROUP_ORDER
    }
