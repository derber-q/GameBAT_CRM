"""Проверки запуска LAN без изменения сетевых настроек и рабочих процессов."""

import json
import shutil
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import skipUnless

from django.test import SimpleTestCase


@skipUnless(sys.platform == "win32" and shutil.which("powershell.exe"), "Нужен Windows PowerShell")
class LocalNetworkTests(SimpleTestCase):
    def test_worker_coverage_checks_service_and_preserves_other_projects(self):
        commands = [
            r'"C:\CRM\.venv\Scripts\python.exe" -u manage.py run_integration_worker --service yandex',
            r'"C:\CRM-copy\.venv\Scripts\python.exe" manage.py run_integration_worker',
            r'"C:\CRM\.venv\Scripts\python.exe" manage.py run_label_print_worker',
        ]
        fixtures = json.dumps([{'Name': 'python.exe', 'CommandLine': command} for command in commands])
        result = self.run_powershell(
            f"$script:fixtures = '{fixtures}' | ConvertFrom-Json; "
            "function Get-CimInstance { $script:fixtures }; "
            "$specific = @('avito','yandex','google') | ForEach-Object { Test-GameBATIntegrationWorker -ProjectDir 'C:\\CRM' -Service $_ }; "
            "$script:fixtures[0].CommandLine = 'C:\\CRM\\python.exe manage.py run_integration_worker'; "
            "$all = @('avito','yandex','google') | ForEach-Object { Test-GameBATIntegrationWorker -ProjectDir 'C:\\CRM' -Service $_ }; "
            "ConvertTo-Json -InputObject @($specific + $all)"
        )
        self.assertEqual(result, [False, True, False, True, True, True])

    def run_powershell(self, code):
        helper = Path(__file__).resolve().parent.parent / "scripts" / "local_network.ps1"
        command = (
            "$ErrorActionPreference = 'Stop'; "
            "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
            f". '{str(helper).replace(chr(39), chr(39) * 2)}'; "
            + code
        )
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
            capture_output=True, encoding="utf-8", timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_selects_all_active_physical_addresses_without_vpn_or_old_wifi(self):
        def config(addresses, metric, *, physical=True, status="Up"):
            return {
                "NetAdapter": {"Status": status, "HardwareInterface": physical},
                "NetIPv4Interface": {"InterfaceMetric": metric},
                "IPv4Address": [{"IPAddress": ip} for ip in addresses],
            }

        configurations = [
            config(["172.18.0.1"], 1, physical=False),
            config(["192.168.0.101"], 5, status="Disconnected"),
            config(["192.168.0.132"], 40),
            config(["192.168.0.131", "192.168.0.131", "169.254.1.2", "::1", "bad"], 35),
        ]
        fixture = json.dumps(configurations)
        result = self.run_powershell(
            f"$script:fixtures = '{fixture}' | ConvertFrom-Json; "
            "function Get-NetIPConfiguration { $script:fixtures }; "
            "ConvertTo-Json -InputObject @(Get-GameBATLanAddresses)"
        )
        self.assertEqual(result, ["192.168.0.131", "192.168.0.132"])

    def test_no_lan_address_when_only_vpn_and_link_local_are_available(self):
        result = self.run_powershell(
            "function Get-NetIPConfiguration { "
            "[pscustomobject]@{NetAdapter=@{Status='Up'; HardwareInterface=$false}; "
            "IPv4Address=@(@{IPAddress='172.18.0.1'})}; "
            "[pscustomobject]@{NetAdapter=@{Status='Up'; HardwareInterface=$true}; "
            "IPv4Address=@(@{IPAddress='169.254.1.2'}, @{IPAddress='127.0.0.1'})} }; "
            "ConvertTo-Json -InputObject @(Get-GameBATLanAddresses)"
        )
        self.assertEqual(result, [])

    def test_restart_selection_preserves_workers_other_projects_and_other_ports(self):
        project = r"C:\CRM"
        commands = [
            rf'"{project}\.venv\Scripts\python.exe" -u manage.py runserver 0.0.0.0:8000 --noreload',
            rf'"{project}\.venv\Scripts\python.exe" manage.py run_integration_worker --service avito',
            r'"C:\CRM-copy\.venv\Scripts\python.exe" manage.py runserver 0.0.0.0:8000',
            rf'"{project}\.venv\Scripts\python.exe" manage.py runserver 0.0.0.0:8001',
        ]
        fixture = json.dumps([
            {"Name": "python.exe", "ProcessId": index, "CommandLine": command}
            for index, command in enumerate(commands)
        ])
        result = self.run_powershell(
            f"$script:fixtures = '{fixture}' | ConvertFrom-Json; "
            "function Get-CimInstance { $script:fixtures }; "
            r"ConvertTo-Json -InputObject @(Get-GameBATServerProcesses -ProjectDir 'C:\CRM' "
            "| Select-Object -ExpandProperty ProcessId)"
        )
        self.assertEqual(result, [0])

    def test_health_probe_bypasses_proxy_and_rejects_foreign_or_disallowed_hosts(self):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                statuses = {"/crm": 302, "/foreign": 200, "/bad-host": 400, "/external": 302}
                self.send_response(statuses[self.path])
                if self.path == "/crm":
                    self.send_header("Location", "/crm/accounts/login/")
                elif self.path == "/external":
                    self.send_header("Location", "http://example.invalid/")
                self.send_header("Content-Length", "0")
                self.end_headers()

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base_url = f"http://127.0.0.1:{server.server_port}"
            result = self.run_powershell(
                "[System.Net.WebRequest]::DefaultWebProxy = "
                "New-Object System.Net.WebProxy('http://127.0.0.1:1', $false); "
                "ConvertTo-Json -InputObject @("
                + "; ".join(
                    f"Test-GameBATServer -Url '{base_url}/{path}'"
                    for path in ("crm", "foreign", "bad-host", "external")
                ) + ")"
            )
            self.assertEqual(result, [True, False, False, False])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
