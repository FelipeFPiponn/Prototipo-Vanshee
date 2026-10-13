Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
ScriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = ScriptDir

PythonwPath = ScriptDir & "\.venv\Scripts\pythonw.exe"
RunUiPath = ScriptDir & "\run_ui.py"

' El parametro 0 indica que la ejecucion es 100% oculta sin ventana negra de consola
WshShell.Run """" & PythonwPath & """ """ & RunUiPath & """", 0, False
