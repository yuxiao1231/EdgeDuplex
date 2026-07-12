import argparse
import asyncio
import os
import signal
import subprocess
import sys
import time
from typing import Optional

from .config import config, LOG_FILE
from .state import runtime_state, STOP_FILE, STATE_FILE
from .routing import RoutingManager, DuplexError
from .edge import EdgeLauncher
from .proxy import SocksProxy, log

def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        # PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        h_process = kernel32.OpenProcess(0x1000, False, pid)
        if h_process == 0:
            return False
        exit_code = ctypes.c_ulong()
        kernel32.GetExitCodeProcess(h_process, ctypes.byref(exit_code))
        kernel32.CloseHandle(h_process)
        # STILL_ACTIVE = 259
        return exit_code.value == 259
    except Exception:
        return False

def free_port(preferred: int) -> int:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", preferred))
            return preferred
        except OSError:
            pass
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])

def cleanup_from_state(verbose: bool = True) -> None:
    runtime_state.load()
    routes = runtime_state.added_routes[:]
    if routes:
        RoutingManager.remove_all_host_routes_fast(routes)
        if verbose:
            print(f"removed {len(routes)} temporary routes in batch")
    runtime_state.added_routes = []

    old_metrics = runtime_state.old_metrics
    if RoutingManager.is_admin():
        for alias, metric in old_metrics.items():
            try:
                RoutingManager.set_metric(alias, int(metric))
                if verbose:
                    print(f"restored metric {alias} -> {metric}")
            except Exception as exc:
                if verbose:
                    print(f"metric restore failed for {alias}: {exc}")
    elif old_metrics and verbose:
        print("not elevated; metric restore skipped")

    runtime_state.clear()

def start_background(args: argparse.Namespace) -> None:
    if STOP_FILE.exists():
        STOP_FILE.unlink()

    runtime_state.load()
    if runtime_state.pid and pid_alive(runtime_state.pid):
        print(f"already running, pid={runtime_state.pid}")
        return

    proxy_if_info = RoutingManager.get_interface_info(args.proxy_interface)
    main_if_info = RoutingManager.get_interface_info(args.main_interface)
    proxy_ip = proxy_if_info.get("IPv4Address")
    proxy_gateway = proxy_if_info.get("Gateway")
    
    if not proxy_ip:
        raise DuplexError(f"Proxy interface {args.proxy_interface!r} has no usable IPv4 address")
    if not proxy_gateway:
        raise DuplexError(f"Proxy interface {args.proxy_interface!r} has no IPv4 gateway")

    old_metrics = {
        args.main_interface: int(main_if_info.get("Metric") or 0),
        args.proxy_interface: int(proxy_if_info.get("Metric") or 0),
    }

    if args.metrics:
        if not RoutingManager.is_admin():
            print("warning: not elevated; interface metrics and fallback host routes may fail")
        else:
            RoutingManager.set_metric(args.main_interface, args.main_metric)
            RoutingManager.set_metric(args.proxy_interface, args.proxy_metric)

    port = free_port(args.port)
    
    runtime_state.pid = 0
    runtime_state.started_at = time.strftime("%Y-%m-%d %H:%M:%S")
    runtime_state.port = port
    runtime_state.proxy_interface = args.proxy_interface
    runtime_state.main_interface = args.main_interface
    runtime_state.proxy_ip = proxy_ip
    runtime_state.proxy_gateway = proxy_gateway
    runtime_state.old_metrics = old_metrics
    runtime_state.added_routes = []
    runtime_state.force_routes = bool(args.force_routes)
    runtime_state.save()

    import sys
    from pathlib import Path
    
    if getattr(sys, 'frozen', False):
        cmd = [
            sys.executable,
            "serve",
            "--proxy-interface", args.proxy_interface,
            "--proxy-ip", proxy_ip,
            "--proxy-gateway", proxy_gateway,
            "--port", str(port),
            "--dns", args.dns,
        ]
    else:
        # run.py or __main__.py
        cmd = [
            sys.executable,
            str(Path(__file__).resolve().parent.parent / "run.py"),
            "serve",
            "--proxy-interface", args.proxy_interface,
            "--proxy-ip", proxy_ip,
            "--proxy-gateway", proxy_gateway,
            "--port", str(port),
            "--dns", args.dns,
        ]
        
    if args.force_routes:
        cmd.append("--force-routes")
    if getattr(args, "url", None):
        cmd.extend(["--url", args.url])

    log_handle = LOG_FILE.open("a", encoding="utf-8")
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    proc = subprocess.Popen(
        cmd,
        stdout=log_handle,
        stderr=log_handle,
        stdin=subprocess.DEVNULL,
        creationflags=creationflags,
    )
    runtime_state.pid = proc.pid
    runtime_state.save()
    print(f"duplex mode on: pid={proc.pid}, proxy=socks5://127.0.0.1:{port}")

