# Desbasement Agent V2

Desbasement Agent V2 is an analytical Python screener for assets that may be moving from extreme decline into exhaustion, lateralization, volatility compression, support defense, structure recovery and possible technical confirmation.

It does not recommend buying or selling. It generates analysis, classification, risk, confirmation trigger and invalidation level.

## First Delivery

Implemented now:

- broad multi-class universe;
- per-class thresholds;
- market data collection with `yfinance`;
- technical engine with drawdown, RSI, ATR, volatility compression, support, SMA structure, trigger and invalidation;
- neutral macro, intermarket and narrative engines with stable interfaces for future APIs;
- thesis phase scoring from 0 to 100;
- general ranking report;
- full screener report;
- macro report;
- individual reports.

Prepared for next modules:

- FRED for macro data;
- CoinGecko for crypto market data;
- Alpha Vantage for additional equities and indicators;
- Finnhub for company news;
- GDELT for global narrative/news monitoring.

Configured FRED series:

- `FEDFUNDS`, `CPIAUCSL`, `CPILFESL`, `PCEPI`, `PCEPILFE`, `UNRATE`
- `DGS2`, `DGS10`, `DGS30`, `T10Y2Y`
- `M2SL`, `WALCL`

## Install

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Create a local `.env` only when you need API keys:

```bash
copy .env.example .env
```

## Run

```bash
python main.py individual
python main.py screener
python main.py daily-alert
python main.py weekly-report
python main.py momentum-alert
python main.py test-telegram
python main.py validate-universe
python main.py validate-brazil
python main.py backtest-summary
```

Optional:

```bash
python main.py screener --full
python main.py screener --no-macro
python main.py screener --no-intermarket
python main.py screener --narrative
python main.py daily-alert --full --narrative
python main.py weekly-report --full --narrative
python main.py momentum-alert --min-score 55
```

Rules:

- `individual`: analyzes `INDIVIDUAL_ASSETS`.
- `screener`: with `TEST_MODE=True`, analyzes `get_test_universe()`.
- `screener --full`: runs the full universe.
- `daily-alert`: runs the full universe, saves complete reports, and only sends Telegram when mature setups pass the daily alert filter.
- `weekly-report`: runs the full universe, saves complete reports, and sends a weekly context report.
- `momentum-alert`: runs the momentum universe and sends Telegram alerts for the strongest momentum setups.
- `test-telegram`: validates `.env`, sends a Telegram test message, logs the API status and writes `reports/execution_report.md`.
- `validate-universe`: checks recent yfinance data for every configured ticker and writes `reports/universe_validation_report.md`.
- `validate-brazil`: checks the Brazilian universe over the last 60 days and writes `reports/brazil_validation_report.md`.
- `backtest-summary`: reads historical notified signals and writes `reports/backtest_summary.md`.
- `--no-macro`: disables macro analysis.
- `--no-intermarket`: disables intermarket analysis.
- `--narrative`: enables narrative analysis.

## Outputs

Reports are written to:

- `reports/ranking_report.md`
- `reports/full_screener_report.md`
- `reports/macro_report.md`
- `reports/brazil_report.md`
- `reports/execution_report.md`
- `reports/universe_validation_report.md`
- `reports/universe_validation_errors.txt`
- `reports/individual/{SYMBOL}_report.md`
- `reports/backtest_summary.md`
- `reports/momentum_YYYY-MM-DD.md`

Cached data is written to:

- `data/cache/*.csv`
- `data/raw/*.csv`
- `data/signals/signals_history.csv`
- `logs/app.log`

## Scoring Thesis

The score is not a "buy the dip" score. It looks for assets that pass through:

1. extreme decline for the asset class;
2. decline exhaustion;
3. lateralization or possible accumulation;
4. volatility compression;
5. support defense;
6. structure recovery;
7. technical confirmation;
8. favorable or at least non-hostile macro/intermarket/narrative context;
9. clear confirmation trigger;
10. clear invalidation point.

## Implementation Order

