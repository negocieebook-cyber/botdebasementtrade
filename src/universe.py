from __future__ import annotations

import warnings
from dataclasses import dataclass

from src.config import TEST_ASSETS


DISABLED_TICKERS: dict[str, str] = {
    "SQ": "Block Inc. changed its NYSE ticker from SQ to XYZ in January 2025.",
    "EMBR3.SA": "yfinance returned empty dataset in recurring validation.",
    "AZUL4.SA": "yfinance returned empty dataset in recurring validation.",
    "GOLL4.SA": "yfinance returned empty dataset in recurring validation.",
    "BRFS3.SA": "yfinance returned empty dataset in recurring validation.",
    "JBSS3.SA": "yfinance returned empty dataset in recurring validation.",
    "ELET3.SA": "yfinance returned empty dataset in recurring validation.",
    "ELET6.SA": "yfinance returned empty dataset in recurring validation.",
}


@dataclass(frozen=True)
class Asset:
    symbol: str
    name: str
    asset_class: str
    region: str = "global"
    liquidity_note: str = "large/liquid proxy"


UNIVERSE_BY_CLASS: dict[str, list[str]] = {
    "bonds": [
        "TLT",
        "IEF",
        "SHY",
        "GOVT",
        "EDV",
        "ZROZ",
        "HYG",
        "LQD",
        "JNK",
        "BND",
        "AGG",
        "TIP",
        "TIPS",
        "MUB",
        "EMB",
        "VWOB",
    ],
    "commodities": [
        "GLD",
        "IAU",
        "SLV",
        "GDX",
        "GDXJ",
        "DBC",
        "USO",
        "UNG",
        "COPX",
        "URA",
        "PDBC",
        "DBA",
        "CPER",
        "WEAT",
        "CORN",
        "SOYB",
        "NIB",
        "UGA",
        "XME",
        "PICK",
    ],
    "equity_indices": [
        "SPY",
        "QQQ",
        "IWM",
        "DIA",
        "VTI",
        "EEM",
        "EFA",
        "ACWI",
        "VT",
        "VEA",
        "VWO",
        "QQQM",
        "RSP",
        "MDY",
        "IJH",
        "IJR",
    ],
    "sectors": [
        "XLF",
        "XLK",
        "XLE",
        "XLY",
        "XLI",
        "XLV",
        "XLU",
        "XLB",
        "XLC",
        "XLRE",
        "XBI",
        "SMH",
        "SOXX",
        "IBB",
        "KBE",
        "KRE",
        "XRT",
        "ITB",
        "TAN",
        "FAN",
        "ARKK",
    ],
    "growth_stocks": [
        "TSLA",
        "COIN",
        "PLTR",
        "SHOP",
        "SQ",
        "XYZ",
        "ROKU",
        "SNOW",
        "NET",
        "DDOG",
        "CRWD",
        "U",
        "PATH",
        "AFRM",
        "HOOD",
        "RBLX",
        "UPST",
        "SOFI",
        "DKNG",
        "SE",
        "MELI",
        "CELH",
    ],
    "mega_caps": [
        "AAPL",
        "MSFT",
        "NVDA",
        "AMZN",
        "GOOGL",
        "META",
        "AVGO",
        "NFLX",
        "AMD",
        "ORCL",
        "CRM",
        "ADBE",
        "INTC",
        "CSCO",
        "IBM",
        "QCOM",
        "TXN",
        "MU",
    ],
    "banks": [
        "JPM",
        "BAC",
        "C",
        "GS",
        "MS",
        "SCHW",
        "KRE",
        "WFC",
        "USB",
        "PNC",
        "TFC",
        "COF",
        "AXP",
        "BLK",
        "BX",
        "PYPL",
        "MA",
        "V",
    ],
    "emerging_markets": [
        "FXI",
        "KWEB",
        "BABA",
        "JD",
        "BIDU",
        "PDD",
        "EWZ",
        "EWW",
        "INDA",
        "EZA",
        "TUR",
        "EIDO",
        "EWY",
        "EWT",
        "MCHI",
        "ASHR",
        "ILF",
        "FM",
    ],
    "crypto": [
        "BTC-USD",
        "ETH-USD",
        "SOL-USD",
        "BNB-USD",
        "XRP-USD",
        "ADA-USD",
        "AVAX-USD",
        "LINK-USD",
        "DOGE-USD",
        "DOT-USD",
        "LTC-USD",
        "BCH-USD",
        "NEAR-USD",
        "ATOM-USD",
        "FIL-USD",
        "ICP-USD",
        "INJ-USD",
        "APT-USD",
        "ARB-USD",
        "OP-USD",
        "SUI-USD",
        "FET-USD",
        "RENDER-USD",
        "TIA-USD",
        "STX-USD",
        "IMX-USD",
    ],
    "defensive_dividends": [
        "KO",
        "PEP",
        "MCD",
        "WMT",
        "COST",
        "PG",
        "CL",
        "JNJ",
        "MRK",
        "ABBV",
        "T",
        "VZ",
        "NEE",
        "DUK",
        "SO",
    ],
    "developed_international": [
        "EWJ",
        "EWU",
        "EWQ",
        "EWG",
        "EWI",
        "EWP",
        "EWL",
        "EWA",
        "EWC",
        "EWS",
        "EWH",
    ],
    "reits": [
        "VNQ",
        "IYR",
        "SCHH",
        "XLRE",
        "O",
        "PLD",
        "AMT",
        "EQIX",
        "SPG",
        "PSA",
    ],
    "brazil_indices": [],
    "brazil_etfs": [
        "BOVA11.SA",
        "SMAL11.SA",
        "IVVB11.SA",
        "HASH11.SA",
        "B5P211.SA",
        "IMAB11.SA",
        "DIVO11.SA",
        "XFIX11.SA",
    ],
    "brazil_stocks": [
        "WEGE3.SA",
        "ABEV3.SA",
        "RENT3.SA",
        "LREN3.SA",
        "MGLU3.SA",
        "VIVA3.SA",
        "RAIL3.SA",
        "EMBR3.SA",
        "AZUL4.SA",
        "GOLL4.SA",
    ],
    "brazil_banks": [
        "ITUB4.SA",
        "BBDC4.SA",
        "BBAS3.SA",
        "SANB11.SA",
        "BPAC11.SA",
    ],
    "brazil_commodities": [
        "VALE3.SA",
        "PETR4.SA",
        "PETR3.SA",
        "PRIO3.SA",
        "CSNA3.SA",
        "GGBR4.SA",
        "SUZB3.SA",
        "KLBN11.SA",
        "BRFS3.SA",
        "JBSS3.SA",
    ],
    "brazil_utilities": [
        "ELET3.SA",
        "ELET6.SA",
        "CMIG4.SA",
        "CPFE3.SA",
        "ENGI11.SA",
        "TAEE11.SA",
        "EQTL3.SA",
    ],
    "brazil_reits": [
        "HGLG11.SA",
        "KNRI11.SA",
        "XPML11.SA",
        "MXRF11.SA",
        "VISC11.SA",
        "HGRU11.SA",
        "BTLG11.SA",
        "RBRF11.SA",
    ],
}


