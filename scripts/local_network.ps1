function Get-GameBATLanAddresses {
    # VPN и отключённый Wi-Fi не должны определять адрес CRM.
    Get-NetIPConfiguration -ErrorAction SilentlyContinue | Where-Object {
        $_.NetAdapter.Status -eq 'Up' -and $_.NetAdapter.HardwareInterface
    } | Sort-Object { $_.NetIPv4Interface.InterfaceMetric } | ForEach-Object {
        foreach ($address in $_.IPv4Address) {
            $ip = $null
            if ([System.Net.IPAddress]::TryParse($address.IPAddress, [ref]$ip) `
                -and $ip.AddressFamily -eq [System.Net.Sockets.AddressFamily]::InterNetwork `
                -and $ip.IPAddressToString -notmatch '^(127\.|169\.254\.|0\.)') {
                $ip.IPAddressToString
            }
        }
    } | Select-Object -Unique
}

function Test-GameBATServer {
    param([Parameter(Mandatory)][string]$Url)

    $response = $null
    try {
        $request = [System.Net.HttpWebRequest]::Create($Url)
        # Системный прокси/VPN не должен участвовать в проверке LAN-сервера.
        $request.Proxy = $null
        $request.AllowAutoRedirect = $false
        $request.Timeout = 1500
        $response = $request.GetResponse()
        # Корневой URL CRM всегда ведёт на вход. Чужой сервис на 8000 не подходит.
        return [int]$response.StatusCode -eq 302 `
            -and $response.Headers['Location'] -eq '/crm/accounts/login/'
    }
    catch {
        return $false
    }
    finally {
        if ($response) { $response.Close() }
    }
}

function Get-GameBATServerProcesses {
    param([Parameter(Mandatory)][string]$ProjectDir)

    $projectPattern = [Regex]::Escape($ProjectDir.TrimEnd('\')) + '(?:\\|")'
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_.Name -match '^python' `
            -and $_.CommandLine -match $projectPattern `
            -and $_.CommandLine -match '\bmanage\.py"?\s+runserver\s+(?:\S+:)?8000(?:\s|$)'
    }
}

function Test-GameBATIntegrationWorker {
    param(
        [Parameter(Mandatory)][string]$ProjectDir,
        [Parameter(Mandatory)][ValidateSet('avito', 'yandex', 'google')][string]$Service
    )
    return @((Get-GameBATWorkerProcesses -ProjectDir $ProjectDir) | Where-Object {
        $_.services -contains $Service
    }).Count -gt 0
}

function Get-GameBATWorkerProcesses {
    param([Parameter(Mandatory)][string]$ProjectDir)
    $project = $ProjectDir.TrimEnd('\')
    $pythonPattern = '^"?' + [Regex]::Escape((Join-Path $project '.venv\Scripts\python.exe')) + '"?\s+'
    $managePattern = '(?:^|\s)"?(?:' + [Regex]::Escape($project + '\') + ')?manage\.py"?\s+(run_integration_worker|run_label_print_worker|run_worker_supervisor|run_telegram_staff_bot)(?:\s|$)'
    # Ошибка CIM не означает пустой список: контроллер обязан запретить запуск.
    foreach ($worker in @(Get-CimInstance Win32_Process -ErrorAction Stop)) {
        if ($worker.Name -notmatch '^python' -or $worker.CommandLine -notmatch $pythonPattern) { continue }
        $command = [Regex]::Match($worker.CommandLine, $managePattern, 'IgnoreCase')
        if (-not $command.Success) { continue }
        $services = @()
        switch ($command.Groups[1].Value) {
            'run_label_print_worker' { $services = @('print') }
            'run_worker_supervisor' { $services = @('supervisor') }
            'run_telegram_staff_bot' { $services = @('telegram_staff') }
            'run_integration_worker' {
                $selection = [Regex]::Match($worker.CommandLine, '--service(?:=|\s+)["'']?(all|avito|yandex|google)\b', 'IgnoreCase')
                if (-not $selection.Success -or $selection.Groups[1].Value -eq 'all') {
                    $services = @('avito', 'yandex', 'google')
                } else { $services = @($selection.Groups[1].Value.ToLowerInvariant()) }
            }
        }
        $instance = [Regex]::Match($worker.CommandLine, '--worker-instance(?:=|\s+)["'']?([0-9a-f-]{36})\b', 'IgnoreCase')
        $birth = if ($worker.CreationDate) { $worker.CreationDate.ToUniversalTime().ToString('o') } else { '' }
        [pscustomobject]@{ pid = $worker.ProcessId; parent = $worker.ParentProcessId; birth = $birth;
            services = $services; instance = $instance.Groups[1].Value }
    }
}

function Start-GameBATSupervisor {
    param([Parameter(Mandatory)][string]$ProjectDir,
          [Parameter(Mandatory)][string]$PythonExe,
          [Parameter(Mandatory)][string]$RuntimeDir)
    $supervisor = @(Get-GameBATWorkerProcesses -ProjectDir $ProjectDir | Where-Object {
        $_.services -contains 'supervisor'
    })
    if ($supervisor.Count) { return }
    $logPrefix = Join-Path $RuntimeDir ((Get-Date -Format 'yyyyMMdd_HHmmss_fff') + '_supervisor')
    Start-Process -FilePath $PythonExe `
        -ArgumentList @('-u', 'manage.py', 'run_worker_supervisor') `
        -WorkingDirectory $ProjectDir -WindowStyle Hidden `
        -RedirectStandardOutput "$logPrefix.stdout.log" `
        -RedirectStandardError "$logPrefix.stderr.log"
}
