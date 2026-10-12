# Script para crear acceso directo de Vanshee en el Escritorio
$WshShell = New-Object -ComObject WScript.Shell
$DesktopPath = [System.Environment]::GetFolderPath('Desktop')
$ShortcutPath = Join-Path -Path $DesktopPath -ChildPath "Vanshee.lnk"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$TargetExe = Join-Path -Path $ScriptDir -ChildPath "dist\Vanshee\Vanshee.exe"

if (Test-Path $TargetExe) {
    $Shortcut = $WshShell.CreateShortcut($ShortcutPath)
    $Shortcut.TargetPath = $TargetExe
    $Shortcut.WorkingDirectory = (Split-Path -Parent $TargetExe)
    $Shortcut.Description = "Vanshee - Asistente Autónomo de Windows"
    $Shortcut.Save()
    Write-Host "✅ Acceso directo creado exitosamente en tu Escritorio: $ShortcutPath" -ForegroundColor Green
} else {
    Write-Host "❌ No se encontró $TargetExe. Asegúrate de compilar el proyecto primero." -ForegroundColor Red
}
