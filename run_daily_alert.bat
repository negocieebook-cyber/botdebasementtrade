@echo off
cd /d "D:\ARQUIVOS PC\Documents\Antigravity\BotDebasementtrade\desbasement-agent-v2"
"C:\Users\BARBARA DE PAULA\AppData\Local\Programs\Python\Python311\python.exe" -m src.brazil_tickers_updater
"C:\Users\BARBARA DE PAULA\AppData\Local\Programs\Python\Python311\python.exe" -m src.us_tickers_updater
"C:\Users\BARBARA DE PAULA\AppData\Local\Programs\Python\Python311\python.exe" main.py daily-alert --full --narrative
