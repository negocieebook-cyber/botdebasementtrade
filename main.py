from __future__ import annotations

import argparse
from datetime import datetime
import os
from pathlib import Path
import sys
import time

from src.config import (
    DAILY_ALERT_ENABLED,
    INDIVIDUAL_ASSETS,
    REPORTS_DIR,
    SEND_EMPTY_DAILY_ALERT,
    WEEKLY_REPORT_ENABLED,
    ensure_project_dirs,
    load_settings,
)
from src.backtest_engine import evaluate_signal_history
from src.logger_config import setup_logging
from src.market_groups import empty_group_stats, market_group_for_class
from src.report_generator import (
    generate_daily_telegram_messages,
    generate_telegram_messages,
    generate_weekly_telegram_messages,
    save_daily_report,
    save_reports,
)
from src.screener_engine import (
    analyze_single_asset,
    filter_daily_alerts,
    filter_notification_candidates,
    run_screener_with_metadata,
)
from src.signal_history import append_signal_snapshot, compare_signal_change, get_previous_signal, should_notify_with_history
from src.telegram_notifier import TelegramSendResult, send_telegram_message_detailed
from src.universe import get_asset_class, get_disabled_tickers, get_full_universe, get_test_universe
from src.universe_validator import validate_brazil, validate_universe
from src.utils import write_text


