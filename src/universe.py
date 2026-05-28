from __future__ import annotations

import csv
import warnings
from dataclasses import dataclass

from src.config import DATA_DIR, TEST_ASSETS


BRAZIL_STOCKS_ALL_FILE = DATA_DIR / "brazil_stocks_all.csv"
US_STOCKS_CORE_FILE = DATA_DIR / "us_stocks_core.csv"


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


def _load_all_brazil_stock_symbols() -> list[str]:
    if not BRAZIL_STOCKS_ALL_FILE.exists():
        return []
    symbols: list[str] = []
    with BRAZIL_STOCKS_ALL_FILE.open("r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            symbol = (row.get("yfinance_symbol") or row.get("ticker") or "").strip().upper()
            if not symbol:
                continue
            if not symbol.endswith(".SA"):
                symbol = f"{symbol}.SA"
            symbols.append(symbol)
    return symbols


def _load_us_core_stock_symbols() -> list[str]:
    if not US_STOCKS_CORE_FILE.exists():
        return []
    symbols: list[str] = []
    with US_STOCKS_CORE_FILE.open("r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            symbol = (row.get("yfinance_symbol") or row.get("ticker") or "").strip().upper()
            if symbol:
                symbols.append(symbol)
    return symbols


def _build_universe(emit_warnings: bool = False) -> list[Asset]:
    assets: list[Asset] = []
    seen: set[str] = set()
    universe_by_class = {key: list(value) for key, value in UNIVERSE_BY_CLASS.items()}
    universe_by_class.setdefault("us_core_stocks", []).extend(_load_us_core_stock_symbols())
    universe_by_class.setdefault("brazil_all_stocks", []).extend(_load_all_brazil_stock_symbols())
    for asset_class, symbols in universe_by_class.items():
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
    universe_by_class = {key: list(value) for key, value in UNIVERSE_BY_CLASS.items()}
    universe_by_class.setdefault("us_core_stocks", []).extend(_load_us_core_stock_symbols())
    universe_by_class.setdefault("brazil_all_stocks", []).extend(_load_all_brazil_stock_symbols())
    for asset_class, symbols in universe_by_class.items():
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


MOMENTUM_UNIVERSE_BY_CLASS: dict[str, list[str]] = {  # V4
    "defense_space": [  # V4
        "LMT", "RTX", "NOC", "GD", "BA", "HII", "LDOS", "SAIC", "VOYG", "RKLB",  # V4
        "ASTS", "AVAV", "KTOS", "BBAI",  # V4
        "RHEG.DE", "LDO.MI", "HO.PA", "BAE.L", "AIR.PA",  # V4
        "ITA", "XAR", "SHLD", "PPA", "FITE",  # V4
    ],  # V4
    "ai_semis": [  # V4
        "TSM", "ASML", "AMAT", "LRCX", "KLAC", "MRVL", "ARM", "CRDO", "MPWR",  # V4
        "NOW", "GTLB", "AI",  # V4
        "SMH", "SOXX", "ROBO", "BOTZ", "AIQ", "IRBO",  # V4
    ],  # V4
    "robotics_automation": [  # V4
        "FANUY", "ABB", "ROK", "ISRG", "GMED", "OUST", "SERV", "VPG", "TER", "CGNX",  # V4
    ],  # V4
    "biotech_health": [  # V4
        "LLY", "NVO", "SMMT", "RXRX", "BEAM", "CRSP", "NTLA", "MRNA", "BNTX",  # V4
        "XBI", "IBB", "ARKG",  # V4
    ],  # V4
    "clean_energy": [  # V4
        "ENPH", "FSLR", "SEDG", "RUN", "NEE", "BEP", "PLUG", "FCEL", "BE",  # V4
        "ICLN", "TAN", "QCLN",  # V4
    ],  # V4
    "international_momentum": [  # V4
        "EZU", "VGK", "FEZ", "EWG", "EWQ", "EWU",  # V4
        "EWJ", "EWY", "EWT", "MCHI", "EWH", "EWA",  # V4
        "VWO", "FM", "EEMS",  # V4
    ],  # V4
    "brazil_momentum": [  # V4
        "POSI3.SA", "TOTS3.SA", "INTB3.SA", "LWSA3.SA", "SMLL11.SA",  # V4
        "AGRO3.SA", "SLCE3.SA", "GGBR4.SA", "EGIE3.SA", "TAEE11.SA", "CPFE3.SA",  # V4
    ],  # V4
}  # V4


def get_momentum_universe() -> list[Asset]:  # V4
    """Retorna o universo de momentum deduplicado, respeitando DISABLED_TICKERS."""  # V4
    assets: list[Asset] = []  # V4
    seen: set[str] = set()  # V4
    universe_by_class = {key: list(value) for key, value in MOMENTUM_UNIVERSE_BY_CLASS.items()}  # V4
    universe_by_class.setdefault("us_core_momentum", []).extend(_load_us_core_stock_symbols())  # V5
    universe_by_class.setdefault("brazil_momentum", []).extend(_load_all_brazil_stock_symbols())  # V4
    for asset_class, symbols in universe_by_class.items():  # V4
        for symbol in symbols:  # V4
            normalized = symbol.upper()  # V4
            if normalized in seen:  # V4
                continue  # V4
            seen.add(normalized)  # V4
            if normalized in DISABLED_TICKERS:  # V4
                continue  # V4
            region = "brazil" if normalized.endswith(".SA") else "global"  # V4
            assets.append(Asset(symbol=symbol, name=symbol, asset_class=asset_class, region=region))  # V4
    return assets  # V4
