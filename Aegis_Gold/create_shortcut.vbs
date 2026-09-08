Set WshShell = WScript.CreateObject("WScript.Shell")
strDesktop = WshShell.SpecialFolders("Desktop")
Set oShellLink = WshShell.CreateShortcut(strDesktop & "\Start Aegis Gold.lnk")
oShellLink.TargetPath = "D:\Trading\run_aegis.bat"
oShellLink.WorkingDirectory = "D:\Trading"
oShellLink.Description = "Launch MetaTrader 5, Aegis Gold Bot and Dashboard UI"
oShellLink.Save
WScript.Echo "Shortcut created successfully on your Desktop!"