TEST_TELEGRAM_MESSAGE = "✅ Teste do Desbasement Agent: Telegram funcionando."


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Desbasement Agent V2 analytical screener.")
    parser.add_argument(
        "command",
        choices=[
            "individual",
            "screener",
            "daily-alert",
            "weekly-report",
            "backtest-summary",
            "test-telegram",
            "validate-universe",
            "validate-brazil",
            "scheduler-debug",
        ],
        help="Run individual assets, screener, daily alert, weekly report, backtest or Telegram diagnostic.",
    )
    parser.add_argument("--full", action="store_true", help="Run the complete universe.")
    parser.add_argument("--no-macro", action="store_true", help="Disable macro analysis.")
    parser.add_argument("--no-intermarket", action="store_true", help="Disable intermarket analysis.")
    parser.add_argument("--narrative", action="store_true", help="Enable narrative analysis.")
    parser.add_argument("--start-date", default=None, help="Start date for price history, e.g. 2015-01-01.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logger = setup_logging()
    started_at = time.time()
    logger.info("Inicio da execucao: %s", _command_text(args))
    settings = load_settings()
    start_date = args.start_date or settings.start_date
    use_macro = not args.no_macro
    use_intermarket = not args.no_intermarket

    ensure_project_dirs()

    if args.command == "test-telegram":
        result = _run_test_telegram(logger)
        _write_execution_report(
            args=args,
            mode="diagnostico",
            universe_type="teste",
            started_at=started_at,
            payload={},
            telegram_called=result.called,
            telegram_success=result.success,
            telegram_sent_count=1 if result.success else 0,
            telegram_api_status=result.api_status(),
        )
        return

    if args.command == "validate-universe":
        payload = validate_universe()
        _write_execution_report(args, "validate-universe", "completo", started_at, payload)
        print("Validacao do universo concluida.")
        print("Relatorio salvo em: reports/universe_validation_report.md")
        print("Tickers com erro salvos em: reports/universe_validation_errors.txt")
        logger.info(
            "Universe validation: total=%s erros=%s tempo=%.1fs",
            payload.get("planned_count", 0),
            payload.get("rejected_count", 0),
            time.time() - started_at,
        )
        return

    if args.command == "validate-brazil":
        payload = validate_brazil()
        _write_execution_report(args, "validate-brazil", "brasil", started_at, payload)
        print("Validacao do mercado brasileiro concluida.")
        print(f"Total de ativos brasileiros: {payload.get('planned_brazil_count', 0)}")
        print(f"Funcionaram: {payload.get('analyzed_brazil_count', 0)}")
        print(f"Falharam: {payload.get('brazil_error_count', 0)}")
        if payload.get("brazil_errors"):
            print("Tickers com erro:")
            for item in payload["brazil_errors"]:
                print(f"- {item.get('ticker')}: {item.get('reason')}")
        print("Relatorio salvo em: reports/brazil_validation_report.md")
        logger.info(
            "Brazil validation: total=%s erros=%s tempo=%.1fs",
            payload.get("planned_brazil_count", 0),
            payload.get("brazil_error_count", 0),
            time.time() - started_at,
        )
        return

    if args.command == "scheduler-debug":
        payload = _run_scheduler_debug(logger)
        _write_execution_report(
            args=args,
            mode="scheduler-debug",
            universe_type="teste",
            started_at=started_at,
            payload=payload,
            telegram_called=payload.get("telegram_called", False),
            telegram_success=payload.get("telegram_success", False),
            telegram_sent_count=1 if payload.get("telegram_success", False) else 0,
            telegram_api_status=payload.get("telegram_api_status", "Telegram API not called."),
        )
        return

    if args.command == "individual":
        payload = _run_individual_payload(start_date, use_macro, use_intermarket, args.narrative)
        save_reports(payload)
        append_signal_snapshot(payload["all_results"], run_type="individual")
        _print_summary(payload, telegram_count=0)
        _write_execution_report(args, "individual", "teste", started_at, payload)
        logger.info("Fim da execucao individual em %.1fs", time.time() - started_at)
        return

    if args.command == "screener":
        payload = _run_screener_payload(args, start_date, use_macro, use_intermarket, args.narrative)
        _attach_history_changes(payload)
        save_reports(payload)
        notification_results = filter_notification_candidates(payload["results"])
        telegram_status = _send_telegram_messages(generate_telegram_messages(payload, notification_results))
        _mark_notified(payload, notification_results)
        append_signal_snapshot(payload["all_results"], run_type="screener")
        _print_summary(payload, telegram_count=len(notification_results))
        _write_execution_report(
            args,
            "screener",
            _universe_type(args, force_full=False),
            started_at,
            payload,
            telegram_status.called,
            telegram_status.success,
            len(notification_results),
            telegram_status.api_status,
        )
        logger.info(
            "Screener: analisados=%s aprovados=%s notificados=%s tempo=%.1fs",
            payload["analyzed_count"],
            payload["approved_count"],
            len(notification_results),
            time.time() - started_at,
        )
        if telegram_status.success:
            print("Resumo enviado para o Telegram.")
        return

    if args.command == "daily-alert":
        payload = _run_screener_payload(args, start_date, use_macro, use_intermarket, args.narrative, force_full=True)
        _attach_history_changes(payload)
        save_reports(payload)
        raw_daily_alerts = filter_daily_alerts(payload["results"])
        daily_alerts = []
        for result in raw_daily_alerts:
            previous = get_previous_signal(result.get("symbol", ""))
            should_send, reason = should_notify_with_history(result, previous)
            if should_send:
                enriched = dict(result)
                enriched["daily_alert_reason"] = reason
                enriched["notification_reason"] = reason
                daily_alerts.append(enriched)
        _attach_group_alert_counts(payload, daily_alerts)
        save_daily_report(payload, daily_alerts)
        telegram_status = TelegramDispatchStatus()
        if DAILY_ALERT_ENABLED and (daily_alerts or SEND_EMPTY_DAILY_ALERT):
            telegram_status = _send_telegram_messages(generate_daily_telegram_messages(payload, daily_alerts, payload))
        _mark_notified(payload, daily_alerts)
        append_signal_snapshot(payload["all_results"], run_type="daily-alert")
        _print_summary(payload, telegram_count=len(daily_alerts))
        _write_execution_report(
            args,
            "daily-alert",
            "completo",
            started_at,
            payload,
            telegram_status.called,
            telegram_status.success,
            len(daily_alerts),
            telegram_status.api_status,
        )
        logger.info(
            "Daily alert: analisados=%s aprovados=%s notificados=%s telegram=%s tempo=%.1fs",
            payload["analyzed_count"],
            payload["approved_count"],
            len(daily_alerts),
            telegram_status.success,
            time.time() - started_at,
        )
        if telegram_status.success:
            print("Alerta diario enviado para o Telegram.")
        elif not daily_alerts:
            print("Nenhum ativo atingiu a regua do alerta diario; alerta vazio foi tentado." if SEND_EMPTY_DAILY_ALERT else "Telegram nao enviado.")
        return

    if args.command == "weekly-report":
        payload = _run_screener_payload(args, start_date, use_macro, use_intermarket, args.narrative, force_full=True)
        _attach_history_changes(payload)
        save_reports(payload)
        telegram_status = TelegramDispatchStatus()
        if WEEKLY_REPORT_ENABLED:
            telegram_status = _send_telegram_messages(generate_weekly_telegram_messages(payload["results"], payload))
        append_signal_snapshot(payload["all_results"], run_type="weekly-report")
        _print_summary(payload, telegram_count=0)
        _write_execution_report(
            args,
            "weekly-report",
            "completo",
            started_at,
            payload,
            telegram_status.called,
            telegram_status.success,
            0,
            telegram_status.api_status,
        )
        print(f"Relatorio semanal enviado: {'sim' if telegram_status.success else 'nao'}")
        logger.info(
            "Weekly report: analisados=%s aprovados=%s enviado=%s tempo=%.1fs",
            payload["analyzed_count"],
            payload["approved_count"],
            telegram_status.success,
            time.time() - started_at,
        )
        return

    if args.command == "backtest-summary":
        summary = evaluate_signal_history()
        payload = {"planned_count": 0, "analyzed_count": len(summary), "approved_count": 0, "rejected_count": 0, "all_results": []}
        _write_execution_report(args, "backtest-summary", "teste", started_at, payload)
        print(f"Backtest avaliado. Linhas: {len(summary)}")
        print("Relatorio salvo em: reports/backtest_summary.md")
        logger.info("Backtest summary gerado com %s linhas em %.1fs", len(summary), time.time() - started_at)
        return


class TelegramDispatchStatus:
    def __init__(self, called: bool = False, success: bool = False, api_status: str = "Telegram API not called.") -> None:
        self.called = called
        self.success = success
        self.api_status = api_status


def _send_telegram_messages(messages: list[str]) -> TelegramDispatchStatus:
    status = TelegramDispatchStatus()
    for message in messages:
        result = send_telegram_message_detailed(message)
        status.called = status.called or result.called
        status.success = status.success or result.success
        status.api_status = result.api_status()
    return status


def _run_test_telegram(logger) -> TelegramSendResult:
    settings = load_settings()
    missing = []
    if not settings.telegram_bot_token:
        missing.append("TELEGRAM_BOT_TOKEN")
    if not settings.telegram_chat_id:
        missing.append("TELEGRAM_CHAT_ID")
    if missing:
        error = "Variaveis ausentes no .env: " + ", ".join(missing)
        print(error)
        logger.error(error)
        return TelegramSendResult(called=False, success=False, error=error)

    result = send_telegram_message_detailed(TEST_TELEGRAM_MESSAGE)
    print("Status da API do Telegram:")
    print(result.api_status())
    if result.success:
        logger.info("Teste Telegram concluido com sucesso: %s", result.api_status())
    else:
        logger.error("Teste Telegram falhou: %s", result.api_status())
    return result


def _run_scheduler_debug(logger) -> dict:
    settings = load_settings()
    cwd = Path(os.getcwd())
    env_path = cwd / ".env"
    token_loaded = bool(settings.telegram_bot_token)
    chat_id_loaded = bool(settings.telegram_chat_id)
    telegram_result = send_telegram_message_detailed("Desbasement Agent - scheduler-debug")
    status_code = telegram_result.status_code if telegram_result.status_code is not None else "n/a"
    failure_response = ""
    if not telegram_result.success:
        failure_response = telegram_result.response_text or telegram_result.error

    lines = [
        "# Desbasement Agent V2 - Scheduler Debug",
        "",
        f"- Data e hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- Diretório atual os.getcwd(): {cwd}",
        f"- Caminho do Python sys.executable: {sys.executable}",
        f"- Argumentos recebidos sys.argv: {sys.argv}",
        f"- Arquivo .env existe no diretório atual: {'sim' if env_path.exists() else 'nao'}",
        f"- TELEGRAM_BOT_TOKEN carregado: {'sim (' + _mask_secret(settings.telegram_bot_token) + ')' if token_loaded else 'nao'}",
        f"- TELEGRAM_CHAT_ID carregado: {'sim' if chat_id_loaded else 'nao'}",
        f"- Pasta reports existe: {'sim' if REPORTS_DIR.exists() else 'nao'}",
        f"- Pasta logs existe: {'sim' if (Path(__file__).resolve().parent / 'logs').exists() else 'nao'}",
        f"- Tentativa de envio Telegram: {'sucesso' if telegram_result.success else 'falha'}",
        f"- status_code da API: {status_code}",
        f"- Status resumido da API: {telegram_result.api_status()}",
        f"- Resposta da API se falhar: {failure_response or 'n/a'}",
        "",
    ]
    content = "\n".join(lines)
    write_text(REPORTS_DIR / "scheduler_debug.md", content)
    print(content)
    for line in lines:
        if line:
            logger.info("scheduler-debug | %s", line)
    return {
        "planned_count": 0,
        "analyzed_count": 0,
        "approved_count": 0,
        "rejected_count": 0,
        "all_results": [],
        "telegram_called": telegram_result.called,
        "telegram_success": telegram_result.success,
        "telegram_api_status": telegram_result.api_status(),
    }


def _mask_secret(value: str | None) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}...{value[-4:]}"


