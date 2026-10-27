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
    $projectPattern = [Regex]::Escape($ProjectDir.TrimEnd('\')) + '(?:\\|")'
    $workers = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_.Name -match '^python' -and $_.CommandLine -match $projectPattern `
            -and $_.CommandLine -match '\bmanage\.py"?\s+run_integration_worker(?:\s|$)'
    }
    foreach ($worker in $workers) {
        $selection = [Regex]::Match($worker.CommandLine, '--service(?:=|\s+)["'']?(all|avito|yandex|google)\b', 'IgnoreCase')
        if (-not $selection.Success -or $selection.Groups[1].Value -eq 'all' -or $selection.Groups[1].Value -eq $Service) {
            return $true
        }
    }
    return $false
}
