"""
HAMNA Desktop — Tema visual, colores y widgets base
Tkinter dark theme inspirado en software de radiodifusión profesional.
"""
import tkinter as tk
from tkinter import ttk
from typing import Callable

# ── Paletas ───────────────────────────────────────────────────────────────────
PALETTES: dict[str, dict] = {
    "dark": {
        "bg":        "#0d1117",
        "surface":   "#161b22",
        "surface2":  "#21262d",
        "border":    "#30363d",
        "accent":    "#1f6feb",
        "accent_h":  "#388bfd",
        "success":   "#238636",
        "success_h": "#2ea043",
        "danger":    "#da3633",
        "danger_h":  "#f85149",
        "warning":   "#9e6a03",
        "warning_h": "#d29922",
        "text":      "#e6edf3",
        "text2":     "#8b949e",
        "text3":     "#484f58",
        "input_bg":  "#0d1117",
        "header":    "#010409",
        "on_air":    "#da3633",
        "tts_bg":    "#1c2a3a",
        "tts_fg":    "#388bfd",
        "audio_bg":  "#1a2d1a",
        "audio_fg":  "#3fb950",
        "sonido_bg": "#2d2114",
        "sonido_fg": "#d29922",
    },
    "light": {
        "bg":        "#f6f8fa",
        "surface":   "#ffffff",
        "surface2":  "#f3f4f6",
        "border":    "#d0d7de",
        "accent":    "#0969da",
        "accent_h":  "#0550ae",
        "success":   "#1a7f37",
        "success_h": "#116329",
        "danger":    "#cf222e",
        "danger_h":  "#a40e26",
        "warning":   "#9a6700",
        "warning_h": "#7d4e00",
        "text":      "#24292f",
        "text2":     "#57606a",
        "text3":     "#8c959f",
        "input_bg":  "#ffffff",
        "header":    "#eaeef2",
        "on_air":    "#cf222e",
        "tts_bg":    "#ddf4ff",
        "tts_fg":    "#0969da",
        "audio_bg":  "#dafbe1",
        "audio_fg":  "#1a7f37",
        "sonido_bg": "#fff8c5",
        "sonido_fg": "#9a6700",
    },
}

# C es la paleta activa — se actualiza con apply_palette() antes de crear widgets
C = dict(PALETTES["dark"])


def apply_palette(theme_name: str) -> None:
    """Actualiza C con la paleta del tema indicado.
    Debe llamarse ANTES de crear cualquier widget."""
    C.update(PALETTES.get(theme_name, PALETTES["dark"]))


def apply_fonts(base_size: int = 10) -> None:
    """Recalculates FONTS with a new base size. Call before creating widgets."""
    b = max(8, min(16, base_size))
    FONTS["h1"]      = ("Segoe UI", b + 6, "bold")
    FONTS["h2"]      = ("Segoe UI", b + 3, "bold")
    FONTS["h3"]      = ("Segoe UI", b + 1, "bold")
    FONTS["body"]    = ("Segoe UI", b)
    FONTS["small"]   = ("Segoe UI", max(8, b - 1))
    FONTS["mono"]    = ("Consolas", b)
    FONTS["mono_sm"] = ("Consolas", max(8, b - 1))
    FONTS["badge"]   = ("Segoe UI", max(7, b - 2), "bold")

FONTS = {
    "h1":    ("Segoe UI", 16, "bold"),
    "h2":    ("Segoe UI", 13, "bold"),
    "h3":    ("Segoe UI", 11, "bold"),
    "body":  ("Segoe UI", 10),
    "small": ("Segoe UI", 9),
    "mono":  ("Consolas", 10),
    "mono_sm": ("Consolas", 9),
    "badge": ("Segoe UI", 8, "bold"),
}

TIPO_COLORS = {
    "TTS":    (C["tts_bg"],    C["tts_fg"]),
    "Audio":  (C["audio_bg"],  C["audio_fg"]),
    "Sonido": (C["sonido_bg"], C["sonido_fg"]),
}


