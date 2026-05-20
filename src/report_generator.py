from __future__ import annotations

from datetime import datetime

import pandas as pd

from src.config import (
    DAILY_ALERT_MIN_SCORE,
    DAILY_ALERT_PHASES,
    SEND_EMPTY_DAILY_ALERT,
    SEND_EMPTY_WEEKLY_REPORT,
    WEEKLY_REPORT_MAX_ASSETS,
    REPORTS_DIR,
    SAFETY_RULES,
)
from src.market_groups import GROUP_ORDER, empty_group_stats, market_group_for_class
from src.screener_engine import AssetAnalysis, ranking_frame
from src.utils import number, pct, slugify, write_text


def generate_ranking_report(results: list) -> str:
    metadata = _extract_metadata(results)
    rows = []
    for index, result in enumerate(_extract_report_results(results), start=1):
        rows.append(
            "| {rank} | {symbol} | {asset_class} | {phase} | {score} | {trigger} | {risk} |".format(
                rank=index,
                symbol=result.get("symbol", ""),
                asset_class=result.get("asset_class", ""),
                phase=result.get("phase", ""),
                score=result.get("score", 0),
                trigger=simplify_trigger_text(result.get("confirmation_trigger", ""), result.get("confirmation_trigger_value")),
                risk=simplify_invalidation_text(result.get("invalidation_level", ""), result.get("invalidation_level_value")),
            )
        )
    return "\n".join(
        [
            "# Ranking do Desbasement Agent",
            "",
            _timestamp(),
            "",
            "Radar quantitativo para estudo. Nao e recomendacao financeira.",
            "",
            "## Resumo",
            f"- Ativos analisados: {metadata.get('analyzed_count', len(rows))}",
            f"- Aprovados no screener: {metadata.get('approved_count', len(rows))}",
            f"- Ativos brasileiros analisados: {metadata.get('analyzed_brazil_count', 0)}",
            f"- Ativos brasileiros aprovados: {metadata.get('approved_brazil_count', 0)}",
            "",
            "## Ativos ranqueados",
            "| # | Ativo | Classe | Fase | Score | Gatilho | Risco |",
            "| ---: | --- | --- | --- | ---: | --- | --- |",
            *rows,
            "",
        ]
    )


def generate_individual_report(result: dict) -> str:
    pros = "\n".join(f"- {item}" for item in result.get("pros", [])) or "- None."
    cons = "\n".join(f"- {item}" for item in result.get("cons", [])) or "- None."
    macro = result.get("macro", {})
    intermarket = result.get("intermarket", {})
    narrative = result.get("narrative", {})
    data_quality = result.get("data_quality", {})
    return "\n".join(
        [
            f"# Relatório — {result.get('symbol', '')}",
            "",
            "## Resumo",
            f"- Ativo: {result.get('symbol', '')}",
            f"- Classe: {result.get('asset_class', '')}",
            f"- Data: {result.get('date', '')}",
            f"- Fase: {result.get('phase', '')}",
            f"- Score: {result.get('score', 0)}/100",
            f"- Classificação: {result.get('classification', '')}",
            "",
            "## Por que entrou no radar",
            result.get("why_on_radar", ""),
            "",
            "## Pontos a favor",
            pros,
            "",
            "## Pontos contra",
            cons,
            "",
            "## Macro",
            _dict_as_bullets(macro),
            "",
            "## Intermarket",
            _dict_as_bullets(intermarket),
            "",
            "## Narrativa",
            _dict_as_bullets(narrative),
            "",
            "## Gatilho de confirmação",
            result.get("confirmation_trigger", ""),
            "",
            "## Ponto de invalidação",
            result.get("invalidation_level", ""),
            "",
            "## Qualidade dos dados",
            _dict_as_bullets(data_quality),
            "",
            "## Conclusão",
            _conclusion(result),
            "",
            "## Aviso",
            "Este relatório é uma análise quantitativa e qualitativa inicial. Não é recomendação financeira, não promete retorno e deve ser usado apenas como apoio ao estudo.",
            "",
            "## Regras de segurança",
            "\n".join(f"- {rule}" for rule in SAFETY_RULES),
            "",
        ]
    )


def generate_full_screener_report(results: list) -> str:
    metadata = _extract_metadata(results)
    rows = []
    for result in _extract_report_results(results):
        rows.append(
            {
                "Ativo": result.get("symbol", ""),
                "Classe": result.get("asset_class", ""),
                "Fase": result.get("phase", ""),
                "Score": result.get("score", 0),
                "Gatilho": simplify_trigger_text(result.get("confirmation_trigger", ""), result.get("confirmation_trigger_value")),
                "Risco": simplify_invalidation_text(result.get("invalidation_level", ""), result.get("invalidation_level_value")),
                "Resumo": simplify_reason_text(result.get("why_on_radar", "")),
            }
        )
    frame = pd.DataFrame(rows)
    table = _dataframe_to_markdown(frame)
    return "\n".join(
        [
            "# Relatorio completo do screener",
            "",
            _timestamp(),
            "",
            "## Resumo",
            f"- Ativos planejados: {metadata.get('planned_count', metadata.get('analyzed_count', len(rows)))}",
            f"- Ativos analisados: {metadata.get('analyzed_count', len(rows))}",
            f"- Aprovados no screener: {metadata.get('approved_count', len(rows))}",
            f"- Ativos brasileiros analisados: {metadata.get('analyzed_brazil_count', 0)}",
            f"- Ativos brasileiros aprovados: {metadata.get('approved_brazil_count', 0)}",
            f"- Ativos brasileiros com erro: {metadata.get('brazil_error_count', 0)}",
            "",
            "## Resultado por ativo",
            table,
            "",
        ]
    )


def generate_macro_report(results: list) -> str:
    normalized_results = _extract_report_results(results)
    macro_blocks = []
    for result in normalized_results:
        macro = result.get("macro", {})
        macro_blocks.append(
            "\n".join(
                [
                    f"## {result.get('symbol', '')}",
                    _dict_as_bullets(macro),
                    "",
                ]
            )
        )
    return "\n".join(
        [
            "# Desbasement Agent V2 - Macro Report",
            "",
            _timestamp(),
            "",
            *macro_blocks,
        ]
    )


