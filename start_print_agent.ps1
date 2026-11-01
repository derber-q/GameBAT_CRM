param([switch]$Stop)
$ErrorActionPreference='Stop'
$projectDir=Split-Path -Parent $MyInvocation.MyCommand.Path
$stateDir=Join-Path $env:LOCALAPPDATA 'ReSOURCE\PrintAgent'
$config=Join-Path $stateDir 'config.json'
if (-not (Test-Path -LiteralPath $config)) {throw 'Сначала выполните setup_print_agent.ps1.'}
if ($Stop) {
    Set-Content -LiteralPath (Join-Path $stateDir 'stop-request') -Value 'stop' -Encoding ASCII
    Write-Output 'Запрошено завершение агента после текущей операции.'
    exit 0
}
$pattern=[Regex]::Escape($config)
$running=@(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $_.Name -match '^python' -and $_.CommandLine -match '-m\s+print_agent(?:\s|$)' -and $_.CommandLine -match $pattern
})
if ($running.Count) {Write-Output 'Print Agent уже работает.';exit 0}
$log=Join-Path $stateDir ('agent_'+(Get-Date -Format 'yyyyMMdd_HHmmss'))
$env:PYTHONIOENCODING='utf-8'
Start-Process -FilePath (Join-Path $projectDir '.venv/Scripts/python.exe') `
    -ArgumentList @('-u','-m','print_agent','--config',('"'+$config+'"')) `
    -WorkingDirectory $projectDir -WindowStyle Hidden `
    -RedirectStandardOutput ($log+'.out.log') -RedirectStandardError ($log+'.err.log')
Write-Output 'Print Agent запущен. Состояние доступно на странице «Обработчики».'
