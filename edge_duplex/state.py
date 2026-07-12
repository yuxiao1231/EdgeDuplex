import json
from typing import List, Dict
from .config import STATE_FILE, STOP_FILE

class RuntimeState:
    def __init__(self):
        self.pid: int = 0
        self.edge_pid: int = 0
        self.port: int = 0
        self.started_at: str = ""
        self.proxy_interface: str = ""
        self.main_interface: str = ""
        self.proxy_ip: str = ""
        self.proxy_gateway: str = ""
        self.old_metrics: Dict[str, int] = {}
        self.added_routes: List[str] = []
        self.force_routes: bool = False
        
        self.load()

    def load(self):
        if not STATE_FILE.exists():
            return
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.pid = data.get("pid", 0)
                self.edge_pid = data.get("edge_pid", 0)
                self.port = data.get("port", 0)
                self.started_at = data.get("started_at", "")
                self.proxy_interface = data.get("proxy_interface", "")
                self.main_interface = data.get("main_interface", "")
                self.proxy_ip = data.get("proxy_ip", "")
                self.proxy_gateway = data.get("proxy_gateway", "")
                self.old_metrics = data.get("old_metrics", {})
                self.added_routes = data.get("added_routes", [])
                self.force_routes = data.get("force_routes", False)
        except Exception:
            pass

    def save(self):
        data = {
            "pid": self.pid,
            "edge_pid": self.edge_pid,
            "port": self.port,
            "started_at": self.started_at,
            "proxy_interface": self.proxy_interface,
            "main_interface": self.main_interface,
            "proxy_ip": self.proxy_ip,
            "proxy_gateway": self.proxy_gateway,
            "old_metrics": self.old_metrics,
            "added_routes": self.added_routes,
            "force_routes": self.force_routes,
        }
        try:
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception:
            pass

    def clear(self):
        self.pid = 0
        self.edge_pid = 0
        self.added_routes = []
        self.old_metrics = {}
        try:
            STATE_FILE.unlink()
        except FileNotFoundError:
            pass
        try:
            STOP_FILE.unlink()
        except FileNotFoundError:
            pass

runtime_state = RuntimeState()
