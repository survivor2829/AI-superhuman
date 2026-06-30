$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backend = Join-Path $root "backend"
$sidecar = Join-Path $root "rpa-sidecar"
$desktop = Join-Path $root "desktop-client"

function Test-Port {
    param([int]$Port)
    $connection = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    return $null -ne $connection
}

function Wait-Http {
    param(
        [string]$Url,
        [int]$Seconds = 20
    )

    $deadline = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $deadline) {
        try {
            Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3 | Out-Null
            return $true
        } catch {
            Start-Sleep -Milliseconds 600
        }
    }
    return $false
}

function Start-UvicornApp {
    param(
        [string]$Name,
        [string]$WorkingDirectory,
        [int]$Port,
        [string]$OutLog,
        [string]$ErrLog
    )

    if (Test-Port -Port $Port) {
        Write-Host "$Name already listening on port $Port"
        return
    }

    Start-Process `
        -WindowStyle Hidden `
        -FilePath python `
        -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$Port") `
        -WorkingDirectory $WorkingDirectory `
        -RedirectStandardOutput $OutLog `
        -RedirectStandardError $ErrLog

    Write-Host "Started $Name on port $Port"
}

function Start-DesktopPreview {
    if (Test-Port -Port 5173) {
        Write-Host "Desktop preview already listening on port 5173"
        return
    }

    $npm = Get-Command npm -ErrorAction SilentlyContinue
    if (-not $npm) {
        throw "npm was not found in PATH."
    }

    $npmSource = $npm.Source
    if ($npmSource.EndsWith(".ps1")) {
        Start-Process `
            -WindowStyle Hidden `
            -FilePath powershell.exe `
            -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $npmSource, "run", "dev", "--", "--host", "127.0.0.1", "--port", "5173") `
            -WorkingDirectory $desktop `
            -RedirectStandardOutput (Join-Path $desktop "vite.log") `
            -RedirectStandardError (Join-Path $desktop "vite.err.log")
    } else {
        Start-Process `
            -WindowStyle Hidden `
            -FilePath $npmSource `
            -ArgumentList @("run", "dev", "--", "--host", "127.0.0.1", "--port", "5173") `
            -WorkingDirectory $desktop `
            -RedirectStandardOutput (Join-Path $desktop "vite.log") `
            -RedirectStandardError (Join-Path $desktop "vite.err.log")
    }

    Write-Host "Started desktop preview on port 5173"
}

Start-UvicornApp `
    -Name "Backend" `
    -WorkingDirectory $backend `
    -Port 8710 `
    -OutLog (Join-Path $backend "backend.log") `
    -ErrLog (Join-Path $backend "backend.err.log")

Start-UvicornApp `
    -Name "RPA sidecar" `
    -WorkingDirectory $sidecar `
    -Port 8720 `
    -OutLog (Join-Path $sidecar "sidecar.log") `
    -ErrLog (Join-Path $sidecar "sidecar.err.log")

Start-DesktopPreview

$backendOk = Wait-Http -Url "http://127.0.0.1:8710/health"
$sidecarOk = Wait-Http -Url "http://127.0.0.1:8720/health"
$desktopOk = Wait-Http -Url "http://127.0.0.1:5173"

Write-Host ""
Write-Host "Agent MVP status:"
Write-Host "Backend       http://127.0.0.1:8710/docs      $backendOk"
Write-Host "RPA sidecar   http://127.0.0.1:8720/docs      $sidecarOk"
Write-Host "Desktop       http://127.0.0.1:5173           $desktopOk"
Write-Host ""
Write-Host "Logs are written under backend, rpa-sidecar, and desktop-client."
