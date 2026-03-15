"""
HAMNA Desktop — Vista de Secciones (Biblioteca)
Gestión completa de la biblioteca de secciones independiente de eventos.
"""
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
import database as db
from ui_theme import C, FONTS, HButton
from forms.seccion_form import SeccionForm
from forms.audio_player_window import AudioPlayerWindow


TIPO_BG = {"TTS": C["tts_bg"], "Audio": C["audio_bg"], "Sonido": C["sonido_bg"]}
TIPO_FG = {"TTS": C["tts_fg"], "Audio": C["audio_fg"], "Sonido": C["sonido_fg"]}


class ViewSecciones(tk.Frame):

    def __init__(self, parent, cfg: dict):
        super().__init__(parent, bg=C["bg"])
        self.cfg = cfg
        self._all_secs = []
        self._build()
        self.load_secciones()

    # ── Build ──────────────────────────────────────────────────────────────────
    def _build(self) -> None:
        # Toolbar
        tb = tk.Frame(self, bg=C["surface"], padx=12, pady=8)
        tb.pack(fill=tk.X)
        tk.Frame(self, bg=C["border"], height=1).pack(fill=tk.X)

        HButton(tb, "＋ Nueva Sección",
                command=self._nueva_seccion,
                variant="primary").pack(side=tk.LEFT)
        HButton(tb, "✏️ Editar",
                command=self._edit_seccion_sel,
                variant="edit").pack(side=tk.LEFT, padx=(6, 0))
        HButton(tb, "🗑 Eliminar",
                command=self._del_seccion_sel,
                variant="danger").pack(side=tk.LEFT, padx=(6, 0))
        HButton(tb, "↺ Actualizar",
                command=self.load_secciones,
                variant="info").pack(side=tk.LEFT, padx=(6, 0))

        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._filter())
        ttk.Entry(tb, textvariable=self._search_var, width=22).pack(side=tk.RIGHT)
        tk.Label(tb, text="🔍", font=FONTS["body"],
                 bg=C["surface"], fg=C["text2"]).pack(side=tk.RIGHT, padx=(0, 4))

        # Filtro de tipo
        self._tipo_var = tk.StringVar(value="Todos")
        tipo_cb = ttk.Combobox(tb, textvariable=self._tipo_var,
                               values=["Todos", "TTS", "Audio", "Sonido"],
                               state="readonly", width=10)
        tipo_cb.pack(side=tk.RIGHT, padx=(0, 8))
        tipo_cb.bind("<<ComboboxSelected>>", lambda _: self._filter())
        tk.Label(tb, text="Tipo:", font=FONTS["small"],
                 bg=C["surface"], fg=C["text2"]).pack(side=tk.RIGHT, padx=(0, 2))

        # Área con header + canvas alineados
        area = tk.Frame(self, bg=C["bg"])
        area.pack(fill=tk.BOTH, expand=True)

        # Scrollbar primero para que header y canvas compartan el mismo ancho
        sb = ttk.Scrollbar(area, orient="vertical")
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        # Header de columnas
        hdr = tk.Frame(area, bg=C["surface2"])
        hdr.pack(fill=tk.X)
        hdr.columnconfigure(2, weight=1)

        tk.Frame(hdr, width=3, bg=C["surface2"]).grid(
            row=0, column=0, sticky="ns")
        tk.Label(hdr, text="Nombre", font=FONTS["badge"],
                 bg=C["surface2"], fg=C["text3"],
                 anchor="w", padx=10, pady=5).grid(
            row=0, column=2, sticky="ew")
        tk.Label(hdr, text="Tipo", font=FONTS["badge"],
                 bg=C["surface2"], fg=C["text3"],
                 width=9, anchor="center").grid(row=0, column=3, padx=4)
        tk.Label(hdr, text="Dur.", font=FONTS["badge"],
                 bg=C["surface2"], fg=C["text3"],
                 width=6, anchor="e").grid(row=0, column=4, padx=(4, 8))
        tk.Label(hdr, text="Acciones", font=FONTS["badge"],
                 bg=C["surface2"], fg=C["text3"],
                 width=12, anchor="center").grid(row=0, column=5, padx=(0, 6))

        tk.Frame(area, bg=C["border"], height=1).pack(fill=tk.X)

        # Canvas scrollable
        self._canvas = tk.Canvas(area, bg=C["bg"], highlightthickness=0,
                                  yscrollcommand=sb.set)
        sb.config(command=self._canvas.yview)
        self._inner = tk.Frame(self._canvas, bg=C["bg"])
        self._inner.bind("<Configure>",
            lambda e: self._canvas.configure(
                scrollregion=self._canvas.bbox("all")))
        _win = self._canvas.create_window((0, 0), window=self._inner, anchor="nw")
        self._canvas.bind("<Configure>",
            lambda e: self._canvas.itemconfig(_win, width=e.width))
        self._canvas.pack(fill=tk.BOTH, expand=True)

        # Footer resumen
        tk.Frame(self, bg=C["border"], height=1).pack(fill=tk.X, side=tk.BOTTOM)
        foot = tk.Frame(self, bg=C["surface"], padx=12, pady=5)
        foot.pack(fill=tk.X, side=tk.BOTTOM)
        self._lbl_summary = tk.Label(foot, text="",
                                      font=FONTS["small"],
                                      bg=C["surface"], fg=C["text2"])
        self._lbl_summary.pack(side=tk.LEFT)

        self._selected_id: int | None = None

    # ── Datos ──────────────────────────────────────────────────────────────────
    def load_secciones(self) -> None:
        self._all_secs = [dict(s) for s in db.get_all_secciones()]
        self._filter()

    def _filter(self) -> None:
        q    = self._search_var.get().lower()
        tipo = self._tipo_var.get()
        rows = [s for s in self._all_secs
                if (not q or q in s["nombre"].lower()
                    or q in (s["tipo"] or "").lower())
                and (tipo == "Todos" or (s["tipo"] or "") == tipo)]
        self._render(rows)

    # ── Render ─────────────────────────────────────────────────────────────────
    def _render(self, secs: list) -> None:
        for w in self._inner.winfo_children():
            w.destroy()

        if not secs:
            tk.Label(self._inner,
                     text="No hay secciones — crea una con '＋ Nueva Sección'",
                     font=FONTS["small"], bg=C["bg"], fg=C["text3"],
                     pady=24).pack(expand=True)
            self._canvas.configure(scrollregion=self._canvas.bbox("all"))
            total_dur = sum(s["duracion"] for s in self._all_secs)
            self._lbl_summary.config(
                text=f"{len(self._all_secs)} sección(es) en biblioteca"
                     f" · {self._fmt(total_dur)} total")
            return

        for sec in secs:
            self._make_row(sec)

        self._canvas.configure(scrollregion=self._canvas.bbox("all"))
        total_dur = sum(s["duracion"] for s in self._all_secs)
        shown = len(secs)
        total = len(self._all_secs)
        suffix = f"(mostrando {shown} de {total})" if shown != total else ""
        self._lbl_summary.config(
            text=f"{total} sección(es) · {self._fmt(total_dur)} total {suffix}")

    def _make_row(self, sec: dict) -> None:
        is_sel = self._selected_id == sec["id"]
        bg = C["surface"] if is_sel else C["bg"]
        tipo = sec.get("tipo") or ""

        row = tk.Frame(self._inner, bg=bg, cursor="hand2")
        row.pack(fill=tk.X)
        row.columnconfigure(2, weight=1)

        ind = tk.Frame(row, bg=TIPO_BG.get(tipo, C["border"]), width=3)
        ind.grid(row=0, column=0, sticky="ns")

        lbl_nombre = tk.Label(row, text=sec["nombre"], font=FONTS["body"],
                               bg=bg, fg=C["text"], anchor="w", padx=10, pady=8)
        lbl_nombre.grid(row=0, column=2, sticky="ew")

        lbl_tipo = tk.Label(row,
                             text=tipo or "—", font=FONTS["badge"],
                             bg=TIPO_BG.get(tipo, C["surface2"]),
                             fg=TIPO_FG.get(tipo, C["text2"]),
                             padx=6, pady=2, width=9, anchor="center")
        lbl_tipo.grid(row=0, column=3, padx=4)

        lbl_dur = tk.Label(row, text=self._fmt(sec.get("duracion", 0)),
                            font=FONTS["mono_sm"], bg=bg, fg=C["text3"],
                            width=6, anchor="e")
        lbl_dur.grid(row=0, column=4, padx=(4, 8))

        btns = tk.Frame(row, bg=bg)
        btns.grid(row=0, column=5, padx=(0, 6))

        sec_id = sec["id"]
        for txt, fg_col, cmd in [
            ("▶",  C["text2"],   lambda sid=sec_id: self._play(sid)),
            ("✏️", C["text2"],   lambda sid=sec_id: self._edit(sid)),
            ("🗑", C["danger"],  lambda sid=sec_id, nm=sec["nombre"]: self._delete(sid, nm)),
        ]:
            tk.Button(btns, text=txt, font=FONTS["small"],
                      bg=C["surface2"], fg=fg_col,
                      relief="flat", bd=0, padx=6, pady=2,
                      cursor="hand2", command=cmd
                      ).pack(side=tk.LEFT, padx=1)

        def _enter(e, widgets=(row, lbl_nombre, lbl_dur), b=btns):
            for w in widgets:
                w.config(bg=C["surface"])
            b.config(bg=C["surface"])
            for child in b.winfo_children():
                child.config(bg=C["surface2"])

        def _leave(e, widgets=(row, lbl_nombre, lbl_dur), b=btns,
                   bg_=bg, sel=is_sel):
            nb = C["surface"] if sel else bg_
            for w in widgets:
                w.config(bg=nb)
            b.config(bg=nb)
            for child in b.winfo_children():
                child.config(bg=C["surface2"])

        handler = lambda e, sid=sec["id"]: self._select(sid)
        for w in (row, ind, lbl_nombre, lbl_dur):
            w.bind("<Enter>",    _enter)
            w.bind("<Leave>",    _leave)
            w.bind("<Button-1>", handler)
        lbl_tipo.bind("<Button-1>", handler)

        tk.Frame(self._inner, bg=C["surface"], height=1).pack(fill=tk.X)

    def _select(self, sec_id: int) -> None:
        self._selected_id = sec_id
        self._filter()

    # ── Acciones ───────────────────────────────────────────────────────────────
    def _nueva_seccion(self) -> None:
        SeccionForm(self, cfg=self.cfg, on_saved=self.load_secciones)

    def _edit_seccion_sel(self) -> None:
        if not self._selected_id:
            messagebox.showinfo("Selección",
                "Selecciona una sección primero.", parent=self)
            return
        self._edit(self._selected_id)

    def _edit(self, sec_id: int) -> None:
        SeccionForm(self, seccion_id=sec_id,
                    cfg=self.cfg, on_saved=self.load_secciones)

    def _del_seccion_sel(self) -> None:
        if not self._selected_id:
            messagebox.showinfo("Selección",
                "Selecciona una sección primero.", parent=self)
            return
        sec = next((s for s in self._all_secs
                    if s["id"] == self._selected_id), None)
        if sec:
            self._delete(sec["id"], sec["nombre"])

    def _delete(self, sec_id: int, nombre: str) -> None:
        if messagebox.askyesno("Confirmar eliminación",
                f"¿Eliminar «{nombre}» de la biblioteca?\n"
                "Se quitará de todos los eventos que la tengan.",
                parent=self):
            db.delete_seccion(sec_id)
            if self._selected_id == sec_id:
                self._selected_id = None
            self.load_secciones()

    def _play(self, sec_id: int) -> None:
        sec = db.get_seccion_by_id(sec_id)
        if sec and sec["ruta_archivo"]:
            if Path(sec["ruta_archivo"]).is_file():
                AudioPlayerWindow(self, sec["ruta_archivo"])
            else:
                messagebox.showwarning("Archivo no encontrado",
                    f"No se encontró:\n{sec['ruta_archivo']}", parent=self)
        else:
            messagebox.showinfo("Sin archivo",
                "Esta sección no tiene archivo de audio asignado.",
                parent=self)

    # ── Utilidad ───────────────────────────────────────────────────────────────
    @staticmethod
    def _fmt(s: float) -> str:
        s = int(max(0, s))
        return f"{s // 60}:{s % 60:02d}"
