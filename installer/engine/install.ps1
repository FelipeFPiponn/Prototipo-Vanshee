<#
.SYNOPSIS
    Instalador Offline Autónomo para V.ANSHEE Core en Windows OS.
.DESCRIPTION
    Instala V.ANSHEE con todos sus componentes, librerias, modelos de IA (Llama 3.2),
    motor de voz Faster-Whisper y runtime de Ollama sin conexion a internet.
#>

param(
    [string]$InstallPath = (Join-Path $env:LOCALAPPDATA "Programs\Vanshee"),
    [switch]$Silent = $false,
    [switch]$NoLaunch = $false
)

$ErrorActionPreference = "Stop"

function Write-Banner {
    Clear-Host
    Write-Host "================================================================================" -ForegroundColor Cyan
    Write-Host "           ⚡ V.ANSHEE CORE - INSTALADOR INTEGRAL OFFLINE ⚡                    " -ForegroundColor Yellow
    Write-Host "    Sistema Autonomo de Control por Voz y Automatizacion para Windows OS         " -ForegroundColor Cyan
    Write-Host "================================================================================" -ForegroundColor Cyan
    Write-Host ""
}

function Write-Step {
    param([int]$StepNum, [string]$Title)
    Write-Host ""
    Write-Host "[$StepNum/6] $Title" -ForegroundColor Green
    Write-Host "--------------------------------------------------------------------------------" -ForegroundColor DarkGray
}

Write-Banner

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
# La raiz del paquete del instalador es el directorio padre de 'engine'
$PackageRoot = Split-Path -Parent $ScriptDir
if (-not (Test-Path (Join-Path $PackageRoot "app"))) {
    # Si 'engine' esta en la misma carpeta o subdirectorio
    if (Test-Path (Join-Path $ScriptDir "app")) {
        $PackageRoot = $ScriptDir
    }
}

Write-Host "Ruta del paquete de instalacion: $PackageRoot" -ForegroundColor Gray
Write-Host "Ruta de instalacion destino:    $InstallPath" -ForegroundColor White
Write-Host ""

if (-not $Silent) {
    Write-Host "Este instalador configurara V.ANSHEE en tu equipo de forma 100% OFFLINE:" -ForegroundColor Yellow
    Write-Host " - Runtime completo de V.ANSHEE (Interfaz HUD cyberpunk y servidor FastAPI)"
    Write-Host " - Motor de voz local Faster-Whisper (Modelo Medium precargado)"
    Write-Host " - Servicio de Inteligencia Artificial Local Ollama con modelo Llama 3.2"
    Write-Host " - Accesos directos en Escritorio y Menu Inicio"
    Write-Host ""
    $confirm = Read-Host "Deseas continuar con la instalacion? (S/N) [S]"
    if ($confirm -and $confirm.Trim().ToUpper() -ne "S") {
        Write-Host "Instalacion cancelada por el usuario." -ForegroundColor Yellow
        exit 0
    }
}

# -------------------------------------------------------------
# PASO 1: VERIFICACION DE ARQUITECTURA
# -------------------------------------------------------------
Write-Step 1 "Verificando compatibilidad del sistema"

$is64Bit = [Environment]::Is64BitOperatingSystem
if (-not $is64Bit) {
    Write-Host "ERROR: V.ANSHEE requiere un sistema operativo Windows de 64 bits." -ForegroundColor Red
    exit 1
}
Write-Host "  [OK] Arquitectura de 64 bits detectada." -ForegroundColor Green

$os = Get-CimInstance Win32_OperatingSystem
Write-Host "  [OK] Sistema Operativo: $($os.Caption) (Build $($os.BuildNumber))" -ForegroundColor Green

# -------------------------------------------------------------
# PASO 2: INSTALACION DE OLLAMA (MOTOR LLM LOCAL)
# -------------------------------------------------------------
Write-Step 2 "Configurando motor de IA Ollama (Offline)"

