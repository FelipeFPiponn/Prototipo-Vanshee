<#
.SYNOPSIS
    Desinstalador limpio de V.ANSHEE Core.
#>

param(
    [string]$InstallPath = (Join-Path $env:LOCALAPPDATA "Programs\Vanshee"),
    [switch]$Force = $false
)

Clear-Host
Write-Host "================================================================================" -ForegroundColor Red
Write-Host "               🗑️ DESINSTALADOR DE V.ANSHEE CORE 🗑️                            " -ForegroundColor Yellow
Write-Host "================================================================================" -ForegroundColor Red
Write-Host ""

if (-not $Force) {
    $confirm = Read-Host "Estas seguro de que deseas desinstalar V.ANSHEE y sus accesos directos? (S/N)"
    if ($confirm.Trim().ToUpper() -ne "S") {
        Write-Host "Desinstalacion cancelada." -ForegroundColor Yellow
        exit 0
    }
}

Write-Host "1. Deteniendo procesos activos de Vanshee..." -ForegroundColor Cyan
Get-Process -Name "Vanshee" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

Write-Host "2. Eliminando accesos directos..." -ForegroundColor Cyan
$DesktopShortcut = Join-Path ([System.Environment]::GetFolderPath('Desktop')) "Vanshee.lnk"
if (Test-Path $DesktopShortcut) {
    Remove-Item -Path $DesktopShortcut -Force
    Write-Host "  [OK] Acceso directo de Escritorio eliminado." -ForegroundColor Green
}

$StartShortcutDir = Join-Path ([System.Environment]::GetFolderPath('Programs')) "Vanshee"
if (Test-Path $StartShortcutDir) {
    Remove-Item -Path $StartShortcutDir -Recurse -Force
    Write-Host "  [OK] Acceso directo de Menu Inicio eliminado." -ForegroundColor Green
}

Write-Host "3. Eliminando archivos del programa en $InstallPath..." -ForegroundColor Cyan
if (Test-Path $InstallPath) {
    # Si se ejecuta desde dentro de la carpeta, programar borrado o borrar contenidos
    try {
        Remove-Item -Path $InstallPath -Recurse -Force
        Write-Host "  [OK] Carpeta del programa eliminada." -ForegroundColor Green
    } catch {
        Write-Host "  [AVISO] Algunos archivos bloqueados se eliminaran al reiniciar o manualmente: $_" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "Desinstalacion finalizada." -ForegroundColor Green
