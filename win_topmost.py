# -*- coding: utf-8 -*-
"""
================================================================================
 WinTop —— Windows 窗口一键置顶工具（霓虹发光边框版）
--------------------------------------------------------------------------------
 功能：
   1) 全局热键，把「当前前台窗口」一键置顶（Always On Top）
   2) 再按一次同一热键 → 取消置顶并移除视觉效果（同键双态切换）
   3) 置顶窗口四周显示「点击穿透」的霓虹发光边框，一眼看出哪些窗口被钉住了
   4) 支持多个窗口同时置顶，每个窗口独立记录状态与效果层

 运行环境：
   Windows 10 / 11 + Python 3.8 及以上
   只用标准库（ctypes + tkinter），不需要 pip 安装任何东西

 默认热键：
   Ctrl + Alt + Space   置顶 / 取消置顶 当前窗口
   Ctrl + Alt + D       取消全部置顶
   Ctrl + Alt + Q       退出工具（会自动恢复所有窗口）

 作者备注：
   想改快捷键 / 颜色 / 粗细，只改下面的 CONFIG 字典即可，不用动逻辑代码。
================================================================================
"""

from __future__ import annotations

import ctypes
import math
import os
import queue
import sys
import tempfile
import time
import traceback
from ctypes import wintypes

import tkinter as tk


# ============================================================================
# 一、用户配置区（改这里就够了）
# ============================================================================
CONFIG = {
    # ---- 快捷键（写法：修饰键 + 主键，用 + 连接）----
    # 修饰键支持 ctrl / alt / shift / win；主键支持 a-z、0-9、f1-f12、space 等
    # ⚠️ 默认没用 Ctrl+Space，因为中文输入法默认占用它来切换中英文；
    #    若你想换成别的，例如 Ctrl+Shift+T，写成 "ctrl+shift+t" 即可。
    "hotkey_toggle": "ctrl+alt+space",   # 置顶 / 取消置顶
    "hotkey_clear": "ctrl+alt+d",        # 取消全部置顶
    "hotkey_quit": "ctrl+alt+q",         # 退出工具

    # ---- 视觉效果 ----
    "glow_color": "#00FF9C",   # 发光颜色（十六进制 RGB）。参考：#00BFFF 冰蓝 / #FF4D6D 玫红 / #FFD400 琥珀
    "glow_width": 14,          # 光晕带宽（像素），越大越粗越"亮"
    "radius": 16,              # 圆角半径（像素），0 = 直角
    "breath": True,            # 是否开启呼吸灯效果（关闭后为静态常亮，更省 CPU）
    "breath_period_ms": 1800,  # 呼吸周期（毫秒）
    "breath_min": 0.55,        # 呼吸最暗时的亮度比例（0~1）
    "flash_ms": 420,           # 刚置顶时的一次高亮脉冲时长（毫秒），设 0 关闭

    # ---- 运行参数 ----
    "fps": 30,                 # 跟随刷新率（窗口拖动时的跟手程度）。卡顿可降到 20
    "show_toast": True,        # 启动时是否弹一个右下角提示
    "write_log": True,         # 是否把启动/错误信息写到 %TEMP%\wintop.log（排查问题用）
}

APP_NAME = "WinTop"
LOG_PATH = os.path.join(tempfile.gettempdir(), "wintop.log")
KEY_COLOR = "#010203"          # 透明色键（必须与发光颜色不同，且不会出现在画面里）

# 不参与置顶的系统外壳窗口类名（桌面、任务栏等）
SHELL_CLASSES = {
    "Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd",
    "Windows.UI.Core.CoreWindow", "ApplicationManager_DesktopShellWindow",
    "MultitaskingViewFrame", "TaskListThumbnailWnd", "ForegroundStaging",
}


