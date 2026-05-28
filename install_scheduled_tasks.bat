@echo off
setlocal

set "PROJECT_DIR=%~dp0"
set "DAILY_BAT=%PROJECT_DIR%run_daily_alert.bat"
set "MOMENTUM_BAT=%PROJECT_DIR%run_momentum_alert.bat"
set "WEEKLY_BAT=%PROJECT_DIR%run_weekly_report.bat"

echo Criando/atualizando tarefas do Desbasement Agent...
echo.

schtasks /Create /TN "Desbasement Daily Alert" /TR "\"%DAILY_BAT%\"" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 19:30 /RL HIGHEST /F
if errorlevel 1 goto error

schtasks /Create /TN "Desbasement Momentum Alert" /TR "\"%MOMENTUM_BAT%\"" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 20:00 /RL HIGHEST /F
if errorlevel 1 goto error

schtasks /Create /TN "Desbasement Weekly Report" /TR "\"%WEEKLY_BAT%\"" /SC WEEKLY /D SUN /ST 18:00 /RL HIGHEST /F
if errorlevel 1 goto error

echo.
echo Tarefas configuradas com sucesso.
echo Abra o Agendador de Tarefas e teste cada tarefa com o botao direito ^> Executar.
pause
exit /b 0

:error
echo.
echo ERRO: nao foi possivel criar as tarefas.
echo Clique com o botao direito neste arquivo e escolha "Executar como administrador".
pause
exit /b 1
