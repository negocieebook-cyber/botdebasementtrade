$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path

$Tasks = @(
    @{
        Name = "Desbasement Daily Alert"
        Bat = "run_daily_alert.bat"
        Schedule = "WEEKLY"
        Days = "MON,TUE,WED,THU,FRI"
        Time = "19:30"
    },
    @{
        Name = "Desbasement Momentum Alert"
        Bat = "run_momentum_alert.bat"
        Schedule = "WEEKLY"
        Days = "MON,TUE,WED,THU,FRI"
        Time = "20:00"
    },
    @{
        Name = "Desbasement Weekly Report"
        Bat = "run_weekly_report.bat"
        Schedule = "WEEKLY"
        Days = "SUN"
        Time = "18:00"
    }
)

foreach ($Task in $Tasks) {
    $BatPath = Join-Path $ProjectDir $Task.Bat
    if (-not (Test-Path -LiteralPath $BatPath)) {
        throw "Arquivo nao encontrado: $BatPath"
    }

    Write-Host "Criando/atualizando tarefa: $($Task.Name)"
    schtasks.exe /Create `
        /TN $Task.Name `
        /TR "`"$BatPath`"" `
        /SC $Task.Schedule `
        /D $Task.Days `
        /ST $Task.Time `
        /RL HIGHEST `
        /F

    if ($LASTEXITCODE -ne 0) {
        throw "Falha ao criar/atualizar a tarefa '$($Task.Name)'. Abra o PowerShell como Administrador e execute este script de novo."
    }
}

Write-Host ""
Write-Host "Tarefas configuradas."
Write-Host "Abra o Agendador de Tarefas e use Executar em cada uma para testar."
