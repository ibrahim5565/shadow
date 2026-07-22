@echo off
title AEGIS VPS CONTROL — AUTOSTART INSTALLER
cls
echo.
echo  ============================================================
echo    AEGIS VPS CONTROL — AUTOSTART INSTALLER
echo  ============================================================
echo.

:: Check for administrative privileges
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo  [ERROR] This installer requires Administrator privileges!
    echo  Please right-click this batch file and select "Run as administrator".
    echo.
    pause
    exit /b 1
)

:: Create the scheduled task to trigger on logon
echo  [+] Registering Aegis Startup sequence in Windows Task Scheduler...
schtasks /create /tn "AegisVPSStartup" /tr "D:\Trading\Aegis_Gold\START_VPS_SERVICES.bat" /sc onlogon /rl highest /f

if %errorlevel% equ 0 (
    echo.
    echo  [SUCCESS] Aegis Autostart Task registered successfully!
    echo            The system will automatically start on user logon.
    echo            (Ensure your Windows VPS is set to auto-logon the user on boot).
    echo.
) else (
    echo.
    echo  [ERROR] Failed to register task in Task Scheduler. Status: %errorlevel%
    echo.
)

pause