async def serve(args: argparse.Namespace) -> None:
    proxy = SocksProxy(args.proxy_ip, args.proxy_gateway, args.proxy_interface, args.port, args.force_routes, getattr(args, "dns", "1.1.1.1"))
    await proxy.start()
    
    runtime_state.load()
    runtime_state.pid = os.getpid()
    runtime_state.port = args.port
    runtime_state.proxy_interface = args.proxy_interface
    runtime_state.proxy_ip = args.proxy_ip
    runtime_state.proxy_gateway = args.proxy_gateway
    runtime_state.force_routes = bool(args.force_routes)
    runtime_state.save()

    edge_proc = EdgeLauncher.launch(args.port, getattr(args, "url", None))
    runtime_state.edge_pid = edge_proc.pid
    runtime_state.save()

    async def watch_stop_file() -> None:
        while not proxy.stopping.is_set():
            if STOP_FILE.exists():
                log("stop file detected")
                await proxy.stop()
                break
            await asyncio.sleep(1)

    async def watch_edge() -> None:
        from .edge import EdgeLauncher
        _, exe_name, is_compat = EdgeLauncher.get_default_browser()
        if not is_compat:
            exe_name = "msedge.exe"
            
        while not proxy.stopping.is_set():
            await asyncio.sleep(2)
            CREATE_NO_WINDOW = 0x08000000
            try:
                proc = await asyncio.create_subprocess_exec(
                    "tasklist", "/FI", f"IMAGENAME eq {exe_name}",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    creationflags=CREATE_NO_WINDOW
                )
                stdout, _ = await proc.communicate()
                out_text = stdout.decode("utf-8", "replace").lower()
                if exe_name.lower() not in out_text:
                    log("All browser processes exited. Stopping proxy.")
                    await proxy.stop()
                    break
            except Exception as e:
                log(f"Error checking browser processes: {e}")

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: asyncio.create_task(proxy.stop()))
        except NotImplementedError:
            pass

    tasks = [asyncio.create_task(watch_stop_file()), asyncio.create_task(watch_edge())]
    try:
        while not proxy.stopping.is_set():
            await asyncio.sleep(0.5)
    finally:
        for task in tasks:
            task.cancel()
        await proxy.stop()
        cleanup_from_state(verbose=False)
        log("duplex mode cleaned up")

def stop_background() -> None:
    runtime_state.load()
    pid = runtime_state.pid
    if not pid:
        cleanup_from_state(verbose=True)
        print("duplex mode is not running")
        return
    STOP_FILE.write_text(str(time.time()), encoding="utf-8")
    EdgeLauncher.force_kill_all()
    
    for _ in range(20):
        if not pid_alive(pid):
            cleanup_from_state(verbose=True)
            print("duplex mode off")
            return
        time.sleep(0.5)
        
    CREATE_NO_WINDOW = 0x08000000
    subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, creationflags=CREATE_NO_WINDOW)
    cleanup_from_state(verbose=True)
    print("duplex mode off; process was force-stopped")

def status() -> None:
    runtime_state.load()
    if not runtime_state.pid:
        print("duplex mode: off")
        return
    print("duplex mode:", "on" if pid_alive(runtime_state.pid) else "stale")
    if STATE_FILE.exists():
        with STATE_FILE.open("r", encoding="utf-8") as f:
            print(f.read())
