$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    Write-Host "[V.ANSHEE] No se encontro .venv. Crea el entorno con: py -m venv .venv" -ForegroundColor Yellow
    exit 1
}

$env:PYTHONIOENCODING = "utf-8"
try {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
} catch {}

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "       [V.ANSHEE CORE] INTERFAZ DE VANGUARDIA               " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Iniciando servidor de la interfaz y abriendo consola..." -ForegroundColor Green

& $Python run_ui.py