$OllamaBin = $null
$StandardOllamaPaths = @(
    (Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"),
    (Join-Path $env:ProgramFiles "Ollama\ollama.exe"),
    (Join-Path ${env:ProgramFiles(x86)} "Ollama\ollama.exe")
)

foreach ($p in $StandardOllamaPaths) {
    if (Test-Path $p) {
        $OllamaBin = $p
        break
    }
}

if (-not $OllamaBin) {
    $cmd = Get-Command "ollama" -ErrorAction SilentlyContinue
    if ($cmd) { $OllamaBin = $cmd.Source }
}

$OllamaInstaller = Join-Path $PackageRoot "ollama\OllamaSetup.exe"
if (-not $OllamaBin -and (Test-Path $OllamaInstaller)) {
    Write-Host "  -> Instalando Ollama desde el paquete local..." -ForegroundColor Cyan
    $proc = Start-Process -FilePath $OllamaInstaller -ArgumentList "/silent" -Wait -PassThru
    Start-Sleep -Seconds 2
    
    foreach ($p in $StandardOllamaPaths) {
        if (Test-Path $p) {
            $OllamaBin = $p
            break
        }
    }
}

if ($OllamaBin -and (Test-Path $OllamaBin)) {
    Write-Host "  [OK] Ollama detectado en: $OllamaBin" -ForegroundColor Green
} else {
    Write-Host "  [AVISO] No se pudo instalar Ollama automaticamente. Se usara modo portatil si esta disponible." -ForegroundColor Yellow
}

# -------------------------------------------------------------
# PASO 3: INSTALACION DE MODELOS OLLAMA (LLAMA 3.2 OFFLINE)
# -------------------------------------------------------------
Write-Step 3 "Desplegando modelo de razonamiento Llama 3.2 (Offline)"

$SourceOllamaModels = Join-Path $PackageRoot "ollama\models"
$TargetOllamaModels = Join-Path $env:USERPROFILE ".ollama\models"

if (Test-Path $SourceOllamaModels) {
    if (-not (Test-Path $TargetOllamaModels)) {
        New-Item -Path $TargetOllamaModels -ItemType Directory -Force | Out-Null
    }
    Write-Host "  -> Copiando modelos pre-descargados a $TargetOllamaModels..." -ForegroundColor Cyan
    # Robocopy para copia rapida y segura con preservacion de hashes
    & robocopy $SourceOllamaModels $TargetOllamaModels /E /R:1 /W:1 /NFL /NDL /NJH /NJS | Out-Null
    Write-Host "  [OK] Modelo Llama 3.2 copiado exitosamente (100% Offline)." -ForegroundColor Green
} else {
    Write-Host "  [INFO] No se encontro carpeta 'ollama/models' en el paquete." -ForegroundColor Gray
}

# -------------------------------------------------------------
# PASO 4: COPIAR APLICACION V.ANSHEE A DESTINO
# -------------------------------------------------------------
Write-Step 4 "Desplegando ejecutables y librerias de V.ANSHEE"

$SourceApp = Join-Path $PackageRoot "app"
if (-not (Test-Path $SourceApp)) {
    Write-Host "ERROR: No se encontro el directorio 'app' dentro del paquete del instalador: $SourceApp" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $InstallPath)) {
    New-Item -Path $InstallPath -ItemType Directory -Force | Out-Null
}

Write-Host "  -> Copiando archivos a: $InstallPath..." -ForegroundColor Cyan
& robocopy $SourceApp $InstallPath /E /R:1 /W:1 /NFL /NDL /NJH /NJS | Out-Null

$MainExe = Join-Path $InstallPath "Vanshee.exe"
if (-not (Test-Path $MainExe)) {
    Write-Host "ERROR: No se pudo verificar la creacion de $MainExe" -ForegroundColor Red
    exit 1
}
Write-Host "  [OK] Archivos de V.ANSHEE desplegados correctamente." -ForegroundColor Green

