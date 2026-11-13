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
$env:GAMEBAT_LOCAL_CRM_URL = if ($lan.Count) { "http://$($lan[0]):8000" } else { 'http://127.0.0.1:8000' }
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
# Только отдельный volume и зашифрованные архивы; DB/WAL/SHM не монтируются
# в служебный контейнер и не заменяются при обновлении.
& docker volume create resource-crm-backups | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Не удалось подготовить хранилище резервных копий.' }
$legacyBackups = Join-Path $projectDir '.local-backup-cache'
New-Item -ItemType Directory -Path $legacyBackups -Force | Out-Null
$storageScript = Join-Path $projectDir 'scripts/prepare_backup_storage.py'
& docker run --rm --network none --read-only --user 0:0 --cap-drop ALL --cap-add CHOWN --cap-add FOWNER `
    --mount 'type=volume,source=resource-crm-backups,target=/backup' `
    --mount "type=bind,source=$legacyBackups,target=/legacy,readonly" `
    --mount "type=bind,source=$storageScript,target=/prepare.py,readonly" `
    --entrypoint python resource-crm-local:current /prepare.py
if ($LASTEXITCODE -ne 0) { throw 'Архивы не перенесены безопасно. Рабочий контейнер не переключён.' }
# Метка позволяет старому ярлыку проверить владельца БД до любых обращений Django.
@{container='resource-crm-local';database=(Join-Path $projectDir 'db.sqlite3')} |
    ConvertTo-Json | Set-Content -LiteralPath (Join-Path $runtime 'owner.json') -Encoding UTF8
& docker @composeArgs up -d
if ($LASTEXITCODE -ne 0) { throw 'Не удалось запустить рабочий контейнер.' }
if ($Restart) {
    & docker @composeArgs restart crm-local
    if ($LASTEXITCODE -ne 0) { throw 'Не удалось перезапустить рабочий контейнер.' }
}
$agentConfig = Join-Path $env:LOCALAPPDATA 'ReSOURCE\PrintAgent\config.json'
if (Test-Path -LiteralPath $agentConfig -PathType Leaf) {
    try { & (Join-Path $projectDir 'start_print_agent.ps1') }
    catch { Write-Warning 'Не удалось запустить Windows-агент печати. Проверьте страницу «Обработчики».' }
}
$ready = $false
for ($attempt=0; $attempt -lt 180; $attempt++) {
    if (Test-GameBATServer -Url 'http://127.0.0.1:8000/') { $ready=$true; break }
    if (($attempt % 15) -eq 0) { Write-Output 'Ожидается запуск сайта в контейнере...' }
    Start-Sleep -Seconds 1
}
if (-not $ready) { throw 'Рабочий сайт пока не отвечает. Проверьте docker logs resource-crm-local.' }
Write-Output 'Рабочая CRM: http://127.0.0.1:8000/'
$workersReady = $false
for ($attempt=0; $attempt -lt 12; $attempt++) {
    $health = & docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}missing{{end}}' resource-crm-local
    if ($LASTEXITCODE -eq 0 -and $health -eq 'healthy') { $workersReady=$true; break }
    Write-Output 'Сайт доступен. Ожидается подтверждение рабочих циклов обработчиков и связи ботов...'
    Start-Sleep -Seconds 15
}
if ($workersReady) { Write-Output 'Необходимые обработчики и боты подтвердили работу.' }
else { Write-Warning 'Сайт запущен, но работа всех обработчиков пока не подтверждена. Откройте «Интеграции → Обработчики».' }
foreach ($ip in $lan) { Write-Output "LAN: http://${ip}:8000/" }
if (-not $NoBrowser) { Start-Process 'http://127.0.0.1:8000/' }
