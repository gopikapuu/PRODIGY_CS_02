"""
Pixel Image Encryptor — tkinter GUI
=====================================
Encrypt and decrypt images using four pixel-manipulation methods:
  1. XOR Cipher       — XOR every R/G/B byte with key % 256
  2. Channel Swap     — Shuffle R/G/B channels via seeded permutation
  3. Pixel Shuffle    — Scramble pixel positions via seeded permutation
  4. Brightness Flip  — Invert each channel: 255 - value

Requirements:
    pip install Pillow numpy

Run:
    python pixel_encryptor_gui.py
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import time
import random
import numpy as np
from PIL import Image, ImageTk
import os


# ══════════════════════════════════════════════════════════════════════════════
# Colour palette  (dark amber theme)
# ══════════════════════════════════════════════════════════════════════════════
BG       = "#0a0a0f"
SURFACE  = "#111118"
CARD     = "#16161f"
BORDER   = "#2a2a3a"
AMBER    = "#f59e0b"
AMBER2   = "#fbbf24"
AMBERDIM = "#1f1a0a"
GREEN    = "#10b981"
GREENDIM = "#0a1f16"
MUTED    = "#6b6880"
TEXT     = "#e8e6f0"
RED      = "#ef4444"
CODEBG   = "#0c0a09"


# ══════════════════════════════════════════════════════════════════════════════
# Pixel encryption logic
# ══════════════════════════════════════════════════════════════════════════════

def _seeded_shuffle(n: int, seed: int):
    """Return a seeded random permutation of range(n)."""
    rng = random.Random(seed)
    indices = list(range(n))
    rng.shuffle(indices)
    return indices


def apply_xor(arr: np.ndarray, key: int) -> np.ndarray:
    k = np.uint8(key % 256)
    out = arr.copy()
    out[..., :3] ^= k
    return out


def apply_channel_swap_enc(arr: np.ndarray, key: int) -> np.ndarray:
    rng = random.Random(key ^ 0xCAFE)
    order = [0, 1, 2]
    rng.shuffle(order)
    out = arr.copy()
    out[..., 0] = arr[..., order[0]]
    out[..., 1] = arr[..., order[1]]
    out[..., 2] = arr[..., order[2]]
    return out


def apply_channel_swap_dec(arr: np.ndarray, key: int) -> np.ndarray:
    rng = random.Random(key ^ 0xCAFE)
    order = [0, 1, 2]
    rng.shuffle(order)
    out = arr.copy()
    out[..., order[0]] = arr[..., 0]
    out[..., order[1]] = arr[..., 1]
    out[..., order[2]] = arr[..., 2]
    return out


def apply_pixel_shuffle_enc(arr: np.ndarray, key: int) -> np.ndarray:
    h, w, c = arr.shape
    flat = arr.reshape(-1, c)
    indices = _seeded_shuffle(h * w, key ^ 0xDEAD)
    out = np.empty_like(flat)
    for new_pos, old_pos in enumerate(indices):
        out[new_pos] = flat[old_pos]
    return out.reshape(h, w, c)


def apply_pixel_shuffle_dec(arr: np.ndarray, key: int) -> np.ndarray:
    h, w, c = arr.shape
    flat = arr.reshape(-1, c)
    indices = _seeded_shuffle(h * w, key ^ 0xDEAD)
    out = np.empty_like(flat)
    for new_pos, old_pos in enumerate(indices):
        out[old_pos] = flat[new_pos]
    return out.reshape(h, w, c)


def apply_brightness_flip(arr: np.ndarray) -> np.ndarray:
    out = arr.copy()
    out[..., :3] = 255 - out[..., :3]
    return out


def process_image(arr: np.ndarray, key: int, methods: list, mode: str) -> np.ndarray:
    steps = methods if mode == "encrypt" else list(reversed(methods))
    for method in steps:
        reverse = (mode == "decrypt")
        if method == "xor":
            arr = apply_xor(arr, key)
        elif method == "channel":
            arr = apply_channel_swap_dec(arr, key) if reverse else apply_channel_swap_enc(arr, key)
        elif method == "pixel":
            arr = apply_pixel_shuffle_dec(arr, key) if reverse else apply_pixel_shuffle_enc(arr, key)
        elif method == "brightness":
            arr = apply_brightness_flip(arr)
    return arr


# ══════════════════════════════════════════════════════════════════════════════
# Helper widgets
# ══════════════════════════════════════════════════════════════════════════════

class RoundedFrame(tk.Canvas):
    """A canvas-backed rounded rectangle container."""
    def __init__(self, parent, radius=12, bg=CARD, border_color=BORDER, **kw):
        super().__init__(parent, bg=BG, highlightthickness=0, **kw)
        self._radius = radius
        self._bg     = bg
        self._border = border_color
        self.bind("<Configure>", self._redraw)

    def _redraw(self, _=None):
        self.delete("bg")
        w, h = self.winfo_width(), self.winfo_height()
        r = self._radius
        self.create_rounded_rect(2, 2, w-2, h-2, r, fill=self._bg,
                                 outline=self._border, tags="bg")
        self.tag_lower("bg")

    def create_rounded_rect(self, x1, y1, x2, y2, r, **kw):
        pts = [
            x1+r, y1,  x2-r, y1,
            x2,   y1,  x2,   y1+r,
            x2,   y2-r,x2,   y2,
            x2-r, y2,  x1+r, y2,
            x1,   y2,  x1,   y2-r,
            x1,   y1+r,x1,   y1,
            x1+r, y1,
        ]
        return self.create_polygon(pts, smooth=True, **kw)


# ══════════════════════════════════════════════════════════════════════════════
# Main application
# ══════════════════════════════════════════════════════════════════════════════

class PixelEncryptorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Pixel Image Encryptor")
        self.geometry("1100x720")
        self.minsize(900, 620)
        self.configure(bg=BG)

        # State
        self.orig_image    = None   # PIL Image (original)
        self.result_image  = None   # PIL Image (result)
        self.orig_tk       = None
        self.result_tk     = None
        self.method_vars   = {}
        self.key_var       = tk.IntVar(value=42)
        self.status_var    = tk.StringVar(value="READY")
        self.log_var       = tk.StringVar(value="[ System ready. Load an image to begin. ]")

        self._build_ui()
        self._apply_style()

    # ── Style ────────────────────────────────────────────────────────────────

    def _apply_style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TScale",
                         background=BG, troughcolor=BORDER,
                         sliderlength=16, sliderrelief="flat")
        style.configure("Amber.Horizontal.TScale",
                         background=BG, troughcolor=BORDER,
                         sliderlength=18, sliderrelief="flat")
        style.map("Amber.Horizontal.TScale",
                  background=[("active", BG)],
                  troughcolor=[("active", BORDER)])

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        # ── Header ────────────────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=BG)
        hdr.pack(fill="x", padx=20, pady=(18, 10))

        tk.Label(hdr, text="🔐", font=("Segoe UI Emoji", 22),
                 bg=AMBERDIM, fg=AMBER,
                 width=3, relief="flat").pack(side="left", padx=(0, 12))

        title_f = tk.Frame(hdr, bg=BG)
        title_f.pack(side="left")
        tk.Label(title_f, text="Pixel  Encryptor",
                 font=("Courier", 20, "bold"),
                 fg=TEXT, bg=BG).pack(anchor="w")
        tk.Label(title_f, text="// IMAGE ENCRYPTION VIA PIXEL MANIPULATION",
                 font=("Courier", 8), fg=MUTED, bg=BG).pack(anchor="w")

        tk.Label(hdr, textvariable=self.status_var,
                 font=("Courier", 9, "bold"), fg=AMBER,
                 bg=SURFACE, padx=10, pady=4,
                 relief="flat", bd=1).pack(side="right")

        # ── Main layout ───────────────────────────────────────────────────────
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=20, pady=(0, 8))

        # Left control panel
        left = tk.Frame(body, bg=BG, width=300)
        left.pack(side="left", fill="y", padx=(0, 12))
        left.pack_propagate(False)

        # Right canvas area
        right = tk.Frame(body, bg=BG)
        right.pack(side="left", fill="both", expand=True)

        self._build_controls(left)
        self._build_canvases(right)
        self._build_log()

    # ── Controls ──────────────────────────────────────────────────────────────

    def _build_controls(self, parent):
        # Upload section
        self._section_label(parent, "INPUT IMAGE")

        upload_frame = tk.Frame(parent, bg=CARD, bd=0,
                                highlightbackground=BORDER, highlightthickness=1)
        upload_frame.pack(fill="x", pady=(4, 12))

        tk.Label(upload_frame, text="🖼️",
                 font=("Segoe UI Emoji", 24), bg=CARD,
                 fg=TEXT).pack(pady=(14, 4))
        tk.Label(upload_frame, text="Drop image or click to open",
                 font=("Courier", 9, "bold"), fg=TEXT, bg=CARD).pack()
        tk.Label(upload_frame, text="PNG · JPG · WEBP · BMP",
                 font=("Courier", 7), fg=MUTED, bg=CARD).pack(pady=(2, 14))

        tk.Button(upload_frame, text="  Browse File  ",
                  font=("Courier", 9, "bold"),
                  bg=AMBER, fg=CODEBG, activebackground=AMBER2,
                  relief="flat", bd=0, cursor="hand2",
                  command=self._open_image).pack(pady=(0, 14))

        # Methods
        self._section_label(parent, "ENCRYPTION METHODS")
        methods_frame = tk.Frame(parent, bg=BG)
        methods_frame.pack(fill="x", pady=(4, 12))

        method_defs = [
            ("xor",        "⊕ XOR Cipher",      "XOR each byte with key",    True),
            ("channel",    "🎨 Channel Swap",    "Shuffle R/G/B channels",    True),
            ("pixel",      "🔀 Pixel Shuffle",   "Scramble pixel positions",  True),
            ("brightness", "☀ Brightness Flip",  "Invert: 255 − value",       False),
        ]

        methods_frame.columnconfigure(0, weight=1)
        methods_frame.columnconfigure(1, weight=1)

        for i, (key, label, desc, default) in enumerate(method_defs):
            var = tk.BooleanVar(value=default)
            self.method_vars[key] = var

            row, col = divmod(i, 2)
            btn = tk.Frame(methods_frame, bg=CARD if not default else AMBERDIM,
                           highlightbackground=AMBER if default else BORDER,
                           highlightthickness=1, cursor="hand2")
            btn.grid(row=row, column=col, padx=3, pady=3, sticky="nsew")

            name_parts = label.split(" ", 1)
            tk.Label(btn, text=name_parts[0],
                     font=("Segoe UI Emoji", 14), bg=btn["bg"],
                     fg=TEXT).pack(anchor="w", padx=8, pady=(8, 2))
            tk.Label(btn, text=" ".join(name_parts[1:]) if len(name_parts)>1 else label,
                     font=("Courier", 8, "bold"), fg=TEXT,
                     bg=btn["bg"]).pack(anchor="w", padx=8)
            tk.Label(btn, text=desc, font=("Courier", 7), fg=MUTED,
                     bg=btn["bg"]).pack(anchor="w", padx=8, pady=(0, 8))

            # Toggle on click
            def _toggle(b=btn, v=var, m=key):
                v.set(not v.get())
                on = v.get()
                b.configure(
                    bg=AMBERDIM if on else CARD,
                    highlightbackground=AMBER if on else BORDER)
                for w in b.winfo_children():
                    w.configure(bg=AMBERDIM if on else CARD)

            btn.bind("<Button-1>", lambda e, t=_toggle: t())
            for child in btn.winfo_children():
                child.bind("<Button-1>", lambda e, t=_toggle: t())

        # Key slider
        self._section_label(parent, "ENCRYPTION KEY  (1 – 255)")
        key_frame = tk.Frame(parent, bg=BG)
        key_frame.pack(fill="x", pady=(4, 12))

        self.key_label = tk.Label(key_frame,
                                   text=str(self.key_var.get()),
                                   font=("Courier", 14, "bold"),
                                   fg=AMBER, bg=AMBERDIM,
                                   width=4, anchor="center",
                                   relief="flat", padx=4)
        self.key_label.pack(side="right", padx=(8, 0))

        slider = ttk.Scale(key_frame, from_=1, to=255,
                           variable=self.key_var,
                           orient="horizontal",
                           style="Amber.Horizontal.TScale",
                           command=self._update_key_label)
        slider.pack(side="left", fill="x", expand=True)

        # Action buttons
        self._section_label(parent, "OPERATIONS")
        btn_frame = tk.Frame(parent, bg=BG)
        btn_frame.pack(fill="x", pady=(4, 0))
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)

        self._btn(btn_frame, "▲  ENCRYPT", AMBER, CODEBG,
                  self._encrypt).grid(row=0, column=0, padx=(0,4), pady=3, sticky="ew")
        self._btn(btn_frame, "▼  DECRYPT", GREENDIM, GREEN,
                  self._decrypt, border=GREEN).grid(row=0, column=1, padx=(4,0), pady=3, sticky="ew")
        self._btn(btn_frame, "⇄  Swap result → input", SURFACE, MUTED,
                  self._swap).grid(row=1, column=0, columnspan=2, pady=2, sticky="ew")
        self.dl_btn = self._btn(btn_frame, "⬇  Download Result", SURFACE, TEXT,
                                self._download)
        self.dl_btn.grid(row=2, column=0, columnspan=2, pady=2, sticky="ew")
        self._btn(btn_frame, "✕  Clear All", SURFACE, MUTED,
                  self._clear).grid(row=3, column=0, columnspan=2, pady=2, sticky="ew")

        # Stats
        self._section_label(parent, "IMAGE INFO")
        stats = tk.Frame(parent, bg=BG)
        stats.pack(fill="x", pady=(4, 0))
        stats.columnconfigure(0, weight=1)
        stats.columnconfigure(1, weight=1)
        stats.columnconfigure(2, weight=1)

        self.stat_w = self._stat_cell(stats, "—", "WIDTH",  0)
        self.stat_h = self._stat_cell(stats, "—", "HEIGHT", 1)
        self.stat_p = self._stat_cell(stats, "—", "PIXELS", 2)

    def _section_label(self, parent, text):
        tk.Label(parent, text=f"// {text}",
                 font=("Courier", 7), fg=MUTED,
                 bg=BG, anchor="w").pack(fill="x", pady=(8, 0))

    def _btn(self, parent, text, bg, fg, cmd, border=None):
        b = tk.Button(parent, text=text,
                      font=("Courier", 9, "bold"),
                      bg=bg, fg=fg, activebackground=bg,
                      activeforeground=fg,
                      relief="flat", bd=0,
                      padx=8, pady=8, cursor="hand2",
                      command=cmd,
                      highlightbackground=border or BORDER,
                      highlightthickness=1)
        return b

    def _stat_cell(self, parent, value, label, col):
        f = tk.Frame(parent, bg=SURFACE,
                     highlightbackground=BORDER, highlightthickness=1)
        f.grid(row=0, column=col, padx=3, pady=2, sticky="ew")
        lv = tk.Label(f, text=value,
                      font=("Courier", 13, "bold"),
                      fg=AMBER, bg=SURFACE)
        lv.pack(pady=(6, 0))
        tk.Label(f, text=label,
                 font=("Courier", 6), fg=MUTED, bg=SURFACE).pack(pady=(0, 6))
        return lv

    # ── Canvases ──────────────────────────────────────────────────────────────

    def _build_canvases(self, parent):
        # Two image panes
        panes = tk.Frame(parent, bg=BG)
        panes.pack(fill="both", expand=True)
        panes.columnconfigure(0, weight=1)
        panes.columnconfigure(1, weight=1)
        panes.rowconfigure(0, weight=1)

        self.orig_canvas   = self._img_pane(panes, "ORIGINAL",  0)
        self.result_canvas = self._img_pane(panes, "RESULT",    1)

    def _img_pane(self, parent, title, col):
        frame = tk.Frame(parent, bg=CARD,
                         highlightbackground=BORDER, highlightthickness=1)
        frame.grid(row=0, column=col, padx=(0 if col else 0, 6 if col==0 else 0),
                   pady=0, sticky="nsew")
        if col == 0:
            frame.grid(padx=(0, 6))

        header = tk.Frame(frame, bg=CARD)
        header.pack(fill="x", padx=12, pady=(10, 0))

        dot_color = AMBER if col == 0 else GREEN
        tk.Label(header, text="●", font=("Courier", 8),
                 fg=dot_color, bg=CARD).pack(side="left", padx=(0, 6))
        tk.Label(header, text=title,
                 font=("Courier", 8, "bold"), fg=MUTED,
                 bg=CARD).pack(side="left")

        self._badge_var = tk.StringVar(value="NO IMAGE" if col==0 else "PENDING")
        badge_var = tk.StringVar(value="NO IMAGE" if col==0 else "PENDING")
        badge = tk.Label(header, textvariable=badge_var,
                         font=("Courier", 7), fg=AMBER if col==0 else GREEN,
                         bg=AMBERDIM if col==0 else GREENDIM,
                         padx=6, pady=2)
        badge.pack(side="right")

        sep = tk.Frame(frame, bg=BORDER, height=1)
        sep.pack(fill="x", pady=(8, 0))

        canvas = tk.Canvas(frame, bg="#1a1a25",
                           highlightthickness=0, cursor="crosshair")
        canvas.pack(fill="both", expand=True, padx=1, pady=1)

        # Store references
        if col == 0:
            self.orig_canvas_widget  = canvas
            self.orig_badge_var      = badge_var
        else:
            self.result_canvas_widget = canvas
            self.result_badge_var     = badge_var

        return canvas

    # ── Log bar ───────────────────────────────────────────────────────────────

    def _build_log(self):
        log_frame = tk.Frame(self, bg=CARD,
                             highlightbackground=BORDER, highlightthickness=1)
        log_frame.pack(fill="x", padx=20, pady=(4, 14))

        tk.Label(log_frame, text="● OPERATION LOG",
                 font=("Courier", 7, "bold"), fg=MUTED,
                 bg=CARD, padx=12, pady=6).pack(side="left")

        tk.Label(log_frame, textvariable=self.log_var,
                 font=("Courier", 9), fg=AMBER,
                 bg=CARD, anchor="w", padx=8).pack(side="left", fill="x", expand=True)

    # ── Key label update ──────────────────────────────────────────────────────

    def _update_key_label(self, val=None):
        self.key_label.configure(text=str(int(float(self.key_var.get()))))

    # ── Image display ─────────────────────────────────────────────────────────

    def _show_image(self, pil_img, canvas_widget, badge_var, badge_text, badge_color, badge_bg):
        canvas_widget.update_idletasks()
        cw = canvas_widget.winfo_width()
        ch = canvas_widget.winfo_height()
        if cw < 10 or ch < 10:
            cw, ch = 400, 280

        # Fit image
        img_w, img_h = pil_img.size
        scale = min(cw / img_w, ch / img_h, 1.0)
        nw, nh = int(img_w * scale), int(img_h * scale)
        resized = pil_img.resize((nw, nh), Image.LANCZOS)
        tk_img  = ImageTk.PhotoImage(resized)

        canvas_widget.delete("all")
        canvas_widget.create_image(cw//2, ch//2, anchor="center", image=tk_img)
        canvas_widget.image = tk_img  # prevent GC

        badge_var.set(badge_text)
        # Can't easily change badge colors in place without storing ref — skip dynamic recolor

    # ── Open image ────────────────────────────────────────────────────────────

    def _open_image(self):
        path = filedialog.askopenfilename(
            title="Select an image",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.webp *.bmp *.gif"), ("All", "*.*")]
        )
        if not path:
            return
        try:
            img = Image.open(path).convert("RGBA")
            self.orig_image = img
            self.result_image = None

            self._show_image(img, self.orig_canvas_widget,
                             self.orig_badge_var,
                             f"{img.width}×{img.height}", AMBER, AMBERDIM)

            self.stat_w.configure(text=str(img.width))
            self.stat_h.configure(text=str(img.height))
            mp = f"{img.width * img.height / 1e6:.1f}M"
            self.stat_p.configure(text=mp)

            # Clear result pane
            self.result_canvas_widget.delete("all")
            self.result_badge_var.set("PENDING")

            self.status_var.set("IMAGE LOADED")
            self._log(f"Loaded: {os.path.basename(path)}  [{img.width}×{img.height}]")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open image:\n{e}")

    # ── Process ───────────────────────────────────────────────────────────────

    def _get_methods(self):
        return [m for m, var in self.method_vars.items() if var.get()]

    def _encrypt(self):
        self._run_process("encrypt")

    def _decrypt(self):
        self._run_process("decrypt")

    def _run_process(self, mode: str):
        if not self.orig_image:
            messagebox.showwarning("No Image", "Please load an image first.")
            return
        methods = self._get_methods()
        if not methods:
            messagebox.showwarning("No Methods", "Select at least one encryption method.")
            return

        key  = int(self.key_var.get())
        self.status_var.set("PROCESSING…")
        self._log(f"Running {mode} · methods=[{' → '.join(methods)}] · key={key}")

        def worker():
            t0   = time.time()
            arr  = np.array(self.orig_image.convert("RGBA"), dtype=np.uint8)
            result_arr = process_image(arr, key, methods, mode)
            result_img = Image.fromarray(result_arr, "RGBA")
            ms = int((time.time() - t0) * 1000)

            self.result_image = result_img
            self.after(0, lambda: self._on_result(result_img, mode, methods, key, ms))

        threading.Thread(target=worker, daemon=True).start()

    def _on_result(self, img, mode, methods, key, ms):
        badge = "ENCRYPTED" if mode == "encrypt" else "DECRYPTED"
        self._show_image(img, self.result_canvas_widget,
                         self.result_badge_var, badge, GREEN, GREENDIM)
        self.status_var.set(badge)
        self._log(
            f"{'Encrypted' if mode=='encrypt' else 'Decrypted'} · "
            f"[{' → '.join(methods)}] · key={key} · {ms}ms"
        )

    # ── Swap ─────────────────────────────────────────────────────────────────

    def _swap(self):
        if not self.result_image:
            messagebox.showinfo("Nothing to swap", "Run encrypt or decrypt first.")
            return
        self.orig_image = self.result_image
        self.result_image = None
        self._show_image(self.orig_image, self.orig_canvas_widget,
                         self.orig_badge_var,
                         f"{self.orig_image.width}×{self.orig_image.height}",
                         AMBER, AMBERDIM)
        self.result_canvas_widget.delete("all")
        self.result_badge_var.set("PENDING")
        self.status_var.set("SWAPPED")
        self._log("Swapped — result is now the input image")

    # ── Download ─────────────────────────────────────────────────────────────

    def _download(self):
        if not self.result_image:
            messagebox.showinfo("Nothing to save", "Run encrypt or decrypt first.")
            return
        path = filedialog.asksaveasfilename(
            title="Save result image",
            defaultextension=".png",
            filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg"), ("All", "*.*")],
            initialfile="encrypted_result.png"
        )
        if path:
            self.result_image.convert("RGB").save(path)
            self._log(f"Saved → {os.path.basename(path)}")
            messagebox.showinfo("Saved", f"Image saved to:\n{path}")

    # ── Clear ────────────────────────────────────────────────────────────────

    def _clear(self):
        self.orig_image    = None
        self.result_image  = None
        self.orig_canvas_widget.delete("all")
        self.result_canvas_widget.delete("all")
        self.orig_badge_var.set("NO IMAGE")
        self.result_badge_var.set("PENDING")
        self.stat_w.configure(text="—")
        self.stat_h.configure(text="—")
        self.stat_p.configure(text="—")
        self.status_var.set("READY")
        self._log("Cleared. Ready for a new image.")

    # ── Log helper ────────────────────────────────────────────────────────────

    def _log(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        self.log_var.set(f"[ {ts} ]  {msg}")


# ══════════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app = PixelEncryptorApp()
    app.mainloop()
