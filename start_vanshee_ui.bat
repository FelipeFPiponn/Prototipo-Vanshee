@echo off
title V.ANSHEE Core Console
cd /d "%~dp0"

if exist "%~dp0.venv\Scripts\python.exe" (
    echo [V.ANSHEE] Iniciando servidor y consola desde entorno .venv...
    "%~dp0.venv\Scripts\python.exe" run_ui.py
) else if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    echo [V.ANSHEE] Iniciando servidor y consola con Python 3.11...
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" run_ui.py
) else if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    echo [V.ANSHEE] Iniciando servidor y consola con Python 3.12...
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" run_ui.py
) else if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" (
    echo [V.ANSHEE] Iniciando servidor y consola con Python 3.13...
    "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" run_ui.py
) else (
    where python >nul 2>nul
    if %errorlevel% equ 0 (
        echo [V.ANSHEE] Iniciando servidor y consola con Python del sistema...
        python run_ui.py
    ) else (
        where py >nul 2>nul
        if %errorlevel% equ 0 (
            echo [V.ANSHEE] Iniciando servidor y consola con launcher py...
            py run_ui.py
        ) else if exist "%~dp0dist\Vanshee\Vanshee.exe" (
            echo [V.ANSHEE] Iniciando aplicacion compilada Vanshee.exe...
            start "" /d "%~dp0dist\Vanshee" "Vanshee.exe"
        ) else (
            echo [ERROR] No se encontro entorno Python (.venv, Python 3.11/3.12/3.13, PATH) ni dist\Vanshee\Vanshee.exe en %~dp0
            pause
            exit /b 1
        )
    )
)

