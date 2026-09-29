$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvDir = Join-Path $Root ".venv"
$Python = Join-Path $VenvDir "Scripts\python.exe"
$Requirements = Join-Path $Root "requirements.txt"
$CheckScript = Join-Path $Root "scripts\check_system.py"
$SyncRequirementsScript = Join-Path $Root "scripts\sync_requirements.py"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Resolve-SystemPython {
    $Candidates = @(
        @{ Command = "py"; Args = @("-3") },
        @{ Command = "python"; Args = @() },
        @{ Command = "python3"; Args = @() }
    )

    foreach ($Candidate in $Candidates) {
        $Command = Get-Command $Candidate.Command -ErrorAction SilentlyContinue
        if ($Command) {
            return @{
                Command = $Candidate.Command
                Args = $Candidate.Args
            }
        }
    }

    return $null
}

Set-Location $Root

Write-Host "=== Instalador V.ANSHEE Core ===" -ForegroundColor Green
Write-Host "Ruta del proyecto: $Root"

if (-not (Test-Path $Requirements)) {
    throw "No se encontro requirements.txt en $Root"
}

$SystemPython = Resolve-SystemPython

if (-not (Test-Path $Python)) {
    if (-not $SystemPython) {
        throw "No se encontro Python instalado en PATH. Instala Python 3 y vuelve a ejecutar este script."
    }

    Write-Step "Creando entorno virtual .venv"
    & $SystemPython.Command @($SystemPython.Args + @("-m", "venv", $VenvDir))
}
else {
    Write-Step "Usando entorno virtual existente"
    & $Python --version
}

if (-not (Test-Path $Python)) {
    throw "No se pudo crear o encontrar $Python"
}

Write-Step "Actualizando pip, setuptools y wheel"
& $Python -m pip install --upgrade pip setuptools wheel

if (Test-Path $SyncRequirementsScript) {
    Write-Step "Sincronizando requirements.txt segun imports actuales del proyecto"
    & $Python $SyncRequirementsScript
}

Write-Step "Instalando dependencias de requirements.txt"
& $Python -m pip install -r $Requirements

$PackageJson = Join-Path $Root "package.json"
if (Test-Path $PackageJson) {
    $Npm = Get-Command "npm" -ErrorAction SilentlyContinue
    if (-not $Npm) {
        Write-Host "[WARN] Se encontro package.json, pero npm no esta disponible en PATH." -ForegroundColor Yellow
    }
    else {
        Write-Step "Instalando dependencias Node detectadas en package.json"
        if (Test-Path (Join-Path $Root "package-lock.json")) {
            & npm ci
        }
        else {
            & npm install
        }
    }
}

Write-Step "Verificando instalacion de V.ANSHEE"
& $Python $CheckScript

Write-Host ""
Write-Host "=== Instalacion finalizada ===" -ForegroundColor Green
Write-Host "Para revisar el sistema:"
Write-Host "  .\.venv\Scripts\python.exe scripts\check_system.py" -ForegroundColor Yellow
Write-Host "Para iniciar V.ANSHEE:"
Write-Host "  .\start_vanshee.ps1" -ForegroundColor Yellow