def log(msg: str) -> None:
    """把关键信息写入临时目录日志，方便 pythonw（无控制台）模式下排查问题。"""
    if not CONFIG.get("write_log", True):
        return
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write("%s  %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    except OSError:
        pass


# ============================================================================
# 二、Win32 API 声明（ctypes 64 位安全写法）
#    注意：句柄类参数务必设置 argtypes/restype，否则 64 位下会被截断成 32 位
# ============================================================================
user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
try:
    dwmapi = ctypes.WinDLL("dwmapi", use_last_error=True)
except OSError:                                     # 极端精简系统可能没有
    dwmapi = None

kernel32.CreateMutexW.argtypes = [wintypes.LPCWSTR, wintypes.BOOL, wintypes.LPCWSTR]
kernel32.CreateMutexW.restype = wintypes.HANDLE

HWND = wintypes.HWND
BOOL = wintypes.BOOL
DWORD = wintypes.DWORD
UINT = wintypes.UINT

# ---- 常量 ----
GWL_EXSTYLE = -20                # 扩展窗口样式在 Get/SetWindowLong 中的索引
WS_EX_TOPMOST = 0x00000008       # 置顶标志位
WS_EX_TRANSPARENT = 0x00000020   # 鼠标点击穿透（命中测试时跳过本窗口）
WS_EX_TOOLWINDOW = 0x00000080    # 工具窗口：不出现在 Alt+Tab / 任务栏
WS_EX_LAYERED = 0x00080000       # 分层窗口：支持透明色键 / 逐像素透明
WS_EX_NOACTIVATE = 0x08000000    # 永不激活：不会抢走目标窗口的焦点

HWND_TOPMOST = -1                # SetWindowPos 的"置顶"伪句柄
HWND_NOTOPMOST = -2              # SetWindowPos 的"取消置顶"伪句柄

SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_NOSENDCHANGING = 0x0400

GA_ROOT = 2                      # GetAncestor：取顶层窗口
WM_HOTKEY = 0x0312               # 热键消息
MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x8, 0x4000
DWMWA_EXTENDED_FRAME_BOUNDS = 9  # 窗口真实可视边界（不含 Win10/11 那圈隐形拖拽边框）

HOTKEY_IDS = {"toggle": 1, "clear": 2, "quit": 3}


class MSG(ctypes.Structure):
    """Win32 MSG 结构体：热键线程的消息循环要用。"""
    _fields_ = [
        ("hwnd", HWND),
        ("message", UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", DWORD),
        ("pt", wintypes.POINT),
    ]


# ---- 函数签名（顺手把 argtypes 写全，规避 64 位指针截断的经典坑）----
user32.GetForegroundWindow.restype = HWND
user32.GetForegroundWindow.argtypes = []

user32.GetAncestor.argtypes = [HWND, UINT]
user32.GetAncestor.restype = HWND

user32.IsWindow.argtypes = [HWND]
user32.IsWindow.restype = BOOL

user32.IsIconic.argtypes = [HWND]
user32.IsIconic.restype = BOOL

user32.IsWindowVisible.argtypes = [HWND]
user32.IsWindowVisible.restype = BOOL

user32.GetWindowRect.argtypes = [HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetWindowRect.restype = BOOL

user32.GetWindowLongW.argtypes = [HWND, ctypes.c_int]
user32.GetWindowLongW.restype = ctypes.c_int

user32.SetWindowLongW.argtypes = [HWND, ctypes.c_int, ctypes.c_int]
user32.SetWindowLongW.restype = ctypes.c_int

user32.SetWindowPos.argtypes = [HWND, HWND, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, UINT]
user32.SetWindowPos.restype = BOOL

user32.GetClassNameW.argtypes = [HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetClassNameW.restype = ctypes.c_int

user32.GetWindowThreadProcessId.argtypes = [HWND, ctypes.POINTER(DWORD)]
user32.GetWindowThreadProcessId.restype = DWORD

user32.RegisterHotKey.argtypes = [HWND, ctypes.c_int, UINT, UINT]
user32.RegisterHotKey.restype = BOOL

user32.UnregisterHotKey.argtypes = [HWND, ctypes.c_int]
user32.UnregisterHotKey.restype = BOOL

user32.GetMessageW.argtypes = [ctypes.POINTER(MSG), HWND, UINT, UINT]
user32.GetMessageW.restype = ctypes.c_int

if dwmapi is not None:
    dwmapi.DwmGetWindowAttribute.argtypes = [HWND, DWORD, ctypes.c_void_p, DWORD]
    dwmapi.DwmGetWindowAttribute.restype = ctypes.c_long


def enable_dpi_awareness() -> None:
    """
    声明进程为「系统 DPI 感知」。
    不做这一步，在缩放 125%/150% 的屏幕上，Tk 的坐标与 Win32 的物理像素会错位，
    发光边框就会整体偏移。必须在创建任何窗口之前调用。
    """
    try:
        user32.SetProcessDPIAware()
    except Exception:
        pass


# ============================================================================
# 三、小工具函数
# ============================================================================
def hex_to_rgb(h: str):
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def rgb_to_hex(rgb) -> str:
    return "#%02x%02x%02x" % rgb


VK_NAMES = {
    "space": 0x20, "tab": 0x09, "enter": 0x0D, "return": 0x0D, "esc": 0x1B, "escape": 0x1B,
    "backspace": 0x08, "delete": 0x2E, "insert": 0x2D, "home": 0x24, "end": 0x23,
    "pageup": 0x21, "pagedown": 0x22, "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "`": 0xC0, "-": 0xBD, "=": 0xBB, "[": 0xDB, "]": 0xDD, "\\": 0xDC, ";": 0xBA,
    "'": 0xDE, ",": 0xBC, ".": 0xBE, "/": 0xBF,
}


def parse_hotkey(spec: str):
    """把 'ctrl+alt+space' 解析成 (修饰键掩码, 虚拟键码)。写法非法时抛 ValueError。"""
    mods, vk = 0, None
    for part in spec.lower().replace(" ", "").split("+"):
        if part in ("ctrl", "control"):
            mods |= MOD_CONTROL
        elif part == "alt":
            mods |= MOD_ALT
        elif part == "shift":
            mods |= MOD_SHIFT
        elif part in ("win", "super", "meta"):
            mods |= MOD_WIN
        elif len(part) == 1 and part.isalpha():
            vk = ord(part.upper())
        elif len(part) == 1 and part.isdigit():
            vk = ord(part)
        elif part in VK_NAMES:
            vk = VK_NAMES[part]
        elif part.startswith("f") and part[1:].isdigit() and 1 <= int(part[1:]) <= 24:
            vk = 0x70 + int(part[1:]) - 1
        else:
            raise ValueError("无法识别的按键：%s" % part)
    if vk is None or mods == 0:
        raise ValueError("快捷键必须包含至少一个修饰键（ctrl/alt/shift/win）：%s" % spec)
    return mods, vk


def get_class_name(hwnd) -> str:
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(HWND(hwnd), buf, 256)
    return buf.value


def get_visual_rect(hwnd):
    """
    取窗口的"真实可视边界"。
    直接用 GetWindowRect 会包含 Win10/11 那圈约 7px 的隐形拖拽边框，
    导致发光框离窗口边缘有肉眼可见的空隙；DWM 的 EXTENDED_FRAME_BOUNDS 才是实际边框。
    """
    rc = wintypes.RECT()
    if dwmapi is not None:
        hr = dwmapi.DwmGetWindowAttribute(HWND(hwnd), DWMWA_EXTENDED_FRAME_BOUNDS,
                                          ctypes.byref(rc), ctypes.sizeof(rc))
        if hr == 0 and rc.right > rc.left and rc.bottom > rc.top:
            return rc
    if user32.GetWindowRect(HWND(hwnd), ctypes.byref(rc)):
        return rc
    return None


def is_topmost(hwnd) -> bool:
    """读扩展样式里的 WS_EX_TOPMOST 位判断是否置顶（比猜更可靠）。"""
    return bool(user32.GetWindowLongW(HWND(hwnd), GWL_EXSTYLE) & WS_EX_TOPMOST)


def make_click_through_win32(hwnd, add_layered: bool = False) -> None:
    """
    给窗口打上「点击穿透 + 不抢焦点 + 不进 Alt+Tab」的扩展样式。
    WS_EX_TRANSPARENT 是关键：命中测试时直接跳过，鼠标事件落到下面的窗口上。
    """
    ex = user32.GetWindowLongW(HWND(hwnd), GWL_EXSTYLE)
    new = ex | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
    if add_layered and not (ex & WS_EX_LAYERED):
        new |= WS_EX_LAYERED
    user32.SetWindowLongW(HWND(hwnd), GWL_EXSTYLE, new)


def rounded_rect_points(x0, y0, x1, y1, r, seg=7):
    """生成圆角矩形的闭合路径点（Tk 画布坐标，y 轴向下）。"""
    r = max(0.0, min(float(r), (x1 - x0) / 2.0, (y1 - y0) / 2.0))
    pts = []
    corners = (((x1 - r, y1 - r), 0), ((x0 + r, y1 - r), 90),
               ((x0 + r, y0 + r), 180), ((x1 - r, y0 + r), 270))
    for (cx, cy), start in corners:
        for i in range(seg + 1):
            a = math.radians(start + 90.0 * i / seg)
            pts.append(cx + r * math.cos(a))
            pts.append(cy + r * math.sin(a))
    return pts


# ============================================================================
# 四、发光边框覆盖层
# ============================================================================
class GlowOverlay:
    """
    一个置顶窗口对应一个覆盖层。
    实现要点：
      · 顶层无边框窗口（overrideredirect）→ 没有任何标题栏/边框
      · -transparentcolor 色键透明 → 只显示画出来的发光边，中间完全透明
      · WS_EX_TRANSPARENT 点击穿透 → 完全不挡鼠标操作
      · 画 N 圈由内到外逐渐变暗的圆角矩形 → 视觉上形成霓虹光晕
    """

    def __init__(self, master: tk.Misc, target_hwnd: int):
        self.target = target_hwnd
        self.base_rgb = hex_to_rgb(CONFIG["glow_color"])
        self.rings = max(1, int(CONFIG["glow_width"]))
        self.margin = self.rings + 4          # 覆盖层比目标窗口外扩的像素数
        self.size = (-1, -1)
        self.items = []                       # 每一圈对应的画布 item id
        self.factors = []                     # 每一圈的基础亮度系数
        self.last_factor = None
        self.flash_until = time.time() + CONFIG["flash_ms"] / 1000.0
        self.hidden = False

        self.win = tk.Toplevel(master)
        self.win.overrideredirect(True)       # 无边框、无标题栏
        self.win.attributes("-topmost", True)
        self.win.configure(bg=KEY_COLOR)
        try:
            self.win.attributes("-transparentcolor", KEY_COLOR)   # 色键透明
        except tk.TclError:
            log("警告：当前 Tk 不支持 -transparentcolor，覆盖层会显示为实心方块")
        self.canvas = tk.Canvas(self.win, bg=KEY_COLOR, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        self.win.update_idletasks()
        self._apply_styles()

    # ---- 把 Windows 样式打到真正的顶层窗口句柄上 ----
    def _apply_styles(self) -> None:
        hwnd = 0
        try:
            hwnd = int(self.win.wm_frame(), 16)       # 顶层"框架"窗口（真正的 top-level）
        except Exception:
            hwnd = 0
        if not hwnd:
            hwnd = self.win.winfo_id()
        make_click_through_win32(hwnd, add_layered=True)
        log("覆盖层句柄=0x%X 目标=0x%X" % (hwnd, self.target))

    # ---- 位置 / 尺寸跟随目标窗口 ----
    def place(self, rc) -> None:
        m = self.margin
        w = (rc.right - rc.left) + 2 * m
        h = (rc.bottom - rc.top) + 2 * m
        x = rc.left - m
        y = rc.top - m
        if (w, h) != self.size:
            self.size = (w, h)
            self.win.geometry("%dx%d+%d+%d" % (w, h, x, y))
            self._rebuild(w, h)
        else:
            self.win.geometry("+%d+%d" % (x, y))     # 只移动，不重画，省 CPU
        if self.hidden:
            self.win.deiconify()
            self.win.attributes("-topmost", True)
            self._apply_styles()
            self.hidden = False

    def hide(self) -> None:
        """目标窗口最小化时把光晕一起藏起来，避免边框"飘"在屏幕上。"""
        if not self.hidden:
            self.win.withdraw()
            self.hidden = True

    # ---- 重画所有光圈 ----
    def _rebuild(self, w: int, h: int) -> None:
        self.canvas.delete("all")
        self.items, self.factors = [], []
        m = self.margin
        tw = w - 2 * m
        th = h - 2 * m
        for k in range(self.rings):
            off = k                       # 第 k 圈相对目标窗口边缘向外偏移 k 像素
            x0, y0 = m - off, m - off
            x1, y1 = m + tw + off, m + th + off
            pts = rounded_rect_points(x0, y0, x1, y1, CONFIG["radius"])
            item = self.canvas.create_polygon(pts, fill="", outline="#000000", width=2)
            self.items.append(item)
            self.factors.append((1.0 - k / float(self.rings)) ** 1.8)

    # ---- 亮度计算（呼吸灯 + 置顶瞬间的脉冲）----
    def _update_colors(self, now: float) -> None:
        if CONFIG["breath"]:
            period = max(200, int(CONFIG["breath_period_ms"])) / 1000.0
            phase = (now % period) / period
            ease = 0.5 - 0.5 * math.cos(2 * math.pi * phase)      # 0~1 平滑往复
            factor = CONFIG["breath_min"] + (1.0 - CONFIG["breath_min"]) * ease
        else:
            factor = 1.0
        if CONFIG["flash_ms"] and now < self.flash_until:
            left = (self.flash_until - now) / (CONFIG["flash_ms"] / 1000.0)
            factor *= 1.0 + 0.9 * left                            # 刚置顶时闪一下
        # 亮度变化不明显就跳过重绘，省 CPU
        if self.last_factor is not None and abs(factor - self.last_factor) < 0.012:
            return
        self.last_factor = factor
        br, bg, bb = self.base_rgb
        for item, f0 in zip(self.items, self.factors):
            f = factor * f0
            col = rgb_to_hex((min(255, int(br * f)), min(255, int(bg * f)), min(255, int(bb * f))))
            self.canvas.itemconfig(item, outline=col)

    def refresh(self, now: float) -> None:
        self._update_colors(now)

    def destroy(self) -> None:
        try:
            self.canvas.delete("all")
            self.win.destroy()
        except Exception:
            pass


# ============================================================================
# 五、热键监听线程
# ============================================================================
class HotkeyThread:
    """
    RegisterHotKey 注册的热键，会以 WM_HOTKEY 投递到「注册它的线程」的消息队列，
    所以必须在独立线程里跑自己的 GetMessage 消息循环，不能占用 Tk 的主循环。
    """

    def __init__(self, out_queue: "queue.Queue"):
        self.q = out_queue
        self.thread = None
        self.failed = []

    def start(self) -> None:
        import threading
        self.thread = threading.Thread(target=self._run, name="wintop-hotkey", daemon=True)
        self.thread.start()

    def _run(self) -> None:
        ids = {}
        for name, hid in HOTKEY_IDS.items():
            spec = {"toggle": CONFIG["hotkey_toggle"],
                    "clear": CONFIG["hotkey_clear"],
                    "quit": CONFIG["hotkey_quit"]}[name]
            try:
                mods, vk = parse_hotkey(spec)
            except ValueError as exc:
                self.failed.append("%s（配置错误：%s）" % (spec, exc))
                continue
            if user32.RegisterHotKey(None, hid, mods | MOD_NOREPEAT, vk):
                ids[hid] = name
                log("热键注册成功：%s -> id=%d" % (spec, hid))
            else:
                self.failed.append(spec)
                log("热键注册失败：%s（错误码 %d）" % (spec, ctypes.get_last_error()))
        # 把线程 ID 写进日志，便于自动化自检时直接投递 WM_HOTKEY
        try:
            import threading as _t
            log("HOTKEY_THREAD_ID=%d" % _t.get_ident())
        except Exception:
            pass
        self.q.put(("hotkeys_ready", list(self.failed)))

        msg = MSG()
        while True:
            ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if ret in (0, -1):           # 0 = WM_QUIT，-1 = 出错
                break
            if msg.message == WM_HOTKEY:
                name = ids.get(int(msg.wParam))
                if name:
                    self.q.put(("hotkey", name))
        for hid in ids:
            user32.UnregisterHotKey(None, hid)


# ============================================================================
# 六、主程序
# ============================================================================
class WinTopApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.withdraw()                    # 主窗口藏起来，只当"窗口工厂"
        self.root.title(APP_NAME)
        self.tops = {}                          # {目标窗口句柄: GlowOverlay}
        self.q = queue.Queue()
        self.frame_ms = max(15, int(1000 / max(5, CONFIG["fps"])))
        self.hotkeys = HotkeyThread(self.q)
        self.hotkeys.start()
        self.root.after(self.frame_ms, self._tick)
        self.root.after(50, self._pump)

    # ---- 取当前应该被操作的目标窗口 ----
    def current_target(self):
        fg = user32.GetForegroundWindow()
        if not fg:
            return None
        pid = DWORD()
        user32.GetWindowThreadProcessId(HWND(fg), ctypes.byref(pid))
        if pid.value == os.getpid():
            return None                         # 前台是我们自己的窗口（含光晕层），忽略
        hwnd = user32.GetAncestor(HWND(fg), GA_ROOT) or HWND(fg)
        hwnd = int(hwnd)
        if not hwnd or not user32.IsWindow(HWND(hwnd)):
            return None
        if get_class_name(hwnd) in SHELL_CLASSES:
            return None                         # 桌面 / 任务栏 不给置顶
        return hwnd

    # ---- 核心：置顶 ----
    def do_top(self, hwnd) -> None:
        ok = user32.SetWindowPos(HWND(hwnd), HWND(HWND_TOPMOST), 0, 0, 0, 0,
                                 SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_NOSENDCHANGING)
        if not ok or not is_topmost(hwnd):
            # 典型原因：目标窗口以管理员权限运行，普通进程无法改变它的层级
            err = ctypes.get_last_error()
            log("置顶失败 hwnd=0x%X err=%d" % (hwnd, err))
            Toast.show(self.root, "置顶失败：该窗口可能以管理员权限运行\n"
                                  "请右键用「以管理员身份运行」重启 WinTop")
            return
        ov = GlowOverlay(self.root, hwnd)
        self.tops[hwnd] = ov
        log("已置顶 hwnd=0x%X，当前共 %d 个" % (hwnd, len(self.tops)))

    # ---- 核心：取消置顶 ----
    def do_untop(self, hwnd) -> None:
        ov = self.tops.pop(hwnd, None)
        if ov is not None:
            ov.destroy()                        # 先销毁效果层，保证不留残影
        if user32.IsWindow(HWND(hwnd)):
            user32.SetWindowPos(HWND(hwnd), HWND(HWND_NOTOPMOST), 0, 0, 0, 0,
                                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_NOSENDCHANGING)
        log("已取消置顶 hwnd=0x%X，剩余 %d 个" % (hwnd, len(self.tops)))

    def toggle_current(self) -> None:
        hwnd = self.current_target()
        if hwnd is None:
            log("当前前台窗口不可用，忽略本次切换")
            return
        if hwnd in self.tops:
            self.do_untop(hwnd)
        else:
            self.do_top(hwnd)

    def clear_all(self) -> None:
        for hwnd in list(self.tops.keys()):
            self.do_untop(hwnd)

    def quit_app(self) -> None:
        self.clear_all()                        # 退出前恢复所有窗口层级
        log("WinTop 退出")
        try:
            self.root.destroy()
        except Exception:
            pass
        os._exit(0)                             # 热键线程还阻塞在 GetMessage，直接结束进程

    # ---- 消息泵：把热键线程的事件搬到 Tk 主线程处理（Tk 不是线程安全的）----
    def _pump(self) -> None:
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "hotkey":
                    if payload == "toggle":
                        self.toggle_current()
                    elif payload == "clear":
                        self.clear_all()
                    elif payload == "quit":
                        self.quit_app()
                        return
                elif kind == "hotkeys_ready":
                    if payload:
                        log("以下热键被占用，注册失败：%s" % "、".join(payload))
                        Toast.show(self.root, "热键被占用，注册失败：\n" +
                                   "\n".join(payload) + "\n改 win_topmost.py 里的 CONFIG 即可")
                    elif CONFIG["show_toast"]:
                        Toast.show(self.root, "%s 已启动　%s　置顶 / 取消" %
                                   (APP_NAME, CONFIG["hotkey_toggle"].upper()))
        except queue.Empty:
            pass
        self.root.after(40, self._pump)

    # ---- 跟随循环：让光晕实时粘住目标窗口 ----
    def _tick(self) -> None:
        now = time.time()
        for hwnd in list(self.tops.keys()):
            ov = self.tops[hwnd]
            try:
                if not user32.IsWindow(HWND(hwnd)):
                    self.do_untop(hwnd)                     # 窗口被关掉了，清理
                    continue
                if user32.IsIconic(HWND(hwnd)) or not user32.IsWindowVisible(HWND(hwnd)):
                    ov.hide()
                    continue
                rc = get_visual_rect(hwnd)
                if rc is None:
                    continue
                ov.place(rc)
                ov.refresh(now)
            except Exception:
                log("跟随异常：\n" + traceback.format_exc())
                self.do_untop(hwnd)
        self.root.after(self.frame_ms, self._tick)

    def run(self) -> None:
        self.root.mainloop()


# ============================================================================
# 七、右下角提示气泡
# ============================================================================
class Toast:
    """右下角弹出的临时提示（点击穿透、2.6 秒自动消失）。"""

    @staticmethod
    def show(root: tk.Misc, text: str, ms: int = 2600) -> None:
        try:
            t = tk.Toplevel(root)
            t.overrideredirect(True)
            t.attributes("-topmost", True)
            t.configure(bg="#101418")
            tk.Label(t, text=text, bg="#101418", fg=CONFIG["glow_color"],
                     font=("Microsoft YaHei UI", 10), justify="left",
                     padx=16, pady=10).pack()
            t.update_idletasks()
            w, h = t.winfo_reqwidth(), t.winfo_reqheight()
            x = t.winfo_screenwidth() - w - 24
            y = t.winfo_screenheight() - h - 64
            t.geometry("%dx%d+%d+%d" % (w, h, x, y))
            try:
                hwnd = int(t.wm_frame(), 16)
            except Exception:
                hwnd = t.winfo_id()
            make_click_through_win32(hwnd)
            root.after(ms, t.destroy)
        except Exception:
            log("提示气泡创建失败：\n" + traceback.format_exc())


# ============================================================================
# 八、入口
# ============================================================================
def main() -> None:
    enable_dpi_awareness()
    # ---- 单实例保护：onefile exe 被双开时，第二个实例的热键必然注册失败，不如直接提示退出 ----
    kernel32.CreateMutexW(None, False, "WinTop.SingleInstance")
    if ctypes.get_last_error() == 183:              # ERROR_ALREADY_EXISTS
        log("检测到已有 WinTop 实例在运行，本次启动直接退出")
        user32.MessageBoxW(None, "WinTop 已经在运行了，不用再开一份。", "WinTop", 0x40)
        return
    log("-" * 60)
    log("%s 启动，Python %s" % (APP_NAME, sys.version.split()[0]))
    try:
        app = WinTopApp()
    except Exception:
        log("启动失败：\n" + traceback.format_exc())
        raise
    app.run()


if __name__ == "__main__":
    main()