1. Project structure.
2. `src/universe.py`.
3. `src/thresholds.py`.
4. `src/data_collector.py`.
5. `src/technical_engine.py`.
6. `src/macro_engine.py`, with fallback when FRED is unavailable.
7. `src/intermarket_engine.py`, using `yfinance` proxies.
8. `src/narrative_engine.py`, with optional score.
9. `src/scoring_engine.py`.
10. `src/screener_engine.py`.
11. `src/report_generator.py`.
12. `main.py`.
13. `src/backtest_engine.py` stub.
14. Test with `TEST_MODE=True`.
15. Corrections.
16. Test with the full universe.

## Scheduling

The thesis is designed for swing/position monitoring, not intraday alerts.

## Agendador de Tarefas no Windows

Se o Agendador do Windows mostrar aviso de argumentos misturados ao usar `python.exe`, nao coloque o Python diretamente em `Programa/script`. Use os arquivos `.bat` da raiz do projeto.

- `Programa/script` deve apontar para o arquivo `.bat`.
- `Adicionar argumentos` deve ficar vazio.
- `Iniciar em` deve ser a pasta do projeto.
- Primeiro teste `run_test_telegram.bat` com duplo clique.
- Depois teste `run_test_telegram.bat` pelo Agendador.
- So depois configure `run_daily_alert.bat` e `run_weekly_report.bat`.
- Para configurar tudo de uma vez, clique com o botao direito em `install_scheduled_tasks.bat` e escolha "Executar como administrador".

Arquivos disponiveis:

- `run_test_telegram.bat`: envia mensagem de teste para o Telegram e deixa a janela aberta.
- `run_daily_alert.bat`: roda `main.py daily-alert --full --narrative`.
- `run_momentum_alert.bat`: roda `main.py momentum-alert --min-score 55`.
- `run_weekly_report.bat`: roda `main.py weekly-report --full --narrative`.
- `CLIQUE_AQUI_ATUALIZAR_ACOES_BRASIL.bat`: atualiza `data/brazil_stocks_all.csv` com a lista publica de acoes brasileiras.
- `CLIQUE_AQUI_ATUALIZAR_ACOES_EUA.bat`: atualiza `data/us_stocks_core.csv` com S&P 500 + Nasdaq 100.
- `run_scheduler_debug.bat`: valida a pasta de execucao e deixa a janela aberta.

Guia completo: `install_task_scheduler_windows.md`.

### Windows

Use Task Scheduler.

Daily alert:

- Frequency: Monday to Friday
- Time: 19:30
- Programa/script:

```
C:\caminho\para\.venv\Scripts\python.exe
```

- Argumentos:

```
main.py daily-alert --full
```

- Iniciar em:

```
C:\caminho\da\pasta\do\projeto
```

Weekly report:

- Frequency: Sunday
- Time: 18:00
- Programa/script:

```
C:\caminho\para\.venv\Scripts\python.exe
```

- Argumentos:

```
main.py weekly-report --full
```

- Iniciar em:

```
C:\caminho\da\pasta\do\projeto
```

O script nao precisa ficar ligado no Prompt. O Agendador inicia o Python, o projeto roda a analise, envia o Telegram, grava os relatorios e finaliza. Isso e normal.

Para validar se o Agendador esta realmente executando o Python, crie uma tarefa temporaria com:

- Programa/script:

```
C:\caminho\para\.venv\Scripts\python.exe
```

- Argumentos:

```
scheduler_test.py
```

- Iniciar em:

```
C:\caminho\da\pasta\do\projeto
```

Quando a tarefa rodar, ela deve criar ou atualizar `scheduler_test_output.txt` com data e hora da execucao.

### Mac/Linux

Use cron.

Daily alert, Monday to Friday at 19:30:

```cron
30 19 * * 1-5 cd /caminho/do/projeto && python main.py daily-alert
```

Weekly report, Sunday at 18:00:

```cron
0 18 * * 0 cd /caminho/do/projeto && python main.py weekly-report
```

## Important Note

This project is for research and analytical classification only. It is not financial advice and does not generate buy or sell recommendations.
