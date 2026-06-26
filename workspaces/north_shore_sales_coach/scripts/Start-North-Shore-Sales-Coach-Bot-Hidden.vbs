Option Explicit

Dim shell
Dim fso
Dim scriptDirectory
Dim launcher
Dim command

Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

scriptDirectory = fso.GetParentFolderName(WScript.ScriptFullName)
launcher = fso.BuildPath(scriptDirectory, "Start-North-Shore-Sales-Coach-Bot.ps1")
command = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File " & Chr(34) & launcher & Chr(34)

shell.Run command, 0, False
