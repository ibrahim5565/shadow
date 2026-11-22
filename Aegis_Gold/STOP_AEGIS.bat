@echo off
title AEGIS-GOLD - EMERGENCY STOP
color 0C
echo.
echo AEGIS-GOLD - TARGETED EMERGENCY STOP
echo.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$root = [IO.Path]::GetFullPath((Get-Location).Path); " ^
  "$procs = Get-CimInstance Win32_Process | Where-Object { " ^
  "($_.Name -in @('python.exe','pythonw.exe')) -and $_.CommandLine -and $_.CommandLine.Contains($root) }; " ^
  "$procs | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }; " ^
  "Write-Host ('Stopped ' + @($procs).Count + ' Aegis Python process(es).')"
if exist "data\bot.lock" del /f "data\bot.lock"
if exist "data\watchdog.lock" del /f "data\watchdog.lock"
if exist "data\daemon.lock" del /f "data\daemon.lock"
echo.
echo Emergency stop command completed. Verify Aegis processes in Task Manager.
pause
