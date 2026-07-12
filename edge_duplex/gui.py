import tkinter as tk
from tkinter import ttk, messagebox
import threading
import argparse
import subprocess
from .config import config
from .i18n import t, i18n
from .state import runtime_state
from .cli import pid_alive, start_background, stop_background, cleanup_from_state

class EdgeDuplexApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Edge Duplex")
        self.root.geometry("400x380")
        self.root.resizable(False, False)
        
        # Subscribe to language changes
        i18n.add_listener(self.update_ui_texts)
        self.action_lock = threading.Lock()
        
        self.create_widgets()
        self.update_status()
        self.update_ui_texts()

    def create_widgets(self):
        # Status Frame
        self.frame_status = ttk.LabelFrame(self.root, text="")
        self.frame_status.pack(fill="x", padx=10, pady=5)
        self.lbl_status = ttk.Label(self.frame_status, font=("Microsoft YaHei", 12))
        self.lbl_status.pack(pady=10)

        # Settings Frame
        self.frame_settings = ttk.LabelFrame(self.root, text="")
        self.frame_settings.pack(fill="x", padx=10, pady=5)
        
        # Reverse Mode
        self.var_reverse = tk.BooleanVar(value=config.reverse_mode)
        self.chk_reverse = ttk.Checkbutton(self.frame_settings, text="", variable=self.var_reverse, command=self.save_config)
        self.chk_reverse.grid(row=0, column=0, columnspan=2, sticky="w", padx=5, pady=5)
        
        # DNS
        self.lbl_dns = ttk.Label(self.frame_settings, text="")
        self.lbl_dns.grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.entry_dns = ttk.Entry(self.frame_settings)
        self.entry_dns.insert(0, config.dns)
        self.entry_dns.grid(row=1, column=1, sticky="ew", padx=5, pady=5)
        self.entry_dns.bind("<FocusOut>", self.save_config)
        
        # Port
        self.lbl_port = ttk.Label(self.frame_settings, text="")
        self.lbl_port.grid(row=2, column=0, sticky="w", padx=5, pady=5)
        self.entry_port = ttk.Entry(self.frame_settings)
        self.entry_port.insert(0, str(config.port))
        self.entry_port.grid(row=2, column=1, sticky="ew", padx=5, pady=5)
        self.entry_port.bind("<FocusOut>", self.save_config)

        # Language
        self.lbl_lang = ttk.Label(self.frame_settings, text="")
        self.lbl_lang.grid(row=3, column=0, sticky="w", padx=5, pady=5)
        
        self.combo_lang = ttk.Combobox(self.frame_settings, values=["中文", "English"], state="readonly")
        if config.language == "zh":
            self.combo_lang.current(0)
        else:
            self.combo_lang.current(1)
        self.combo_lang.grid(row=3, column=1, sticky="ew", padx=5, pady=5)
        self.combo_lang.bind("<<ComboboxSelected>>", self.on_lang_select)

        self.frame_settings.columnconfigure(1, weight=1)

        # Controls Frame
        self.frame_controls = ttk.LabelFrame(self.root, text="")
        self.frame_controls.pack(fill="x", padx=10, pady=5)
        
        self.btn_start = tk.Button(self.frame_controls, text="", command=self.do_start, bg="#4CAF50", fg="white", font=("Microsoft YaHei", 10, "bold"), height=2)
        self.btn_start.pack(fill="x", padx=5, pady=5)

        self.btn_stop = tk.Button(self.frame_controls, text="", command=self.do_stop, bg="#F44336", fg="white", font=("Microsoft YaHei", 10, "bold"), height=2)
        self.btn_stop.pack(fill="x", padx=5, pady=5)
        
        self.lbl_auto_cleanup = ttk.Label(self.root, text="", foreground="gray")
        self.lbl_auto_cleanup.pack(pady=5)

    def save_config(self, event=None):
        config.reverse_mode = self.var_reverse.get()
        
        import re
        dns_input = self.entry_dns.get().strip()
        if re.match(r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$", dns_input):
            config.dns = dns_input
        else:
            self.entry_dns.delete(0, tk.END)
            self.entry_dns.insert(0, config.dns)
            
        try:
            port_input = int(self.entry_port.get().strip())
            if 1 <= port_input <= 65535:
                config.port = port_input
            else:
                raise ValueError
        except ValueError:
            self.entry_port.delete(0, tk.END)
            self.entry_port.insert(0, str(config.port))
            
        config.save()

    def on_lang_select(self, event=None):
        val = self.combo_lang.get()
        if val == "中文":
            i18n.set_language("zh")
        else:
            i18n.set_language("en")

    def update_ui_texts(self):
        self.frame_status.config(text=t("frame_status"))
        self.frame_settings.config(text=t("frame_settings"))
        self.frame_controls.config(text=t("frame_controls"))
        
        self.chk_reverse.config(text=t("reverse_mode"))
        self.lbl_dns.config(text=t("dns_label"))
        self.lbl_port.config(text=t("port_label"))
        self.lbl_lang.config(text=t("lang_label"))
        
        self.btn_start.config(text=t("btn_start"))
        self.btn_stop.config(text=t("btn_stop"))
        self.lbl_auto_cleanup.config(text=t("msg_auto_cleanup"))
        self.refresh_status_text()

    def refresh_status_text(self):
        if self.action_lock.locked():
            return
            
        runtime_state.load()
        pid = runtime_state.pid
        if pid and pid_alive(pid):
            self.lbl_status.config(text=t("status_running", pid=pid))
            self.btn_start.config(state=tk.DISABLED)
            self.btn_stop.config(state=tk.NORMAL)
            # Disable settings while running
            self.chk_reverse.config(state=tk.DISABLED)
            self.entry_dns.config(state=tk.DISABLED)
            self.entry_port.config(state=tk.DISABLED)
        else:
            self.lbl_status.config(text=t("status_stopped"))
            self.btn_start.config(state=tk.NORMAL)
            self.btn_stop.config(state=tk.DISABLED)
            self.chk_reverse.config(state=tk.NORMAL)
            self.entry_dns.config(state=tk.NORMAL)
            self.entry_port.config(state=tk.NORMAL)

    def update_status(self):
        self.refresh_status_text()
        self.root.after(2000, self.update_status)

    def do_start(self):
        if not self.action_lock.acquire(blocking=False):
            return
        
        # Check browser synchronously before background thread
        try:
            self.save_config()
            self.btn_start.config(state=tk.DISABLED)
            
            from .edge import EdgeLauncher
            name, exe_name, is_compat = EdgeLauncher.get_default_browser()
            
            if not is_compat:
                if not messagebox.askyesno(t("incompatible_browser_title"), t("incompatible_browser_msg", browser=name)):
                    self.btn_start.config(state=tk.NORMAL)
                    self.action_lock.release()
                    return
                name, exe_name = "Edge", "msedge.exe"
                
            CREATE_NO_WINDOW = 0x08000000
            output = subprocess.check_output(f'tasklist /FI "IMAGENAME eq {exe_name}"', text=True, creationflags=CREATE_NO_WINDOW)
            if exe_name.lower() in output.lower():
                if not messagebox.askyesno(t("browser_running_title", browser=name), t("browser_running_msg", browser=name)):
                    self.btn_start.config(state=tk.NORMAL)
                    self.action_lock.release()
                    return
                subprocess.run(["taskkill", "/F", "/IM", exe_name, "/T"], capture_output=True, creationflags=CREATE_NO_WINDOW)
                import time
                time.sleep(1.5)
        except Exception:
            pass

        def task():
            try:
                is_reverse = config.reverse_mode
                args = argparse.Namespace(
                    proxy_interface="以太网" if is_reverse else "WLAN",
                    main_interface="WLAN" if is_reverse else "以太网",
                    port=config.port,
                    url=None,
                    main_metric=10,
                    proxy_metric=500,
                    metrics=True,
                    force_routes=True,
                    dns=config.dns,
                    cmd="on"
                )
                start_background(args)
            except Exception as e:
                self.root.after(0, lambda e=e: messagebox.showerror(t("start_failed"), str(e)))
            finally:
                self.root.after(0, self.refresh_status_text)
                self.action_lock.release()

        threading.Thread(target=task, daemon=True).start()

    def do_stop(self, on_exit=False):
        if not self.action_lock.acquire(blocking=False):
            return
            
        self.btn_stop.config(state=tk.DISABLED)
        
        def task():
            try:
                stop_background()
                if on_exit:
                    self.root.after(0, lambda: messagebox.showinfo("Edge Duplex", t("stop_success_msg")))
                    self.root.after(100, self.root.quit)
            except Exception as e:
                if on_exit:
                    self.root.after(0, lambda e=e: messagebox.showerror(t("error_title"), t("cleanup_error_msg", e=e)))
                    self.root.after(100, self.root.quit)
                else:
                    self.root.after(0, lambda e=e: messagebox.showerror(t("stop_failed"), str(e)))
            finally:
                if not on_exit:
                    self.root.after(0, self.refresh_status_text)
                self.action_lock.release()

        threading.Thread(target=task).start()

    def on_closing(self):
        runtime_state.load()
        pid = runtime_state.pid
        if pid and pid_alive(pid):
            if messagebox.askokcancel(t("exit_confirm_title"), t("exit_confirm_msg")):
                self.root.withdraw()
                self.do_stop(on_exit=True)
        else:
            cleanup_from_state(verbose=False)
            self.root.quit()

def run_gui() -> None:
    try:
        root = tk.Tk()
        app = EdgeDuplexApp(root)
        root.protocol("WM_DELETE_WINDOW", app.on_closing)
        root.mainloop()
    except Exception as e:
        print(f"Failed to start GUI: {e}")