def _run_individual_payload(start_date: str, use_macro: bool, use_intermarket: bool, use_narrative: bool) -> dict:
    results = [
        analyze_single_asset(
            symbol=symbol,
            asset_class=get_asset_class(symbol),
            start_date=start_date,
            use_macro=use_macro,
            use_intermarket=use_intermarket,
            use_narrative=use_narrative,
        )
        for symbol in INDIVIDUAL_ASSETS
    ]
    approved = [result for result in results if result.get("data_quality", {}).get("approved")]
    return {
        "planned_count": len(INDIVIDUAL_ASSETS),
        "analyzed_count": len(results),
        "approved_count": len(approved),
        "rejected_count": len(results) - len(approved),
        "results": approved,
        "all_results": results,
        "rejected_by_phase": {},
        "mode_note": "Rodando analise individual.",
        "start_date": start_date,
    }


def _run_screener_payload(
    args: argparse.Namespace,
    start_date: str,
    use_macro: bool,
    use_intermarket: bool,
    use_narrative: bool,
    force_full: bool = False,
) -> dict:
    use_full_universe = force_full or args.full
    universe = get_full_universe() if use_full_universe else get_test_universe()
    mode_note = "Rodando universo completo." if use_full_universe else "Rodando em modo teste: universo reduzido."
    print(mode_note)
    payload = run_screener_with_metadata(
        universe=universe,
        start_date=start_date,
        use_macro=use_macro,
        use_intermarket=use_intermarket,
        use_narrative=use_narrative,
        as_dict=True,
        mode_note=mode_note,
    )
    payload["planned_count"] = payload.get("planned_count", len(universe))
    payload["ignored_tickers"] = get_disabled_tickers()
    return payload


