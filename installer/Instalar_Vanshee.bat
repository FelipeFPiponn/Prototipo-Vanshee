@echo off
setlocal enabledelayedexpansion
title Instalador V.ANSHEE Core (100%% Offline)
cd /d "%~dp0"

echo ================================================================================
echo           V.ANSHEE CORE - INSTALADOR OFFLINE PARA WINDOWS
echo ================================================================================
echo Iniciando asistente de instalacion...
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0engine\install.ps1"

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] La instalacion encontro un problema (Codigo de salida: %ERRORLEVEL%).
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo Presiona cualquier tecla para cerrar el instalador.
pause >nul
exit /b 0
