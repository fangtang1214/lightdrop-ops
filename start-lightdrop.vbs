Option Explicit

Dim shell
Dim fso
Dim projectDir
Dim electronPath
Dim mainPath
Dim command

Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

projectDir = fso.GetParentFolderName(WScript.ScriptFullName)
electronPath = fso.BuildPath(projectDir, "node_modules\electron\dist\electron.exe")
mainPath = fso.BuildPath(projectDir, "apps\desktop\main.js")

If Not fso.FileExists(electronPath) Then
  MsgBox "Electron was not found." & vbCrLf & "Please run start-lightdrop-debug.cmd or reinstall dependencies.", vbExclamation, "LightDrop startup failed"
  WScript.Quit 1
End If

If Not fso.FileExists(mainPath) Then
  MsgBox "Launcher entry was not found:" & vbCrLf & mainPath, vbExclamation, "LightDrop startup failed"
  WScript.Quit 1
End If

command = """" & electronPath & """ """ & mainPath & """"

shell.CurrentDirectory = projectDir
shell.Run command, 1, False