def generate_brazil_report(results: list | dict) -> str:
    metadata = _extract_metadata(results)
    normalized_results = [item for item in _extract_report_results(results) if _is_brazil_result(item)]
    approved = [item for item in normalized_results if item.get("data_quality", {}).get("approved")]
    top_items = sorted(approved, key=lambda item: item.get("score", 0), reverse=True)[:20]
    errors = [item for item in normalized_results if item.get("data_quality", {}).get("error")]
    phase_counts = _phase_counts(normalized_results)

    return "\n".join(
        [
            "# Relatorio Brasil",
            "",
            _timestamp(),
            "",
            "## Resumo",
            f"- Planejados: {metadata.get('planned_brazil_count', len(normalized_results))}",
            f"- Analisados: {metadata.get('analyzed_brazil_count', len(normalized_results) - len(errors))}",
            f"- Aprovados: {metadata.get('approved_brazil_count', len(approved))}",
            f"- Erros: {metadata.get('brazil_error_count', len(errors))}",
            "",
            "## Top Brasil",
            _brazil_items_table(top_items),
            "",
            "## Por fase",
            _counts_as_bullets(phase_counts),
            "",
            "## Erros",
            _errors_as_bullets(errors),
            "",
        ]
    )


def generate_telegram_summary(all_results: list | dict, notification_results: list | None = None) -> str:
    metadata = _extract_metadata(all_results)
    approved_results = _extract_results(all_results)
    notification_results = _coerce_results(notification_results or [])
    analysis_date = _analysis_date_from_results(approved_results)
    analyzed_count = metadata.get("analyzed_count", len(approved_results))
    approved_count = metadata.get("approved_count", len(approved_results))
    rejected_count = metadata.get("rejected_count", max(0, analyzed_count - approved_count))
    rejected_by_phase = metadata.get("rejected_by_phase", {})
    mode_note = metadata.get("mode_note", "")

    if not notification_results:
        return (
            "📊 *Desbasement Agent — Radar de Hoje*\n\n"
            f"Ativos analisados: *{analyzed_count}*\n"
            f"Ativos aprovados no screener: *{approved_count}*\n"
            "Ativos bons o suficiente para alerta: *0*\n"
            f"Ativos rejeitados: *{rejected_count}*\n"
            f"Fora do padrão: *{rejected_by_phase.get('Fora do padrão', 0)}*\n"
            f"Queda extrema, mas sem fundo: *{rejected_by_phase.get('Queda extrema, mas sem fundo', 0)}*\n"
            f"{mode_note}\n\n"
            "Nenhum ativo atingiu a régua mínima de qualidade hoje.\n\n"
            "*Critérios para alerta:*\n"
            "- Score mínimo: 65\n"
            "- Fase: Acumulação avançada, Rompimento inicial ou Tese forte\n"
            "- Pelo menos 3 confirmações técnicas\n"
            "- Sem risco técnico grave\n\n"
            + _telegram_interpretation_text()
            + "\n\n⚠️ Isso não é recomendação financeira. É apenas um filtro quantitativo para estudo."
        )

    sorted_results = sorted(
        notification_results,
        key=lambda item: item.get("score", 0),
        reverse=True,
    )

    top_results = sorted_results[:10]

    message = "📊 *Desbasement Agent — Alertas Relevantes*\n\n"
    message += f"Data da análise: {analysis_date}\n"
    message += f"Ativos analisados: *{analyzed_count}*\n"
    message += f"Ativos aprovados no screener: *{approved_count}*\n"
    message += f"Ativos notificados: *{len(notification_results)}*\n"
    message += f"Ativos rejeitados: *{rejected_count}*\n"
    if rejected_by_phase:
        message += f"Fora do padrão: *{rejected_by_phase.get('Fora do padrão', 0)}*\n"
        message += f"Queda extrema, mas sem fundo: *{rejected_by_phase.get('Queda extrema, mas sem fundo', 0)}*\n"
    if mode_note:
        message += f"{mode_note}\n"
    message += "\n"
    message += (
        "Critério usado:\n"
        "Score >= 65 + fase avançada + confirmações técnicas + sem risco técnico grave.\n\n"
    )
    message += _telegram_interpretation_text()
    message += "\n\n*ATIVOS QUE ENTRARAM NO ALERTA*\n\n"

    for index, item in enumerate(top_results, start=1):
        symbol = item.get("symbol", "N/A")
        asset_class = item.get("asset_class", "N/A")
        phase = item.get("phase", "N/A")
        score = item.get("score", 0)
        trigger = item.get("confirmation_trigger", "N/A")
        risk = item.get("invalidation_level", "N/A")
        why = item.get("notification_reason", item.get("why_on_radar", "N/A"))
        watch = item.get("what_to_watch_now", "N/A")

        if _is_brazil_result(item):
            message += "🇧🇷 Mercado brasileiro\n"
        message += f"*{index}. {symbol}* — {asset_class}\n"
        message += f"Fase: {phase}\n"
        message += f"Score: {score}/100\n"
        message += f"Motivo do alerta: {why}\n"
        message += f"Gatilho: {trigger}\n"
        message += f"Invalidação: {risk}\n"
        message += f"O que observar agora: {watch}\n\n"

    message += (
        "⚠️ *Aviso:*\n"
        "Este alerta não é recomendação financeira. Ele apenas mostra ativos que entraram no radar quantitativo. "
        "Aguardar confirmação e respeitar o ponto de invalidação. A tese pode falhar."
    )

    return message


def generate_telegram_messages(all_results: list | dict, notification_results: list | None = None) -> list[str]:
    message = generate_telegram_summary(all_results, notification_results)
    metadata = _extract_metadata(all_results)
    if len(message) <= 3900:
        return [message]
    compact_message = _generate_compact_telegram_summary(all_results, notification_results)
    stats = (
        "📊 *Estatísticas do Screener*\n\n"
        f"Ativos analisados: *{metadata.get('analyzed_count', 0)}*\n"
        f"Ativos aprovados: *{metadata.get('approved_count', 0)}*\n"
        f"Ativos rejeitados: *{metadata.get('rejected_count', 0)}*\n"
        f"Fora do padrão: *{metadata.get('rejected_by_phase', {}).get('Fora do padrão', 0)}*\n"
        "Queda extrema, mas sem fundo: "
        f"*{metadata.get('rejected_by_phase', {}).get('Queda extrema, mas sem fundo', 0)}*"
    )
    path_message = "Relatório completo salvo em: reports/full_screener_report.md"
    return [compact_message, stats, path_message]


