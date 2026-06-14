# Run this script as Administrator (right-click → "Run as Administrator")
# It installs WSL2 + Docker Desktop to D:\Program Files\Docker

#Requires -RunAsAdministrator

$ErrorActionPreference = "Stop"
$dockerInstallDir = "D:\Program Files\Docker"
$installerPath    = "D:\Temp\DockerDesktopInstaller.exe"

Write-Host "=== Anchor AI — Docker Setup ===" -ForegroundColor Cyan

# 1. Enable Windows features needed for WSL2
Write-Host "`n[1/4] Enabling VirtualMachinePlatform..." -ForegroundColor Yellow
$vmFeature = Get-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform
if ($vmFeature.State -ne "Enabled") {
    Enable-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform -NoRestart | Out-Null
    Write-Host "     Enabled VirtualMachinePlatform" -ForegroundColor Green
} else {
    Write-Host "     Already enabled" -ForegroundColor Gray
}

$wslFeature = Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Windows-Subsystem-Linux
if ($wslFeature.State -ne "Enabled") {
    Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Windows-Subsystem-Linux -NoRestart | Out-Null
    Write-Host "     Enabled WSL feature" -ForegroundColor Green
}

# 2. Install WSL2 kernel via winget
Write-Host "`n[2/4] Installing WSL2 kernel..." -ForegroundColor Yellow
try {
    winget install --id Microsoft.WSL --accept-package-agreements --accept-source-agreements --silent 2>&1 | Out-Null
    Write-Host "     WSL2 installed" -ForegroundColor Green
} catch {
    Write-Host "     WSL2 might already be installed or needs a restart first — continuing" -ForegroundColor Gray
}

# 3. Download Docker Desktop installer
Write-Host "`n[3/4] Downloading Docker Desktop installer to D:\Temp..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force "D:\Temp" | Out-Null
if (-not (Test-Path $installerPath)) {
    $url = "https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe"
    Write-Host "     Downloading (~600 MB, please wait)..." -ForegroundColor Gray
    Invoke-WebRequest -Uri $url -OutFile $installerPath -UseBasicParsing
    Write-Host "     Download complete" -ForegroundColor Green
} else {
    Write-Host "     Installer already downloaded, skipping" -ForegroundColor Gray
}

# 4. Install Docker Desktop to D:\
Write-Host "`n[4/4] Installing Docker Desktop to $dockerInstallDir ..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force $dockerInstallDir | Out-Null
$installArgs = "install --quiet --accept-license --installation-dir=`"$dockerInstallDir`""
$proc = Start-Process -FilePath $installerPath -ArgumentList $installArgs -Wait -PassThru
if ($proc.ExitCode -eq 0) {
    Write-Host "     Docker Desktop installed successfully!" -ForegroundColor Green
} else {
    Write-Host "     Installer exited with code $($proc.ExitCode)" -ForegroundColor Red
    Write-Host "     Try running the installer manually from: $installerPath" -ForegroundColor Yellow
}

Write-Host "`n=== Done! ===" -ForegroundColor Cyan
Write-Host "A RESTART may be required for WSL2 to activate." -ForegroundColor Yellow
Write-Host "After restart:" -ForegroundColor White
Write-Host "  1. Open Docker Desktop (D:\Program Files\Docker\Docker Desktop.exe)" -ForegroundColor White
Write-Host "  2. Wait for it to finish initializing (~2 min on first launch)" -ForegroundColor White
Write-Host "  3. Come back to Claude Code and run: .\scripts.ps1 dev" -ForegroundColor White

Read-Host "`nPress Enter to exit"
