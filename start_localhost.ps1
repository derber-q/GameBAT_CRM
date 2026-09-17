$ErrorActionPreference = "Stop"

$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonExe = Join-Path $projectDir ".venv\Scripts\python.exe"
$siteUrl = "http://127.0.0.1:8000/"
$lanConfiguration = Get-NetIPConfiguration -ErrorAction SilentlyContinue | Where-Object {
    $_.NetAdapter.Status -eq "Up" `
        -and $_.IPv4DefaultGateway `
        -and $_.InterfaceAlias -notmatch "(?i)vpn|tun|tap|loopback"
} | Select-Object -First 1
$lanIp = if ($lanConfiguration) { $lanConfiguration.IPv4Address.IPAddress } else { $null }
$networkUrl = if ($lanIp) { "http://${lanIp}:8000/" } else { $siteUrl }

function Test-GameBATServer {
    try {
        Invoke-WebRequest -Uri $networkUrl -UseBasicParsing -TimeoutSec 1 | Out-Null
        return $true
    }
    catch {
        return $false
    }
}

function Stop-StaleGameBATServer {
    $escapedProjectDir = [Regex]::Escape($projectDir)
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_.Name -match "^python" `
            -and $_.CommandLine -match $escapedProjectDir `
            -and $_.CommandLine -match "manage\.py runserver"
    } | ForEach-Object {
        Stop-Process -Id $_.ProcessId -ErrorAction SilentlyContinue
    }
    Start-Sleep -Milliseconds 300
}

function Test-IntegrationWorker {
    $escapedProjectDir = [Regex]::Escape($projectDir)
    return [bool](Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_.CommandLine -match $escapedProjectDir -and $_.CommandLine -match "run_integration_worker"
    } | Select-Object -First 1)
}

if (-not (Test-Path -LiteralPath $pythonExe)) {
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show(
        "Не найден Python проекта: $pythonExe",
        "GameBAT CRM"
    ) | Out-Null
    exit 1
}

if (-not (Test-GameBATServer)) {
    Stop-StaleGameBATServer
    $allowedHosts = @("localhost", "127.0.0.1")
    if ($lanIp) { $allowedHosts += $lanIp }
    $env:DJANGO_ALLOWED_HOSTS = $allowedHosts -join ","
    Start-Process `
        -FilePath $pythonExe `
        -ArgumentList @("manage.py", "runserver", "0.0.0.0:8000", "--noreload") `
        -WorkingDirectory $projectDir `
        -WindowStyle Hidden

    $started = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        Start-Sleep -Milliseconds 300
        if (Test-GameBATServer) {
            $started = $true
            break
        }
    }

    if (-not $started) {
        Add-Type -AssemblyName PresentationFramework
        [System.Windows.MessageBox]::Show(
            "Не удалось запустить локальный сервер на порту 8000.",
            "GameBAT CRM"
        ) | Out-Null
        exit 1
    }
}

if (-not (Test-IntegrationWorker)) {
    Start-Process `
        -FilePath $pythonExe `
        -ArgumentList @("manage.py", "run_integration_worker") `
        -WorkingDirectory $projectDir `
        -WindowStyle Hidden
}

Start-Process $networkUrl
