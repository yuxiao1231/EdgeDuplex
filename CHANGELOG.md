# Changelog

All notable changes to EdgeDuplex are documented here.

---

## [v2.0.1] - 2026-07-11

### 🔧 Fixed
- **GUI Input Validation**: Added strict IPv4 regex validation for the DNS input field and integer range validation (1-65535) for the Port input field. Invalid inputs are automatically reverted on focus loss, preventing `route add` injection failures and DoH resolution crashes.
- **Automated Releases**: Restructured GitHub Actions to only trigger PyInstaller releases on tags matching `v*.*.*` instead of every push to main.

---

## [v2.0.0] - 2026-07-11

### ✨ Major Features & Architecture Redesign
- **Fully Modular Architecture**: The core logic has been refactored from a single script into a robust multi-module package (`gui.py`, `proxy.py`, `routing.py`, `edge.py`, `state.py`, `i18n.py`).
- **Dynamic Chromium Detection**: Automatically detects the user's default Chromium-based browser (Chrome, Brave, Edge). Prompts for confirmation and forcefully manages the isolated browser's lifecycle. Falls back to Edge safely if an incompatible browser (e.g., Firefox) is set as default.
- **Fast Routing (Zero-Delay Proxy)**: Replaced slow PowerShell routing injection with native Windows `route add` commands. The proxy now *proactively* injects a temporary `/32` Host Route before attempting a connection, eliminating the 12-second DNS timeout completely.
- **Tasklist Polling Lifecyle**: Replaced standard PID tracking with a robust, global `tasklist` polling mechanism. If the browser delegates its initial PID to a background task or spawns new tabs, the proxy will stay alive as long as *any* instance of the browser executable remains open.
- **UAC Privileges & Silent Execution**: The executable is now built with PyInstaller using `--uac-admin` (auto-requests Administrator privileges on launch) and `--windowed` (fully silent background execution with no CMD window).
- **Internationalization (i18n)**: Upgraded UI to feature a real-time `ttk.Combobox` for language switching between English and Chinese (zh).
- **Thread-safe UI Actions**: Introduced threading locks during start/stop operations to prevent race conditions (e.g., rapid clicking causing multiple zombie proxy instances).

### 🐛 Fixed
- Fixed an issue where the proxy failed to route DoH requests over the target interface due to the Windows Strong Host Model aggressively dropping spoofed packets.
- Fixed a bug where changing the UI language during the asynchronous connection phase would prematurely enable the "Start" button and break the UI state machine.
- Fixed an issue where closing the proxy via the UI could leave dangling `/32` routes in the system routing table for up to a minute by adopting the fast route deletion algorithm.

---

## [v1.0.0] - 2026-06-01

### 🎉 Initial Release
- Basic single-script proxy routing implementation.
- Basic Windows routing metric manipulation via PowerShell.
- SOCKS5 traffic interception for Microsoft Edge.
