param(
    [Parameter(Mandatory=$true)]
    [string]$InstallDir
)

$WshShell = New-Object -ComObject WScript.Shell

$TargetExe = Join-Path $InstallDir "Vanshee.exe"
if (-not (Test-Path $TargetExe)) {
    Write-Host "[Error Shortcuts] No se encontro Vanshee.exe en $InstallDir" -ForegroundColor Red
    return
}

# 1. Acceso directo en el Escritorio
$DesktopPath = [System.Environment]::GetFolderPath('Desktop')
$DesktopShortcutPath = Join-Path $DesktopPath "Vanshee.lnk"

$Shortcut = $WshShell.CreateShortcut($DesktopShortcutPath)
$Shortcut.TargetPath = $TargetExe
$Shortcut.WorkingDirectory = $InstallDir
$Shortcut.Description = "V.ANSHEE - Asistente y Copiloto Autonomo de Windows"
$Shortcut.Save()
Write-Host "  [OK] Acceso directo en Escritorio creado: $DesktopShortcutPath" -ForegroundColor Green

# 2. Acceso directo en el Menu Inicio
$StartMenuPath = [System.Environment]::GetFolderPath('Programs')
$VansheeStartFolder = Join-Path $StartMenuPath "Vanshee"
if (-not (Test-Path $VansheeStartFolder)) {
    New-Item -Path $VansheeStartFolder -ItemType Directory -Force | Out-Null
}

$StartMenuShortcutPath = Join-Path $VansheeStartFolder "Vanshee.lnk"
$StartShortcut = $WshShell.CreateShortcut($StartMenuShortcutPath)
$StartShortcut.TargetPath = $TargetExe
$StartShortcut.WorkingDirectory = $InstallDir
$StartShortcut.Description = "V.ANSHEE - Asistente y Copiloto Autonomo de Windows"
$StartShortcut.Save()
Write-Host "  [OK] Acceso directo en Menu Inicio creado: $StartMenuShortcutPath" -ForegroundColor Green