def _build_universe(emit_warnings: bool = False) -> list[Asset]:
    assets: list[Asset] = []
    seen: set[str] = set()
    for asset_class, symbols in UNIVERSE_BY_CLASS.items():
        for symbol in symbols:
            normalized = symbol.upper()
            if normalized in seen:
                if emit_warnings:
                    warnings.warn(
                        f"Duplicate asset {symbol} ignored in class {asset_class}; first class kept.",
                        RuntimeWarning,
                        stacklevel=2,
                    )
                continue
            seen.add(normalized)
            if normalized in DISABLED_TICKERS:
                continue
            region = "brazil" if asset_class.startswith("brazil_") else "global"
            assets.append(Asset(symbol=symbol, name=symbol, asset_class=asset_class, region=region))
    return assets


DEFAULT_UNIVERSE: list[Asset] = _build_universe()


def get_default_universe() -> list[Asset]:
    return get_full_universe()


def get_full_universe() -> list[Asset]:
    return _build_universe(emit_warnings=True)


def get_test_universe() -> list[Asset]:
    return get_assets_by_symbols(TEST_ASSETS)


def get_asset_class(symbol: str) -> str:
    normalized_symbol = symbol.upper()
    known_assets = {asset.symbol.upper(): asset for asset in DEFAULT_UNIVERSE}
    if normalized_symbol in known_assets:
        return known_assets[normalized_symbol].asset_class
    if normalized_symbol.endswith("-USD"):
        return "crypto"
    if normalized_symbol.endswith("=X"):
        return "fx"
    return "growth_stocks"


def get_assets_by_symbols(symbols: list[str]) -> list[Asset]:
    known_assets = {asset.symbol.upper(): asset for asset in DEFAULT_UNIVERSE}
    return [
        known_assets.get(
            symbol.upper(),
            Asset(symbol=symbol, name=symbol, asset_class=get_asset_class(symbol), region="unknown"),
        )
        for symbol in symbols
        if not is_disabled_ticker(symbol)
    ]


def is_disabled_ticker(symbol: str) -> bool:
    return symbol.upper() in DISABLED_TICKERS


def get_disabled_tickers() -> dict[str, str]:
    return dict(DISABLED_TICKERS)


def get_validation_universe() -> list[Asset]:
    assets: list[Asset] = []
    seen: set[str] = set()
    for asset_class, symbols in UNIVERSE_BY_CLASS.items():
        for symbol in symbols:
            normalized = symbol.upper()
            if normalized in seen:
                continue
            seen.add(normalized)
            region = "brazil" if asset_class.startswith("brazil_") else "global"
            assets.append(Asset(symbol=symbol, name=symbol, asset_class=asset_class, region=region))
    return assets


def get_brazil_validation_universe() -> list[Asset]:
    return [asset for asset in get_validation_universe() if asset.region == "brazil"]
