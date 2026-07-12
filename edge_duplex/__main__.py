import sys
import argparse
import asyncio
from .gui import run_gui
from .cli import start_background, serve, stop_background, status, cleanup_from_state
from .config import config
from .routing import DuplexError

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Run a dedicated Edge profile through WLAN on Windows.")
    sub = p.add_subparsers(dest="cmd")

    on = sub.add_parser("on", help="start background duplex mode")
    on.add_argument("--proxy-interface", default="WLAN")
    on.add_argument("--main-interface", default="以太网")
    on.add_argument("--port", type=int, default=config.port)
    on.add_argument("--url", default=None)
    on.add_argument("--main-metric", type=int, default=10)
    on.add_argument("--proxy-metric", type=int, default=500)
    on.add_argument("--no-metrics", dest="metrics", action="store_false")
    on.add_argument("--force-routes", action="store_true")
    on.add_argument("--dns", default=config.dns)
    on.set_defaults(metrics=True)

    serve_p = sub.add_parser("serve", help=argparse.SUPPRESS)
    serve_p.add_argument("--proxy-interface", required=True)
    serve_p.add_argument("--proxy-ip", required=True)
    serve_p.add_argument("--proxy-gateway", required=True)
    serve_p.add_argument("--port", type=int, required=True)
    serve_p.add_argument("--url", default=None)
    serve_p.add_argument("--force-routes", action="store_true")
    serve_p.add_argument("--dns", default=config.dns)

    sub.add_parser("off", help="stop and clean up")
    sub.add_parser("status", help="show current state")
    sub.add_parser("cleanup", help="remove saved routes and restore metrics from state")
    return p

def main() -> int:
    if len(sys.argv) == 1:
        run_gui()
        return 0
    args = build_parser().parse_args()
    try:
        if getattr(args, 'cmd', None) == "on":
            start_background(args)
        elif getattr(args, 'cmd', None) == "serve":
            asyncio.run(serve(args))
        elif getattr(args, 'cmd', None) == "off":
            stop_background()
        elif getattr(args, 'cmd', None) == "status":
            status()
        elif getattr(args, 'cmd', None) == "cleanup":
            cleanup_from_state(verbose=True)
        else:
            build_parser().print_help()
        return 0
    except DuplexError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        cleanup_from_state(verbose=True)
        return 130

if __name__ == "__main__":
    sys.exit(main())
