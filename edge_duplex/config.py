import json
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).parent
else:
    # Running from run.py or source
    APP_DIR = Path(__file__).resolve().parent.parent

CONFIG_FILE = APP_DIR / "config.json"
STATE_FILE = APP_DIR / "state.json"
STOP_FILE = APP_DIR / "stop"
LOG_FILE = APP_DIR / "edge-duplex.log"

DEFAULT_CONFIG = {
    "language": "zh",
    "reverse_mode": False,
    "dns": "1.1.1.1",
    "port": 10888
}

class ConfigManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance._load()
        return cls._instance
        
    def _load(self):
        self.language = DEFAULT_CONFIG["language"]
        self.reverse_mode = DEFAULT_CONFIG["reverse_mode"]
        self.dns = DEFAULT_CONFIG["dns"]
        self.port = DEFAULT_CONFIG["port"]
        
        if not CONFIG_FILE.exists():
            self.save()
            return
            
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.language = data.get("language", self.language)
                self.reverse_mode = data.get("reverse_mode", self.reverse_mode)
                self.dns = data.get("dns", self.dns)
                self.port = data.get("port", self.port)
        except Exception:
            pass

    def save(self):
        data = {
            "language": self.language,
            "reverse_mode": self.reverse_mode,
            "dns": self.dns,
            "port": self.port
        }
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception:
            pass

config = ConfigManager()
