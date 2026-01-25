#!/usr/bin/env python3
"""
Keyboard Playground — a small desktop port of keyboard-playground.html

Features:
- Displays the last key pressed in a large centered label
- Background color changes pseudo-randomly based on the key
- "ishaan" typed (case-insensitive) toggles fullscreen mode
- Fade-out of the display after 1s of inactivity (emulated using window alpha)
- Attempts to keep focus while fullscreen

Run:
	python keyboard_playground.py
"""
import sys
import tkinter as tk
from tkinter import font
import colorsys

TOGGLE_WORD = "ishaan"
SUPPORTED_KEYS_FOR_HUE = "abcdefghijklmnopqrstuvwxyz0123456789;"

# Base background used in the original HTML/CSS
BASE_BG = "#f7f7f8"

# ---- Color utilities ----
def hsl_to_hex(h, s, l):
	"""Convert HSL (degrees, %, %) to hex color string."""
	# colorsys uses H, L, S in range [0,1]
	r, g, b = colorsys.hls_to_rgb(h / 360.0, l / 100.0, s / 100.0)
	return "#{:02x}{:02x}{:02x}".format(int(r * 255), int(g * 255), int(b * 255))

def key_to_color(key):
	"""DJB2-like hash -> HSL mapping (similar to original JS keyToColor)."""
	s = str(key)
	hash_ = 5381
	for ch in s:
		hash_ = ((hash_ << 5) + hash_) + ord(ch)
		hash_ = hash_ & 0xFFFFFFFF
	hue = abs(hash_) % 360
	sat = 68 + ((abs(hash_) >> 4) % 20)
	light = 54 + ((abs(hash_) >> 8) % 15)
	return hsl_to_hex(hue, sat, light)

def key_to_color2(key):
	"""Simple hue wheel for alphanumerics (like keyToColor2)."""
	k = (key or "").lower()
	if k in SUPPORTED_KEYS_FOR_HUE:
		size = len(SUPPORTED_KEYS_FOR_HUE)
		idx = SUPPORTED_KEYS_FOR_HUE.index(k)
		hue = int((idx / size) * 360)
		return hsl_to_hex(hue, 70, 50)
	return "#444444"

def hex_to_rgb(hexcolor):
	hexcolor = hexcolor.lstrip("#")
	return tuple(int(hexcolor[i:i+2], 16) for i in (0, 2, 4))

def rgb_to_hex(rgb):
	return "#{:02x}{:02x}{:02x}".format(*rgb)

def blend_over(bg_hex, fg_rgb, alpha):
	"""Blend an fg_rgb color (0-255) over a background hex color with given alpha [0..1]."""
	bg = hex_to_rgb(bg_hex)
	r = int(round(fg_rgb[0] * alpha + bg[0] * (1 - alpha)))
	g = int(round(fg_rgb[1] * alpha + bg[1] * (1 - alpha)))
	b = int(round(fg_rgb[2] * alpha + bg[2] * (1 - alpha)))
	return (r, g, b)

# Precompute a Tk-friendly "faint" hint color equivalent to "#0000003d" (black at ~0.239 alpha)
_HINT_ALPHA = 0.239  # 0x3d / 255 ≈ 0.239
_HINT_COLOR = rgb_to_hex(blend_over(BASE_BG, (0, 0, 0), _HINT_ALPHA))

# ---- Formatting utils ----
def format_key_display(keysym, char):
	"""Format a human-friendly representation for various keys."""
	key = keysym
	if key in ("space", "Space", "spacebar") or char == " ":
		return "Space"
	if key in ("Up", "Down", "Left", "Right"):
		return {"Up": "↑", "Down": "↓", "Left": "←", "Right": "→"}[key]
	if key.startswith("Control"):
		return "Ctrl"
	if key in ("Escape", "Esc"):
		return "Esc"
	# If it's a single printable character, show it uppercased
	if char and len(char) == 1 and char.isprintable():
		return char.upper()
	# Fall back to the keysym (pretty)
	return key

