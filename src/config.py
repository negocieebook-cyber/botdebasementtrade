from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
REPORTS_DIR = PROJECT_ROOT / "reports"
INDIVIDUAL_REPORTS_DIR = REPORTS_DIR / "individual"
CACHE_DIR = DATA_DIR / "cache"
MACRO_DIR = DATA_DIR / "macro"
CRYPTO_DIR = DATA_DIR / "crypto"
NEWS_DIR = DATA_DIR / "news"

START_DATE = "2015-01-01"
TEST_MODE = True

TEST_ASSETS = [
    "TLT",
    "GLD",
    "QQQ",
    "SPY",
    "IWM",
    "BTC-USD",
    "ETH-USD",
    "TSLA",
    "COIN",
    "KWEB",
]

INDIVIDUAL_ASSETS = [
    "TLT",
    "GLD",
    "SPY",
    "QQQ",
    "BTC-USD",
    "ETH-USD",
]

FRED_SERIES = [
    "FEDFUNDS",
    "CPIAUCSL",
    "CPILFESL",
    "PCEPI",
    "PCEPILFE",
    "UNRATE",
    "DGS2",
    "DGS10",
    "DGS30",
    "T10Y2Y",
    "M2SL",
    "WALCL",
]

SAFETY_RULES = [
    "Nunca recomendar compra ou venda diretamente.",
    "Nunca prometer retorno.",
    "Sempre mostrar riscos.",
    "Sempre mostrar gatilho de confirmacao.",
    "Sempre mostrar ponto de invalidacao.",
    "Avisar quando faltar dado.",
    "Avisar quando API falhar.",
    "Nao inventar dados ausentes.",
    "Diferenciar dado de interpretacao.",
    "Mostrar que a tese pode estar errada.",
]

MIN_NOTIFICATION_SCORE = 65

NOTIFICATION_PHASES = [
    "Acumulação avançada",
    "Rompimento inicial",
    "Tese forte",
]

MAX_TELEGRAM_ALERTS = 10
MIN_TECHNICAL_CONFIRMATIONS = 3
STRICT_MODE = True

DAILY_ALERT_ENABLED = True
WEEKLY_REPORT_ENABLED = True

SEND_EMPTY_DAILY_ALERT = True
SEND_EMPTY_WEEKLY_REPORT = True

DAILY_ALERT_MIN_SCORE = 70
DAILY_ALERT_PHASES = [
    "Rompimento inicial",
    "Tese forte",
]

DAILY_ALERT_STRICT_MODE = True
DAILY_ALERT_MAX_ASSETS = 10

WEEKLY_REPORT_MAX_ASSETS = 20

MARKET_TIMEZONE = "America/Sao_Paulo"

DAILY_ALERT_TIME = "19:30"
WEEKLY_REPORT_DAY = "Sunday"
WEEKLY_REPORT_TIME = "18:00"


@dataclass(frozen=True)
class Settings:
    period: str = "2y"
    interval: str = "1d"
    top_n: int = 25
    start_date: str = START_DATE
    test_mode: bool = TEST_MODE
    fred_api_key: str | None = None
    alpha_vantage_api_key: str | None = None
    finnhub_api_key: str | None = None
    coingecko_api_key: str | None = None
    news_api_key: str | None = None
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None


def load_settings() -> Settings:
    load_dotenv(PROJECT_ROOT / ".env")
    return Settings(
        period=os.getenv("DESBASEMENT_PERIOD", "2y"),
        interval=os.getenv("DESBASEMENT_INTERVAL", "1d"),
        top_n=int(os.getenv("DESBASEMENT_TOP_N", "25")),
        start_date=os.getenv("DESBASEMENT_START_DATE", START_DATE),
        test_mode=os.getenv("DESBASEMENT_TEST_MODE", str(TEST_MODE)).lower() in {"1", "true", "yes", "on"},
        fred_api_key=os.getenv("FRED_API_KEY") or None,
        alpha_vantage_api_key=os.getenv("ALPHA_VANTAGE_API_KEY") or None,
        finnhub_api_key=os.getenv("FINNHUB_API_KEY") or None,
        coingecko_api_key=os.getenv("COINGECKO_API_KEY") or None,
        news_api_key=os.getenv("NEWS_API_KEY") or None,
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN") or None,
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID") or None,
    )


def ensure_project_dirs() -> None:
    for path in [
        DATA_DIR / "raw",
        CACHE_DIR,
        MACRO_DIR,
        CRYPTO_DIR,
        NEWS_DIR,
        INDIVIDUAL_REPORTS_DIR,
    ]:
        path.mkdir(parents=True, exist_ok=True)
