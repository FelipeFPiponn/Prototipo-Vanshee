@echo off
title V.ANSHEE Core Console
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo ============================================================
    echo  [AVISO] No se encontro el entorno virtual .venv en este equipo.
    echo ============================================================
    echo  Es necesario configurar las dependencias antes del primer uso.
    echo.
    set /p INSTALL_NOW="Deseas crearlo y configurarlo ahora mismo? (S/N) [S]: "
)

if not exist ".venv\Scripts\python.exe" (
    if /i "%INSTALL_NOW%"=="N" (
        echo Operacion cancelada. Ejecuta install_vanshee.ps1 cuando desees instalar.
        pause
        exit /b 1
    )
    echo.
    echo ==> Configurando entorno V.ANSHEE de forma automatica...
    if exist "installer\offline_wheels" (
        powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0installer\install_dev_offline.ps1"
    ) else (
        powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_vanshee.ps1"
    )
    if not exist ".venv\Scripts\python.exe" (
        echo.
        echo [ERROR] No se pudo crear o verificar el entorno .venv.
        pause
        exit /b 1
    )
)

echo ============================================================
echo        V.ANSHEE CORE - INTERFAZ DE CONTROL WEB
echo ============================================================
echo Iniciando servidor y consola de usuario...
".venv\Scripts\python.exe" run_ui.py
pause
