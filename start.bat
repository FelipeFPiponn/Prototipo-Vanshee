@echo off
TITLE V.ANSHEE Core - Lanzador Automatico
echo ========================================================
echo       V.ANSHEE - Sistema Inteligente de Control por Voz
echo ========================================================
echo.

REM Verificar si Node.js esta instalado
where node >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Node.js no esta instalado o no se encuentra en el PATH.
    echo Por favor descarga e instala Node.js 18 o superior desde: https://nodejs.org/
    echo.
    pause
    exit /b 1
)

echo [1/3] Node.js detectado correctamente.
node -v

REM Verificar si node_modules existe, si no, instalar dependencias
if not exist "node_modules\" (
    echo [2/3] Instalando dependencias del proyecto por primera vez...
    call npm install
    if %errorlevel% neq 0 (
        echo [ERROR] Hubo un problema al instalar las dependencias con npm install.
        pause
        exit /b 1
    )
) else (
    echo [2/3] Dependencias ya instaladas.
)

REM Iniciar el servidor
echo [3/3] Iniciando V.ANSHEE Core en http://localhost:3000...
echo.
echo Presiona Ctrl+C para detener el servidor.
echo.

start "" http://localhost:3000
call npm run dev
pause
