from .config import config

TRANSLATIONS = {
    "zh": {
        "status_running": "状态: 运行中 (PID: {pid})",
        "status_stopped": "状态: 未运行",
        "btn_start": "启动 (Start)",
        "btn_stop": "停止并回滚 (Stop)",
        "msg_auto_cleanup": "退出程序前将自动检查并执行回滚操作",
        "browser_running_title": "{browser} 正在运行",
        "browser_running_msg": "为了使用隔离配置，必须彻底关闭所有已打开的 {browser} 窗口。\n\n是否允许程序现在强制关闭所有 {browser} 进程？",
        "incompatible_browser_title": "浏览器不兼容",
        "incompatible_browser_msg": "检测到你的默认浏览器是 {browser}，不支持通过命令行进行代理隔离。\n\n请手动设置 Edge/Chrome 为默认浏览器，或者我们将尝试强制使用 Edge。是否继续使用 Edge？",
        "start_failed": "启动失败",
        "stop_success_msg": "回滚清理操作已完成，程序即将完全退出。",
        "error_title": "错误",
        "cleanup_error_msg": "清理时发生错误: {e}",
        "stop_failed": "停止失败",
        "exit_confirm_title": "确认退出",
        "exit_confirm_msg": "Edge Profile 仍在运行，是否回滚清理并退出？",
        "reverse_mode": "反向分流 (以太网做代理，WLAN主干)",
        "dns_label": "DNS 服务器:",
        "port_label": "本地端口:",
        "lang_label": "语言 (Language):",
        "frame_status": "运行状态",
        "frame_settings": "高级设置",
        "frame_controls": "操作区",
        "already_running": "代理已经在运行中！",
        "not_running": "代理未运行",
        "cleanup_success": "清理成功",
        "process_killed": "进程已被强制终止",
    },
    "en": {
        "status_running": "Status: Running (PID: {pid})",
        "status_stopped": "Status: Stopped",
        "btn_start": "Start",
        "btn_stop": "Stop & Revert",
        "msg_auto_cleanup": "Will auto-check and revert routes before exiting",
        "browser_running_title": "{browser} is Running",
        "browser_running_msg": "To apply network isolation, all existing {browser} windows must be closed completely.\n\nForce close all {browser} processes now?",
        "incompatible_browser_title": "Incompatible Browser",
        "incompatible_browser_msg": "Detected {browser} as default, which does not support isolated proxy arguments.\n\nPlease set Edge/Chrome as default, or we can try to force-launch Edge. Continue with Edge?",
        "start_failed": "Failed to Start",
        "stop_success_msg": "Cleanup and rollback complete. Exiting...",
        "error_title": "Error",
        "cleanup_error_msg": "Error during cleanup: {e}",
        "stop_failed": "Failed to Stop",
        "exit_confirm_title": "Confirm Exit",
        "exit_confirm_msg": "Edge Profile is still running. Rollback routes and exit?",
        "reverse_mode": "Reverse Mode (Proxy via Ethernet, WLAN Main)",
        "dns_label": "DNS Server:",
        "port_label": "Local Port:",
        "lang_label": "Language:",
        "frame_status": "Status",
        "frame_settings": "Settings",
        "frame_controls": "Controls",
        "already_running": "Proxy is already running!",
        "not_running": "Proxy is not running",
        "cleanup_success": "Cleanup successful",
        "process_killed": "Process force-killed",
    }
}

class I18nManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(I18nManager, cls).__new__(cls)
            cls._instance.current_lang = config.language
            cls._instance.listeners = []
        return cls._instance

    def set_language(self, lang: str):
        if lang in TRANSLATIONS:
            self.current_lang = lang
            config.language = lang
            config.save()
            for callback in self.listeners:
                callback()

    def t(self, key: str, **kwargs) -> str:
        lang = self.current_lang if self.current_lang in TRANSLATIONS else "en"
        text = TRANSLATIONS[lang].get(key, key)
        if kwargs:
            return text.format(**kwargs)
        return text

    def add_listener(self, callback):
        self.listeners.append(callback)

i18n = I18nManager()
t = i18n.t