def generate_daily_telegram_alert(all_results: list | dict, daily_alerts: list, metadata: dict) -> str:
    approved_results = _extract_results(all_results)
    analyzed_count = metadata.get("analyzed_count", len(approved_results))
    approved_count = metadata.get("approved_count", len(approved_results))
    analysis_date = _analysis_date_from_results(approved_results)
    alert_count = len(daily_alerts)
    groups = _groups_with_alerts(metadata, daily_alerts)

    if not daily_alerts:
        if not SEND_EMPTY_DAILY_ALERT:
            return ""
        return _generate_empty_daily_alert_message(analyzed_count, approved_count, analysis_date, groups)

    grouped_alerts = _group_items(daily_alerts)
    lines = [
        "📊 DESBASEMENT AGENT — ALERTA DIÁRIO",
        "",
        f"Data: {analysis_date}",
        "Mercado: Global + EUA + Brasil + Cripto",
        "",
        "Resumo:",
        f"- Ativos analisados: {analyzed_count}",
        f"- Aprovados no screener: {approved_count}",
        f"- Alertas relevantes: {alert_count}",
        "",
        *_daily_group_summary_lines(groups),
    ]
    for group, title in [
        ("us_equities", "🇺🇸 ALERTAS EUA"),
        ("crypto", "₿ ALERTAS CRIPTO"),
        ("brazil", "🇧🇷 ALERTAS BRASIL"),
        ("bonds_commodities_others", "🏦 ALERTAS BONDS / COMMODITIES / OUTROS"),
    ]:
        lines.extend(["", title])
        group_alerts = sorted(grouped_alerts.get(group, []), key=lambda item: item.get("score", 0), reverse=True)[:5]
        if not group_alerts:
            lines.append("Nenhum alerta relevante neste grupo hoje.")
            continue
        for index, item in enumerate(group_alerts, start=1):
            lines.append(_format_daily_alert_item(item, index))

    lines.extend(
        [
            "",
            "📄 Relatório completo:",
            "reports/full_screener_report.md",
            "",
            "⚠️ Não é recomendação financeira. É apenas um radar quantitativo para estudo.",
        ]
    )
    return "\n".join(lines)


def generate_daily_telegram_messages(all_results: list | dict, daily_alerts: list, metadata: dict) -> list[str]:
    message = generate_daily_telegram_alert(all_results, daily_alerts, metadata)
    if not message:
        return []
    return split_telegram_message(message)


def generate_weekly_telegram_report(results: list, metadata: dict) -> str:
    normalized_results = _coerce_results(results)
    if not normalized_results and not SEND_EMPTY_WEEKLY_REPORT:
        return ""

    sorted_results = sorted(normalized_results, key=lambda item: item.get("score", 0), reverse=True)
    grouped_results = _group_items(sorted_results)
    groups = _groups_from_metadata(metadata)
    phase_counts = _phase_counts(normalized_results)
    changes = metadata.get("history_changes", {})
    lines = [
        "📅 DESBASEMENT AGENT — RELATÓRIO SEMANAL",
        "",
        "Resumo da semana",
        f"- Ativos analisados: {metadata.get('analyzed_count', len(normalized_results))}",
        f"- Aprovados no screener: {metadata.get('approved_count', len(normalized_results))}",
        f"- EUA analisados: {groups['us_equities']['analyzed']}",
        f"- Cripto analisada: {groups['crypto']['analyzed']}",
        f"- Mercado brasileiro analisado: {groups['brazil']['analyzed']}",
        f"- Outros mercados analisados: {groups['bonds_commodities_others']['analyzed']}",
        "",
        "Distribuição por fase:",
    ]
    for phase in [
        "Possível estabilização",
        "Acumulação inicial",
        "Acumulação avançada",
        "Rompimento inicial",
        "Tese forte",
    ]:
        lines.append(f"- {phase}: {phase_counts.get(phase, 0)}")

    lines.extend(
        [
            "",
            "Resumo por mercado:",
            f"- EUA: {groups['us_equities']['approved']} aprovados",
            f"- Cripto: {groups['crypto']['approved']} aprovados",
            f"- Brasil: {groups['brazil']['approved']} aprovados",
            f"- Bonds/commodities/outros: {groups['bonds_commodities_others']['approved']} aprovados",
            "",
            "Mudanças da semana:",
            f"- Ativos que subiram de fase: {len(changes.get('phase_up', []))}",
            f"- Ativos que caíram de fase: {len(changes.get('phase_down', []))}",
            f"- Ativos invalidados: {len(changes.get('invalidated', []))}",
            f"- Novos ativos no radar: {len(changes.get('new', []))}",
            "",
            "🇧🇷 BRASIL",
            f"- Ativos brasileiros analisados: {groups['brazil']['analyzed']}",
            f"- Ativos brasileiros aprovados: {groups['brazil']['approved']}",
            f"- Ativos brasileiros com erro: {groups['brazil']['errors']}",
        ]
    )
    if groups["brazil"]["approved"] == 0:
        lines.append("Nenhum ativo brasileiro entrou no radar relevante nesta semana.")
    if metadata.get("brazil_errors"):
        lines.append("Tickers brasileiros com falha de dados: " + _brazil_error_symbols(metadata.get("brazil_errors", [])))

    lines.extend(["", "🇺🇸 TOP EUA"])
    lines.extend(_format_weekly_top_items(grouped_results.get("us_equities", [])[:5], empty_text="Sem ativos dos EUA relevantes nesta semana."))

    lines.extend(["", "₿ TOP CRIPTO"])
    lines.extend(_format_weekly_top_items(grouped_results.get("crypto", [])[:5], empty_text="Sem cripto relevante nesta semana."))

    lines.extend(["", "🇧🇷 TOP BRASIL"])
    lines.extend(_format_weekly_top_items(grouped_results.get("brazil", [])[:5], empty_text="Sem ativos brasileiros relevantes nesta semana."))

    lines.extend(["", "🏦 TOP BONDS / COMMODITIES / OUTROS"])
    lines.extend(_format_weekly_top_items(grouped_results.get("bonds_commodities_others", [])[:5], empty_text="Sem ativos relevantes neste grupo nesta semana."))

    important_alerts = _weekly_important_alerts(changes)
    if important_alerts:
        lines.extend(["", "⚠️ ALERTAS IMPORTANTES", *important_alerts])

    if len(sorted_results) > 10:
        lines.extend(["", "📄 Relatório completo:", "reports/full_screener_report.md"])

    lines.extend(
        [
            "",
            "⚠️ AVISO FINAL",
            "",
            "Este relatório não é recomendação financeira.",
            "Ele serve como radar quantitativo para estudo e acompanhamento.",
            "",
            "Como usar:",
            "• Score alto não significa compra automática.",
            "• Gatilho é o nível que pode fortalecer a tese.",
            "• Risco é o nível que enfraquece ou invalida a tese.",
            "• Ativos em \"Possível estabilização\" ainda estão em fase inicial.",
        ]
    )
    return "\n".join(lines)


