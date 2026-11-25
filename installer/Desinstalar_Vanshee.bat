@echo off
setlocal
title Desinstalador V.ANSHEE Core
cd /d "%~dp0"

echo ================================================================================
echo               DESINSTALADOR DE V.ANSHEE CORE
echo ================================================================================
echo.

if exist "%~dp0engine\uninstall.ps1" (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0engine\uninstall.ps1"
) else if exist "%~dp0uninstall.ps1" (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0uninstall.ps1"
) else (
    echo [ERROR] No se encontro el script de desinstalacion uninstall.ps1.
)

pause
