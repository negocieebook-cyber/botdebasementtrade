from __future__ import annotations

import csv
from io import StringIO
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd

from src.config import DATA_DIR


SP500_SOURCE_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
NASDAQ100_SOURCE_URL = "https://en.wikipedia.org/wiki/Nasdaq-100"
US_STOCKS_CORE_FILE = DATA_DIR / "us_stocks_core.csv"


def fetch_us_core_tickers() -> list[dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    for ticker in _fetch_sp500_tickers():
        rows.setdefault(ticker, {"ticker": ticker, "source": "S&P 500"})
    for ticker in _fetch_nasdaq100_tickers():
        if ticker in rows:
            rows[ticker]["source"] = "S&P 500; Nasdaq 100"
        else:
            rows[ticker] = {"ticker": ticker, "source": "Nasdaq 100"}
    return [rows[ticker] for ticker in sorted(rows)]


def update_us_core_stock_file(path: Path = US_STOCKS_CORE_FILE) -> list[dict[str, str]]:
    tickers = fetch_us_core_tickers()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["ticker", "yfinance_symbol", "source", "updated_at"])
        updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for row in tickers:
            ticker = row["ticker"]
            writer.writerow([ticker, _to_yfinance_symbol(ticker), row["source"], updated_at])
    return tickers


def _fetch_sp500_tickers() -> list[str]:
    tables = pd.read_html(StringIO(_download_html(SP500_SOURCE_URL)))
    for table in tables:
        if "Symbol" in table.columns:
            return [_normalize_ticker(value) for value in table["Symbol"].dropna()]
    raise RuntimeError("Tabela do S&P 500 nao encontrada.")


def _fetch_nasdaq100_tickers() -> list[str]:
    tables = pd.read_html(StringIO(_download_html(NASDAQ100_SOURCE_URL)))
    for table in tables:
        columns = {str(column).strip().lower(): column for column in table.columns}
        ticker_column = columns.get("ticker") or columns.get("symbol")
        if ticker_column is not None:
            values = [_normalize_ticker(value) for value in table[ticker_column].dropna()]
            filtered = [ticker for ticker in values if ticker and ticker != "TICKER"]
            if len(filtered) >= 50:
                return filtered
    raise RuntimeError("Tabela do Nasdaq 100 nao encontrada.")


def _normalize_ticker(value: object) -> str:
    return str(value).strip().upper().replace(".", "-")


def _to_yfinance_symbol(ticker: str) -> str:
    return ticker.strip().upper().replace(".", "-")


def _download_html(url: str) -> str:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=45) as response:
        return response.read().decode("utf-8", errors="ignore")


def main() -> None:
    tickers = update_us_core_stock_file()
    print(f"Arquivo atualizado: {US_STOCKS_CORE_FILE}")
    print(f"Tickers americanos carregados: {len(tickers)}")


if __name__ == "__main__":
    main()