def generate_weekly_telegram_messages(results: list, metadata: dict) -> list[str]:
    message = generate_weekly_telegram_report(results, metadata)
    if not message:
        return []
    return split_telegram_message(message)


def generate_daily_markdown_report(all_results: list | dict, daily_alerts: list) -> str:
    metadata = _extract_metadata(all_results)
    groups = _groups_with_alerts(metadata, daily_alerts)
    grouped_alerts = _group_items(daily_alerts)
    return "\n".join(
        [
            "# Relatório Diário",
            "",
            "## Resumo",
            f"- Ativos analisados: {metadata.get('analyzed_count', 0)}",
            f"- Aprovados no screener: {metadata.get('approved_count', 0)}",
            f"- Alertas relevantes: {len(daily_alerts)}",
            "",
            "## EUA",
            _daily_markdown_group_summary(groups["us_equities"]),
            _daily_alerts_table(grouped_alerts.get("us_equities", [])),
            "",
            "## Cripto",
            _daily_markdown_group_summary(groups["crypto"]),
            _daily_alerts_table(grouped_alerts.get("crypto", [])),
            "",
            "## Brasil",
            _daily_markdown_group_summary(groups["brazil"]),
            _daily_alerts_table(grouped_alerts.get("brazil", [])),
            "",
            "## Bonds, commodities e outros",
            _daily_markdown_group_summary(groups["bonds_commodities_others"]),
            _daily_alerts_table(grouped_alerts.get("bonds_commodities_others", [])),
            "",
            "## Observação",
            "Não é recomendação financeira.",
            "",
        ]
    )


def save_daily_report(all_results: list | dict, daily_alerts: list) -> None:
    write_text(REPORTS_DIR / "daily_report.md", generate_daily_markdown_report(all_results, daily_alerts))


def split_telegram_message(message: str, max_length: int = 3500) -> list[str]:
    if len(message) <= max_length:
        return [message]

    chunks: list[str] = []
    current_lines: list[str] = []
    current_length = 0

    for line in message.splitlines():
        line_length = len(line) + 1
        if current_lines and current_length + line_length > max_length:
            chunks.append("\n".join(current_lines))
            current_lines = []
            current_length = 0

        if line_length > max_length:
            while line:
                chunks.append(line[:max_length])
                line = line[max_length:]
            continue

        current_lines.append(line)
        current_length += line_length

    if current_lines:
        chunks.append("\n".join(current_lines))

    total = len(chunks)
    return [f"Parte {index}/{total}\n\n{chunk}" for index, chunk in enumerate(chunks, start=1)]


def save_reports(results: list | dict) -> None:
    normalized_results = _extract_report_results(results)
    write_text(REPORTS_DIR / "ranking_report.md", generate_ranking_report(results))
    write_text(REPORTS_DIR / "full_screener_report.md", generate_full_screener_report(results))
    write_text(REPORTS_DIR / "macro_report.md", generate_macro_report(normalized_results))
    write_text(REPORTS_DIR / "brazil_report.md", generate_brazil_report(results))
    for result in normalized_results:
        symbol = result.get("symbol", "unknown")
        write_text(REPORTS_DIR / "individual" / f"{slugify(symbol)}_report.md", generate_individual_report(result))


