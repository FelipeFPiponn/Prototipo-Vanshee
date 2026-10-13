param(
    [switch]$Cli
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    Write-Host "[V.ANSHEE] No existe .venv. Crea el entorno con: py -m venv .venv" -ForegroundColor Yellow
    exit 1
}

$env:PYTHONIOENCODING = "utf-8"
try {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
} catch {}

if ($Cli) {
    Write-Host "[V.ANSHEE] Iniciando en modo Consola por Voz CLI..." -ForegroundColor Cyan
    & $Python -m src.main
} else {
    Write-Host "[V.ANSHEE] Iniciando Interfaz de Control de Vanguardia..." -ForegroundColor Cyan
    Write-Host "(Para usar el modo de voz en terminal sin interfaz, usa: .\start_vanshee.ps1 -Cli)" -ForegroundColor DarkGray
    & $Python run_ui.py
}
