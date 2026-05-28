from __future__ import annotations

import time  # V3
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import requests
import yfinance as yf

from src.config import DATA_DIR, FRED_SERIES, MACRO_DIR
from src.universe import Asset
from src.utils import slugify


def get_price_data(symbol: str, start_date: str) -> pd.DataFrame:
    df = yf.download(
        tickers=symbol,
        start=start_date,
        interval="1d",
        auto_adjust=False,
        progress=False,
        threads=False,
    )
    if df.empty:
        return df

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df.reset_index()
    df = df.rename(
        columns={
            "Date": "date",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Adj Close": "adj_close",
            "Volume": "volume",
        }
    )

    expected_columns = ["date", "open", "high", "low", "close", "adj_close", "volume"]
    for column in expected_columns:
        if column not in df.columns:
            df[column] = pd.NA

    return df[expected_columns].dropna(subset=["close"])


@dataclass
class MarketDataResult:
    asset: Asset
    data: pd.DataFrame
    error: str | None = None


class YFinanceCollector:
    def __init__(self, cache_dir: Path | None = None) -> None:
        self.cache_dir = cache_dir or DATA_DIR / "cache"
        self.raw_dir = DATA_DIR / "raw"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.raw_dir.mkdir(parents=True, exist_ok=True)

    def fetch_asset(
        self,
        asset: Asset,
        period: str,
        interval: str,
        start_date: str | None = None,
    ) -> MarketDataResult:
        # V3 — TTL cache: reuse file if last download was < 20 hours ago
        cache_path = self.cache_dir / f"{slugify(asset.symbol)}.csv"  # V3
        if cache_path.exists():  # V3
            age_hours = (time.time() - cache_path.stat().st_mtime) / 3600  # V3
            if age_hours < 20:  # V3
                try:  # V3
                    cached_df = pd.read_csv(cache_path, index_col=0, parse_dates=True)  # V3
                    cached_df.columns = [str(c) for c in cached_df.columns]  # V3
                    cached_df = cached_df.dropna(subset=["Close"])  # V3
                    return MarketDataResult(asset=asset, data=cached_df)  # V3
                except Exception:  # V3
                    pass  # V3 — fall through to fresh download

        download_kwargs = {
            "tickers": asset.symbol,
            "interval": interval,
            "auto_adjust": True,
            "progress": False,
            "threads": False,
        }
        if start_date:
            download_kwargs["start"] = start_date
        else:
            download_kwargs["period"] = period

        # V3 — retry loop with exponential backoff (max 3 attempts)
        last_exc: Exception | None = None  # V3
        df = pd.DataFrame()  # V3
        for attempt in range(3):  # V3
            try:  # V3
                df = yf.download(**download_kwargs)  # V3
                break  # V3 — success, exit retry loop
            except Exception as exc:  # V3
                last_exc = exc  # V3
                if attempt < 2:  # V3
                    time.sleep(2 ** attempt)  # V3 — backoff: 1s, 2s

        if df.empty and asset.symbol.upper().endswith(".SA"):
            try:
                df = yf.download(
                    tickers=asset.symbol,
                    start="2020-01-01",
                    interval=interval,
                    auto_adjust=True,
                    progress=False,
                    threads=False,
                )
            except Exception as exc:
                last_exc = exc

        if df.empty:
            return MarketDataResult(asset=asset, data=df, error=str(last_exc) if last_exc else "empty dataset")

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df = df.rename(columns=str.title)
        df = df.dropna(subset=["Close"])
        self._persist(asset, df)
        return MarketDataResult(asset=asset, data=df)

    def fetch_universe(
        self,
        universe: list[Asset],
        period: str,
        interval: str,
        start_date: str | None = None,
    ) -> list[MarketDataResult]:
        return [self.fetch_asset(asset, period, interval, start_date) for asset in universe]

    def _persist(self, asset: Asset, df: pd.DataFrame) -> None:
        filename = f"{slugify(asset.symbol)}.csv"
        df.to_csv(self.cache_dir / filename)
        df.tail(500).to_csv(self.raw_dir / filename)


class FredCollector:
    base_url = "https://api.stlouisfed.org/fred/series/observations"

    def __init__(self, api_key: str | None = None, macro_dir: Path | None = None) -> None:
        self.api_key = api_key
        self.macro_dir = macro_dir or MACRO_DIR
        self.macro_dir.mkdir(parents=True, exist_ok=True)

    def fetch_series(self, series_id: str, start_date: str) -> pd.DataFrame:
        cache_path = self.macro_dir / f"{slugify(series_id)}.csv"
        if not self.api_key:
            if cache_path.exists():
                return pd.read_csv(cache_path, parse_dates=["date"])
            return pd.DataFrame(columns=["date", "value", "series_id"])

        try:
            response = requests.get(
                self.base_url,
                params={
                    "series_id": series_id,
                    "api_key": self.api_key,
                    "file_type": "json",
                    "observation_start": start_date,
                },
                timeout=30,
            )
            response.raise_for_status()
            observations = response.json().get("observations", [])
        except Exception as error:
            print(f"Warning: FRED failed for {series_id}: {error}")
            if cache_path.exists():
                print(f"Warning: using cached FRED data for {series_id}.")
                return pd.read_csv(cache_path, parse_dates=["date"])
            return pd.DataFrame(columns=["date", "value", "series_id"])

        df = pd.DataFrame(observations)
        if df.empty:
            return pd.DataFrame(columns=["date", "value", "series_id"])

        df = df[["date", "value"]].copy()
        df["value"] = pd.to_numeric(df["value"].replace(".", pd.NA), errors="coerce")
        df["date"] = pd.to_datetime(df["date"])
        df["series_id"] = series_id
        df = df.dropna(subset=["value"])
        df.to_csv(cache_path, index=False)
        return df

    def fetch_many(self, start_date: str, series_ids: list[str] | None = None) -> dict[str, pd.DataFrame]:
        selected_series = series_ids or FRED_SERIES
        data = {}
        for series_id in selected_series:
            data[series_id] = self.fetch_series(series_id, start_date)
        return data


class CoinGeckoCollector:
    def fetch_market_chart(self, coin_id: str) -> pd.DataFrame:
        raise NotImplementedError("CoinGecko integration is reserved for the next delivery.")


class AlphaVantageCollector:
    def fetch_daily_adjusted(self, symbol: str) -> pd.DataFrame:
        raise NotImplementedError("Alpha Vantage integration is reserved for the next delivery.")


class FinnhubCollector:
    def fetch_company_news(self, symbol: str) -> list[dict]:
        raise NotImplementedError("Finnhub integration is reserved for the next delivery.")


class GdeltCollector:
    def search_news(self, query: str) -> list[dict]:
        raise NotImplementedError("GDELT integration is reserved for the next delivery.")