# -------------------------------------------------------------
# PASO 5: DESPLEGAR MODELO LOCAL FASTER-WHISPER
# -------------------------------------------------------------
Write-Step 5 "Desplegando modelo de Reconocimiento por Voz (Faster-Whisper)"

$SourceWhisper = Join-Path $PackageRoot "models\whisper"
if (Test-Path $SourceWhisper) {
    $TargetWhisper = Join-Path $InstallPath "models\whisper"
    if (-not (Test-Path $TargetWhisper)) {
        New-Item -Path $TargetWhisper -ItemType Directory -Force | Out-Null
    }
    Write-Host "  -> Copiando modelo Faster-Whisper a la carpeta de la aplicacion..." -ForegroundColor Cyan
    & robocopy $SourceWhisper $TargetWhisper /E /R:1 /W:1 /NFL /NDL /NJH /NJS | Out-Null
    Write-Host "  [OK] Modelo de voz Faster-Whisper instalado para uso offline." -ForegroundColor Green

    # Opcional: registrarlo tambien en el cache Hugging Face por compatibilidad
    $hfSnapshotDir = Join-Path $env:USERPROFILE ".cache\huggingface\hub\models--Systran--faster-whisper-medium\snapshots\08e178d48790749d25932bbc082711ddcfdfbc4f"
    $mediumLocal = Join-Path $SourceWhisper "medium"
    if ((Test-Path $mediumLocal) -and (-not (Test-Path $hfSnapshotDir))) {
        New-Item -Path $hfSnapshotDir -ItemType Directory -Force | Out-Null
        & robocopy $mediumLocal $hfSnapshotDir /E /R:1 /W:1 /NFL /NDL /NJH /NJS | Out-Null
        Write-Host "  [OK] Registrado en cache de Hugging Face de usuario." -ForegroundColor Green
    }
} else {
    Write-Host "  [AVISO] No se encontro 'models/whisper' en el paquete." -ForegroundColor Yellow
}

# -------------------------------------------------------------
# PASO 6: CREAR ACCESOS DIRECTOS Y DESINSTALADOR
# -------------------------------------------------------------
Write-Step 6 "Configurando accesos directos y desinstalador"

$ShortcutsScript = Join-Path $ScriptDir "create_shortcuts.ps1"
if (Test-Path $ShortcutsScript) {
    & $ShortcutsScript -InstallDir $InstallPath
}

# Copiar scripts de desinstalacion en la carpeta de la aplicacion
$UninstallPs1 = Join-Path $ScriptDir "uninstall.ps1"
if (Test-Path $UninstallPs1) {
    Copy-Item -Path $UninstallPs1 -Destination (Join-Path $InstallPath "uninstall.ps1") -Force
}

$UninstallBatSource = Join-Path $PackageRoot "Desinstalar_Vanshee.bat"
if (Test-Path $UninstallBatSource) {
    Copy-Item -Path $UninstallBatSource -Destination (Join-Path $InstallPath "Desinstalar_Vanshee.bat") -Force
}

Write-Host ""
Write-Host "================================================================================" -ForegroundColor Green
Write-Host "          🎉 ¡INSTALACION DE V.ANSHEE COMPLETADA EXITOSAMENTE! 🎉               " -ForegroundColor Green
Write-Host "================================================================================" -ForegroundColor Green
Write-Host ""
Write-Host "V.ANSHEE esta listo para operar de forma 100% autonoma y offline." -ForegroundColor White
Write-Host "Ubicacion: $InstallPath" -ForegroundColor Gray
Write-Host "Acceso directo: Escritorio y Menu Inicio (Vanshee)" -ForegroundColor Yellow
Write-Host ""

if (-not $NoLaunch -and -not $Silent) {
    $launch = Read-Host "Deseas iniciar V.ANSHEE ahora? (S/N) [S]"
    if (-not $launch -or $launch.Trim().ToUpper() -eq "S") {
        Write-Host "Iniciando V.ANSHEE..." -ForegroundColor Cyan
        Start-Process -FilePath $MainExe -WorkingDirectory $InstallPath
    }
}
