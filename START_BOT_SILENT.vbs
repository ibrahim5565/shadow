' ====================================================================
' AEGIS / BOT SILENT LAUNCHER
' Launches the bot batch script in the background with hidden window (0)
' ====================================================================
Set WshShell = CreateObject("WScript.Shell")
Dim scriptDir
scriptDir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)

' Run START_AEGIS.bat or run_aegis.bat silently
WshShell.Run """" & scriptDir & "\run_aegis.bat""", 0, False
Set WshShell = Nothing
