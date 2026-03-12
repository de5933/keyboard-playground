"""
Lock Screen Application v2 — with animations
- Full screen, blocks Alt+Tab/Win/etc via low-level keyboard hook
- Shows key names on screen with animations
- Floating particles, color-cycling key text, ripple on keypress
- Unlock with password sequence: ishaan
"""

import tkinter as tk
import ctypes
import ctypes.wintypes
import threading
import sys
import math
import random
import time

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

# Properly set SetWindowsHookExW return/arg types
user32.SetWindowsHookExW.restype = ctypes.wintypes.HHOOK
user32.SetWindowsHookExW.argtypes = [
    ctypes.c_int,
    ctypes.c_void_p,
    ctypes.wintypes.HINSTANCE,
    ctypes.wintypes.DWORD,
]
user32.CallNextHookEx.restype = ctypes.c_long
user32.CallNextHookEx.argtypes = [
    ctypes.wintypes.HHOOK,
    ctypes.c_int,
    ctypes.wintypes.WPARAM,
    ctypes.wintypes.LPARAM,
]
user32.UnhookWindowsHookEx.argtypes = [ctypes.wintypes.HHOOK]
user32.UnhookWindowsHookEx.restype = ctypes.wintypes.BOOL

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


BLOCKED_VKS = {VK_LWIN, VK_RWIN}
hook_id = None
hook_thread_id = None
app = None


def low_level_keyboard_proc(nCode, wParam, lParam):
    if nCode >= 0:
        kb = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
        vk = kb.vkCode
        alt_down = kb.flags & 0x20

        # Block Win keys
        if vk in BLOCKED_VKS:
            return 1
        # Block Alt+Tab, Alt+Esc, Alt+F4
        if alt_down and vk in (VK_TAB, VK_ESCAPE, VK_F4):
            return 1
        # Block Ctrl+Esc (opens Start menu) and Ctrl+Shift+Esc (Task Manager)
        if vk == VK_ESCAPE:
            if user32.GetAsyncKeyState(0x11) & 0x8000:
                return 1

    return user32.CallNextHookEx(hook_id, nCode, wParam, lParam)


# Hold a reference at module level so it cannot be garbage collected
callback = HOOKPROC(low_level_keyboard_proc)


def install_hook():
    global hook_id, hook_thread_id
    hook_thread_id = kernel32.GetCurrentThreadId()
    hook_id = user32.SetWindowsHookExW(
        WH_KEYBOARD_LL, callback, kernel32.GetModuleHandleW(None), 0
    )
    if not hook_id:
        print(f"[ERROR] SetWindowsHookExW failed: {ctypes.GetLastError()}")
        return
    print(f"[INFO] Keyboard hook installed (handle={hook_id})")
    msg = ctypes.wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))


def uninstall_hook():
    global hook_id
    if hook_id:
        user32.UnhookWindowsHookEx(hook_id)
        hook_id = None
    # Post WM_QUIT to stop the hook thread's message loop
    if hook_thread_id:
        user32.PostThreadMessageW(hook_thread_id, 0x0012, 0, 0)  # WM_QUIT


# --- Helper ---
def hsl_to_hex(h, s, l):
    """Convert HSL (h=0-360, s=0-1, l=0-1) to hex color string."""
    c = (1 - abs(2 * l - 1)) * s
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = l - c / 2
    if h < 60:
        r, g, b = c, x, 0
    elif h < 120:
        r, g, b = x, c, 0
    elif h < 180:
        r, g, b = 0, c, x
    elif h < 240:
        r, g, b = 0, x, c
    elif h < 300:
        r, g, b = x, 0, c
    else:
        r, g, b = c, 0, x
    r, g, b = int((r + m) * 255), int((g + m) * 255), int((b + m) * 255)
    return f"#{r:02x}{g:02x}{b:02x}"


# --- Tkinter lock screen ---
PASSWORD = "ishaan"
BG_COLOR = "#0a0a1a"


class Particle:
    """A floating particle on the canvas."""

    def __init__(self, canvas_w, canvas_h):
        self.x = random.uniform(0, canvas_w)
        self.y = random.uniform(0, canvas_h)
        self.r = random.uniform(1.5, 4)
        self.speed = random.uniform(0.3, 1.2)
        self.angle = random.uniform(0, 2 * math.pi)
        self.drift = random.uniform(-0.005, 0.005)
        self.hue = random.uniform(0, 360)
        self.alpha_phase = random.uniform(0, 2 * math.pi)
        self.w = canvas_w
        self.h = canvas_h

    def update(self, t):
        self.angle += self.drift
        self.x += math.cos(self.angle) * self.speed
        self.y += math.sin(self.angle) * self.speed
        # Wrap around
        if self.x < -10:
            self.x = self.w + 10
        elif self.x > self.w + 10:
            self.x = -10
        if self.y < -10:
            self.y = self.h + 10
        elif self.y > self.h + 10:
            self.y = -10
        # Pulsing brightness
        brightness = 0.3 + 0.2 * math.sin(t * 2 + self.alpha_phase)
        self.hue = (self.hue + 0.3) % 360
        return hsl_to_hex(self.hue, 0.8, brightness)


