@echo off
title V.ANSHEE Core Console
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] No se encontro el entorno .venv en esta carpeta.
    pause
    exit /b 1
)

echo ============================================================
echo        V.ANSHEE CORE - INTERFAZ DE CONTROL WEB
echo ============================================================
echo Iniciando servidor y consola de usuario...
".venv\Scripts\python.exe" run_ui.py
pause
