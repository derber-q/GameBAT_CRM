param([switch]$NoBrowser, [switch]$Restart)

$ErrorActionPreference = 'Stop'
$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $projectDir 'scripts/local_network.ps1')
$runtime = Join-Path $projectDir 'outputs/local_container'
New-Item -ItemType Directory -Path $runtime -Force | Out-Null

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'Не найден Docker CLI.' }
$native = @(Get-GameBATServerProcesses -ProjectDir $projectDir)
$native += @(Get-GameBATWorkerProcesses -ProjectDir $projectDir)
if ($native.Count) {
    throw 'Сначала остановите нативный сайт и worker этой CRM. Одновременно Windows и контейнер не должны писать в одну SQLite.'
}
foreach ($name in @('db.sqlite3','.django-secret-key','.integration-encryption-key','.resource-token-encryption-key')) {
    if (-not (Test-Path -LiteralPath (Join-Path $projectDir $name) -PathType Leaf)) {
        throw "Отсутствует рабочий файл $name. Пустая БД и новые ключи автоматически не создаются."
    }
}

$lan = @(Get-GameBATLanAddresses)
$env:GAMEBAT_LOCAL_ALLOWED_HOSTS = (@('localhost','127.0.0.1') + $lan | Select-Object -Unique) -join ','
$composeArgs = @('compose','-f',(Join-Path $projectDir 'deploy/local_live/compose.yaml'))
$googleOverride = Join-Path $runtime 'google.compose.json'
if ($env:GOOGLE_SERVICE_ACCOUNT_FILE) {
    $googleFile = (Resolve-Path -LiteralPath $env:GOOGLE_SERVICE_ACCOUNT_FILE).Path
    $config = @{services=@{'crm-local'=@{
        volumes=@(@{type='bind';source=$googleFile;target='/run/secrets/google-service-account.json';read_only=$true;bind=@{create_host_path=$false}})
        environment=@{GOOGLE_SERVICE_ACCOUNT_FILE='/run/secrets/google-service-account.json'}
    }}}
    $config | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $googleOverride -Encoding UTF8
}
if (Test-Path -LiteralPath $googleOverride) { $composeArgs += @('-f',$googleOverride) }

& docker @composeArgs config --quiet
if ($LASTEXITCODE -ne 0) { throw 'Неверная конфигурация рабочего контейнера.' }
# Метка позволяет старому ярлыку проверить владельца БД до любых обращений Django.
@{container='resource-crm-local';database=(Join-Path $projectDir 'db.sqlite3')} |
    ConvertTo-Json | Set-Content -LiteralPath (Join-Path $runtime 'owner.json') -Encoding UTF8
& docker @composeArgs up -d
if ($LASTEXITCODE -ne 0) { throw 'Не удалось запустить рабочий контейнер.' }
if ($Restart) {
    & docker @composeArgs restart crm-local
    if ($LASTEXITCODE -ne 0) { throw 'Не удалось перезапустить рабочий контейнер.' }
}
$ready = $false
for ($attempt=0; $attempt -lt 60; $attempt++) {
    if (Test-GameBATServer -Url 'http://127.0.0.1:8000/') { $ready=$true; break }
    Start-Sleep -Milliseconds 500
}
if (-not $ready) { throw 'Рабочий сайт пока не отвечает. Проверьте docker logs resource-crm-local.' }
Write-Output 'Рабочая CRM: http://127.0.0.1:8000/'
foreach ($ip in $lan) { Write-Output "LAN: http://${ip}:8000/" }
if (-not $NoBrowser) { Start-Process 'http://127.0.0.1:8000/' }
