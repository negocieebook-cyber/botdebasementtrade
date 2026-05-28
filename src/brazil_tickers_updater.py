from __future__ import annotations

import csv
import re
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen

from src.config import DATA_DIR


BRAZIL_STOCKS_SOURCE_URL = "https://api.dadosdemercado.com.br/acoes"
BRAZIL_STOCKS_ALL_FILE = DATA_DIR / "brazil_stocks_all.csv"


def fetch_brazil_stock_tickers() -> list[str]:
    request = Request(BRAZIL_STOCKS_SOURCE_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=45) as response:
        html = response.read().decode("utf-8", errors="ignore")

    tickers = {
        match.upper()
        for match in re.findall(r'href="/acoes/([a-z0-9]{4,6})"', html)
        if _looks_like_brazil_stock_ticker(match)
    }
    if not tickers:
        raise RuntimeError("Nenhum ticker brasileiro encontrado na fonte publica.")
    return sorted(tickers)


def update_brazil_stock_file(path: Path = BRAZIL_STOCKS_ALL_FILE) -> list[str]:
    tickers = fetch_brazil_stock_tickers()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["ticker", "yfinance_symbol", "source", "updated_at"])
        updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for ticker in tickers:
            writer.writerow([ticker, f"{ticker}.SA", BRAZIL_STOCKS_SOURCE_URL, updated_at])
    return tickers


def _looks_like_brazil_stock_ticker(ticker: str) -> bool:
    normalized = ticker.upper()
    return bool(re.fullmatch(r"[A-Z]{4}[0-9]{1,2}[A-Z]?", normalized))


def main() -> None:
    tickers = update_brazil_stock_file()
    print(f"Arquivo atualizado: {BRAZIL_STOCKS_ALL_FILE}")
    print(f"Tickers brasileiros carregados: {len(tickers)}")


if __name__ == "__main__":
    main()
