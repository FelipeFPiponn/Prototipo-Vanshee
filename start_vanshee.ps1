param(
    [switch]$Cli
)

$ErrorActionPreference = "Stop"

$Root = $PSScriptRoot
if (-not $Root -and $MyInvocation.MyCommand.Path) {
    $Root = Split-Path -Parent $MyInvocation.MyCommand.Path
}
if (-not $Root) {
    $Root = (Get-Location).Path
}

Set-Location -LiteralPath $Root

$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    $PythonFallback = "C:\Users\$env:USERNAME\AppData\Local\Programs\Python\Python311\python.exe"
    if (Test-Path $PythonFallback) {
        $Python = $PythonFallback
    }
}
$DistExe = Join-Path $Root "dist\Vanshee\Vanshee.exe"

$env:PYTHONIOENCODING = "utf-8"
try {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
} catch {}

if (Test-Path $Python) {
    if ($Cli) {
        Write-Host "[V.ANSHEE] Iniciando en modo Consola por Voz CLI..." -ForegroundColor Cyan
        & $Python -m src.main
    } else {
        Write-Host "[V.ANSHEE] Iniciando Interfaz de Control de Vanguardia..." -ForegroundColor Cyan
        Write-Host "(Para usar el modo de voz en terminal sin interfaz, usa: .\start_vanshee.ps1 -Cli)" -ForegroundColor DarkGray
        & $Python run_ui.py
    }
} elseif (Test-Path $DistExe) {
    Write-Host "[V.ANSHEE] Iniciando aplicación compilada (Vanshee.exe)..." -ForegroundColor Cyan
    Start-Process -FilePath $DistExe -WorkingDirectory (Split-Path -Parent $DistExe)
} else {
    Write-Host "[V.ANSHEE] No existe .venv ni ejecutable en dist\Vanshee\Vanshee.exe en $Root." -ForegroundColor Yellow
    exit 1
}
