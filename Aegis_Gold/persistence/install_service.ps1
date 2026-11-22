# AEGIS AUTO TRADING — WINDOWS SERVICE INSTALLATION
# Requires: NSSM (Non-Sucking Service Manager)
# Run as Administrator

param(
    [string]$Action = "install",  # install, uninstall, status, start, stop
    [string]$ServiceName = "AegisGoldBot"
)

# Check admin privileges
$currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($currentUser)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "ERROR: This script must run as Administrator" -ForegroundColor Red
    exit 1
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir
$PythonExe = "C:\Python\python.exe"  # Adjust path if needed
$MainScript = Join-Path $ProjectDir "start_aegis.py"
$LogDir = Join-Path $ProjectDir "logs"

# Ensure log directory exists
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir | Out-Null
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "AEGIS AUTO TRADING — SERVICE MANAGER"
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Service Name: $ServiceName"
Write-Host "Python Exe: $PythonExe"
Write-Host "Main Script: $MainScript"
Write-Host "Log Dir: $LogDir"
Write-Host ""

# Check if NSSM exists
$nssm = Get-Command nssm -ErrorAction SilentlyContinue
if (-not $nssm) {
    Write-Host "ERROR: NSSM (Non-Sucking Service Manager) not found" -ForegroundColor Red
    Write-Host ""
    Write-Host "Install NSSM:"
    Write-Host "  1. Download: https://nssm.cc/download"
    Write-Host "  2. Extract nssm.exe to C:\nssm\ or add to PATH"
    Write-Host "  3. Re-run this script"
    exit 1
}

Write-Host "✅ NSSM found: $(nssm -v)" -ForegroundColor Green
Write-Host ""

# Verify Python
if (-not (Test-Path $PythonExe)) {
    Write-Host "ERROR: Python not found at $PythonExe" -ForegroundColor Red
    Write-Host "Adjust the `$PythonExe path in this script"
    exit 1
}

Write-Host "✅ Python found: $($PythonExe | python --version 2>&1)" -ForegroundColor Green
Write-Host ""

# Verify main script
if (-not (Test-Path $MainScript)) {
    Write-Host "ERROR: Main script not found at $MainScript" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Main script found: $MainScript" -ForegroundColor Green
Write-Host ""

# Execute action
switch ($Action.ToLower()) {
    "install" {
        Write-Host "Installing service..." -ForegroundColor Yellow
        
        # Check if service already exists
        $serviceExists = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
        if ($serviceExists) {
            Write-Host "Service already exists. Removing first..." -ForegroundColor Yellow
            nssm remove $ServiceName confirm
            Start-Sleep -Seconds 2
        }
        
        # Install service
        Write-Host "Creating service..."
        nssm install $ServiceName $PythonExe $MainScript
        
        # Set working directory
        nssm set $ServiceName AppDirectory $ProjectDir
        
        # Set output log files
        nssm set $ServiceName AppStdout $(Join-Path $LogDir "stdout.log")
        nssm set $ServiceName AppStderr $(Join-Path $LogDir "stderr.log")
        
        # Fail-safe policy: never restart the bot automatically after exit.
        nssm set $ServiceName AppExit Default Exit
        
        # Rotating file settings
        nssm set $ServiceName AppRotateFiles 1
        nssm set $ServiceName AppRotateSeconds 86400  # 24 hours
        nssm set $ServiceName AppRotateBytes 10485760  # 10MB
        
        Write-Host ""
        Write-Host "✅ Service installed successfully" -ForegroundColor Green
        Write-Host ""
        Write-Host "Next steps:"
        Write-Host "  Start service: nssm start $ServiceName"
        Write-Host "  Check status: nssm status $ServiceName"
        Write-Host "  View logs: Get-Content $(Join-Path $LogDir 'stdout.log') -Wait"
    }
    
    "uninstall" {
        Write-Host "Removing service $ServiceName..." -ForegroundColor Yellow
        
        $serviceExists = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
        if ($serviceExists) {
            # Stop service first
            Write-Host "Stopping service..."
            try {
                Stop-Service -Name $ServiceName -Force -ErrorAction Stop
                Start-Sleep -Seconds 2
            } catch {
                Write-Host "Could not stop service: $_" -ForegroundColor Yellow
            }
            
            # Remove service
            nssm remove $ServiceName confirm
            Write-Host "✅ Service removed" -ForegroundColor Green
        } else {
            Write-Host "Service not found: $ServiceName" -ForegroundColor Yellow
        }
    }
    
    "status" {
        $status = nssm status $ServiceName
        Write-Host "Service Status: $status" -ForegroundColor Cyan
        
        $service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
        if ($service) {
            Write-Host "State: $($service.Status)" -ForegroundColor Green
        }
    }
    
    "start" {
        Write-Host "Starting service..." -ForegroundColor Yellow
        nssm start $ServiceName
        Start-Sleep -Seconds 2
        $status = nssm status $ServiceName
        Write-Host "✅ Service started. Status: $status" -ForegroundColor Green
    }
    
    "stop" {
        Write-Host "Stopping service..." -ForegroundColor Yellow
        nssm stop $ServiceName
        Start-Sleep -Seconds 2
        $status = nssm status $ServiceName
        Write-Host "✅ Service stopped. Status: $status" -ForegroundColor Green
    }
    
    default {
        Write-Host "Usage: .\install_service.ps1 -Action <install|uninstall|status|start|stop>" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
