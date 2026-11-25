Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
ScriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = ScriptDir

PythonwPath = ScriptDir & "\.venv\Scripts\pythonw.exe"
RunUiPath = ScriptDir & "\run_ui.py"
DistExe = ScriptDir & "\dist\Vanshee\Vanshee.exe"

If fso.FileExists(PythonwPath) Then
    WshShell.Run """" & PythonwPath & """ """ & RunUiPath & """", 0, False
ElseIf fso.FileExists(DistExe) Then
    WshShell.CurrentDirectory = ScriptDir & "\dist\Vanshee"
    WshShell.Run """" & DistExe & """", 0, False
Else
    UserProf = WshShell.ExpandEnvironmentStrings("%USERPROFILE%")
    For Each pyVer In Array("Python311", "Python312", "Python313", "Python310")
        cand = UserProf & "\AppData\Local\Programs\Python\" & pyVer & "\pythonw.exe"
        If fso.FileExists(cand) Then
            WshShell.Run """" & cand & """ """ & RunUiPath & """", 0, False
            Exit For
        End If
    Next
End If