# ── Aplicar tema ttk ──────────────────────────────────────────────────────────
def apply_theme(root: tk.Misc) -> None:
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(".",
        background=C["bg"], foreground=C["text"],
        fieldbackground=C["input_bg"], bordercolor=C["border"],
        darkcolor=C["surface"], lightcolor=C["surface2"],
        troughcolor=C["surface"], selectbackground=C["accent"],
        selectforeground=C["text"], insertcolor=C["text"],
        font=FONTS["body"],
    )
    style.configure("TFrame",   background=C["bg"])
    style.configure("TLabel",   background=C["bg"], foreground=C["text"])
    style.configure("Muted.TLabel", background=C["bg"], foreground=C["text2"])
    style.configure("Small.TLabel", background=C["bg"], foreground=C["text3"],
                    font=FONTS["small"])
    style.configure("Surface.TFrame",  background=C["surface"])
    style.configure("Surface.TLabel",  background=C["surface"], foreground=C["text"])
    style.configure("Surface2.TFrame", background=C["surface2"])
    style.configure("TEntry",
        fieldbackground=C["input_bg"], foreground=C["text"],
        insertcolor=C["text"], bordercolor=C["border"],
        lightcolor=C["border"], darkcolor=C["border"], padding=(8, 6),
    )
    style.map("TEntry",
        bordercolor=[("focus", C["accent"])],
        lightcolor=[("focus", C["accent"])],
    )
    style.configure("TCombobox",
        fieldbackground=C["input_bg"], background=C["surface2"],
        foreground=C["text"], arrowcolor=C["text2"],
        bordercolor=C["border"], padding=(8, 6),
    )
    style.map("TCombobox",
        fieldbackground=[("readonly", C["input_bg"])],
        bordercolor=[("focus", C["accent"])],
    )
    style.configure("TScrollbar",
        background=C["surface2"], troughcolor=C["surface"],
        arrowcolor=C["text2"], bordercolor=C["border"],
    )
    style.configure("Treeview",
        background=C["surface"], foreground=C["text"],
        fieldbackground=C["surface"], rowheight=32,
        bordercolor=C["border"],
    )
    style.configure("Treeview.Heading",
        background=C["surface2"], foreground=C["text2"],
        relief="flat", font=FONTS["badge"],
    )
    style.map("Treeview",
        background=[("selected", C["accent"])],
        foreground=[("selected", C["text"])],
    )
    style.map("Treeview.Heading",
        background=[("active", C["border"])],
    )
    style.configure("TSeparator", background=C["border"])
    style.configure("TNotebook",
        background=C["header"], bordercolor=C["border"],
    )
    style.configure("TNotebook.Tab",
        background=C["surface"], foreground=C["text2"],
        padding=(14, 8), font=FONTS["body"],
    )
    style.map("TNotebook.Tab",
        background=[("selected", C["bg"])],
        foreground=[("selected", C["accent"])],
    )
    style.configure("TProgressbar",
        troughcolor=C["surface2"], background=C["accent"],
        bordercolor=C["border"],
    )


