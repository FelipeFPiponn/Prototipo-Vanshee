<#
.SYNOPSIS
    Instalador Offline de Entorno Virtual de Desarrollo para V.ANSHEE Core.
.DESCRIPTION
    Crea un .venv local e instala todas las dependencias usando las ruedas .whl
    pre-descargadas sin conexion a internet.
#>

param(
    [string]$VenvPath = (Join-Path (Split-Path -Parent $PSScriptRoot) ".venv")
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$WheelDir = Join-Path $PSScriptRoot "offline_wheels"
$Reqs = Join-Path $Root "requirements.txt"

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "        🐍 INSTALADOR OFFLINE DE ENTORNO PYTHON (DEV) - V.ANSHEE 🐍             " -ForegroundColor Yellow
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "Ruta del proyecto: $Root" -ForegroundColor White
Write-Host "Carpeta de ruedas: $WheelDir" -ForegroundColor White
Write-Host "Entorno virtual:   $VenvPath" -ForegroundColor White
Write-Host ""

if (-not (Test-Path $WheelDir)) {
    Write-Host "ERROR: No se encontro la carpeta de ruedas offline $WheelDir." -ForegroundColor Red
    exit 1
}

# 1. Resolver ejecutable de Python del sistema
function Resolve-SystemPython {
    $Candidates = @(
        @{ Command = "py"; Args = @("-3") },
        @{ Command = "python"; Args = @() },
        @{ Command = "python3"; Args = @() }
    )
    foreach ($c in $Candidates) {
        $cmd = Get-Command $c.Command -ErrorAction SilentlyContinue
        if ($cmd) {
            return @{ Command = $c.Command; Args = $c.Args }
        }
    }
    return $null
}

$SystemPy = Resolve-SystemPython
if (-not $SystemPy) {
    Write-Host "ERROR: No se encontro Python 3 instalado en PATH. Instala Python 3 en este equipo." -ForegroundColor Red
    exit 1
}

# 2. Crear .venv si no existe
$VenvPy = Join-Path $VenvPath "Scripts\python.exe"
if (-not (Test-Path $VenvPy)) {
    Write-Host "==> Creando entorno virtual .venv en $VenvPath..." -ForegroundColor Cyan
    & $SystemPy.Command @($SystemPy.Args + @("-m", "venv", $VenvPath))
}

if (-not (Test-Path $VenvPy)) {
    Write-Host "ERROR: No se pudo crear el entorno virtual en $VenvPath." -ForegroundColor Red
    exit 1
}

# 3. Instalar librerías 100% offline
Write-Host "==> Instalando dependencias desde 'offline_wheels' (100% Offline)..." -ForegroundColor Cyan
& $VenvPy -m pip install --no-index --find-links=$WheelDir -r $Reqs

Write-Host ""
Write-Host "==> Verificando instalacion..." -ForegroundColor Cyan
$CheckScript = Join-Path $Root "scripts\check_system.py"
if (Test-Path $CheckScript) {
    & $VenvPy $CheckScript
}

Write-Host ""
Write-Host "================================================================================" -ForegroundColor Green
Write-Host "   ✅ Entorno Python configurado exitosamente sin conexion a internet!           " -ForegroundColor Green
Write-Host "================================================================================" -ForegroundColor Green
Write-Host "Para iniciar V.ANSHEE en modo desarrollo:" -ForegroundColor White
Write-Host "  .\start_vanshee.ps1" -ForegroundColor Yellow
