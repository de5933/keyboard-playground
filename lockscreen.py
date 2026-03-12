"""
Lock Screen Application
- Full screen, blocks Alt+Tab/Win/etc via low-level keyboard hook
- Shows key names on screen
- Unlock with password: ishaan
"""

import tkinter as tk
import ctypes
import ctypes.wintypes
import threading
import sys

# --- Low-level keyboard hook to block system keys ---
WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_SYSKEYDOWN = 0x0104
VK_TAB = 0x09
VK_ESCAPE = 0x1B
VK_LWIN = 0x5B
VK_RWIN = 0x5C
VK_F4 = 0x73

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

HOOKPROC = ctypes.CFUNCTYPE(
    ctypes.c_long,
    ctypes.c_int,
    ctypes.wintypes.WPARAM,
    ctypes.wintypes.LPARAM,
)


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", ctypes.wintypes.DWORD),
        ("scanCode", ctypes.wintypes.DWORD),
        ("flags", ctypes.wintypes.DWORD),
        ("time", ctypes.wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


hook_id = None
app = None


def low_level_keyboard_proc(nCode, wParam, lParam):
    if nCode >= 0:
        kb = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
        vk = kb.vkCode
        alt_down = kb.flags & 0x20  # LLKHF_ALTDOWN

        # Block: Win keys, Alt+Tab, Alt+Esc, Ctrl+Esc, Alt+F4
        if vk in (VK_LWIN, VK_RWIN):
            return 1
        if alt_down and vk == VK_TAB:
            return 1
        if alt_down and vk == VK_ESCAPE:
            return 1
        if alt_down and vk == VK_F4:
            return 1
        if vk == VK_ESCAPE:
            # Block Ctrl+Esc (opens Start)
            ctrl_down = ctypes.windll.user32.GetAsyncKeyState(0x11) & 0x8000
            if ctrl_down:
                return 1

    return user32.CallNextHookEx(hook_id, nCode, wParam, lParam)


callback = HOOKPROC(low_level_keyboard_proc)


def install_hook():
    global hook_id
    hook_id = user32.SetWindowsHookExW(
        WH_KEYBOARD_LL, callback, kernel32.GetModuleHandleW(None), 0
    )
    msg = ctypes.wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))


def uninstall_hook():
    global hook_id
    if hook_id:
        user32.UnhookWindowsHookEx(hook_id)
        hook_id = None


# --- Tkinter lock screen ---
PASSWORD = "ishaan"


class LockScreen:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Lock Screen")
        self.root.attributes("-fullscreen", True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#1a1a2e")
        self.root.overrideredirect(True)

        # Prevent closing
        self.root.protocol("WM_DELETE_WINDOW", lambda: None)

        # Rolling buffer to detect password sequence
        self.buffer = ""

        # Layout
        self.key_label = tk.Label(
            self.root,
            text="",
            font=("Consolas", 48, "bold"),
            fg="#e94560",
            bg="#1a1a2e",
        )
        self.key_label.pack(expand=True)

        self.prompt_label = tk.Label(
            self.root,
            text="Type password to unlock",
            font=("Segoe UI", 20),
            fg="#888888",
            bg="#1a1a2e",
        )
        self.prompt_label.pack(side="bottom", pady=(0, 80))

        # Bind keys
        self.root.bind("<Key>", self.on_key)
        self.root.bind("<FocusOut>", self._refocus)

        # Confine cursor
        self.root.after(200, self._confine_cursor)
        self.root.after(500, self._stay_on_top)

        # Focus
        self.root.focus_force()
        self.root.grab_set_global()

    def _confine_cursor(self):
        """Clip cursor to this window."""
        try:
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            rect = ctypes.wintypes.RECT()
            ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
            ctypes.windll.user32.ClipCursor(ctypes.byref(rect))
        except Exception:
            pass
        self.root.after(300, self._confine_cursor)

    def _stay_on_top(self):
        """Re-assert topmost and focus periodically."""
        try:
            self.root.attributes("-topmost", True)
            self.root.focus_force()
            self.root.lift()
        except Exception:
            pass
        self.root.after(500, self._stay_on_top)

    def _refocus(self, event=None):
        self.root.focus_force()
        self.root.lift()

    def on_key(self, event):
        key_name = event.keysym
        self.key_label.config(text=key_name.upper())

        # Append printable chars to rolling buffer, keep only last len(PASSWORD) chars
        if len(event.char) == 1 and event.char.isprintable():
            self.buffer = (self.buffer + event.char)[-len(PASSWORD):]
            if self.buffer == PASSWORD:
                self.unlock()

    def unlock(self):
        # Release cursor and hook, then exit
        ctypes.windll.user32.ClipCursor(None)
        uninstall_hook()
        self.root.destroy()
        sys.exit(0)

    def run(self):
        self.root.mainloop()


def main():
    # Start keyboard hook in a daemon thread
    hook_thread = threading.Thread(target=install_hook, daemon=True)
    hook_thread.start()

    global app
    app = LockScreen()
    app.run()


if __name__ == "__main__":
    main()