class ReportGenerator:
    def generate_all(self, analyses: list[AssetAnalysis], top_n: int) -> None:
        self.generate_ranking_report(analyses, top_n)
        self.generate_full_screener_report(analyses)
        self.generate_macro_report(analyses)
        for analysis in analyses:
            self.generate_individual_report(analysis)

    def generate_ranking_report(self, analyses: list[AssetAnalysis], top_n: int) -> None:
        rows = []
        for idx, item in enumerate([a for a in analyses if a.score][:top_n], start=1):
            rows.append(
                "| {rank} | {symbol} | {klass} | {phase} | {score:.1f} | {classification} | {trigger} | {risk} |".format(
                    rank=idx,
                    symbol=item.asset.symbol,
                    klass=item.asset.asset_class,
                    phase=item.thesis_phase,
                    score=item.score.total_score,
                    classification=item.score.classification,
                    trigger=item.confirmation_point,
                    risk=item.score.risk,
                )
            )

        content = "\n".join(
            [
                "# Desbasement Agent V2 - Ranking",
                "",
                _timestamp(),
                "",
                "This report is analytical only. It does not recommend buying or selling assets.",
                "",
                "| Posição | Ativo | Classe | Fase da tese | Score | Classificação | Gatilho | Risco |",
                "| ---: | --- | --- | --- | ---: | --- | --- | --- |",
                *rows,
                "",
            ]
        )
        write_text(REPORTS_DIR / "ranking_report.md", content)

    def generate_full_screener_report(self, analyses: list[AssetAnalysis]) -> None:
        frame = ranking_frame(analyses)
        content = "\n".join(
            [
                "# Desbasement Agent V2 - Full Screener",
                "",
                _timestamp(),
                "",
                "The screener ranks relevant/liquid proxies by thesis maturity, not by how much they fell.",
                "",
                _dataframe_to_markdown(frame),
                "",
            ]
        )
        write_text(REPORTS_DIR / "full_screener_report.md", content)

    def generate_macro_report(self, analyses: list[AssetAnalysis]) -> None:
        macro = analyses[0].macro if analyses else None
        if macro is None:
            content = "# Macro Report\n\nNo analyses available.\n"
        else:
            notes = "\n".join(f"- {note}" for note in macro.notes)
            content = "\n".join(
                [
                    "# Desbasement Agent V2 - Macro Report",
                    "",
                    _timestamp(),
                    "",
                    f"- Regime: {macro.regime}",
                    f"- Score: {macro.score:.1f}/100",
                    "",
                    "## Notes",
                    notes,
                    "",
                ]
            )
        write_text(REPORTS_DIR / "macro_report.md", content)

    def generate_individual_report(self, analysis: AssetAnalysis) -> None:
        path = REPORTS_DIR / "individual" / f"{slugify(analysis.asset.symbol)}_report.md"
        if analysis.error or analysis.score is None or analysis.technical is None:
            content = "\n".join(
                [
                    f"# {analysis.asset.symbol} - {analysis.asset.name}",
                    "",
                    "Analysis unavailable.",
                    "",
                    f"Error: {analysis.error or 'unknown'}",
                    "",
                ]
            )
            write_text(path, content)
            return

        tech = analysis.technical
        score = analysis.score
        phase_rows = [
            f"| {phase.name} | {'yes' if phase.passed else 'no'} | {phase.score:.1f} | {phase.detail} |"
            for phase in score.phases
        ]
        notes = "\n".join(f"- {note}" for note in analysis.intermarket.notes + analysis.narrative.notes)
        pros = "\n".join(f"- {item}" for item in analysis.pros or [])
        cons = "\n".join(f"- {item}" for item in analysis.cons or [])
        content = "\n".join(
            [
                f"# {analysis.asset.symbol} - {analysis.asset.name}",
                "",
                _timestamp(),
                "",
                "Analytical classification only. No buy/sell recommendation is generated.",
                "",
                "## Summary",
                f"- Asset class: {analysis.asset.asset_class}",
                f"- Score: {score.total_score:.1f}/100",
                f"- Classification: {score.classification}",
                f"- Approved by screener: {'yes' if analysis.approved else 'no'}",
                f"- Risk: {score.risk}",
                f"- Last close: {number(tech.last_close)}",
                f"- Confirmation point: {analysis.confirmation_point}",
                f"- Invalidation point: {analysis.invalidation_point}",
                "",
                "## Points In Favor",
                pros or "- None.",
                "",
                "## Points Against",
                cons or "- None.",
                "",
                "## Technical State",
                f"- All-time-high drawdown: {pct(tech.drawdown_ath_pct)}",
                f"- 52w drawdown: {pct(tech.drawdown_52w_pct)}",
                f"- 1M return: {pct(tech.return_1m_pct)}",
                f"- 3M return: {pct(tech.return_3m_pct)}",
                f"- 6M return: {pct(tech.return_6m_pct)}",
                f"- 12M return: {pct(tech.return_12m_pct)}",
                f"- RSI14: {number(tech.rsi_14)}",
                f"- MACD: {number(tech.macd)}",
                f"- MACD signal: {number(tech.macd_signal)}",
                f"- ATR14 percent: {pct(tech.atr_14_pct)}",
                f"- ATR compression ratio: {number(tech.atr_compression_ratio)}",
                f"- 30D volatility: {pct(tech.volatility_30d_pct)}",
                f"- 90D volatility: {pct(tech.volatility_90d_pct)}",
                f"- 30D average volume: {number(tech.avg_volume_30d)}",
                f"- 30D volume ratio: {number(tech.volume_ratio_30d)}",
                f"- 90d support: {number(tech.support_90d)}",
                f"- Support distance: {pct(tech.support_distance_pct)}",
                f"- SMA20: {number(tech.sma_20)}",
                f"- SMA50: {number(tech.sma_50)}",
                f"- SMA100: {number(tech.sma_100)}",
                f"- SMA200: {number(tech.sma_200)}",
                f"- Rolling high 60D: {number(tech.rolling_high_60d)}",
                f"- Rolling low 60D: {number(tech.rolling_low_60d)}",
                f"- Rolling high 120D: {number(tech.rolling_high_120d)}",
                f"- Rolling low 120D: {number(tech.rolling_low_120d)}",
                f"- Range position 60D: {pct(tech.range_position_60d)}",
                f"- Range position 120D: {pct(tech.range_position_120d)}",
                "",
                "## Thesis Phases",
                "| Phase | Passed | Score | Detail |",
                "| --- | --- | ---: | --- |",
                *phase_rows,
                "",
                "## Context Notes",
                notes,
                "",
            ]
        )
        write_text(path, content)


def _timestamp() -> str:
    return f"Generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} local time."


def _coerce_results(results: list) -> list[dict]:
    normalized = []
    for result in results:
        if isinstance(result, dict):
            normalized.append(result)
        elif hasattr(result, "to_dict"):
            normalized.append(result.to_dict())
    return normalized


def _extract_results(results: list | dict) -> list[dict]:
    if isinstance(results, dict) and "results" in results:
        return _coerce_results(results.get("results", []))
    return _coerce_results(results)


def _extract_report_results(results: list | dict) -> list[dict]:
    if isinstance(results, dict) and "all_results" in results:
        return _coerce_results(results.get("all_results", []))
    return _extract_results(results)


def _extract_metadata(results: list | dict) -> dict:
    if isinstance(results, dict):
        return {
            "planned_count": results.get("planned_count", 0),
            "analyzed_count": results.get("analyzed_count", 0),
            "approved_count": results.get("approved_count", 0),
            "rejected_count": results.get("rejected_count", 0),
            "planned_brazil_count": results.get("planned_brazil_count", 0),
            "analyzed_brazil_count": results.get("analyzed_brazil_count", 0),
            "approved_brazil_count": results.get("approved_brazil_count", 0),
            "brazil_error_count": results.get("brazil_error_count", 0),
            "brazil_errors": results.get("brazil_errors", []),
            "groups": results.get("groups", empty_group_stats()),
            "rejected_by_phase": results.get("rejected_by_phase", {}),
            "mode_note": results.get("mode_note", ""),
            "start_date": results.get("start_date", ""),
            "history_changes": results.get("history_changes", {}),
        }
    normalized = _coerce_results(results)
    return {
        "planned_count": len(normalized),
        "analyzed_count": len(normalized),
        "approved_count": len(normalized),
        "rejected_count": 0,
        "planned_brazil_count": 0,
        "analyzed_brazil_count": 0,
        "approved_brazil_count": 0,
        "brazil_error_count": 0,
        "brazil_errors": [],
        "groups": empty_group_stats(),
        "rejected_by_phase": {},
        "mode_note": "",
        "start_date": "",
        "history_changes": {},
    }


