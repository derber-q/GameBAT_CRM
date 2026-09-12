$ErrorActionPreference = "Stop"

$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonExe = Join-Path $projectDir ".venv\Scripts\python.exe"
$siteUrl = "http://127.0.0.1:8000/"

function Test-GameBATServer {
    try {
        Invoke-WebRequest -Uri $siteUrl -UseBasicParsing -TimeoutSec 1 | Out-Null
        return $true
    }
    catch {
        return $false
    }
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
    Start-Process `
        -FilePath $pythonExe `
        -ArgumentList @("manage.py", "runserver", "127.0.0.1:8000", "--noreload") `
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

Start-Process $siteUrl