# ── Botón personalizado ───────────────────────────────────────────────────────
class HButton(tk.Canvas):
    """Modern rounded-corner button.

    Variants and their intent:
        primary  — main / neutral action          (blue fill)
        success  — save / confirm / connect       (green fill)
        danger   — delete / disconnect / clear    (red fill)
        warning  — caution action                 (amber fill)
        ghost    — secondary / outlined style     (transparent + border)
        muted    — cancel / dismiss               (mid-gray fill)
        on_air   — PTT transmitting               (deep red + border)

    Colors are read from C at draw-time so theme changes are respected.
    """

    # Variant spec:  (bg, bg_hover, fg, border, border_hover)
    # bg="" means transparent (use parent bg).  border=None = no border.
    _VARIANTS: dict[str, tuple] = {
        "primary": ("accent",   "accent_h",   "#ffffff",  None,       None),
        "success": ("success",  "success_h",  "#ffffff",  None,       None),
        "danger":  ("danger",   "danger_h",   "#ffffff",  None,       None),
        "warning": ("warning_h","_amber_h",   "#ffffff",  None,       None),
        "ghost":   ("",         "surface2",   "text2",    "border",   "accent"),
        "muted":   ("_gray",    "surface2",   "text2",    "border",   None),
        "on_air":  ("on_air",   "danger_h",   "#ffffff",  "danger_h", "danger_h"),
    }
    # Extra literal colors not in palette
    _EXTRA = {"_amber_h": "#e6a817", "_gray": "#3a404a"}

    _H     = 30    # fixed pixel height
    _R     = 5     # corner radius
    _PX    = 16    # horizontal text padding
    _MIN_W = 80    # minimum pixel width

    def __init__(self, parent, text: str = "", command: Callable = None,
                 variant: str = "ghost", width: int = None,
                 icon: str = "", **kw):
        import tkinter.font as _tkfont

        self._label   = f"{icon}  {text}" if icon else text
        self._variant = variant
        self._command = command
        self._hot     = False
        self._enabled = True

        # Measure text to auto-size canvas width
        _mf = _tkfont.Font(family=FONTS["body"][0], size=FONTS["body"][1])
        cw  = max(self._MIN_W, _mf.measure(self._label) + self._PX * 2)
        if width:
            cw = max(cw, width)

        # Canvas bg = parent bg so rounded corners blend seamlessly
        try:
            pbg = parent.cget("bg")
        except Exception:
            pbg = C["bg"]

        for _k in ("padx", "pady", "bd", "relief", "anchor",
                   "activebackground", "activeforeground"):
            kw.pop(_k, None)
        kw["highlightthickness"] = 0
        kw["cursor"] = "hand2"
        super().__init__(parent, width=cw, height=self._H, bg=pbg, **kw)

        self.bind("<Configure>",       lambda e: self._draw())
        self.bind("<Enter>",           self._on_enter)
        self.bind("<Leave>",           self._on_leave)
        self.bind("<ButtonPress-1>",   self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self._draw()

    # ── color helpers ──────────────────────────────────────────────────────
    def _resolve(self, key: str | None) -> str | None:
        """Resolve a palette key or literal hex color to an actual hex color."""
        if key is None or key == "":
            return None
        if key.startswith("#"):
            return key
        if key in self._EXTRA:
            return self._EXTRA[key]
        return C.get(key, "#888888")

    def _colors(self) -> tuple:
        """Return (fill, fill_hover, fg, border, border_hover) for current variant."""
        spec = self._VARIANTS.get(self._variant, self._VARIANTS["ghost"])
        bg_key, bgh_key, fg_raw, bdr_key, bdrh_key = spec
        fill      = self._resolve(bg_key)      # None = transparent
        fill_h    = self._resolve(bgh_key)
        fg        = self._resolve(fg_raw) or C["text"]
        border    = self._resolve(bdr_key)
        border_h  = self._resolve(bdrh_key)
        return fill, fill_h, fg, border, border_h

    # ── drawing ────────────────────────────────────────────────────────────
    def _rrect(self, x0: float, y0: float, x1: float, y1: float,
               r: int, **kw):
        pts = [x0+r, y0,  x1-r, y0,
               x1,   y0+r, x1,  y1-r,
               x1-r, y1,   x0+r, y1,
               x0,   y1-r, x0,   y0+r]
        return self.create_polygon(pts, smooth=True, **kw)

    def _draw(self) -> None:
        self.delete("all")
        w = self.winfo_width()
        if w <= 1:
            try:
                w = int(self["width"])
            except Exception:
                w = self._MIN_W
        h, r, pad = self._H, self._R, 1

        fill, fill_h, fg, border, border_h = self._colors()

        if not self._enabled:
            # Disabled: uniform muted appearance
            eff_fill   = C["surface2"]
            eff_border = C["border"]
            eff_fg     = C["text3"]
        else:
            eff_fill   = fill_h  if self._hot else fill
            eff_border = border_h if (self._hot and border_h) else border
            eff_fg     = fg

        # Background fill (None = transparent, skip drawing)
        if eff_fill:
            self._rrect(pad, pad, w - pad, h - pad, r,
                        fill=eff_fill, outline="", tags="bg")

        # Border
        if eff_border:
            self._rrect(pad, pad, w - pad, h - pad, r,
                        fill="", outline=eff_border, width=1, tags="bdr")

        # Label
        self.create_text(w // 2, h // 2, text=self._label,
                         font=FONTS["body"], fill=eff_fg,
                         anchor="center", tags="lbl")

    # ── events ─────────────────────────────────────────────────────────────
    def _on_enter(self, _e) -> None:
        if self._enabled:
            self._hot = True
            self._draw()

    def _on_leave(self, _e) -> None:
        self._hot = False
        self._draw()

    def _on_press(self, _e) -> None:
        pass

    def _on_release(self, _e) -> None:
        if self._enabled and callable(self._command):
            self._command()

    # ── public API ─────────────────────────────────────────────────────────
    def config(self, **kw) -> None:  # type: ignore[override]
        import tkinter.font as _tkfont
        redraw = False
        if "text" in kw:
            self._label = kw.pop("text")
            _mf = _tkfont.Font(family=FONTS["body"][0], size=FONTS["body"][1])
            cw  = max(self._MIN_W, _mf.measure(self._label) + self._PX * 2)
            super().config(width=cw)
            redraw = True
        if "state" in kw:
            self._enabled = kw.pop("state") != "disabled"
            super().config(cursor="hand2" if self._enabled else "")
            redraw = True
        if "command" in kw:
            self._command = kw.pop("command")
        for _k in ("padx", "pady", "bd", "relief", "anchor",
                   "activebackground", "activeforeground",
                   "fg", "bg", "font"):
            kw.pop(_k, None)
        if kw:
            super().config(**kw)
        if redraw:
            self._draw()

    configure = config  # type: ignore[assignment]

    def set_variant(self, variant: str) -> None:
        self._variant = variant
        self._draw()


# ── Diálogo modal base ────────────────────────────────────────────────────────
class HDialog(tk.Toplevel):
    def __init__(self, parent, title="", width=520, height=460):
        super().__init__(parent)
        self.title(title)
        self.configure(bg=C["bg"])
        self.resizable(True, True)
        apply_theme(self)
        self.update_idletasks()
        px = parent.winfo_rootx() + (parent.winfo_width()  - width)  // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - height) // 2
        self.geometry(f"{width}x{height}+{max(px,20)}+{max(py,20)}")
        self.transient(parent)
        self.grab_set()

    def make_header(self, title: str, subtitle: str = "") -> None:
        hf = tk.Frame(self, bg=C["surface"], padx=20, pady=14)
        hf.pack(fill=tk.X)
        tk.Label(hf, text=title, font=FONTS["h2"],
                 bg=C["surface"], fg=C["text"]).pack(anchor="w")
        if subtitle:
            tk.Label(hf, text=subtitle, font=FONTS["small"],
                     bg=C["surface"], fg=C["text2"]).pack(anchor="w", pady=(2,0))
        tk.Frame(self, bg=C["border"], height=1).pack(fill=tk.X)

    def make_footer(self, buttons: list[tuple]) -> None:
        """buttons = [("Texto", variant, command), ...]"""
        tk.Frame(self, bg=C["border"], height=1).pack(fill=tk.X, side=tk.BOTTOM)
        bf = tk.Frame(self, bg=C["bg"], pady=12, padx=20)
        bf.pack(fill=tk.X, side=tk.BOTTOM)
        for i, (text, variant, cmd) in enumerate(reversed(buttons)):
            HButton(bf, text=text, command=cmd, variant=variant).pack(
                side=tk.RIGHT, padx=(8 if i else 0, 0))


# ── Widgets utilitarios ───────────────────────────────────────────────────────
def make_section_badge(parent: tk.Frame, tipo: str) -> tk.Label:
    bg, fg = TIPO_COLORS.get(tipo, (C["surface2"], C["text2"]))
    lbl = tk.Label(parent, text=tipo, font=FONTS["badge"],
                   bg=bg, fg=fg, padx=6, pady=2)
    return lbl


def labeled_entry(parent: tk.Frame, label: str, row: int,
                  col: int = 0, colspan: int = 1,
                  show: str = "") -> ttk.Entry:
    tk.Label(parent, text=label, font=FONTS["badge"],
             bg=C["bg"], fg=C["text2"]).grid(
        row=row, column=col, sticky="w", pady=(10, 2), padx=(0, 8))
    e = ttk.Entry(parent, show=show)
    e.grid(row=row + 1, column=col, columnspan=colspan, sticky="ew", pady=(0, 4))
    return e


def labeled_combo(parent: tk.Frame, label: str,
                  values: list[str], row: int,
                  col: int = 0) -> ttk.Combobox:
    tk.Label(parent, text=label, font=FONTS["badge"],
             bg=C["bg"], fg=C["text2"]).grid(
        row=row, column=col, sticky="w", pady=(10, 2))
    cb = ttk.Combobox(parent, values=values, state="readonly")
    cb.grid(row=row + 1, column=col, sticky="ew", pady=(0, 4))
    return cb


def separator(parent: tk.Frame) -> None:
    tk.Frame(parent, bg=C["border"], height=1).pack(fill=tk.X, pady=8)


class HSlider(tk.Canvas):
    """Modern flat slider — drop-in replacement for tk.Scale.

    API compatible with tk.Scale:
        .get()        → current int value
        .set(value)   → set value without firing command
        command=cb    → called with int value on change
    """

    _TRACK_H = 4
    _THUMB_R = 7
    _PAD_L   = 10   # left padding
    _PAD_R   = 36   # right padding (space for value label)

    def __init__(self, parent, from_: int = 0, to: int = 100,
                 command=None, **kw):
        kw.setdefault("height", 34)
        kw.setdefault("bg", C["surface"])
        kw.setdefault("highlightthickness", 0)
        kw.setdefault("cursor", "hand2")
        super().__init__(parent, **kw)

        self._from    = int(from_)
        self._to      = int(to)
        self._value   = float(from_)
        self._command = command
        self._hot     = False          # hover state

        self.bind("<Configure>",     lambda e: self._draw())
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<B1-Motion>",     self._on_drag)
        self.bind("<Enter>",         lambda e: self._set_hot(True))
        self.bind("<Leave>",         lambda e: self._set_hot(False))

    # ── geometry helpers ───────────────────────────────────────────────────
    def _track_x0(self) -> int:
        return self._PAD_L

    def _track_x1(self) -> int:
        w = self.winfo_width() or int(self["width"]) if self["width"] else 200
        return w - self._PAD_R

    def _thumb_x(self) -> float:
        span = self._to - self._from
        if span == 0:
            return self._track_x0()
        frac = (self._value - self._from) / span
        return self._track_x0() + frac * (self._track_x1() - self._track_x0())

    def _x_to_value(self, x: int) -> float:
        x0, x1 = self._track_x0(), self._track_x1()
        frac = max(0.0, min(1.0, (x - x0) / max(1, x1 - x0)))
        return self._from + frac * (self._to - self._from)

    # ── drawing ────────────────────────────────────────────────────────────
    def _draw(self):
        self.delete("all")
        w  = self.winfo_width() or 200
        h  = self.winfo_height() or 34
        cy = h // 2
        x0 = self._track_x0()
        x1 = self._track_x1()
        tx = self._thumb_x()
        r  = self._TRACK_H // 2
        tr = self._THUMB_R

        # track background
        self.create_rectangle(x0, cy - r, x1, cy + r,
                               fill=C["surface2"], outline="", tags="bg")
        # track fill
        if tx > x0:
            self.create_rectangle(x0, cy - r, int(tx), cy + r,
                                   fill=C["accent"], outline="", tags="fill")
        # thumb drop-shadow
        self.create_oval(int(tx) - tr + 1, cy - tr + 1,
                          int(tx) + tr + 1, cy + tr + 1,
                          fill=C["bg"], outline="", tags="shadow")
        # thumb
        fill_col = C["accent_h"] if self._hot else C["accent"]
        self.create_oval(int(tx) - tr, cy - tr, int(tx) + tr, cy + tr,
                          fill=fill_col, outline="#ffffff", width=2,
                          tags="thumb")
        # value label
        self.create_text(x1 + self._PAD_R // 2, cy,
                          text=str(int(round(self._value))),
                          font=FONTS["small"], fill=C["text2"],
                          anchor="center", tags="val")

    # ── event handlers ─────────────────────────────────────────────────────
    def _set_hot(self, state: bool):
        self._hot = state
        self._draw()

    def _on_press(self, e):
        self._update(e.x)

    def _on_drag(self, e):
        self._update(e.x)

    def _update(self, x: int):
        raw = self._x_to_value(x)
        self._value = max(float(self._from), min(float(self._to), raw))
        self._draw()
        if callable(self._command):
            self._command(int(round(self._value)))

    # ── public API ─────────────────────────────────────────────────────────
    def get(self) -> int:
        return int(round(self._value))

    def set(self, value) -> None:
        self._value = max(float(self._from), min(float(self._to), float(value)))
        self._draw()