class FallingLetter:
    """A key name that falls and fades after being typed."""

    def __init__(self, text, cx, cy, hue):
        self.text = text
        self.x = cx + random.uniform(-80, 80)
        self.y = cy
        self.vy = random.uniform(1, 3)
        self.vx = random.uniform(-1.5, 1.5)
        self.life = 1.0  # 1.0 -> 0.0
        self.hue = hue
        self.size = random.randint(20, 40)
        self.item_id = None

    def update(self):
        self.y += self.vy
        self.x += self.vx
        self.vy += 0.08  # gravity
        self.life -= 0.015
        return self.life > 0


class Ripple:
    """An expanding ring on keypress."""

    def __init__(self, cx, cy, hue):
        self.cx = cx
        self.cy = cy
        self.radius = 10
        self.max_radius = random.uniform(150, 300)
        self.hue = hue
        self.life = 1.0
        self.item_id = None

    def update(self):
        self.radius += 4
        self.life = max(0, 1 - self.radius / self.max_radius)
        return self.life > 0


class LockScreen:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Lock Screen")
        self.root.attributes("-fullscreen", True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=BG_COLOR)
        self.root.overrideredirect(True)
        self.root.protocol("WM_DELETE_WINDOW", lambda: None)

        self.buffer = ""
        self.hue = 0.0
        self.start_time = time.time()

        # Canvas for all drawing
        self.w = self.root.winfo_screenwidth()
        self.h = self.root.winfo_screenheight()
        self.canvas = tk.Canvas(
            self.root, width=self.w, height=self.h, bg=BG_COLOR, highlightthickness=0
        )
        self.canvas.pack(fill="both", expand=True)

        # Hide the OS cursor
        self.root.config(cursor="none")

        # Custom cursor elements (crosshair + ring)
        self.cursor_ring_id = self.canvas.create_oval(0, 0, 0, 0, outline="#e94560", width=2)
        self.cursor_dot_id = self.canvas.create_oval(0, 0, 0, 0, fill="#e94560", outline="")
        self.cursor_trail = []  # list of (item_id, life)
        self.mouse_x = self.w // 2
        self.mouse_y = self.h // 2
        self.canvas.bind("<Motion>", self._on_mouse_move)

        # Particles
        self.particles = [Particle(self.w, self.h) for _ in range(80)]
        self.particle_ids = []

        # Falling letters & ripples
        self.falling_letters = []
        self.ripples = []

        # Key display text (center)
        self.key_text_id = self.canvas.create_text(
            self.w // 2,
            self.h // 2,
            text="",
            font=("Consolas", 72, "bold"),
            fill="#e94560",
        )


        # Bind keys and mouse
        self.root.bind("<Key>", self.on_key)
        self.root.bind("<Button-1>", self._on_left_click)
        self.root.bind("<Button-2>", self._on_middle_click)
        self.root.bind("<Button-3>", self._on_right_click)
        self.root.bind("<FocusOut>", self._refocus)

        # Confine cursor & stay on top
        self.root.after(200, self._confine_cursor)
        self.root.after(500, self._stay_on_top)

        # Focus
        self.root.focus_force()
        self.root.grab_set_global()

        # Start animation loop
        self._animate()

    def _animate(self):
        t = time.time() - self.start_time
        self.hue = (self.hue + 0.5) % 360

        # Cycle the main key text color
        key_color = hsl_to_hex((self.hue * 3) % 360, 0.9, 0.55)
        self.canvas.itemconfig(self.key_text_id, fill=key_color)

        # Gentle float on key text
        offset_y = math.sin(t * 1.5) * 8
        self.canvas.coords(self.key_text_id, self.w // 2, self.h // 2 + offset_y)

        # Draw particles
        for pid in self.particle_ids:
            self.canvas.delete(pid)
        self.particle_ids.clear()

        for p in self.particles:
            color = p.update(t)
            pid = self.canvas.create_oval(
                p.x - p.r, p.y - p.r, p.x + p.r, p.y + p.r, fill=color, outline=""
            )
            self.particle_ids.append(pid)

        # Update ripples
        for ripple in self.ripples[:]:
            if ripple.item_id:
                self.canvas.delete(ripple.item_id)
            if not ripple.update():
                self.ripples.remove(ripple)
                continue
            color = hsl_to_hex(ripple.hue, 0.7, 0.2 + 0.3 * ripple.life)
            ripple.item_id = self.canvas.create_oval(
                ripple.cx - ripple.radius,
                ripple.cy - ripple.radius,
                ripple.cx + ripple.radius,
                ripple.cy + ripple.radius,
                outline=color,
                width=2,
            )

        # Update falling letters
        for fl in self.falling_letters[:]:
            if fl.item_id:
                self.canvas.delete(fl.item_id)
            if not fl.update():
                self.falling_letters.remove(fl)
                continue
            lightness = 0.2 + 0.4 * fl.life
            color = hsl_to_hex(fl.hue, 0.8, lightness)
            fl.item_id = self.canvas.create_text(
                fl.x, fl.y, text=fl.text, font=("Consolas", fl.size, "bold"), fill=color
            )

        # Update custom cursor
        mx, my = self.mouse_x, self.mouse_y
        ring_r = 16 + 4 * math.sin(t * 3)
        ring_color = hsl_to_hex((self.hue * 3) % 360, 0.9, 0.55)
        self.canvas.coords(self.cursor_ring_id, mx - ring_r, my - ring_r, mx + ring_r, my + ring_r)
        self.canvas.itemconfig(self.cursor_ring_id, outline=ring_color)
        self.canvas.coords(self.cursor_dot_id, mx - 3, my - 3, mx + 3, my + 3)
        self.canvas.itemconfig(self.cursor_dot_id, fill=ring_color)

        # Update cursor trail
        for trail_id, life in self.cursor_trail[:]:
            if life <= 0:
                self.canvas.delete(trail_id)
                self.cursor_trail.remove((trail_id, life))
            else:
                idx = self.cursor_trail.index((trail_id, life))
                self.cursor_trail[idx] = (trail_id, life - 0.06)
                tr_color = hsl_to_hex(self.hue, 0.6, 0.1 + 0.3 * life)
                self.canvas.itemconfig(trail_id, outline=tr_color)

        # Ensure key text and cursor stay on top
        self.canvas.tag_raise(self.key_text_id)
        self.canvas.tag_raise(self.cursor_ring_id)
        self.canvas.tag_raise(self.cursor_dot_id)

        self.root.after(33, self._animate)  # ~30 fps

    def _confine_cursor(self):
        try:
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            rect = ctypes.wintypes.RECT()
            ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
            ctypes.windll.user32.ClipCursor(ctypes.byref(rect))
        except Exception:
            pass
        self.root.after(300, self._confine_cursor)

    def _stay_on_top(self):
        try:
            self.root.attributes("-topmost", True)
            self.root.focus_force()
            self.root.lift()
        except Exception:
            pass
        self.root.after(500, self._stay_on_top)

    def _on_mouse_move(self, event):
        self.mouse_x = event.x
        self.mouse_y = event.y
        # Spawn a trail circle
        r = 8
        trail_id = self.canvas.create_oval(
            event.x - r, event.y - r, event.x + r, event.y + r,
            outline=hsl_to_hex(self.hue, 0.6, 0.4), width=1,
        )
        self.cursor_trail.append((trail_id, 1.0))
        # Cap trail length
        if len(self.cursor_trail) > 30:
            old_id, _ = self.cursor_trail.pop(0)
            self.canvas.delete(old_id)

    def _on_left_click(self, event):
        self.ripples.append(Ripple(event.x, event.y, 0))  # red

    def _on_right_click(self, event):
        self.ripples.append(Ripple(event.x, event.y, 120))  # green

    def _on_middle_click(self, event):
        self.ripples.append(Ripple(event.x, event.y, 240))  # blue

    def _refocus(self, event=None):
        self.root.focus_force()
        self.root.lift()

    def on_key(self, event):
        key_name = event.keysym.upper()
        self.canvas.itemconfig(self.key_text_id, text=key_name)

        # Spawn a ripple at center
        self.ripples.append(Ripple(self.w // 2, self.h // 2, self.hue))

        # Spawn falling letter
        if len(key_name) <= 3:
            self.falling_letters.append(
                FallingLetter(key_name, self.w // 2, self.h // 2, self.hue)
            )

        # Password detection
        if len(event.char) == 1 and event.char.isprintable():
            self.buffer = (self.buffer + event.char)[-len(PASSWORD):]
            if self.buffer == PASSWORD:
                self.unlock()

    def unlock(self):
        ctypes.windll.user32.ClipCursor(None)
        uninstall_hook()
        self.root.destroy()
        sys.exit(0)

    def run(self):
        self.root.mainloop()


def main():
    hook_thread = threading.Thread(target=install_hook, daemon=True)
    hook_thread.start()

    global app
    app = LockScreen()
    app.run()


if __name__ == "__main__":
    main()
