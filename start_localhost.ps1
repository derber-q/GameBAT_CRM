param(
    [switch]$SiteOnly,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"

$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
# После передачи БД контейнеру ярлык не должен запускать Windows-worker рядом с ним.
if (Test-Path -LiteralPath (Join-Path $projectDir 'outputs/local_container/owner.json')) {
    $containerState = & (Join-Path $projectDir '.venv/Scripts/python.exe') -c "import subprocess; r=subprocess.run(['docker','inspect','--format','{{.State.Running}}','resource-crm-local'],capture_output=True,text=True,timeout=15); print(r.stdout.strip() if r.returncode==0 else 'unknown')"
    if ($LASTEXITCODE -ne 0 -or $containerState -eq 'unknown') {
        throw 'Не удалось проверить владельца рабочей БД в Docker. Сначала проверьте resource-crm-local; нативный запуск отменён.'
    }
    if ($containerState -eq 'true') {
        Write-Output 'Рабочая CRM уже запущена в resource-crm-local: http://127.0.0.1:8000/'
        if (-not $NoBrowser) { Start-Process 'http://127.0.0.1:8000/' }
        exit 0
    }
}
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

$monitoringArgs = @('manage.py', 'configure_worker_monitoring')
if ($SiteOnly) { $monitoringArgs += '--site-only' }
& $pythonExe @monitoringArgs
if ($LASTEXITCODE -ne 0) { throw 'Не удалось настроить мониторинг обработчиков. Проверьте миграции.' }

if (-not $SiteOnly) {
    $runtimeDir = Join-Path $projectDir 'outputs\localhost'
    New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null
    # Только контроллер запускает worker. Его блокировка защищает от одновременных ярлыков.
    Start-GameBATSupervisor -ProjectDir $projectDir -PythonExe $pythonExe -RuntimeDir $runtimeDir
}

Write-Output "CRM: $networkUrl"
if (-not $NoBrowser) { Start-Process $networkUrl }
