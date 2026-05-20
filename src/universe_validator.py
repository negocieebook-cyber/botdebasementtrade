from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pandas as pd
import yfinance as yf

from src.config import REPORTS_DIR
from src.universe import Asset, get_brazil_validation_universe, get_disabled_tickers, get_validation_universe, is_disabled_ticker
from src.utils import write_text


VALIDATION_REPORT_PATH = REPORTS_DIR / "universe_validation_report.md"
VALIDATION_ERRORS_PATH = REPORTS_DIR / "universe_validation_errors.txt"
BRAZIL_VALIDATION_REPORT_PATH = REPORTS_DIR / "brazil_validation_report.md"


@dataclass(frozen=True)
class TickerValidationResult:
    symbol: str
    asset_class: str
    status: str
    rows: int
    disabled: bool
    reason: str = ""
    last_date: str = ""


def validate_universe() -> dict:
    assets = get_validation_universe()
    disabled_reasons = get_disabled_tickers()
    results = [_validate_asset(asset, disabled_reasons, period="30d") for asset in assets]
    error_results = [item for item in results if item.status == "ERRO"]
    disabled_results = [item for item in results if item.disabled]
    ok_results = [item for item in results if item.status == "OK"]

    write_text(VALIDATION_REPORT_PATH, _generate_validation_report(results))
    write_text(VALIDATION_ERRORS_PATH, "\n".join(item.symbol for item in error_results) + ("\n" if error_results else ""))

    return {
        "planned_count": len(results),
        "analyzed_count": len(results),
        "approved_count": len(ok_results),
        "rejected_count": len(error_results),
        "all_results": [_result_to_execution_dict(item) for item in results],
        "ignored_tickers": {item.symbol: item.reason for item in disabled_results},
        "validation_errors": {item.symbol: item.reason for item in error_results},
        "report_path": str(VALIDATION_REPORT_PATH),
        "errors_path": str(VALIDATION_ERRORS_PATH),
    }


def validate_brazil() -> dict:
    assets = get_brazil_validation_universe()
    disabled_reasons = get_disabled_tickers()
    results = [_validate_asset(asset, disabled_reasons, period="60d") for asset in assets]
    error_results = [item for item in results if item.status == "ERRO"]
    ok_results = [item for item in results if item.status == "OK"]

    write_text(BRAZIL_VALIDATION_REPORT_PATH, _generate_brazil_validation_report(results))

    return {
        "planned_count": len(results),
        "analyzed_count": len(results),
        "approved_count": len(ok_results),
        "rejected_count": len(error_results),
        "all_results": [_result_to_execution_dict(item) for item in results],
        "validation_errors": {item.symbol: item.reason for item in error_results},
        "report_path": str(BRAZIL_VALIDATION_REPORT_PATH),
        "planned_brazil_count": len(results),
        "analyzed_brazil_count": len(ok_results),
        "approved_brazil_count": len(ok_results),
        "brazil_error_count": len(error_results),
        "brazil_errors": [{"ticker": item.symbol, "reason": item.reason} for item in error_results],
    }


def _validate_asset(asset: Asset, disabled_reasons: dict[str, str], period: str) -> TickerValidationResult:
    disabled = is_disabled_ticker(asset.symbol)
    disabled_reason = disabled_reasons.get(asset.symbol.upper(), "")
    try:
        df = yf.download(
            tickers=asset.symbol,
            period=period,
            interval="1d",
            auto_adjust=True,
            progress=False,
            threads=False,
        )
    except Exception as exc:
        return TickerValidationResult(
            symbol=asset.symbol,
            asset_class=asset.asset_class,
            status="ERRO",
            rows=0,
            disabled=disabled,
            reason=_join_reasons(disabled_reason, str(exc)),
        )

    if df.empty:
        return TickerValidationResult(
            symbol=asset.symbol,
            asset_class=asset.asset_class,
            status="ERRO",
            rows=0,
            disabled=disabled,
            reason=_join_reasons(disabled_reason, "empty dataset"),
        )

    last_date = _last_date(df)
    return TickerValidationResult(
        symbol=asset.symbol,
        asset_class=asset.asset_class,
        status="OK",
        rows=len(df),
        disabled=disabled,
        reason=disabled_reason,
        last_date=last_date,
    )


def _generate_brazil_validation_report(results: list[TickerValidationResult]) -> str:
    ok_results = [item for item in results if item.status == "OK"]
    error_results = [item for item in results if item.status == "ERRO"]
    return "\n".join(
        [
            "# Validacao do mercado brasileiro",
            "",
            f"- Data e hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"- Total de ativos brasileiros: {len(results)}",
            f"- Funcionaram no yfinance: {len(ok_results)}",
            f"- Falharam no yfinance: {len(error_results)}",
            "",
            "## Tickers com erro",
            _results_table(error_results),
            "",
            "## Resultado completo",
            _results_table(results),
            "",
        ]
    )


def _generate_validation_report(results: list[TickerValidationResult]) -> str:
    ok_results = [item for item in results if item.status == "OK"]
    error_results = [item for item in results if item.status == "ERRO"]
    disabled_results = [item for item in results if item.disabled]
    active_error_results = [item for item in error_results if not item.disabled]

    return "\n".join(
        [
            "# Desbasement Agent V2 - Universe Validation",
            "",
            f"- Data e hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"- Total de tickers validados: {len(results)}",
            f"- OK: {len(ok_results)}",
            f"- ERRO: {len(error_results)}",
            f"- Desativados: {len(disabled_results)}",
            "",
            "## Tickers ignorados por ausência de dados.",
            _disabled_table(disabled_results),
            "",
            "## Tickers ativos com erro",
            _results_table(active_error_results),
            "",
            "## Resultado completo",
            _results_table(results),
            "",
            "## Observacao sobre SQ",
            (
                "SQ foi mantido em DISABLED_TICKERS porque a Block Inc. mudou o ticker de SQ para XYZ em janeiro de 2025. "
                "XYZ foi adicionado ao universo ativo como growth stock dos EUA."
            ),
            "",
        ]
    )


def _results_table(results: list[TickerValidationResult]) -> str:
    if not results:
        return "Nenhum."
    rows = ["| Ticker | Classe | Status | Linhas | Ultima data | Disabled | Motivo |", "| --- | --- | --- | ---: | --- | --- | --- |"]
    for item in results:
        rows.append(
            "| {symbol} | {asset_class} | {status} | {rows} | {last_date} | {disabled} | {reason} |".format(
                symbol=item.symbol,
                asset_class=item.asset_class,
                status=item.status,
                rows=item.rows,
                last_date=item.last_date,
                disabled="sim" if item.disabled else "nao",
                reason=item.reason,
            )
        )
    return "\n".join(rows)


def _disabled_table(results: list[TickerValidationResult]) -> str:
    if not results:
        return "Nenhum."
    rows = ["| Ticker | Classe | Status atual | Motivo |", "| --- | --- | --- | --- |"]
    for item in results:
        rows.append(f"| {item.symbol} | {item.asset_class} | {item.status} | {item.reason} |")
    return "\n".join(rows)


def _result_to_execution_dict(item: TickerValidationResult) -> dict:
    return {
        "symbol": item.symbol,
        "asset_class": item.asset_class,
        "data_quality": {
            "approved": item.status == "OK",
            "error": None if item.status == "OK" else item.reason,
        },
    }


def _last_date(df: pd.DataFrame) -> str:
    try:
        value = df.index[-1]
    except Exception:
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    return str(value)


def _join_reasons(*values: str) -> str:
    return "; ".join(value for value in values if value)
