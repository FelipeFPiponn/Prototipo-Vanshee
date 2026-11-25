<#
.SYNOPSIS
    Generador del Paquete de Instalacion Offline de V.ANSHEE Core.
.DESCRIPTION
    Empaqueta la aplicacion compilada (dist/Vanshee), el runtime de Ollama,
    el modelo Llama 3.2, el modelo Faster-Whisper y los instaladores en una carpeta
    autocontenida lista para copiar en pendrive o compartir a cualquier otro equipo sin internet.
#>

param(
    [string]$OutputDir = (Join-Path (Split-Path -Parent $PSScriptRoot) "dist_installer\Vanshee_Offline_Installer"),
    [string]$WhisperModel = "medium",
    [switch]$IncludeWheels = $false
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$DistApp = Join-Path $Root "dist\Vanshee"
$InstallerSource = Join-Path $Root "installer"
$HfCache = Join-Path $env:USERPROFILE ".cache\huggingface\hub\models--Systran--faster-whisper-$WhisperModel\snapshots"
$OllamaInstallerPath = "C:\Users\Entoma\Downloads\OllamaSetup.exe"
if (-not (Test-Path $OllamaInstallerPath)) {
    $OllamaInstallerPath = Join-Path $env:USERPROFILE "Downloads\OllamaSetup.exe"
}
$OllamaModelsPath = Join-Path $env:USERPROFILE ".ollama\models"

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "       📦 CONSTRUCTOR DE PAQUETE DE INSTALACION OFFLINE - V.ANSHEE 📦           " -ForegroundColor Yellow
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "Destino del paquete: $OutputDir" -ForegroundColor White
Write-Host ""

# 1. Verificar prerrequisitos de empaquetado
Write-Host "==> Verificando fuentes requeridas..." -ForegroundColor Cyan

if (-not (Test-Path (Join-Path $DistApp "Vanshee.exe"))) {
    Write-Host "ERROR: No se encontro dist\Vanshee\Vanshee.exe. Compila primero el proyecto con PyInstaller." -ForegroundColor Red
    exit 1
}
Write-Host "  [OK] Binario standalone dist\Vanshee detectado." -ForegroundColor Green

if (-not (Test-Path $HfCache)) {
    Write-Host "ERROR: No se encontro el modelo Faster-Whisper '$WhisperModel' en $HfCache." -ForegroundColor Red
    exit 1
}
Write-Host "  [OK] Cache de Faster-Whisper '$WhisperModel' detectado." -ForegroundColor Green

if (-not (Test-Path $OllamaInstallerPath)) {
    Write-Host "[AVISO] No se encontro OllamaSetup.exe en $OllamaInstallerPath." -ForegroundColor Yellow
} else {
    Write-Host "  [OK] Instalador OllamaSetup.exe detectado." -ForegroundColor Green
}

if (-not (Test-Path $OllamaModelsPath)) {
    Write-Host "[AVISO] No se encontro la carpeta de modelos Ollama en $OllamaModelsPath." -ForegroundColor Yellow
} else {
    Write-Host "  [OK] Modelos de Ollama detectados en $OllamaModelsPath." -ForegroundColor Green
}

# 2. Crear estructura del instalador
Write-Host ""
Write-Host "==> Creando estructura de directorios en $OutputDir..." -ForegroundColor Cyan
if (Test-Path $OutputDir) {
    Write-Host "  -> Limpiando paquete previo..." -ForegroundColor Gray
}
New-Item -Path $OutputDir -ItemType Directory -Force | Out-Null
New-Item -Path (Join-Path $OutputDir "app") -ItemType Directory -Force | Out-Null
New-Item -Path (Join-Path $OutputDir "engine") -ItemType Directory -Force | Out-Null
New-Item -Path (Join-Path $OutputDir "models\whisper\$WhisperModel") -ItemType Directory -Force | Out-Null
New-Item -Path (Join-Path $OutputDir "ollama") -ItemType Directory -Force | Out-Null

# 3. Copiar scripts del instalador
Write-Host ""
Write-Host "==> Copiando scripts de instalacion..." -ForegroundColor Cyan
Copy-Item -Path (Join-Path $InstallerSource "Instalar_Vanshee.bat") -Destination (Join-Path $OutputDir "Instalar_Vanshee.bat") -Force
Copy-Item -Path (Join-Path $InstallerSource "Desinstalar_Vanshee.bat") -Destination (Join-Path $OutputDir "Desinstalar_Vanshee.bat") -Force
Copy-Item -Path (Join-Path $InstallerSource "engine\*") -Destination (Join-Path $OutputDir "engine") -Recurse -Force
Write-Host "  [OK] Scripts de instalacion y desinstalacion copiados." -ForegroundColor Green

# 4. Copiar la aplicacion compilada (dist/Vanshee -> app/)
Write-Host ""
Write-Host "==> Copiando aplicacion compilada (Vanshee + _internal + web + config)..." -ForegroundColor Cyan
& robocopy $DistApp (Join-Path $OutputDir "app") /E /R:1 /W:1 /NFL /NDL /NJH /NJS | Out-Null
Write-Host "  [OK] Aplicacion Vanshee copiada." -ForegroundColor Green

# 5. Copiar modelo Faster-Whisper
Write-Host ""
Write-Host "==> Copiando modelo offline de Faster-Whisper ($WhisperModel)..." -ForegroundColor Cyan
$snapFolder = Get-ChildItem -Path $HfCache -Directory | Select-Object -First 1
if ($snapFolder) {
    & robocopy $snapFolder.FullName (Join-Path $OutputDir "models\whisper\$WhisperModel") /E /R:1 /W:1 /NFL /NDL /NJH /NJS | Out-Null
    Write-Host "  [OK] Modelo Whisper '$WhisperModel' empaquetado ($( [math]::Round((Get-ChildItem -Path (Join-Path $OutputDir "models\whisper\$WhisperModel") -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB, 1) ) MB)." -ForegroundColor Green
}

# 6. Copiar Ollama installer y modelos
Write-Host ""
Write-Host "==> Copiando instalador y modelos de Ollama..." -ForegroundColor Cyan
if (Test-Path $OllamaInstallerPath) {
    Copy-Item -Path $OllamaInstallerPath -Destination (Join-Path $OutputDir "ollama\OllamaSetup.exe") -Force
    Write-Host "  [OK] OllamaSetup.exe copiado." -ForegroundColor Green
}

if (Test-Path $OllamaModelsPath) {
    $TargetOllamaModels = Join-Path $OutputDir "ollama\models"
    New-Item -Path $TargetOllamaModels -ItemType Directory -Force | Out-Null
    & robocopy $OllamaModelsPath $TargetOllamaModels /E /R:1 /W:1 /NFL /NDL /NJH /NJS | Out-Null
    Write-Host "  [OK] Modelos Ollama (Llama 3.2) empaquetados ($( [math]::Round((Get-ChildItem -Path $TargetOllamaModels -Recurse | Measure-Object -Property Length -Sum).Sum / 1GB, 2) ) GB)." -ForegroundColor Green
}

# 7. Ruedas offline y scripts de desarrollo
$LocalWheels = Join-Path $InstallerSource "offline_wheels"
if (Test-Path $LocalWheels) {
    Write-Host ""
    Write-Host "==> Copiando paquetes pip pre-descargados (Modo Desarrollador)..." -ForegroundColor Cyan
    $WheelDir = Join-Path $OutputDir "offline_wheels"
    & robocopy $LocalWheels $WheelDir /E /R:1 /W:1 /NFL /NDL /NJH /NJS | Out-Null
    Copy-Item -Path (Join-Path $InstallerSource "install_dev_offline.bat") -Destination (Join-Path $OutputDir "install_dev_offline.bat") -Force
    Copy-Item -Path (Join-Path $InstallerSource "install_dev_offline.ps1") -Destination (Join-Path $OutputDir "install_dev_offline.ps1") -Force
    Write-Host "  [OK] Ruedas pip y scripts de desarrollo empaquetados." -ForegroundColor Green
}

# 8. Generar documentacion LEEME_INSTALACION.md
$ReadmePath = Join-Path $OutputDir "LEEME_INSTALACION.md"
$ReadmeContent = @"
# ⚡ V.ANSHEE Core - Instalador Autónomo Offline para Windows

Este paquete contiene la instalación completa, autónoma e independiente de **V.ANSHEE Core** para ejecutarse en cualquier computadora con **Windows 10 u 11 (64-bit)** sin requerir conexión a internet ni descargas adicionales de ningún tipo.

---

## 🎯 Modalidades de Instalación

### Modalidad 1: Aplicación Autónoma / Usuario Final (Recomendada)
**No requiere instalar Python.** Incluye todo el entorno compilado, librerías, interfaz HUD, servicio Ollama y modelos neuronales.

1. Conecta la memoria USB o copia esta carpeta a la computadora destino.
2. Haz doble clic en:
   ```
   Instalar_Vanshee.bat
   ```
3. El asistente realizará en cuestión de segundos:
   - ✅ Verificación de arquitectura de 64 bits.
   - ✅ Instalación silenciosa del motor de IA local **Ollama**.
   - ✅ Despliegue de los modelos neuronales **Llama 3.2** (100% offline).
   - ✅ Despliegue del motor de reconocimiento por voz **Faster-Whisper (Medium)** en español.
   - ✅ Despliegue de ejecutables y librerías compiladas de V.ANSHEE.
   - ✅ Creación de accesos directos en el **Escritorio** y en el **Menú Inicio**.

Para iniciar la aplicación:
- Haz doble clic en el acceso directo **Vanshee** en tu Escritorio o búscalo en el Menú Inicio.

---

### Modalidad 2: Entorno de Desarrollo (Código Fuente en Python)
Si en la otra computadora deseas modificar el código fuente con Python en lugar de usar el ejecutable compilado:

1. Asegúrate de tener Python 3.10 o superior instalado en esa computadora.
2. Haz doble clic en:
   ```
   install_dev_offline.bat
   ```
3. Este script creará un entorno virtual `.venv` e instalará todas las librerías desde la carpeta local `offline_wheels\` sin conectarse a internet.

---

## 🗑️ Desinstalación Limpia

Si alguna vez deseas desinstalar V.ANSHEE y sus accesos directos:
- Haz doble clic en **Desinstalar_Vanshee.bat**.

---

## 📦 Estructura del Paquete Offline

- `Instalar_Vanshee.bat` : Asistente de instalación automática en 1 clic.
- `Desinstalar_Vanshee.bat` : Script de desinstalación limpia.
- `install_dev_offline.bat` : Instalador de entorno virtual Python para desarrolladores.
- `app/` : Aplicación standalone completa (ejecutable, runtime, consola HUD).
- `models/whisper/` : Modelo neuronal Faster-Whisper precargado para voz.
- `ollama/` : Instalador oficial de Ollama y modelos Llama 3.2 offline.
- `offline_wheels/` : Repositorio local de todas las ruedas (.whl) de Python.
- `engine/` : Motor PowerShell con gestión de permisos y accesos directos.
"@

Set-Content -Path $ReadmePath -Value $ReadmeContent -Encoding UTF8

Write-Host ""
Write-Host "================================================================================" -ForegroundColor Green
Write-Host "     🎉 ¡PAQUETE DE INSTALACION OFFLINE GENERADO CON EXITO! 🎉                 " -ForegroundColor Green
Write-Host "================================================================================" -ForegroundColor Green
Write-Host "Ubicacion: $OutputDir" -ForegroundColor Yellow
$totalSize = (Get-ChildItem -Path $OutputDir -Recurse | Measure-Object -Property Length -Sum).Sum / 1GB
Write-Host "Tamano total del instalador: $([math]::Round($totalSize, 2)) GB" -ForegroundColor White
Write-Host ""
Write-Host "Para distribuir: Copia la carpeta '$OutputDir' a cualquier PC y ejecuta 'Instalar_Vanshee.bat'." -ForegroundColor Cyan
