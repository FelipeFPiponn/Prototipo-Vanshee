# Script para crear acceso directo de Vanshee en el Escritorio
$WshShell = New-Object -ComObject WScript.Shell
$DesktopPath = [System.Environment]::GetFolderPath('Desktop')
$ShortcutPath = Join-Path -Path $DesktopPath -ChildPath "Vanshee.lnk"

$ScriptDir = $PSScriptRoot
if (-not $ScriptDir -and $MyInvocation.MyCommand.Path) {
    $ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
}
if (-not $ScriptDir) {
    $ScriptDir = (Get-Location).Path
}

$TargetExe = Join-Path -Path $ScriptDir -ChildPath "dist\Vanshee\Vanshee.exe"
if (-not (Test-Path $TargetExe)) {
    $TargetExe = Join-Path -Path $ScriptDir -ChildPath "Vanshee.exe"
}

if (Test-Path $TargetExe) {
    $Shortcut = $WshShell.CreateShortcut($ShortcutPath)
    $Shortcut.TargetPath = $TargetExe
    $Shortcut.WorkingDirectory = (Split-Path -Parent $TargetExe)
    $Shortcut.Description = "Vanshee - Asistente Autónomo de Windows"
    $Shortcut.Save()
    Write-Host "✅ Acceso directo creado exitosamente en tu Escritorio: $ShortcutPath" -ForegroundColor Green
} else {
    $BatLauncher = Join-Path -Path $ScriptDir -ChildPath "start_vanshee_ui.bat"
    if (Test-Path $BatLauncher) {
        $Shortcut = $WshShell.CreateShortcut($ShortcutPath)
        $Shortcut.TargetPath = $BatLauncher
        $Shortcut.WorkingDirectory = $ScriptDir
        $Shortcut.Description = "Vanshee - Asistente Autónomo de Windows"
        $Shortcut.Save()
        Write-Host "✅ Acceso directo a consola creado exitosamente en tu Escritorio: $ShortcutPath" -ForegroundColor Green
    } else {
        Write-Host "❌ No se encontró el ejecutable ni el lanzador en $ScriptDir." -ForegroundColor Red
    }
}

