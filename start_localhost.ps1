param(
    [switch]$SiteOnly,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"

$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $projectDir "scripts\local_network.ps1")
$pythonExe = Join-Path $projectDir ".venv\Scripts\python.exe"
$siteUrl = "http://127.0.0.1:8000/"
$lanAddresses = @(Get-GameBATLanAddresses)
$lanIp = $lanAddresses | Select-Object -First 1
$networkUrl = if ($lanIp) { "http://${lanIp}:8000/" } else { $siteUrl }
$serverUrls = @($siteUrl) + @($lanAddresses | ForEach-Object { "http://${_}:8000/" })

function Test-AllGameBATAddresses {
    foreach ($url in $serverUrls) {
        if (-not (Test-GameBATServer -Url $url)) { return $false }
    }
    return $true
}

function Stop-StaleGameBATServer {
    Get-GameBATServerProcesses -ProjectDir $projectDir | ForEach-Object {
        Stop-Process -Id $_.ProcessId -ErrorAction SilentlyContinue
    }
    Start-Sleep -Milliseconds 300
}

if (-not (Test-Path -LiteralPath $pythonExe)) {
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show(
        "Не найден Python проекта: $pythonExe",
        "GameBAT CRM"
    ) | Out-Null
    exit 1
}

if (-not (Test-AllGameBATAddresses)) {
    Stop-StaleGameBATServer
    $allowedHosts = @("localhost", "127.0.0.1") + $lanAddresses
    $allowedHosts += @($env:DJANGO_ALLOWED_HOSTS -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ })
    $env:DJANGO_ALLOWED_HOSTS = ($allowedHosts | Select-Object -Unique) -join ","
    $runtimeDir = Join-Path $projectDir "outputs\localhost"
    New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null
    $logPrefix = Join-Path $runtimeDir (Get-Date -Format "yyyyMMdd_HHmmss_fff")
    Start-Process `
        -FilePath $pythonExe `
        -ArgumentList @("-u", "manage.py", "runserver", "0.0.0.0:8000", "--noreload") `
        -WorkingDirectory $projectDir `
        -WindowStyle Hidden `
        -RedirectStandardOutput "$logPrefix.stdout.log" `
        -RedirectStandardError "$logPrefix.stderr.log"

    $started = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        Start-Sleep -Milliseconds 300
        if (Test-AllGameBATAddresses) {
            $started = $true
            break
        }
    }

    if (-not $started) {
        Add-Type -AssemblyName PresentationFramework
        [System.Windows.MessageBox]::Show(
            "Не удалось запустить локальный сервер на порту 8000. Журналы: $runtimeDir",
            "GameBAT CRM"
        ) | Out-Null
        exit 1
    }
}

if (-not $SiteOnly) {
    $runtimeDir = Join-Path $projectDir 'outputs\localhost'
    New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null
    foreach ($service in @('avito', 'yandex', 'google')) {
        if (-not (Test-GameBATIntegrationWorker -ProjectDir $projectDir -Service $service)) {
            $workerLogPrefix = Join-Path $runtimeDir ((Get-Date -Format 'yyyyMMdd_HHmmss_fff') + "_${service}_worker")
            Start-Process -FilePath $pythonExe `
                -ArgumentList @('-u', 'manage.py', 'run_integration_worker', '--service', $service) `
                -WorkingDirectory $projectDir -WindowStyle Hidden `
                -RedirectStandardOutput "$workerLogPrefix.stdout.log" `
                -RedirectStandardError "$workerLogPrefix.stderr.log"
        }
    }
}

Write-Output "CRM: $networkUrl"
if (-not $SiteOnly) {
    $escapedProjectDir = [Regex]::Escape($projectDir)
    $printWorker = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_.CommandLine -match $escapedProjectDir -and $_.CommandLine -match 'manage\.py run_label_print_worker\s*$'
    } | Select-Object -First 1
    if (-not $printWorker) {
        Start-Process -FilePath $pythonExe -ArgumentList @('manage.py', 'run_label_print_worker') `
            -WorkingDirectory $projectDir -WindowStyle Hidden
    }
}
if (-not $NoBrowser) { Start-Process $networkUrl }
