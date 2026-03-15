"""
HAMNA Desktop — Tema visual, colores y widgets base
Tkinter dark theme inspirado en software de radiodifusión profesional.
"""
import tkinter as tk
from tkinter import ttk
from typing import Callable

# ── Paleta ────────────────────────────────────────────────────────────────────
C = {
    "bg":           "#0d1117",
    "surface":      "#161b22",
    "surface2":     "#21262d",
    "border":       "#30363d",
    "accent":       "#1f6feb",
    "accent_h":     "#388bfd",
    "success":      "#238636",
    "success_h":    "#2ea043",
    "danger":       "#da3633",
    "danger_h":     "#f85149",
    "warning":      "#9e6a03",
    "warning_h":    "#d29922",
    "text":         "#e6edf3",
    "text2":        "#8b949e",
    "text3":        "#484f58",
    "input_bg":     "#0d1117",
    "header":       "#010409",
    "on_air":       "#da3633",
    "tts_bg":       "#1c2a3a",
    "tts_fg":       "#388bfd",
    "audio_bg":     "#1a2d1a",
    "audio_fg":     "#3fb950",
    "sonido_bg":    "#2d2114",
    "sonido_fg":    "#d29922",
}

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
class HButton(tk.Button):
    VARIANTS = {
        "primary": (C["accent"],   C["accent_h"],   "#ffffff"),
        "success": (C["success"],  C["success_h"],  "#ffffff"),
        "danger":  (C["danger"],   C["danger_h"],   "#ffffff"),
        "warning": (C["warning"],  C["warning_h"],  "#ffffff"),
        "ghost":   (C["surface2"], C["border"],     C["text2"]),
        "muted":   (C["surface"],  C["surface2"],   C["text2"]),
        "on_air":  (C["danger"],   C["danger_h"],   "#ffffff"),
    }

    def __init__(self, parent, text="", command: Callable = None,
                 variant="ghost", width=None, icon="", **kw):
        bg, hover, fg = self.VARIANTS.get(variant, self.VARIANTS["ghost"])
        label = f"{icon}  {text}" if icon else text
        super().__init__(
            parent, text=label, command=command,
            bg=bg, fg=fg, activebackground=hover, activeforeground=fg,
            font=FONTS["h3"], relief="flat", cursor="hand2",
            padx=12, pady=6, bd=0, highlightthickness=0, **kw
        )
        if width:
            self.config(width=width)
        self._bg, self._hover = bg, hover
        self.bind("<Enter>", lambda _: self.config(bg=self._hover))
        self.bind("<Leave>", lambda _: self.config(bg=self._bg))

    def set_variant(self, variant: str) -> None:
        bg, hover, fg = self.VARIANTS.get(variant, self.VARIANTS["ghost"])
        self._bg, self._hover = bg, hover
        self.config(bg=bg, fg=fg, activebackground=hover, activeforeground=fg)


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
