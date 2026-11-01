param(
    [Parameter(Mandatory)][string]$ServerUrl,
    [string]$PrinterName,
    [string]$RegisterDocker,
    [switch]$Rotate
)
$ErrorActionPreference='Stop'
$projectDir=Split-Path -Parent $MyInvocation.MyCommand.Path
$stateDir=Join-Path $env:LOCALAPPDATA 'ReSOURCE\PrintAgent'
New-Item -ItemType Directory -Path $stateDir -Force | Out-Null
# Секрет и локальный журнал доступны только текущему пользователю и SYSTEM.
$identity=[System.Security.Principal.WindowsIdentity]::GetCurrent().User
$acl=New-Object System.Security.AccessControl.DirectorySecurity
$acl.SetOwner($identity)
$acl.SetAccessRuleProtection($true,$false)
$inherit=[System.Security.AccessControl.InheritanceFlags]'ContainerInherit,ObjectInherit'
$propagation=[System.Security.AccessControl.PropagationFlags]::None
$allow=[System.Security.AccessControl.AccessControlType]::Allow
$acl.AddAccessRule((New-Object System.Security.AccessControl.FileSystemAccessRule($identity,'FullControl',$inherit,$propagation,$allow)))
$system=New-Object System.Security.Principal.SecurityIdentifier('S-1-5-18')
$acl.AddAccessRule((New-Object System.Security.AccessControl.FileSystemAccessRule($system,'FullControl',$inherit,$propagation,$allow)))
Set-Acl -LiteralPath $stateDir -AclObject $acl
if (-not $PrinterName) {
    $PrinterName=(Get-Content -LiteralPath (Join-Path $projectDir '.label-printer.json') -Encoding UTF8 | ConvertFrom-Json).printer_name
}
$arguments=@('-m','print_agent.setup','--server-url',$ServerUrl,'--printer',$PrinterName)
if ($RegisterDocker) {$arguments+=@('--register-docker',$RegisterDocker)}
if ($Rotate) {$arguments+='--rotate'}
Push-Location $projectDir
try {
    & (Join-Path $projectDir '.venv/Scripts/python.exe') @arguments
    if ($LASTEXITCODE -ne 0) {throw 'Настройка агента не завершилась.'}
} finally {Pop-Location}
