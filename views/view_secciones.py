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


class ViewSecciones(tk.Frame):

    def __init__(self, parent, cfg: dict):
        super().__init__(parent, bg=C["bg"])
        self.cfg = cfg
        self._all_secs: list[dict] = []
        self._selected_id: int | None = None
        self._sort_col: str = "nombre"
        self._sort_asc: bool = True
        self._build()
        self.load_secciones()

    # ── Build ──────────────────────────────────────────────────────────────────
    def _build(self) -> None:
        # ── Toolbar ────────────────────────────────────────────────────────
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
        HButton(tb, "▶ Reproducir",
                command=self._play_sel,
                variant="success").pack(side=tk.LEFT, padx=(6, 0))
        HButton(tb, "↺ Actualizar",
                command=self.load_secciones,
                variant="info").pack(side=tk.LEFT, padx=(6, 0))

        # Búsqueda
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._filter())
        ttk.Entry(tb, textvariable=self._search_var, width=22).pack(side=tk.RIGHT)
        tk.Label(tb, text="🔍", font=FONTS["body"],
                 bg=C["surface"], fg=C["text2"]).pack(side=tk.RIGHT, padx=(0, 4))

        # Filtro por tipo
        self._tipo_var = tk.StringVar(value="Todos")
        tipo_cb = ttk.Combobox(tb, textvariable=self._tipo_var,
                               values=["Todos", "TTS", "Audio", "Sonido"],
                               state="readonly", width=10)
        tipo_cb.pack(side=tk.RIGHT, padx=(0, 8))
        tipo_cb.bind("<<ComboboxSelected>>", lambda _: self._filter())
        tk.Label(tb, text="Tipo:", font=FONTS["small"],
                 bg=C["surface"], fg=C["text2"]).pack(side=tk.RIGHT, padx=(0, 2))

        # ── Tabla ──────────────────────────────────────────────────────────
        area = tk.Frame(self, bg=C["bg"])
        area.pack(fill=tk.BOTH, expand=True)

        sb = ttk.Scrollbar(area, orient="vertical")
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        cols = ("nombre", "archivo", "tipo", "dur")
        self._tree = ttk.Treeview(
            area, columns=cols, show="headings",
            yscrollcommand=sb.set, selectmode="browse")
        sb.config(command=self._tree.yview)

        # Encabezados con ordenamiento al hacer clic
        self._tree.heading("nombre",  text="Nombre",  anchor="w",
                           command=lambda: self._sort_by("nombre"))
        self._tree.heading("archivo", text="Archivo", anchor="w",
                           command=lambda: self._sort_by("archivo"))
        self._tree.heading("tipo",    text="Tipo",    anchor="center",
                           command=lambda: self._sort_by("tipo"))
        self._tree.heading("dur",     text="Duración", anchor="e",
                           command=lambda: self._sort_by("dur"))

        # Anchos de columna
        self._tree.column("nombre",  anchor="w",      minwidth=120, width=200, stretch=True)
        self._tree.column("archivo", anchor="w",      minwidth=100, width=200, stretch=True)
        self._tree.column("tipo",    anchor="center", minwidth=70,  width=85,  stretch=False)
        self._tree.column("dur",     anchor="e",      minwidth=70,  width=80,  stretch=False)

        # Tags de color por tipo
        self._tree.tag_configure("TTS",    foreground=C["tts_fg"])
        self._tree.tag_configure("Audio",  foreground=C["audio_fg"])
        self._tree.tag_configure("Sonido", foreground=C["sonido_fg"])
        self._tree.tag_configure("none",   foreground=C["text3"])

        self._tree.pack(fill=tk.BOTH, expand=True)
        self._tree.bind("<<TreeviewSelect>>", self._on_select)
        self._tree.bind("<Double-Button-1>",  lambda _: self._edit_seccion_sel())
        self._tree.bind("<Button-3>",         self._on_right_click)

        # Menú contextual
        self._ctx_menu = tk.Menu(self, tearoff=0,
                                 bg=C["surface"], fg=C["text"],
                                 activebackground="#0d6efd",
                                 activeforeground="#ffffff",
                                 font=FONTS["body"], bd=0)
        self._ctx_menu.add_command(label="▶  Reproducir", command=self._play_sel)
        self._ctx_menu.add_command(label="✏️  Editar",     command=self._edit_seccion_sel)
        self._ctx_menu.add_separator()
        self._ctx_menu.add_command(label="🗑  Eliminar",   command=self._del_seccion_sel)

        # ── Footer ─────────────────────────────────────────────────────────
        tk.Frame(self, bg=C["border"], height=1).pack(fill=tk.X, side=tk.BOTTOM)
        foot = tk.Frame(self, bg=C["surface"], padx=12, pady=5)
        foot.pack(fill=tk.X, side=tk.BOTTOM)
        self._lbl_summary = tk.Label(
            foot, text="", font=FONTS["small"],
            bg=C["surface"], fg=C["text2"])
        self._lbl_summary.pack(side=tk.LEFT)

    # ── Datos ──────────────────────────────────────────────────────────────────
    def load_secciones(self) -> None:
        self._all_secs = [dict(s) for s in db.get_all_secciones()]
        self._filter()

    def _filter(self) -> None:
        q    = self._search_var.get().lower()
        tipo = self._tipo_var.get()
        rows = [s for s in self._all_secs
                if (not q or q in s["nombre"].lower()
                    or q in (s["tipo"] or "").lower()
                    or q in (Path(s.get("ruta_archivo") or "").name).lower())
                and (tipo == "Todos" or (s["tipo"] or "") == tipo)]
        rows = self._apply_sort(rows)
        self._render(rows)

    def _sort_by(self, col: str) -> None:
        if self._sort_col == col:
            self._sort_asc = not self._sort_asc
        else:
            self._sort_col = col
            self._sort_asc = True
        self._update_heading_arrows()
        self._filter()

    def _apply_sort(self, rows: list) -> list:
        col = self._sort_col

        def key(s):
            if col == "nombre":
                return s["nombre"].lower()
            if col == "archivo":
                return Path(s.get("ruta_archivo") or "").name.lower()
            if col == "tipo":
                return (s.get("tipo") or "").lower()
            if col == "dur":
                return s.get("duracion") or 0
            return ""

        return sorted(rows, key=key, reverse=not self._sort_asc)

    def _update_heading_arrows(self) -> None:
        labels = {"nombre": "Nombre", "archivo": "Archivo",
                  "tipo": "Tipo", "dur": "Duración"}
        for col, base in labels.items():
            if col == self._sort_col:
                arrow = " ▲" if self._sort_asc else " ▼"
                self._tree.heading(col, text=base + arrow)
            else:
                self._tree.heading(col, text=base)

    # ── Render ─────────────────────────────────────────────────────────────────
    def _render(self, secs: list) -> None:
        self._tree.delete(*self._tree.get_children())

        for sec in secs:
            tipo    = sec.get("tipo") or ""
            ruta    = sec.get("ruta_archivo") or ""
            archivo = Path(ruta).name if ruta else "—"
            dur     = self._fmt(sec.get("duracion", 0))
            tag     = tipo if tipo in ("TTS", "Audio", "Sonido") else "none"
            self._tree.insert(
                "", "end",
                iid=str(sec["id"]),
                values=(sec["nombre"], archivo, tipo or "—", dur),
                tags=(tag,))

        # Restaurar selección si sigue en la lista
        if self._selected_id and str(self._selected_id) in self._tree.get_children():
            self._tree.selection_set(str(self._selected_id))
            self._tree.see(str(self._selected_id))

        # Footer
        total_dur = sum(s["duracion"] for s in self._all_secs)
        shown = len(secs)
        total = len(self._all_secs)
        suffix = f"  (mostrando {shown} de {total})" if shown != total else ""
        self._lbl_summary.config(
            text=f"{total} sección(es) · {self._fmt(total_dur)} total{suffix}")

    def _on_select(self, _event=None) -> None:
        sel = self._tree.selection()
        self._selected_id = int(sel[0]) if sel else None

    def _on_right_click(self, event) -> None:
        iid = self._tree.identify_row(event.y)
        if not iid:
            return
        self._tree.selection_set(iid)
        self._selected_id = int(iid)
        self._ctx_menu.tk_popup(event.x_root, event.y_root)

    # ── Acciones ───────────────────────────────────────────────────────────────
    def _nueva_seccion(self) -> None:
        SeccionForm(self, cfg=self.cfg, on_saved=self.load_secciones)

    def _edit_seccion_sel(self) -> None:
        if not self._selected_id:
            messagebox.showinfo("Selección",
                "Selecciona una sección primero.", parent=self)
            return
        SeccionForm(self, seccion_id=self._selected_id,
                    cfg=self.cfg, on_saved=self.load_secciones)

    def _del_seccion_sel(self) -> None:
        if not self._selected_id:
            messagebox.showinfo("Selección",
                "Selecciona una sección primero.", parent=self)
            return
        sec = next((s for s in self._all_secs
                    if s["id"] == self._selected_id), None)
        if not sec:
            return
        if messagebox.askyesno(
                "Confirmar eliminación",
                f"¿Eliminar «{sec['nombre']}» de la biblioteca?\n"
                "Se quitará de todos los eventos que la tengan.",
                parent=self):
            db.delete_seccion(self._selected_id)
            self._selected_id = None
            self.load_secciones()

    def _play_sel(self) -> None:
        if not self._selected_id:
            messagebox.showinfo("Selección",
                "Selecciona una sección primero.", parent=self)
            return
        sec = db.get_seccion_by_id(self._selected_id)
        if sec and sec["ruta_archivo"]:
            if Path(sec["ruta_archivo"]).is_file():
                AudioPlayerWindow(self, sec["ruta_archivo"])
            else:
                messagebox.showwarning(
                    "Archivo no encontrado",
                    f"No se encontró:\n{sec['ruta_archivo']}", parent=self)
        else:
            messagebox.showinfo(
                "Sin archivo",
                "Esta sección no tiene archivo de audio asignado.",
                parent=self)

    # ── Utilidad ───────────────────────────────────────────────────────────────
    @staticmethod
    def _fmt(s: float) -> str:
        s = int(max(0, s))
        return f"{s // 60}:{s % 60:02d}"
