@echo off
REM Clear all log files in Aegis_Gold\logs
set LOG_DIR="d:\\Trading\\Aegis_Gold\\logs"
echo Deleting log files in %LOG_DIR%
del /Q %LOG_DIR%\*.*
echo Log files cleared.