def _phase_counts(results: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for result in results:
        phase = result.get("phase", "N/A")
        counts[phase] = counts.get(phase, 0) + 1
    return counts


def _class_counts(results: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for result in results:
        asset_class = result.get("asset_class", "N/A")
        counts[asset_class] = counts.get(asset_class, 0) + 1
    return counts


def clean_label_text(text: str, labels: list[str]) -> str:
    cleaned = str(text or "").strip()
    changed = True
    while changed:
        changed = False
        for label in labels:
            if cleaned.lower().startswith(label.lower()):
                cleaned = cleaned[len(label):].strip()
                changed = True
    return cleaned


def simplify_trigger_text(text: str | None, value: float | int | None = None) -> str:
    if not _is_valid_level(value):
        value = None
    text = str(text or "").strip()
    if not text:
        return "aguardar confirmacao tecnica."
    text = clean_label_text(text, ["Gatilho:", "Confirmacao:", "Confirmação:"])
    value = _first_number(text) if value is None else _format_level(value)
    if value and not _is_valid_level_text(value):
        return "aguardar confirmacao tecnica."
    if value:
        return f"fechamento acima de {value} com volume forte."
    return _short_sentence(text)


def simplify_invalidation_text(text: str | None, value: float | int | None = None) -> str:
    invalid_message = "nível de invalidação não definido com segurança."
    if not _is_valid_level(value):
        value = None
    text = str(text or "").strip()
    if not text:
        return invalid_message
    text = clean_label_text(text, ["Risco:", "Invalidação:", "Invalidacao:"])
    value = _first_number(text) if value is None else _format_level(value)
    if not _is_valid_level_text(value):
        return invalid_message
    if value:
        return f"perde força abaixo de {value}."
    return _short_sentence(text)


def simplify_reason_text(text: str | None) -> str:
    text = str(text or "").strip()
    if not text:
        return "Ativo em observacao pelo modelo quantitativo."
    replacements = {
        "Entrou no radar como": "Entrou no radar em",
        "porque combina": "por combinar",
        "sinais técnicos como suporte, médias, RSI, MACD ou compressão de volatilidade": "sinais tecnicos de melhora",
        "Rejeitado nesta leitura:": "Fora do radar nesta leitura:",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return _short_sentence(text)


def _format_daily_alert_item(item: dict, index: int) -> str:
    trigger = simplify_trigger_text(item.get("confirmation_trigger", ""), item.get("confirmation_trigger_value"))
    risk = simplify_invalidation_text(item.get("invalidation_level", ""), item.get("invalidation_level_value"))
    return "\n".join(
        [
            "--------------------------------",
            f"{index}) {item.get('symbol', 'N/A')} | {item.get('asset_class', 'N/A')}",
            f"🔎 Fase: {item.get('phase', 'N/A')}",
            f"📊 Score: {item.get('score', 0)}/100",
            f"🧠 Leitura: {simplify_reason_text(item.get('daily_alert_reason') or item.get('why_on_radar', ''))}",
            f"🎯 Gatilho: {trigger}",
            f"🛑 Risco: {risk}",
            "--------------------------------",
            "",
        ]
    )


def _compact_symbol_list(items: list[dict], limit: int = 10) -> str:
    if not items:
        return "- Nenhum.\n"
    lines = []
    for item in items[:limit]:
        lines.append(f"- {item.get('symbol', 'N/A')} | {item.get('phase', 'N/A')} | {item.get('score', 0)}/100")
    if len(items) > limit:
        lines.append(f"- ... e mais {len(items) - limit}.")
    return "\n".join(lines) + "\n"


def _group_for_item(item: dict) -> str:
    return item.get("market_group") or market_group_for_class(item.get("asset_class", ""), item.get("symbol", ""))


def _group_items(items: list[dict]) -> dict[str, list[dict]]:
    grouped = {group: [] for group in GROUP_ORDER}
    for item in _coerce_results(items):
        grouped.setdefault(_group_for_item(item), []).append(item)
    return grouped


def _groups_from_metadata(metadata: dict) -> dict[str, dict[str, int]]:
    groups = empty_group_stats()
    for group, values in (metadata.get("groups") or {}).items():
        if group not in groups:
            continue
        groups[group].update({key: int(values.get(key, 0) or 0) for key in groups[group]})
    return groups


def _groups_with_alerts(metadata: dict, alerts: list[dict]) -> dict[str, dict[str, int]]:
    groups = _groups_from_metadata(metadata)
    for group in groups.values():
        group["alerts"] = 0
    for item in alerts:
        group = _group_for_item(item)
        if group in groups:
            groups[group]["alerts"] += 1
    return groups


def _daily_group_summary_lines(groups: dict[str, dict[str, int]], compact: bool = False) -> list[str]:
    labels = [
        ("🇺🇸 EUA", "Ações/ETFs analisados", "Ações/ETFs aprovados", "Alertas relevantes EUA", "Analisados", "Aprovados", "Alertas"),
        ("₿ CRIPTO", "Criptos analisadas", "Criptos aprovadas", "Alertas relevantes cripto", "Analisados", "Aprovados", "Alertas"),
        ("🇧🇷 BRASIL", "Ativos brasileiros analisados", "Ativos brasileiros aprovados", "Alertas relevantes Brasil", "Analisados", "Aprovados", "Alertas"),
        ("🏦 BONDS / COMMODITIES / OUTROS", "Ativos analisados", "Ativos aprovados", "Alertas relevantes", "Analisados", "Aprovados", "Alertas"),
    ]
    keys = ["us_equities", "crypto", "brazil", "bonds_commodities_others"]
    lines: list[str] = []
    for key, label_set in zip(keys, labels):
        title, analyzed_label, approved_label, alerts_label, compact_analyzed, compact_approved, compact_alerts = label_set
        stats = groups.get(key, {})
        lines.extend(
            [
                title if not compact or key != "bonds_commodities_others" else "🏦 OUTROS",
                f"- {(compact_analyzed if compact else analyzed_label)}: {stats.get('analyzed', 0)}",
                f"- {(compact_approved if compact else approved_label)}: {stats.get('approved', 0)}",
                f"- {(compact_alerts if compact else alerts_label)}: {stats.get('alerts', 0)}",
                "",
            ]
        )
    return lines


def _daily_markdown_group_summary(stats: dict[str, int]) -> str:
    return "\n".join(
        [
            f"- Planejados: {stats.get('planned', 0)}",
            f"- Analisados: {stats.get('analyzed', 0)}",
            f"- Aprovados: {stats.get('approved', 0)}",
            f"- Alertas: {stats.get('alerts', 0)}",
            f"- Erros: {stats.get('errors', 0)}",
            "",
        ]
    )


def _daily_alerts_table(items: list[dict]) -> str:
    if not items:
        return "Nenhum alerta relevante neste grupo hoje."
    rows = ["| Ativo | Classe | Fase | Score | Gatilho | Risco |", "| --- | --- | --- | ---: | --- | --- |"]
    for item in sorted(items, key=lambda value: value.get("score", 0), reverse=True)[:5]:
        rows.append(
            "| {symbol} | {asset_class} | {phase} | {score} | {trigger} | {risk} |".format(
                symbol=item.get("symbol", ""),
                asset_class=item.get("asset_class", ""),
                phase=item.get("phase", ""),
                score=item.get("score", 0),
                trigger=simplify_trigger_text(item.get("confirmation_trigger", ""), item.get("confirmation_trigger_value")),
                risk=simplify_invalidation_text(item.get("invalidation_level", ""), item.get("invalidation_level_value")),
            )
        )
    return "\n".join(rows)


def _format_weekly_top_items(items: list[dict], empty_text: str) -> list[str]:
    if not items:
        return [empty_text]
    lines: list[str] = []
    for index, item in enumerate(items, start=1):
        trigger = simplify_trigger_text(item.get("confirmation_trigger", ""), item.get("confirmation_trigger_value"))
        risk = simplify_invalidation_text(item.get("invalidation_level", ""), item.get("invalidation_level_value"))
        lines.extend(
            [
                "--------------------------------",
                f"{index}) {item.get('symbol', 'N/A')} | {item.get('asset_class', 'N/A')}",
                f"🔎 Fase: {item.get('phase', 'N/A')}",
                f"📊 Score: {item.get('score', 0)}/100",
                f"🧠 Leitura: {simplify_reason_text(item.get('why_on_radar', ''))}",
                f"🎯 Gatilho: {trigger}",
                f"🛑 Risco: {risk}",
                "--------------------------------",
                "",
            ]
        )
    return lines


def _weekly_important_alerts(changes: dict) -> list[str]:
    lines: list[str] = []
    for item in changes.get("new", [])[:5]:
        lines.append(f"- {item.get('symbol', 'N/A')}: novo ativo no radar")
    for item in changes.get("invalidated", [])[:5]:
        lines.append(f"- {item.get('symbol', 'N/A')}: foi invalidado")
    for item in changes.get("phase_up", [])[:5]:
        previous = item.get("signal_change", {}).get("phase_change", {}).get("previous_phase", "")
        current = item.get("phase", "N/A")
        if current == "Tese forte":
            lines.append(f"- {item.get('symbol', 'N/A')}: virou Tese forte")
        elif previous:
            lines.append(f"- {item.get('symbol', 'N/A')}: subiu de {previous} para {current}")
        else:
            lines.append(f"- {item.get('symbol', 'N/A')}: subiu para {current}")
    return lines[:12]


def _brazil_error_symbols(errors: list[dict] | dict) -> str:
    if isinstance(errors, dict):
        symbols = list(errors.keys())
    else:
        symbols = [item.get("ticker") or item.get("symbol") for item in errors]
    return ", ".join(symbol for symbol in symbols if symbol) or "nenhum"


def _first_number(text: str) -> str:
    parts = []
    current = []
    for char in text:
        if char.isdigit() or char in ".,":
            current.append(char)
        elif current:
            parts.append("".join(current))
            current = []
    if current:
        parts.append("".join(current))
    for part in parts:
        cleaned = part.strip(".,")
        if cleaned and any(char.isdigit() for char in cleaned):
            return cleaned.replace(".", ",")
    return ""


def _is_valid_level(value: float | int | str | None) -> bool:
    if value is None:
        return False
    try:
        numeric = float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return False
    return numeric == numeric and numeric > 0


def _is_valid_level_text(value: str) -> bool:
    return _is_valid_level(value)


def _format_level(value: float | int | str) -> str:
    numeric = float(str(value).replace(",", "."))
    return f"{numeric:.2f}".replace(".", ",")


def _short_sentence(text: str, prefix: str = "") -> str:
    normalized = " ".join(str(text).split())
    if len(normalized) > 140:
        normalized = normalized[:137].rstrip() + "..."
    return prefix + normalized


def _is_brazil_result(item: dict) -> bool:
    return str(item.get("asset_class", "")).startswith("brazil_") or str(item.get("symbol", "")).upper().endswith(".SA")


def _generate_empty_daily_alert_message(
    analyzed_count: int,
    approved_count: int,
    analysis_date: str,
    groups: dict[str, dict[str, int]],
) -> str:
    return "\n".join(
        [
            "📊 DESBASEMENT AGENT — ALERTA DIÁRIO",
            "",
            f"Data: {analysis_date}",
            "",
            "Resumo:",
            f"- Ativos analisados: {analyzed_count}",
            f"- Aprovados no screener: {approved_count}",
            "- Alertas relevantes: 0",
            "",
            *_daily_group_summary_lines(groups, compact=True),
            "",
            "✅ Nenhum ativo atingiu a régua mínima de qualidade hoje.",
            "",
            "Critérios do alerta diário:",
            f"• Score mínimo: {DAILY_ALERT_MIN_SCORE}",
            "• Fase: Rompimento inicial ou Tese forte",
            "• Confirmação técnica",
            "• Sem risco técnico grave",
            "• Dados com confiança aceitável",
            "",
            "⚠️ Não é recomendação financeira. É apenas um radar quantitativo para estudo.",
        ]
    )


def _brazil_items_table(items: list[dict]) -> str:
    if not items:
        return "Nenhum."
    rows = ["| Ativo | Classe | Fase | Score | Gatilho | Risco |", "| --- | --- | --- | ---: | --- | --- |"]
    for item in items:
        rows.append(
            "| {symbol} | {asset_class} | {phase} | {score} | {trigger} | {risk} |".format(
                symbol=item.get("symbol", ""),
                asset_class=item.get("asset_class", ""),
                phase=item.get("phase", ""),
                score=item.get("score", 0),
                trigger=simplify_trigger_text(item.get("confirmation_trigger", ""), item.get("confirmation_trigger_value")),
                risk=simplify_invalidation_text(item.get("invalidation_level", ""), item.get("invalidation_level_value")),
            )
        )
    return "\n".join(rows)


def _counts_as_bullets(counts: dict[str, int]) -> str:
    if not counts:
        return "- Nenhum ativo brasileiro analisado."
    return "\n".join(f"- {key}: {value}" for key, value in sorted(counts.items()))


def _errors_as_bullets(items: list[dict]) -> str:
    if not items:
        return "- Nenhum erro em tickers brasileiros."
    return "\n".join(
        f"- {item.get('symbol', 'N/A')}: {item.get('data_quality', {}).get('error')}" for item in items
    )


def _analysis_date_from_results(results: list[dict]) -> str:
    for result in results:
        if result.get("date"):
            return str(result["date"])
    return datetime.now().strftime("%Y-%m-%d")


def _telegram_scales_text() -> str:
    return (
        "*COMO LER AS ESCALAS*\n\n"
        "*Score:*\n"
        "- 0–30: Sem tese\n"
        "- 31–50: Em observação\n"
        "- 51–70: Tese inicial\n"
        "- 71–85: Tese forte\n"
        "- 86–100: Tese muito forte, exige validação\n\n"
        "*Fases:*\n"
        "- Possível estabilização: o ativo caiu bastante, mas parou de fazer mínimas agressivas.\n"
        "- Acumulação inicial: o preço começou a lateralizar e defender suporte.\n"
        "- Acumulação avançada: já existe melhora de estrutura, RSI e médias.\n"
        "- Rompimento inicial: o ativo está tentando sair da região de acumulação.\n"
        "- Tese forte: tem queda relevante, estrutura, confirmação técnica e score acima de 70.\n"
        "- Tese invalidada: perdeu suporte importante."
    )


def _telegram_interpretation_text() -> str:
    return (
        "*Como interpretar:*\n"
        "- Score alto não significa compra automática.\n"
        "- Fase avançada significa que a tese tem mais confirmação técnica.\n"
        "- Gatilho é o nível que pode fortalecer a tese.\n"
        "- Invalidação é o nível que enfraquece ou derruba a tese.\n"
        "- Se não houver ativos notificados, significa que o mercado não entregou setups com qualidade suficiente hoje."
    )


def _score_reading(score: float, phase: str) -> str:
    if score <= 30:
        bucket = "sem tese"
    elif score <= 50:
        bucket = "em observação"
    elif score <= 70:
        bucket = "tese inicial"
    elif score <= 85:
        bucket = "tese forte"
    else:
        bucket = "tese muito forte, exige validação"
    return (
        f"Score {score}/100 = {bucket}. Ainda assim, a fase atual é {phase}; "
        "o ativo entrou no radar por cumprir os filtros mínimos da tese."
    )


def _generate_compact_telegram_summary(all_results: list | dict, notification_results: list | None = None) -> str:
    metadata = _extract_metadata(all_results)
    normalized_results = _coerce_results(notification_results or [])
    sorted_results = sorted(normalized_results, key=lambda item: item.get("score", 0), reverse=True)
    lines = [
        "📊 *Desbasement Agent — Radar de Hoje*",
        "",
        f"Data da análise: {_analysis_date_from_results(normalized_results)}",
        f"Ativos analisados: *{metadata.get('analyzed_count', len(normalized_results))}*",
        f"Ativos aprovados no screener: *{metadata.get('approved_count', len(normalized_results))}*",
        f"Ativos notificados: *{len(normalized_results)}*",
        f"Ativos rejeitados: *{metadata.get('rejected_count', 0)}*",
    ]
    if metadata.get("mode_note"):
        lines.append(metadata["mode_note"])
    lines.extend(
        [
            "",
            "O Telegram mostra apenas ativos que passaram na régua seletiva de alerta.",
            "",
            "*COMO LER AS ESCALAS*",
            "Score alto não significa compra automática. Fase avançada indica mais confirmação técnica.",
            "",
            "*TOP ALERTAS*",
        ]
    )
    for index, item in enumerate(sorted_results[:10], start=1):
        lines.append(
            f"*{index}. {item.get('symbol', 'N/A')}* — {item.get('asset_class', 'N/A')} | "
            f"{item.get('phase', 'N/A')} | {item.get('score', 0)}/100"
        )
    lines.extend(
        [
            "",
            "⚠️ Este alerta não é recomendação financeira. A tese pode falhar e a invalidação deve ser respeitada.",
        ]
    )
    return "\n".join(lines)


def _dict_as_bullets(value: dict) -> str:
    if not value:
        return "- n/a"
    rows = []
    for key, item in value.items():
        if isinstance(item, list):
            rows.append(f"- {key}: {'; '.join(str(entry) for entry in item)}")
        else:
            rows.append(f"- {key}: {item}")
    return "\n".join(rows)


def _dataframe_to_markdown(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "No results."
    try:
        return frame.to_markdown(index=False)
    except ImportError:
        headers = [str(column) for column in frame.columns]
        separator = ["---" for _ in headers]
        rows = [
            [str(value) if pd.notna(value) else "" for value in row]
            for row in frame.itertuples(index=False, name=None)
        ]
        lines = [
            "| " + " | ".join(headers) + " |",
            "| " + " | ".join(separator) + " |",
        ]
        lines.extend("| " + " | ".join(row) + " |" for row in rows)
        return "\n".join(lines)


def _conclusion(result: dict) -> str:
    phase = result.get("phase", "")
    score = result.get("score", 0)
    if result.get("data_quality", {}).get("approved"):
        return f"O ativo permanece no radar como {phase}, com score {score}/100, aguardando confirmação e respeitando o ponto de invalidação."
    return f"O ativo não passa no filtro principal nesta leitura. Fase atual: {phase}; score {score}/100."
