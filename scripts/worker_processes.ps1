param([Parameter(Mandatory)][string]$ProjectDir)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
. (Join-Path $PSScriptRoot 'local_network.ps1')
ConvertTo-Json -Depth 4 -Compress -InputObject @(Get-GameBATWorkerProcesses -ProjectDir $ProjectDir)
