# Como configurar o Agendador de Tarefas do Windows

Use os arquivos `.bat` da raiz do projeto. Assim o Agendador nao precisa receber o `python.exe` diretamente e nao mistura caminhos com espacos como argumentos.

Pasta do projeto:

```text
D:\ARQUIVOS PC\Documents\Antigravity\BotDebasementtrade\desbasement-agent-v2
```

## Teste Telegram

Programa/script:

```text
D:\ARQUIVOS PC\Documents\Antigravity\BotDebasementtrade\desbasement-agent-v2\run_test_telegram.bat
```

Adicionar argumentos:

```text
deixar vazio
```

Iniciar em:

```text
D:\ARQUIVOS PC\Documents\Antigravity\BotDebasementtrade\desbasement-agent-v2
```

Antes de usar no Agendador, de dois cliques em `run_test_telegram.bat` e confirme se a mensagem chega no Telegram.

## Alerta diario

Este arquivo roda o alerta diario completo com narrativa habilitada:

Programa/script:

```text
D:\ARQUIVOS PC\Documents\Antigravity\BotDebasementtrade\desbasement-agent-v2\run_daily_alert.bat
```

Adicionar argumentos:

```text
deixar vazio
```

Iniciar em:

```text
D:\ARQUIVOS PC\Documents\Antigravity\BotDebasementtrade\desbasement-agent-v2
```

Horario sugerido:

```text
segunda a sexta as 19:30
```

Comando interno do `.bat`:

```text
main.py daily-alert --full --narrative
```

## Alerta de momentum

Este arquivo roda o radar de momentum separado do alerta diario:

Programa/script:

```text
D:\ARQUIVOS PC\Documents\Antigravity\BotDebasementtrade\desbasement-agent-v2\run_momentum_alert.bat
```

Adicionar argumentos:

```text
deixar vazio
```

Iniciar em:

```text
D:\ARQUIVOS PC\Documents\Antigravity\BotDebasementtrade\desbasement-agent-v2
```

Horario sugerido:

```text
segunda a sexta as 20:00
```

Comando interno do `.bat`:

```text
main.py momentum-alert --min-score 55
```

## Relatorio semanal

Este arquivo roda o relatorio semanal completo com narrativa habilitada:

Programa/script:

```text
D:\ARQUIVOS PC\Documents\Antigravity\BotDebasementtrade\desbasement-agent-v2\run_weekly_report.bat
```

Adicionar argumentos:

```text
deixar vazio
```

Iniciar em:

```text
D:\ARQUIVOS PC\Documents\Antigravity\BotDebasementtrade\desbasement-agent-v2
```

Horario sugerido:

```text
domingo as 18:00
```

Comando interno do `.bat`:

```text
main.py weekly-report --full --narrative
```

## Instalacao automatica das tarefas

Opcao recomendada, sem PowerShell:

```text
Clique com o botao direito em install_scheduled_tasks.bat
Escolha Executar como administrador
```

Esse `.bat` usa `schtasks`, que ja vem com o Windows.

Opcao alternativa com PowerShell:

Na pasta do projeto, clique com o botao direito em `install_scheduled_tasks.ps1` e escolha "Executar com PowerShell".

Se o Windows bloquear scripts, abra o PowerShell na pasta do projeto e rode:

```powershell
powershell -ExecutionPolicy Bypass -File .\install_scheduled_tasks.ps1
```

O script cria/atualiza:

```text
Desbasement Daily Alert      segunda a sexta 19:30
Desbasement Momentum Alert   segunda a sexta 20:00
Desbasement Weekly Report    domingo 18:00
```

Os tres `.bat` atualizam automaticamente `data\brazil_stocks_all.csv` antes de rodar, usando a lista publica de acoes brasileiras. Eles tambem atualizam `data\us_stocks_core.csv` com S&P 500 + Nasdaq 100 para cobrir o mercado americano sem carregar milhares de tickers pequenos/OTC.

Para atualizar o Brasil manualmente, de dois cliques em:

```text
CLIQUE_AQUI_ATUALIZAR_ACOES_BRASIL.bat
```

Para atualizar os EUA manualmente, de dois cliques em:

```text
CLIQUE_AQUI_ATUALIZAR_ACOES_EUA.bat
```

## Debug do Agendador

Para validar se o Agendador esta rodando na pasta certa, use:

```text
D:\ARQUIVOS PC\Documents\Antigravity\BotDebasementtrade\desbasement-agent-v2\run_scheduler_debug.bat
```

Deixe `Adicionar argumentos` vazio e use a pasta do projeto em `Iniciar em`.
