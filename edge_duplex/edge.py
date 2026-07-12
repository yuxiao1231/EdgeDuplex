import os
import subprocess
import winreg
from pathlib import Path
from typing import Optional, Tuple
from .routing import DuplexError

class EdgeLauncher:
    @staticmethod
    def get_default_browser() -> Tuple[str, str, bool]:
        """
        Returns (Browser Name, Executable Name, Is Compatible)
        """
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\http\UserChoice") as key:
                prog_id, _ = winreg.QueryValueEx(key, "ProgId")
            
            prog_id = prog_id.lower()
            if "chrome" in prog_id:
                return "Chrome", "chrome.exe", True
            elif "msedge" in prog_id or "edge" in prog_id:
                return "Edge", "msedge.exe", True
            elif "brave" in prog_id:
                return "Brave", "brave.exe", True
            elif "firefox" in prog_id:
                return "Firefox", "firefox.exe", False
            else:
                return "Unknown Browser", "unknown.exe", False
        except Exception:
            # Fallback to Edge if detection fails
            return "Edge", "msedge.exe", True

    @staticmethod
    def find_executable(exe_name: str) -> str:
        candidates = []
        if exe_name == "chrome.exe":
            candidates = [
                Path(os.environ.get("PROGRAMFILES", "")) / "Google/Chrome/Application/chrome.exe",
                Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Google/Chrome/Application/chrome.exe",
                Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
            ]
        elif exe_name == "brave.exe":
            candidates = [
                Path(os.environ.get("PROGRAMFILES", "")) / "BraveSoftware/Brave-Browser/Application/brave.exe",
                Path(os.environ.get("PROGRAMFILES(X86)", "")) / "BraveSoftware/Brave-Browser/Application/brave.exe",
                Path(os.environ.get("LOCALAPPDATA", "")) / "BraveSoftware/Brave-Browser/Application/brave.exe",
            ]
        else: # Default Edge
            candidates = [
                Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Microsoft/Edge/Application/msedge.exe",
                Path(os.environ.get("PROGRAMFILES", "")) / "Microsoft/Edge/Application/msedge.exe",
                Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/Edge/Application/msedge.exe",
            ]
            
        for path in candidates:
            if path.exists():
                return str(path)
                
        # Try `where` command
        cp = subprocess.run(
            ["where", exe_name],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=0x08000000
        )
        for line in cp.stdout.splitlines():
            if line.lower().endswith(exe_name):
                return line.strip()
                
        # If targeting a non-edge browser and it fails, fallback to edge
        if exe_name != "msedge.exe":
            return EdgeLauncher.find_executable("msedge.exe")
            
        raise DuplexError(f"{exe_name} not found")

    @staticmethod
    def launch(port: int, url: Optional[str]) -> subprocess.Popen:
        name, exe_name, is_compat = EdgeLauncher.get_default_browser()
        if not is_compat:
            exe_name = "msedge.exe"
            
        browser_path = EdgeLauncher.find_executable(exe_name)
        args = [
            browser_path,
            f"--proxy-server=socks5://127.0.0.1:{port}",
            "--no-first-run",
            "--new-window",
        ]
        if url:
            args.append(url)
        return subprocess.Popen(args)
        
    @staticmethod
    def force_kill_all():
        name, exe_name, is_compat = EdgeLauncher.get_default_browser()
        if not is_compat:
            exe_name = "msedge.exe"
            
        CREATE_NO_WINDOW = 0x08000000
        subprocess.run(["taskkill", "/F", "/IM", exe_name, "/T"], capture_output=True, creationflags=CREATE_NO_WINDOW)
