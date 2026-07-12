import subprocess
import ctypes
import json
from typing import Dict, Any

class DuplexError(RuntimeError):
    pass

class RoutingManager:
    @staticmethod
    def is_admin() -> bool:
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False

    @staticmethod
    def ps_quote(value: str) -> str:
        return "'" + value.replace("'", "''") + "'"

    @staticmethod
    def run_ps(script: str, check: bool = True) -> subprocess.CompletedProcess:
        cp = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=0x08000000
        )
        if check and cp.returncode != 0:
            raise DuplexError(cp.stderr.strip() or cp.stdout.strip() or "PowerShell failed")
        return cp

    @staticmethod
    def get_interface_info(alias: str) -> Dict[str, Any]:
        script = f"""
$cfg = Get-NetIPConfiguration -InterfaceAlias {RoutingManager.ps_quote(alias)} -ErrorAction Stop
$ipif = Get-NetIPInterface -InterfaceAlias {RoutingManager.ps_quote(alias)} -AddressFamily IPv4 -ErrorAction Stop
[pscustomobject]@{{
  InterfaceAlias = $cfg.InterfaceAlias
  InterfaceIndex = $cfg.InterfaceIndex
  IPv4Address = @($cfg.IPv4Address | Where-Object {{$_.IPAddress -notlike '169.254.*'}} | Select-Object -First 1 -ExpandProperty IPAddress)
  Gateway = @($cfg.IPv4DefaultGateway | Select-Object -First 1 -ExpandProperty NextHop)
  Metric = @($ipif | Select-Object -First 1 -ExpandProperty InterfaceMetric)
  ConnectionState = @($ipif | Select-Object -First 1 -ExpandProperty ConnectionState)
}} | ConvertTo-Json -Compress
"""
        cp = RoutingManager.run_ps(script)
        data = json.loads(cp.stdout.strip())
        for key in ("IPv4Address", "Gateway", "Metric", "ConnectionState", "InterfaceIndex"):
            if isinstance(data.get(key), list):
                data[key] = data[key][0] if data[key] else None
        return data

    @staticmethod
    def set_metric(alias: str, metric: int) -> None:
        RoutingManager.run_ps(
            f"Set-NetIPInterface -InterfaceAlias {RoutingManager.ps_quote(alias)} "
            f"-AddressFamily IPv4 -InterfaceMetric {int(metric)} -ErrorAction Stop"
        )

    @staticmethod
    def add_host_route(ip: str, interface_alias: str, gateway: str) -> bool:
        script = f"""
$existing = Get-NetRoute -DestinationPrefix {RoutingManager.ps_quote(ip + '/32')} -InterfaceAlias {RoutingManager.ps_quote(interface_alias)} -NextHop {RoutingManager.ps_quote(gateway)} -ErrorAction SilentlyContinue
if (-not $existing) {{
  New-NetRoute -DestinationPrefix {RoutingManager.ps_quote(ip + '/32')} -InterfaceAlias {RoutingManager.ps_quote(interface_alias)} -NextHop {RoutingManager.ps_quote(gateway)} -RouteMetric 1 -PolicyStore ActiveStore -ErrorAction Stop | Out-Null
  'added'
}} else {{
  'exists'
}}
"""
        cp = RoutingManager.run_ps(script, check=True)
        return "added" in cp.stdout

    @staticmethod
    def add_host_route_fast(ip: str, gateway: str, if_index: int) -> None:
        CREATE_NO_WINDOW = 0x08000000
        subprocess.run(["route", "add", ip, "mask", "255.255.255.255", gateway, "metric", "1", "if", str(if_index)], capture_output=True, creationflags=CREATE_NO_WINDOW)

    @staticmethod
    async def add_host_route_fast_async(ip: str, gateway: str, if_index: int) -> None:
        import asyncio
        CREATE_NO_WINDOW = 0x08000000
        proc = await asyncio.create_subprocess_exec(
            "route", "add", ip, "mask", "255.255.255.255", gateway, "metric", "1", "if", str(if_index),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW
        )
        await proc.wait()

    @staticmethod
    def remove_host_route_fast(ip: str) -> None:
        CREATE_NO_WINDOW = 0x08000000
        subprocess.run(["route", "delete", ip], capture_output=True, creationflags=CREATE_NO_WINDOW)

    @staticmethod
    def remove_all_host_routes_fast(ips: list[str]) -> None:
        if not ips:
            return
        # Use powershell for batch removal to avoid spinning up route.exe 100 times
        ips_str = ",".join([RoutingManager.ps_quote(ip + "/32") for ip in ips])
        script = f"""
$ips = @({ips_str})
if ($ips.Count -gt 0) {{
    Get-NetRoute -ErrorAction SilentlyContinue | Where-Object {{ $ips -contains $_.DestinationPrefix }} | Remove-NetRoute -Confirm:$false -ErrorAction SilentlyContinue
}}
"""
        RoutingManager.run_ps(script, check=False)

    @staticmethod
    def remove_host_route(ip: str, interface_alias: str, gateway: str) -> None:
        script = f"""
Get-NetRoute -DestinationPrefix {RoutingManager.ps_quote(ip + '/32')} -InterfaceAlias {RoutingManager.ps_quote(interface_alias)} -NextHop {RoutingManager.ps_quote(gateway)} -ErrorAction SilentlyContinue |
  Remove-NetRoute -Confirm:$false -ErrorAction SilentlyContinue
"""
        RoutingManager.run_ps(script, check=False)