def _print_summary(payload: dict, telegram_count: int) -> None:
    print(f"Ativos analisados: {payload['analyzed_count']}")
    print(f"Ativos aprovados no screener: {payload['approved_count']}")
    print(f"Ativos enviados para Telegram: {telegram_count}")
    print(f"Ativos rejeitados: {payload['rejected_count']}")
    if payload.get("rejected_by_phase"):
        print(f"Fora do padrao: {payload['rejected_by_phase'].get('Fora do padrão', 0)}")
        print(f"Queda extrema, mas sem fundo: {payload['rejected_by_phase'].get('Queda extrema, mas sem fundo', 0)}")
    print("Relatorios salvos em:")
    print("- reports/ranking_report.md")
    print("- reports/full_screener_report.md")
    print("- reports/macro_report.md")
    print("- reports/brazil_report.md")
    print("- reports/execution_report.md")
    print("- reports/individual/{SYMBOL}_report.md")


def _write_execution_report(
    args: argparse.Namespace,
    mode: str,
    universe_type: str,
    started_at: float,
    payload: dict,
    telegram_called: bool = False,
    telegram_success: bool = False,
    telegram_sent_count: int = 0,
    telegram_api_status: str = "Telegram API not called.",
) -> None:
    all_results = payload.get("all_results", [])
    errors = _errors_by_ticker(all_results)
    analyzed_count = payload.get("analyzed_count", len(all_results))
    approved_count = payload.get("approved_count", 0)
    lines = [
        "# Desbasement Agent V2 - Execution Report",
        "",
        f"- Data e hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- Comando executado: python main.py {_command_text(args)}",
        f"- Modo executado: {mode}",
        f"- Universo usado: {universe_type}",
        f"- Total de ativos planejados: {payload.get('planned_count', analyzed_count)}",
        f"- Total analisado com sucesso: {analyzed_count - len(errors)}",
        f"- Total com erro: {len(errors)}",
        f"- Total aprovado no screener: {approved_count}",
        f"- Total enviado ao Telegram: {telegram_sent_count}",
        f"- Telegram foi chamado: {'sim' if telegram_called else 'nao'}",
        f"- Telegram respondeu com sucesso: {'sim' if telegram_success else 'nao'}",
        f"- Status da API do Telegram: {telegram_api_status}",
        f"- Tempo total de execucao: {time.time() - started_at:.1f}s",
        "",
        "## Mercado brasileiro",
        f"- Ativos brasileiros planejados: {payload.get('planned_brazil_count', 0)}",
        f"- Ativos brasileiros analisados com sucesso: {payload.get('analyzed_brazil_count', 0)}",
        f"- Ativos brasileiros aprovados no screener: {payload.get('approved_brazil_count', 0)}",
        f"- Ativos brasileiros com erro: {payload.get('brazil_error_count', 0)}",
        "",
        _format_brazil_errors(payload.get("brazil_errors", [])),
        "",
        "## Erros por ticker",
        _format_errors(errors),
        "",
        "## Tickers ignorados por ausência de dados.",
        _format_ignored_tickers(payload.get("ignored_tickers", {})),
        "",
    ]
    write_text(REPORTS_DIR / "execution_report.md", "\n".join(lines))