# ---- App ----
class KeyboardPlayground:
	def __init__(self, root):
		self.root = root
		self.root.title("Keyboard Playground")
		self.is_fullscreen = False
		self.buffer = ""
		self.fade_after_id = None

		# Configure base window
		self.root.geometry("800x600")
		self.root.configure(bg=BASE_BG)
		# Large centered label for the key display
		self.display_font = font.Font(family="Sans", size=120, weight="bold")
		self.hint_font = font.Font(family="Sans", size=12, weight="bold")

		self.hint = tk.Label(root, text="Press any key", font=self.hint_font,
							 bg=self.root["bg"], fg=_HINT_COLOR)
		self.hint.place(relx=0.5, rely=0.03, anchor="n")

		self.label = tk.Label(root, text="_", font=self.display_font,
								bg=self.root["bg"], fg="#ffffff")
		self.label.place(relx=0.5, rely=0.5, anchor="center")

		# Bind all key events to the window
		root.bind_all("<KeyPress>", self.on_key_press, add="+")
		root.bind_all("<KeyRelease>", self.on_key_release, add="+")
		root.bind_all("<Button-1>", self.on_click, add="+")
		root.bind("<Enter>", self.on_mouse_enter)
		root.bind("<FocusOut>", self.on_focus_out)

		# Make sure the window is focusable
		root.focus_force()

		# Start with full opacity if supported
		try:
			root.attributes("-alpha", 1.0)
		except tk.TclError:
			# Some window managers don't support alpha; ignore gracefully.
			pass

	def set_bg_color(self, hexcolor):
		"""Set the window and label backgrounds to the given hex color."""
		try:
			self.root.configure(bg=hexcolor)
			self.hint.configure(bg=hexcolor)
			self.label.configure(bg=hexcolor)
		except tk.TclError:
			pass

	def start_fade_timer(self):
		"""Reset and start the fade timer (1s -> fade to low alpha)."""
		if self.fade_after_id:
			self.root.after_cancel(self.fade_after_id)
			self.fade_after_id = None
		# Restore full opacity immediately
		try:
			self.root.attributes("-alpha", 1.0)
		except tk.TclError:
			pass
		# Schedule fade
		self.fade_after_id = self.root.after(1000, self.fade_out)

	def fade_out(self):
		"""Fade out by setting window alpha low."""
		try:
			self.root.attributes("-alpha", 0.08)
		except tk.TclError:
			pass
		self.fade_after_id = None

	def on_mouse_enter(self, event=None):
		"""Cancel fade and restore alpha when mouse moves over window."""
		if self.fade_after_id:
			self.root.after_cancel(self.fade_after_id)
			self.fade_after_id = None
		try:
			self.root.attributes("-alpha", 1.0)
		except tk.TclError:
			pass

	def on_focus_out(self, event=None):
		"""If fullscreen, aggressively try to keep focus (best effort)."""
		if self.is_fullscreen:
			def focus_back():
				try:
					self.root.focus_force()
				except Exception:
					pass
			self.root.after(50, focus_back)

	def on_click(self, event):
		"""When in fullscreen, clicking the body will attempt to keep focus."""
		if self.is_fullscreen:
			try:
				self.root.focus_force()
			except Exception:
				pass

	def on_key_press(self, event):
		"""Main key handler."""
		keysym = event.keysym
		char = event.char

		# Format for display
		display_text = format_key_display(keysym, char)
		self.label.config(text=display_text)

		# Color background using second color function (prefer similar behavior)
		color = key_to_color2(char or keysym)
		self.set_bg_color(color)

		# Start/reset fade timer
		self.start_fade_timer()

		# Buffer alphabetic characters for the toggle word
		if char and len(char) == 1 and char.isalpha():
			self.buffer += char.lower()
			if len(self.buffer) > len(TOGGLE_WORD):
				self.buffer = self.buffer[-len(TOGGLE_WORD):]
		# If buffer matches, toggle fullscreen and clear buffer
		if self.buffer == TOGGLE_WORD:
			self.buffer = ""
			self.toggle_fullscreen()

		# Prevent default navigation like Tab inside the app by swallowing them here.
		if keysym in ("Tab", "F1", "F3", "F4", "F5", "F11", "F12", "Escape"):
			return "break"

	def on_key_release(self, event):
		return None

	def toggle_fullscreen(self):
		"""Enter or exit fullscreen mode, change theme accordingly."""
		self.is_fullscreen = not self.is_fullscreen
		try:
			self.root.attributes("-fullscreen", self.is_fullscreen)
		except tk.TclError:
			try:
				self.root.wm_attributes("-fullscreen", self.is_fullscreen)
			except Exception:
				pass

		if self.is_fullscreen:
			# Switch to dark theme
			self.set_bg_color("#15181b")
			self.label.config(fg="#f7f7f8")
			self.hint.config(fg="#f7f7f8")
			self.root.focus_force()
		else:
			# Restore light theme
			self.set_bg_color(BASE_BG)
			self.label.config(fg="#000000")
			self.hint.config(fg=_HINT_COLOR)
			try:
				self.root.attributes("-alpha", 1.0)
			except tk.TclError:
				pass

def main():
	root = tk.Tk()
	app = KeyboardPlayground(root)

	try:
		root.mainloop()
	except KeyboardInterrupt:
		sys.exit(0)

if __name__ == "__main__":
	main()