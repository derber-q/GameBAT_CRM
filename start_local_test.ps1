param(
    [ValidateRange(1024,65535)][int]$Port = 8001,
    [ValidatePattern('^[a-zA-Z0-9_-]{1,40}$')][string]$Instance = 'default',
    [switch]$Initialize,
    [switch]$NoBrowser
)
$ErrorActionPreference = 'Stop'
if ($Port -eq 8000) { throw 'Порт 8000 зарезервирован для рабочей CRM.' }
$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonExe = Join-Path $projectDir '.venv\Scripts\python.exe'
$env:GAMEBAT_TEST_ROOT = Join-Path $projectDir "outputs\local_test\$Instance"
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONDONTWRITEBYTECODE = '1'
if (-not (Test-Path -LiteralPath $pythonExe)) { throw 'Не найден Python проекта.' }
$siteUrl = "http://127.0.0.1:$Port/"
# Порт проверяется до migrate: чужой или рабочий сервер не останавливается.
$listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $Port)
try { $listener.Start() } catch { throw 'Тестовый порт занят. Выберите другой порт; существующие процессы сохранены.' }
finally { $listener.Stop() }
if ($Initialize) {
    & $pythonExe -m GameBAT_CRM.local_test migrate --noinput
    if ($LASTEXITCODE -ne 0) { throw 'Не удалось инициализировать тестовую БД.' }
    & $pythonExe -m GameBAT_CRM.local_test initialize_local_test
    if ($LASTEXITCODE -ne 0) { throw 'Не удалось создать учебную учётную запись.' }
}
& $pythonExe -m GameBAT_CRM.local_test migrate --check
if ($LASTEXITCODE -ne 0) { throw 'Тестовая БД не готова. Выполните отдельный запуск с -Initialize.' }
$runtimeDir = Join-Path $env:GAMEBAT_TEST_ROOT 'logs'
$prefix = Join-Path $runtimeDir (Get-Date -Format 'yyyyMMdd_HHmmss_fff')
Start-Process -FilePath $pythonExe -ArgumentList @('-m','GameBAT_CRM.local_test','runserver',"127.0.0.1:$Port",'--noreload','--insecure') -WorkingDirectory $projectDir -WindowStyle Hidden -RedirectStandardOutput "$prefix.stdout.log" -RedirectStandardError "$prefix.stderr.log"
$ready = $false
for ($attempt=0; $attempt -lt 30; $attempt++) {
    Start-Sleep -Milliseconds 500
    $response = $null
    try {
        $probe = [System.Net.HttpWebRequest]::Create($siteUrl + 'crm/accounts/login/')
        $probe.Proxy = $null
        $probe.Timeout = 1000
        $response = $probe.GetResponse()
        if ($response.Headers['X-GameBAT-Environment'] -eq 'local_test') { $ready=$true; break }
    } catch { } finally { if ($response) { $response.Close() } }
}
if (-not $ready) { throw "Тестовый сервер не подтвердил готовность. Журнал: $prefix.stderr.log" }
Write-Output "ТЕСТОВЫЙ РЕЖИМ: $siteUrl"
Write-Output "Учебный логин: outputs/local_test/$Instance/secrets/test-admin.json"
if (-not $NoBrowser) { Start-Process $siteUrl }
