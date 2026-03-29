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
        "bg":        "#020509",   # negro azulado — fondo base muy oscuro
        "surface":   "#0b1120",   # tarjetas — claramente más claro que bg
        "surface2":  "#142035",   # cabeceras de tarjeta / elementos anidados
        "border":    "#1e3a64",   # borde azul visible
        "accent":    "#3b82f6",   # azul eléctrico
        "accent_h":  "#60a5fa",   # azul hover
        "success":   "#059669",   # esmeralda
        "success_h": "#10b981",   # esmeralda hover
        "danger":    "#ef4444",   # rojo vivo
        "danger_h":  "#f87171",   # rojo hover
        "warning":   "#d97706",   # ámbar
        "warning_h": "#fbbf24",   # ámbar hover
        "text":      "#e2e8f0",   # blanco cálido
        "text2":     "#94a3b8",   # gris-azul
        "text3":     "#4a5a72",   # gris-azul oscuro
        "input_bg":  "#060d1a",   # inputs ligeramente más claro que bg
        "header":    "#010305",   # tira superior — más oscuro que bg
        "header_fg": "#e2e8f0",   # texto sobre header
        "on_air":    "#ef4444",
        "tts_bg":    "#1a1640",   # índigo oscuro
        "tts_fg":    "#818cf8",   # índigo claro
        "audio_bg":  "#012a1e",   # esmeralda muy oscuro
        "audio_fg":  "#34d399",   # esmeralda brillante
        "sonido_bg": "#2c1500",   # ámbar muy oscuro
        "sonido_fg": "#fbbf24",   # ámbar brillante
    },
    "light": {
        "bg":        "#f0f4f8",   # gris-azul suave — no blanco puro
        "surface":   "#ffffff",   # tarjetas blancas (contraste con bg)
        "surface2":  "#e2eaf4",   # cabeceras de tarjeta — azul muy claro
        "border":    "#93b4d8",   # borde azul visible
        "accent":    "#1d4ed8",   # azul más profundo
        "accent_h":  "#1e40af",   # azul hover
        "success":   "#047857",   # verde esmeralda oscuro
        "success_h": "#065f46",   # hover
        "danger":    "#dc2626",   # rojo fuerte
        "danger_h":  "#b91c1c",   # hover
        "warning":   "#b45309",   # ámbar oscuro
        "warning_h": "#92400e",   # hover
        "text":      "#0f172a",   # casi negro — alto contraste
        "text2":     "#334155",   # gris oscuro
        "text3":     "#64748b",   # gris medio
        "input_bg":  "#ffffff",
        "header":    "#1e3a5f",   # azul marino oscuro — contraste total con bg
        "header_fg": "#e2e8f0",   # texto claro para usar sobre header oscuro
        "on_air":    "#dc2626",
        "tts_bg":    "#ede9fe",   # violeta muy claro
        "tts_fg":    "#4f46e5",   # índigo
        "audio_bg":  "#d1fae5",   # verde muy claro
        "audio_fg":  "#047857",   # esmeralda
        "sonido_bg": "#fef3c7",   # ámbar muy claro
        "sonido_fg": "#b45309",   # ámbar oscuro
    },

    # ── Midnight — Negro + violeta (astronomía / espacio) ─────────────────────
    "midnight": {
        "bg":        "#06000f",   # negro con tinte violeta
        "surface":   "#100020",   # tarjetas violeta muy oscuro
        "surface2":  "#1c0038",   # cabeceras — violeta profundo
        "border":    "#42186e",   # borde violeta visible
        "accent":    "#a855f7",   # violeta eléctrico
        "accent_h":  "#c084fc",   # hover más claro
        "success":   "#06b6d4",   # cian brillante
        "success_h": "#22d3ee",
        "danger":    "#f43f5e",   # rosa-rojo
        "danger_h":  "#fb7185",
        "warning":   "#fb923c",   # naranja
        "warning_h": "#fdba74",
        "text":      "#f3e8ff",   # blanco lavanda — alto contraste
        "text2":     "#c4b5fd",   # violeta claro
        "text3":     "#6d28d9",   # violeta muted
        "input_bg":  "#0c0018",
        "header":    "#030008",
        "header_fg": "#f3e8ff",
        "on_air":    "#f43f5e",
        "tts_bg":    "#200040",
        "tts_fg":    "#d8b4fe",
        "audio_bg":  "#001a20",
        "audio_fg":  "#22d3ee",
        "sonido_bg": "#1f0d00",
        "sonido_fg": "#fdba74",
    },

    # ── Amber — Cálido oscuro + ámbar (radio vintage / tubo de vacío) ─────────
    "amber": {
        "bg":        "#0a0800",   # negro cálido
        "surface":   "#160f00",   # tarjetas marrón muy oscuro
        "surface2":  "#221700",   # cabeceras
        "border":    "#5c3d00",   # borde ámbar visible
        "accent":    "#f59e0b",   # ámbar puro
        "accent_h":  "#fbbf24",
        "success":   "#65a30d",   # lima — señal OK en radio
        "success_h": "#84cc16",
        "danger":    "#ef4444",
        "danger_h":  "#f87171",
        "warning":   "#d97706",
        "warning_h": "#f59e0b",
        "text":      "#fff8e1",   # blanco cálido — alto contraste
        "text2":     "#fcd34d",   # amarillo dorado
        "text3":     "#7c4f08",   # ámbar muted
        "input_bg":  "#0e0b00",
        "header":    "#040300",
        "header_fg": "#fff8e1",
        "on_air":    "#ef4444",
        "tts_bg":    "#1a0a00",
        "tts_fg":    "#fb923c",
        "audio_bg":  "#001400",
        "audio_fg":  "#86efac",
        "sonido_bg": "#1c1000",
        "sonido_fg": "#fcd34d",
    },

    # ── Forest — Verde oscuro (radio de campo / militar) ──────────────────────
    "forest": {
        "bg":        "#020a04",   # negro verdoso
        "surface":   "#071309",   # tarjetas verde oscuro
        "surface2":  "#0e2012",   # cabeceras
        "border":    "#1a4a20",   # borde verde visible
        "accent":    "#22c55e",   # verde brillante
        "accent_h":  "#4ade80",
        "success":   "#14b8a6",   # teal
        "success_h": "#2dd4bf",
        "danger":    "#ef4444",
        "danger_h":  "#f87171",
        "warning":   "#eab308",   # amarillo campo
        "warning_h": "#facc15",
        "text":      "#dcfce7",   # verde muy claro — alto contraste
        "text2":     "#86efac",   # verde claro
        "text3":     "#166534",   # verde muted
        "input_bg":  "#030c05",
        "header":    "#010502",
        "header_fg": "#dcfce7",
        "on_air":    "#ef4444",
        "tts_bg":    "#18154a",
        "tts_fg":    "#a5b4fc",
        "audio_bg":  "#001a08",
        "audio_fg":  "#4ade80",
        "sonido_bg": "#1a0f00",
        "sonido_fg": "#fbbf24",
    },

    # ── Ocean — Azul profundo + cian (radio marina / costera) ─────────────────
    "ocean": {
        "bg":        "#00080f",   # negro azul océano
        "surface":   "#001525",   # tarjetas azul profundo
        "surface2":  "#002035",   # cabeceras
        "border":    "#004f82",   # borde azul visible
        "accent":    "#06b6d4",   # cian brillante
        "accent_h":  "#22d3ee",
        "success":   "#10b981",
        "success_h": "#34d399",
        "danger":    "#f43f5e",
        "danger_h":  "#fb7185",
        "warning":   "#f59e0b",
        "warning_h": "#fbbf24",
        "text":      "#e0f7fa",   # blanco helado — alto contraste
        "text2":     "#67e8f9",   # cian claro
        "text3":     "#0e5f75",   # cian muted
        "input_bg":  "#000d18",
        "header":    "#00040a",
        "header_fg": "#e0f7fa",
        "on_air":    "#f43f5e",
        "tts_bg":    "#0f0030",
        "tts_fg":    "#a78bfa",
        "audio_bg":  "#001e20",
        "audio_fg":  "#22d3ee",
        "sonido_bg": "#1a0a00",
        "sonido_fg": "#fbbf24",
    },

    # ── Steel — Gris metálico neutro (estudio / consola broadcast) ────────────
    "steel": {
        "bg":        "#08090c",   # negro neutro casi puro
        "surface":   "#111318",   # tarjetas gris muy oscuro
        "surface2":  "#1a1e26",   # cabeceras gris oscuro
        "border":    "#2e3547",   # borde gris-azul visible
        "accent":    "#60a5fa",   # azul claro
        "accent_h":  "#93c5fd",
        "success":   "#34d399",
        "success_h": "#6ee7b7",
        "danger":    "#f87171",
        "danger_h":  "#fca5a5",
        "warning":   "#fbbf24",
        "warning_h": "#fde68a",
        "text":      "#f1f5f9",   # blanco frío — alto contraste
        "text2":     "#94a3b8",   # gris-azul
        "text3":     "#475569",   # gris muted
        "input_bg":  "#0d0f14",
        "header":    "#040506",
        "header_fg": "#f1f5f9",
        "on_air":    "#f87171",
        "tts_bg":    "#181530",
        "tts_fg":    "#a5b4fc",
        "audio_bg":  "#081a12",
        "audio_fg":  "#6ee7b7",
        "sonido_bg": "#1f1600",
        "sonido_fg": "#fde68a",
    },

    # ── Paper — Cálido claro (alta legibilidad / exterior) ────────────────────
    "paper": {
        "bg":        "#f5f0e8",   # papel cálido — no blanco puro
        "surface":   "#fffcf5",   # tarjetas blanco marfil
        "surface2":  "#e8dbc8",   # cabeceras arena
        "border":    "#b0956e",   # borde marrón cálido visible
        "accent":    "#1d4ed8",   # azul profundo
        "accent_h":  "#1e40af",
        "success":   "#047857",
        "success_h": "#065f46",
        "danger":    "#dc2626",
        "danger_h":  "#b91c1c",
        "warning":   "#b45309",
        "warning_h": "#92400e",
        "text":      "#1c1007",   # marrón casi negro — máximo contraste
        "text2":     "#4a3520",   # marrón cálido oscuro
        "text3":     "#8c7458",   # marrón muted
        "input_bg":  "#fffef8",
        "header":    "#2d1a0a",   # marrón oscuro — contraste total con bg
        "header_fg": "#f5f0e8",
        "on_air":    "#dc2626",
        "tts_bg":    "#eae6f8",
        "tts_fg":    "#4f46e5",
        "audio_bg":  "#d8f0e0",
        "audio_fg":  "#047857",
        "sonido_bg": "#faeacc",
        "sonido_fg": "#b45309",
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
        bordercolor=C["border"], thickness=6,
    )


