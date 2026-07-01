$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backend = Join-Path $root "backend"
$sidecar = Join-Path $root "rpa-sidecar"
$desktop = Join-Path $root "desktop-client"

function Import-DotEnv {
    $envPath = Join-Path $root ".env"
    if (-not (Test-Path $envPath)) {
        return
    }

    Get-Content -Path $envPath -Encoding UTF8 | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) {
            return
        }
        $name, $value = $line.Split("=", 2)
        $name = $name.Trim()
        $value = $value.Trim().Trim('"').Trim("'")
        if ($name) {
            [Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
}

function Stop-PortProcess {
    param(
        [int]$Port,
        [string]$Name
    )

    $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    foreach ($connection in $connections) {
        $ownerPid = [int]$connection.OwningProcess
        if ($ownerPid -le 0 -or $ownerPid -eq $PID) {
            continue
        }
        try {
            Stop-Process -Id $ownerPid -Force -ErrorAction Stop
            Write-Host "Stopped stale $Name process $ownerPid on port $Port"
        } catch {
            Write-Host "Could not stop $Name process $ownerPid on port $Port"
        }
    }
}

function Stop-DesktopApp {
    $electronProcesses = Get-CimInstance Win32_Process -Filter "name = 'electron.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like "*$desktop*" }
    foreach ($process in $electronProcesses) {
        try {
            Stop-Process -Id $process.ProcessId -Force -ErrorAction Stop
            Write-Host "Stopped stale desktop app process $($process.ProcessId)"
        } catch {
            Write-Host "Could not stop desktop app process $($process.ProcessId)"
        }
    }

    $nodeProcesses = Get-CimInstance Win32_Process -Filter "name = 'node.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like "*$desktop*" -and ($_.CommandLine -like "*electron*" -or $_.CommandLine -like "*vite*") }
    foreach ($process in $nodeProcesses) {
        try {
            Stop-Process -Id $process.ProcessId -Force -ErrorAction Stop
            Write-Host "Stopped stale desktop helper process $($process.ProcessId)"
        } catch {
            Write-Host "Could not stop desktop helper process $($process.ProcessId)"
        }
    }
}

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

function Start-DesktopApp {
    $existing = Get-CimInstance Win32_Process -Filter "name = 'electron.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like "*$desktop*" }
    if ($existing) {
        Write-Host "Desktop app already running"
        return
    }

    $electronExe = Join-Path $desktop "node_modules\electron\dist\electron.exe"
    if (Test-Path $electronExe) {
        Start-Process `
            -FilePath $electronExe `
            -ArgumentList @(".") `
            -WorkingDirectory $desktop
        Write-Host "Started desktop app"
        return
    }

    $npm = Get-Command npm -ErrorAction SilentlyContinue
    if (-not $npm) {
        throw "npm was not found in PATH, and Electron binary was not found. Run npm install in desktop-client."
    }

    $npmSource = $npm.Source
    if ($npmSource.EndsWith(".ps1")) {
        Start-Process `
            -FilePath powershell.exe `
            -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $npmSource, "run", "electron") `
            -WorkingDirectory $desktop `
            -RedirectStandardOutput (Join-Path $desktop "electron-main.log") `
            -RedirectStandardError (Join-Path $desktop "electron-main.err.log")
    } else {
        Start-Process `
            -FilePath $npmSource `
            -ArgumentList @("run", "electron") `
            -WorkingDirectory $desktop `
            -RedirectStandardOutput (Join-Path $desktop "electron-main.log") `
            -RedirectStandardError (Join-Path $desktop "electron-main.err.log")
    }

    Write-Host "Started desktop app"
}

Import-DotEnv

Stop-DesktopApp
Stop-PortProcess -Port 8710 -Name "Backend"
Stop-PortProcess -Port 8720 -Name "RPA sidecar"
Stop-PortProcess -Port 5173 -Name "Desktop renderer"

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
Start-DesktopApp

$backendOk = Wait-Http -Url "http://127.0.0.1:8710/health"
$sidecarOk = Wait-Http -Url "http://127.0.0.1:8720/health"
$desktopOk = Wait-Http -Url "http://127.0.0.1:5173"

Write-Host ""
Write-Host "Agent MVP status:"
Write-Host "Backend       http://127.0.0.1:8710/docs      $backendOk"
Write-Host "RPA sidecar   http://127.0.0.1:8720/docs      $sidecarOk"
Write-Host "Desktop       http://127.0.0.1:5173           $desktopOk"
Write-Host "Desktop app   Electron window                 started"
Write-Host ""
Write-Host "Logs are written under backend, rpa-sidecar, and desktop-client."
