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

## Relatorio semanal

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

## Debug do Agendador

Para validar se o Agendador esta rodando na pasta certa, use:

```text
D:\ARQUIVOS PC\Documents\Antigravity\BotDebasementtrade\desbasement-agent-v2\run_scheduler_debug.bat
```

Deixe `Adicionar argumentos` vazio e use a pasta do projeto em `Iniciar em`.