# ── Botón personalizado ───────────────────────────────────────────────────────
class HButton(tk.Button):
    """Flat professional button with semantic color variants.

    Variants:
        primary  — main / neutral call-to-action   (blue)
        success  — save / confirm / connect         (green)
        edit     — edit / modify actions            (bright green)
        danger   — delete / disconnect / clear      (red)
        warning  — caution                          (amber)
        ghost    — secondary action                 (dark gray)
        muted    — cancel / dismiss                 (subtle gray)
        on_air   — PTT transmitting                 (deep red)
        info     — refresh / informational          (teal)
    """

    # (bg_normal, bg_hover, fg)
    VARIANTS: dict[str, tuple[str, str, str]] = {
        "primary": ("#3b82f6", "#2563eb", "#ffffff"),
        "success": ("#059669", "#047857", "#ffffff"),
        "edit":    ("#0d9488", "#0f766e", "#ffffff"),
        "danger":  ("#ef4444", "#dc2626", "#ffffff"),
        "warning": ("#d97706", "#b45309", "#ffffff"),
        "ghost":   ("#1c2540", "#2a3a5c", "#94a3b8"),
        "muted":   ("#131929", "#1c2540", "#64748b"),
        "on_air":  ("#991b1b", "#b91c1c", "#ffffff"),
        "info":    ("#0891b2", "#0e7490", "#ffffff"),
    }

    def __init__(self, parent, text: str = "", command: Callable = None,
                 variant: str = "ghost", width: int = None,
                 icon: str = "", **kw):
        bg, hover, fg = self.VARIANTS.get(variant, self.VARIANTS["ghost"])
        label = f"{icon}  {text}" if icon else text
        super().__init__(
            parent, text=label, command=command,
            bg=bg, fg=fg,
            activebackground=hover, activeforeground=fg,
            font=FONTS["body"], relief="flat", cursor="hand2",
            padx=14, pady=6, bd=0, highlightthickness=0, **kw
        )
        if width:
            self.config(width=width)
        self._bg    = bg
        self._hover = hover
        self._variant = variant
        self.bind("<Enter>", lambda _: self.config(bg=self._hover))
        self.bind("<Leave>", lambda _: self.config(bg=self._bg))

    def set_variant(self, variant: str) -> None:
        bg, hover, fg = self.VARIANTS.get(variant, self.VARIANTS["ghost"])
        self._bg      = bg
        self._hover   = hover
        self._variant = variant
        self.config(bg=bg, fg=fg,
                    activebackground=hover, activeforeground=fg)


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
        bf = tk.Frame(self, bg=C["bg"], pady=14)
        bf.pack(fill=tk.X, side=tk.BOTTOM)
        bf.columnconfigure(0, weight=1)
        inner = tk.Frame(bf, bg=C["bg"])
        inner.grid(row=0, column=0)
        for text, variant, cmd in buttons:
            HButton(inner, text=text, command=cmd, variant=variant).pack(
                side=tk.LEFT, padx=6)


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