def _errors_by_ticker(results: list[dict]) -> dict[str, str]:
    errors: dict[str, str] = {}
    for result in results:
        symbol = result.get("symbol", "N/A")
        error = result.get("data_quality", {}).get("error")
        if error:
            errors[symbol] = str(error)
    return errors


def _format_errors(errors: dict[str, str]) -> str:
    if not errors:
        return "- Nenhum."
    return "\n".join(f"- {symbol}: {error}" for symbol, error in sorted(errors.items()))


def _format_brazil_errors(errors: list[dict] | dict) -> str:
    if not errors:
        return "- Nenhum erro em ativos brasileiros."
    if isinstance(errors, dict):
        return "\n".join(f"- {ticker}: {reason}" for ticker, reason in sorted(errors.items()))
    return "\n".join(
        f"- {item.get('ticker', item.get('symbol', 'N/A'))}: {item.get('reason', item.get('error', 'erro nao informado'))}"
        for item in errors
    )


def _format_ignored_tickers(ignored_tickers: dict[str, str]) -> str:
    if not ignored_tickers:
        return "- Nenhum."
    return "\n".join(f"- {symbol}: {reason}" for symbol, reason in sorted(ignored_tickers.items()))


def _command_text(args: argparse.Namespace) -> str:
    parts = [args.command]
    if getattr(args, "full", False):
        parts.append("--full")
    if getattr(args, "no_macro", False):
        parts.append("--no-macro")
    if getattr(args, "no_intermarket", False):
        parts.append("--no-intermarket")
    if getattr(args, "narrative", False):
        parts.append("--narrative")
    if getattr(args, "start_date", None):
        parts.extend(["--start-date", str(args.start_date)])
    return " ".join(parts)


def _universe_type(args: argparse.Namespace, force_full: bool) -> str:
    return "completo" if force_full or args.full else "teste"


def _mark_notified(payload: dict, notified_results: list[dict]) -> None:
    notified_by_symbol = {result.get("symbol"): result for result in notified_results}
    for result in payload.get("all_results", []):
        notified = notified_by_symbol.get(result.get("symbol"))
        if notified:
            result["was_notified"] = True
            result["notification_reason"] = notified.get("notification_reason") or notified.get("daily_alert_reason", "")
            result["alert_type"] = notified.get("alert_type", "")
        else:
            result["was_notified"] = False


def _attach_history_changes(payload: dict) -> None:
    changes = {
        "phase_up": [],
        "phase_down": [],
        "invalidated": [],
        "new": [],
    }
    for result in payload.get("all_results", []):
        previous = get_previous_signal(result.get("symbol", ""))
        comparison = compare_signal_change(result, previous)
        result["signal_change"] = comparison
        phase_change = comparison["phase_change"]
        if phase_change["direction"] == "new" and result.get("data_quality", {}).get("approved"):
            changes["new"].append(result)
        elif phase_change["direction"] == "up":
            changes["phase_up"].append(result)
        elif phase_change["direction"] == "down":
            changes["phase_down"].append(result)
        if result.get("phase") == "Tese invalidada":
            changes["invalidated"].append(result)
    payload["history_changes"] = changes


def _attach_group_alert_counts(payload: dict, alerts: list[dict]) -> None:
    groups = empty_group_stats()
    for group, values in (payload.get("groups") or {}).items():
        if group in groups:
            groups[group].update({key: int(values.get(key, 0) or 0) for key in groups[group]})
    for group in groups.values():
        group["alerts"] = 0
    for item in alerts:
        group = item.get("market_group") or market_group_for_class(item.get("asset_class", ""), item.get("symbol", ""))
        if group in groups:
            groups[group]["alerts"] += 1
    payload["groups"] = groups


if __name__ == "__main__":
    main()
