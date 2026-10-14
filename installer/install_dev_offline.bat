@echo off
setlocal
title Instalador de Entorno Python Offline (Dev)
cd /d "%~dp0"

echo ================================================================================
echo       INSTALADOR OFFLINE DE ENTORNO PYTHON (DESARROLLO) - V.ANSHEE
echo ================================================================================
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_dev_offline.ps1"

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Ocurrio un problema al configurar el entorno virtual.
    pause
    exit /b %ERRORLEVEL%
)

pause
