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

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "       [V.ANSHEE CORE] INTERFAZ DE VANGUARDIA               " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

if (Test-Path $Python) {
    Write-Host "Iniciando servidor de la interfaz y abriendo consola..." -ForegroundColor Green
    & $Python run_ui.py
} elseif (Test-Path $DistExe) {
    Write-Host "Iniciando aplicación compilada (Vanshee.exe)..." -ForegroundColor Green
    Start-Process -FilePath $DistExe -WorkingDirectory (Split-Path -Parent $DistExe)
} else {
    Write-Host "[V.ANSHEE] No se encontro .venv ni dist\Vanshee\Vanshee.exe en $Root." -ForegroundColor Yellow
    exit 1
}

