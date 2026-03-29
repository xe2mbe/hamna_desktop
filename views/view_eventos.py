"""
HAMNA Desktop — Vista de Eventos
Panel izquierdo: gestión de eventos.
Panel derecho: biblioteca de secciones (sin selección) o
               secciones del evento seleccionado.
"""
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
import database as db
from ui_theme import C, FONTS, HButton, HDialog
from forms.evento_form import EventoForm
from forms.seccion_form import SeccionForm
from forms.audio_player_window import AudioPlayerWindow
from modules.audio.audio_player import AudioPlayer


# ── Diálogo selector de secciones ─────────────────────────────────────────────
class _SeccionPickerDialog(HDialog):
    def __init__(self, parent, evento_id: int, evento_nombre: str,
                 on_added: callable):
        super().__init__(parent,
                         title=f"Agregar sección — {evento_nombre}",
                         width=540, height=420)
        self.evento_id = evento_id
        self.on_added  = on_added
        self._build()

    def _build(self) -> None:
        self.make_header(
            "Agregar secciones al evento",
            "Selecciona una o varias secciones de la biblioteca"
        )
        # Footer primero
        self.make_footer([
            ("Cancelar",              "muted",   self.destroy),
            ("Agregar seleccionadas", "primary", self._add),
        ])

        cols = ("nombre", "tipo", "duracion")
        self._tree = ttk.Treeview(self, columns=cols, show="headings",
                                   selectmode="extended")
        self._tree.heading("nombre",   text="Nombre",   anchor="w")
        self._tree.heading("tipo",     text="Tipo",     anchor="center")
        self._tree.heading("duracion", text="Duración", anchor="e")
        self._tree.column("nombre",   anchor="w",      minwidth=160, width=280, stretch=True)
        self._tree.column("tipo",     anchor="center", minwidth=60,  width=80,  stretch=False)
        self._tree.column("duracion", anchor="e",      minwidth=55,  width=80,  stretch=False)
        sb = ttk.Scrollbar(self, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y, pady=(0, 0))
        self._tree.pack(fill=tk.BOTH, expand=True)
        self._load()

    def _load(self) -> None:
        secs = db.get_secciones_disponibles_para_evento(self.evento_id)
        if not secs:
            self._tree.insert("", tk.END,
                values=("— No hay secciones disponibles —", "", ""))
            return
        for sec in secs:
            s = int(max(0, sec["duracion"]))
            self._tree.insert("", tk.END, iid=str(sec["id"]),
                values=(sec["nombre"], sec["tipo"] or "—",
                        f"{s//60}:{s%60:02d}"))

    def _add(self) -> None:
        selected = self._tree.selection()
        if not selected:
            messagebox.showinfo("Selección",
                "Selecciona al menos una sección.", parent=self)
            return
        for iid in selected:
            try:
                db.add_seccion_to_evento(self.evento_id, int(iid))
            except Exception:
                pass
        if callable(self.on_added):
            self.on_added()
        self.destroy()


# ── Vista principal ────────────────────────────────────────────────────────────
class ViewEventos(tk.Frame):

    def __init__(self, parent, cfg: dict, on_transmitir: callable):
        super().__init__(parent, bg=C["bg"])
        self.cfg           = cfg
        self.on_transmitir = on_transmitir
        self._selected_ev  = None
        self._all_eventos  = []
        self._sec_mode     = "biblioteca"
        self._player       = AudioPlayer()
        self._sec_id_map:  dict[str, int] = {}   # iid → sec_id
        self._sec_items:   list[str]      = []   # iids en orden (para mark_active)
        self._sec_sel_iid: str | None     = None
        self._build()
        self.load_eventos()

    # ── Build ──────────────────────────────────────────────────────────────────
    def _build(self) -> None:
        # Toolbar
        tb = tk.Frame(self, bg=C["surface"], padx=12, pady=8)
        tb.pack(fill=tk.X)
        tk.Frame(self, bg=C["border"], height=1).pack(fill=tk.X)

        HButton(tb, "＋ Nuevo Evento",
                command=self._nuevo_evento,
                variant="primary").pack(side=tk.LEFT)
        HButton(tb, "✏️ Editar Evento",
                command=self._edit_evento,
                variant="edit").pack(side=tk.LEFT, padx=(6, 0))
        HButton(tb, "🗑 Eliminar Evento",
                command=self._del_evento,
                variant="danger").pack(side=tk.LEFT, padx=(6, 0))
        HButton(tb, "↺ Actualizar",
                command=self.load_eventos,
                variant="info").pack(side=tk.LEFT, padx=(6, 0))

        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._filter())
        ttk.Entry(tb, textvariable=self._search_var, width=20).pack(side=tk.RIGHT)
        tk.Label(tb, text="🔍", font=FONTS["body"],
                 bg=C["surface"], fg=C["text2"]).pack(side=tk.RIGHT, padx=(0, 4))

        # PanedWindow
        paned = tk.PanedWindow(self, orient=tk.HORIZONTAL,
                               bg=C["border"], sashwidth=4,
                               sashrelief="flat", bd=0)
        paned.pack(fill=tk.BOTH, expand=True)

        # ── Panel izquierdo — eventos ─────────────────────────────────────────
        lp = tk.Frame(paned, bg=C["bg"])
        paned.add(lp, minsize=180, width=310, stretch="never")

        ev_area = tk.Frame(lp, bg=C["surface"])
        ev_area.pack(fill=tk.BOTH, expand=True)

        ev_sb = ttk.Scrollbar(ev_area, orient="vertical")

        def _ev_yscroll(first, last):
            if float(first) <= 0.0 and float(last) >= 1.0:
                ev_sb.pack_forget()
            else:
                ev_sb.pack(side=tk.RIGHT, fill=tk.Y, before=self._ev_tree)
            ev_sb.set(first, last)

        ev_cols = ("nombre", "tipo", "dur")
        self._ev_tree = ttk.Treeview(
            ev_area, columns=ev_cols, show="headings",
            yscrollcommand=_ev_yscroll, selectmode="browse")
        ev_sb.config(command=self._ev_tree.yview)

        self._ev_tree.heading("nombre", text="Nombre", anchor="w")
        self._ev_tree.heading("tipo",   text="Tipo",   anchor="center")
        self._ev_tree.heading("dur",    text="Duración", anchor="e")

        self._ev_tree.column("nombre", anchor="w",      minwidth=100, width=170, stretch=True)
        self._ev_tree.column("tipo",   anchor="center", minwidth=70,  width=90,  stretch=False)
        self._ev_tree.column("dur",    anchor="e",      minwidth=70,  width=80,  stretch=False)

        self._ev_tree.tag_configure("on_air",  foreground=C["danger"])
        self._ev_tree.tag_configure("normal",  foreground=C["text"])

        self._ev_tree.pack(fill=tk.BOTH, expand=True)
        self._ev_tree.bind("<<TreeviewSelect>>", self._on_ev_select)
        self._ev_tree.bind("<Double-Button-1>",  lambda _: self._edit_evento())
        self._ev_tree.bind("<Button-3>",         self._on_ev_right_click)

        # Menú contextual — eventos
        self._ev_ctx = tk.Menu(self, tearoff=0,
                               bg=C["surface"], fg=C["text"],
                               activebackground="#0d6efd", activeforeground="#ffffff",
                               font=FONTS["body"], bd=0)
        self._ev_ctx.add_command(label="📡  Transmitir ahora", command=self._transmitir)
        self._ev_ctx.add_command(label="✏️  Editar",            command=self._edit_evento)
        self._ev_ctx.add_separator()
        self._ev_ctx.add_command(label="🗑  Eliminar",          command=self._del_evento)

        # ── Panel derecho — secciones ─────────────────────────────────────────
        rp = tk.Frame(paned, bg=C["bg"])
        paned.add(rp, minsize=200, stretch="always")

        sec_hdr = tk.Frame(rp, bg=C["surface2"], padx=10, pady=6)
        sec_hdr.pack(fill=tk.X)

        self._lbl_sec_panel = tk.Label(
            sec_hdr, text="BIBLIOTECA DE SECCIONES",
            font=FONTS["badge"], bg=C["surface2"], fg=C["text3"])
        self._lbl_sec_panel.pack(side=tk.LEFT)

        self._btn_agregar = HButton(sec_hdr, "＋ Agregar al evento",
                                     command=self._agregar_seccion,
                                     variant="primary")
        HButton(sec_hdr, "＋ Nueva sección",
                command=self._nueva_seccion,
                variant="primary").pack(side=tk.RIGHT, padx=(4, 0))

        tk.Frame(rp, bg=C["border"], height=1).pack(fill=tk.X)

        # Footer resumen + transmitir (empacado ANTES que el canvas)
        tk.Frame(rp, bg=C["border"], height=1).pack(fill=tk.X, side=tk.BOTTOM)
        self._footer_frame = tk.Frame(rp, bg=C["surface"], padx=10, pady=6)
        self._footer_frame.pack(fill=tk.X, side=tk.BOTTOM)

        self._lbl_sec_summary = tk.Label(
            self._footer_frame, text="",
            font=FONTS["small"], bg=C["surface"], fg=C["text2"])
        self._lbl_sec_summary.pack(side=tk.LEFT)

        self._btn_transmitir = HButton(
            self._footer_frame, "📡 Transmitir ahora",
            command=self._transmitir, variant="success")

        # Secciones Treeview
        sec_area = tk.Frame(rp, bg=C["surface"])
        sec_area.pack(fill=tk.BOTH, expand=True)

        sec_sb = ttk.Scrollbar(sec_area, orient="vertical")

        def _sec_yscroll(first, last):
            if float(first) <= 0.0 and float(last) >= 1.0:
                sec_sb.pack_forget()
            else:
                sec_sb.pack(side=tk.RIGHT, fill=tk.Y, before=self._sec_tree)
            sec_sb.set(first, last)

        sec_cols = ("orden", "nombre", "archivo", "tipo", "dur", "regen", "cont", "dbfs")
        self._sec_tree = ttk.Treeview(
            sec_area, columns=sec_cols, show="headings",
            yscrollcommand=_sec_yscroll, selectmode="browse")
        sec_sb.config(command=self._sec_tree.yview)

        self._sec_tree.heading("orden",   text="#",         anchor="center")
        self._sec_tree.heading("nombre",  text="Nombre",    anchor="w")
        self._sec_tree.heading("archivo", text="Archivo",   anchor="w")
        self._sec_tree.heading("tipo",    text="Tipo",      anchor="center")
        self._sec_tree.heading("dur",     text="Duración",  anchor="e")
        self._sec_tree.heading("regen",   text="🔄 Regen.", anchor="center")
        self._sec_tree.heading("cont",    text="Cont.",     anchor="center")
        self._sec_tree.heading("dbfs",    text="Nivel",     anchor="e")

        self._sec_tree.column("orden",   anchor="center", minwidth=25,  width=30,  stretch=False)
        self._sec_tree.column("nombre",  anchor="w",      minwidth=80,  width=130, stretch=True)
        self._sec_tree.column("archivo", anchor="w",      minwidth=80,  width=130, stretch=True)
        self._sec_tree.column("tipo",    anchor="center", minwidth=60,  width=75,  stretch=False)
        self._sec_tree.column("dur",     anchor="e",      minwidth=70,  width=80,  stretch=False)
        self._sec_tree.column("regen",   anchor="center", minwidth=55,  width=60,  stretch=False)
        self._sec_tree.column("cont",    anchor="center", minwidth=45,  width=50,  stretch=False)
        self._sec_tree.column("dbfs",    anchor="e",      minwidth=65,  width=75,  stretch=False)

        self._sec_tree.tag_configure("TTS",    foreground=C["tts_fg"])
        self._sec_tree.tag_configure("Audio",  foreground=C["audio_fg"])
        self._sec_tree.tag_configure("Sonido", foreground=C["sonido_fg"])
        self._sec_tree.tag_configure("none",   foreground=C["text3"])
        self._sec_tree.tag_configure("active", background=C["audio_bg"])

        self._sec_tree.pack(fill=tk.BOTH, expand=True)
        self._sec_tree.bind("<<TreeviewSelect>>", self._on_sec_select)
        self._sec_tree.bind("<Double-Button-1>",  lambda _: self._edit_seccion_sel())
        self._sec_tree.bind("<Button-3>",         self._on_sec_right_click)

        # Menú contextual — secciones (se reconstruye en cada clic derecho)
        self._sec_ctx = tk.Menu(self, tearoff=0,
                                bg=C["surface"], fg=C["text"],
                                activebackground="#0d6efd", activeforeground="#ffffff",
                                font=FONTS["body"], bd=0)

    # ── Selección — eventos ────────────────────────────────────────────────────
    def _on_ev_select(self, _event=None) -> None:
        sel = self._ev_tree.selection()
        if not sel:
            return
        ev_id = int(sel[0])
        if ev_id == self._selected_ev:
            return
        self._selected_ev = ev_id
        ev = next((e for e in self._all_eventos if e["id"] == ev_id), None)
        if ev:
            self._set_mode_evento(ev_id, ev["nombre"])

    def _on_ev_right_click(self, event) -> None:
        iid = self._ev_tree.identify_row(event.y)
        if not iid:
            return
        self._ev_tree.selection_set(iid)
        self._selected_ev = int(iid)
        ev = next((e for e in self._all_eventos if e["id"] == self._selected_ev), None)
        if ev:
            self._set_mode_evento(self._selected_ev, ev["nombre"])
        self._ev_ctx.tk_popup(event.x_root, event.y_root)

    # ── Selección — secciones ──────────────────────────────────────────────────
    def _on_sec_select(self, _event=None) -> None:
        sel = self._sec_tree.selection()
        self._sec_sel_iid = sel[0] if sel else None

    def _on_sec_right_click(self, event) -> None:
        iid = self._sec_tree.identify_row(event.y)
        if not iid:
            return
        self._sec_tree.selection_set(iid)
        self._sec_sel_iid = iid

        # Reconstruir menú según modo
        self._sec_ctx.delete(0, tk.END)
        self._sec_ctx.add_command(label="▶  Reproducir", command=self._play_seccion_sel)
        self._sec_ctx.add_command(label="✏️  Editar",     command=self._edit_seccion_sel)
        if self._sec_mode == "evento":
            self._sec_ctx.add_separator()
            self._sec_ctx.add_command(label="↑  Mover arriba",
                                      command=lambda: self._mover_sel(-1))
            self._sec_ctx.add_command(label="↓  Mover abajo",
                                      command=lambda: self._mover_sel(1))
            self._sec_ctx.add_separator()
            # Etiqueta dinámica según estado actual
            cont_val = self._sec_tree.set(iid, "cont")
            toggle_lbl = "🔢  Quitar del conteo" if cont_val == "✓" \
                         else "🔢  Incluir en conteo"
            self._sec_ctx.add_command(label=toggle_lbl,
                                      command=self._toggle_contabilizable_sel)
            self._sec_ctx.add_separator()
            self._sec_ctx.add_command(label="✖  Quitar del evento",
                                      command=self._quitar_seccion_sel)
        else:
            self._sec_ctx.add_separator()
            self._sec_ctx.add_command(label="🗑  Eliminar de biblioteca",
                                      command=self._del_seccion_sel)
        self._sec_ctx.tk_popup(event.x_root, event.y_root)

    # ── Modo panel derecho ─────────────────────────────────────────────────────
    def _set_mode_biblioteca(self) -> None:
        self._sec_mode = "biblioteca"
        self._lbl_sec_panel.config(text="BIBLIOTECA DE SECCIONES")
        self._btn_agregar.pack_forget()
        self._btn_transmitir.pack_forget()
        self._sec_tree.column("orden", width=0, minwidth=0, stretch=False)
        self._sec_tree.column("cont",  width=0, minwidth=0, stretch=False)
        self._load_biblioteca()

    def _set_mode_evento(self, ev_id: int, ev_nombre: str) -> None:
        self._sec_mode = "evento"
        self._lbl_sec_panel.config(text=f"SECCIONES — {ev_nombre.upper()}")
        self._btn_agregar.pack(side=tk.RIGHT, padx=(4, 0))
        self._btn_transmitir.pack(side=tk.RIGHT, padx=(0, 6))
        self._sec_tree.column("orden", width=30, minwidth=25, stretch=False)
        self._sec_tree.column("cont",  width=50, minwidth=45, stretch=False)
        self._load_secciones(ev_id)

    # ── Carga de datos ─────────────────────────────────────────────────────────
    def load_eventos(self) -> None:
        self._all_eventos = db.get_all_eventos()
        self._render_eventos(self._all_eventos)
        if self._sec_mode == "biblioteca":
            self._load_biblioteca()
        elif self._sec_mode == "evento" and self._selected_ev:
            self._load_secciones(self._selected_ev)

    def _filter(self) -> None:
        q = self._search_var.get().lower()
        filtered = [e for e in self._all_eventos
                    if not q
                    or q in e["nombre"].lower()
                    or q in (e["tipo"] or "").lower()]
        self._render_eventos(filtered)

    # ── Render: lista de eventos ───────────────────────────────────────────────
    def _render_eventos(self, rows: list) -> None:
        sel = self._ev_tree.selection()
        sel_iid = sel[0] if sel else None

        self._ev_tree.delete(*self._ev_tree.get_children())
        on_air_id = getattr(self, "_on_air_id", None)

        for ev in rows:
            secs = db.get_secciones_by_evento(ev["id"])
            dur  = sum(s["duracion"] for s in secs)
            tag  = "on_air" if on_air_id == ev["id"] else "normal"
            num  = ev["numero"]
            nombre_display = f"{ev['nombre']} #{num}" if num else ev["nombre"]
            self._ev_tree.insert("", "end", iid=str(ev["id"]),
                values=(nombre_display, ev["tipo"] or "—", self._fmt_dur(dur)),
                tags=(tag,))

        if sel_iid and sel_iid in self._ev_tree.get_children():
            self._ev_tree.selection_set(sel_iid)
            self._ev_tree.see(sel_iid)

    # ── Render: lista de secciones ─────────────────────────────────────────────
    def _load_biblioteca(self) -> None:
        secs = db.get_all_secciones()
        self._render_sec_rows(secs, mode="biblioteca")
        total = sum(s["duracion"] for s in secs)
        self._lbl_sec_summary.config(
            text=f"{len(secs)} sección(es) en biblioteca · {self._fmt_dur(total)}")

    def _load_secciones(self, ev_id: int) -> None:
        secs = db.get_secciones_by_evento(ev_id)
        self._render_sec_rows(secs, mode="evento")
        total = sum(s["duracion"] for s in secs)
        self._lbl_sec_summary.config(
            text=f"{len(secs)} sección(es) · {self._fmt_dur(total)} total")

    def _render_sec_rows(self, secs: list, mode: str) -> None:
        from modules.audio.audio_player import measure_dbfs
        self._sec_tree.delete(*self._sec_tree.get_children())
        self._sec_id_map = {}
        self._sec_items  = []
        self._dbfs_render_id = getattr(self, "_dbfs_render_id", 0) + 1
        render_id = self._dbfs_render_id

        # Filas a medir en background: (iid, ruta)
        pending = []

        for i, sec in enumerate(secs):
            sec   = dict(sec)
            tipo  = sec.get("tipo") or ""
            dur   = self._fmt_dur(sec["duracion"])
            tag   = tipo if tipo in ("TTS", "Audio", "Sonido") else "none"
            orden = str(i + 1) if mode == "evento" else ""
            iid   = f"e{i}" if mode == "evento" else str(sec["id"])
            self._sec_id_map[iid] = sec["id"]
            self._sec_items.append(iid)
            regen = "🔄" if sec.get("regenerar_antes") else ""
            cont  = "✓"  if sec.get("contabilizable", 1) else "—"
            ruta  = sec.get("ruta_archivo") or ""
            if ruta and Path(ruta).is_file() and tipo in ("Audio", "Sonido"):
                archivo = Path(ruta).name
                dbfs    = "…"
                pending.append((iid, ruta))
            else:
                archivo = ""
                dbfs    = "—"
            self._sec_tree.insert("", "end", iid=iid,
                values=(orden, sec["nombre"], archivo, tipo or "—", dur, regen, cont, dbfs),
                tags=(tag,))

        if not pending:
            return

        def _measure_all():
            for iid, ruta in pending:
                if self._dbfs_render_id != render_id:
                    return  # render obsoleto, abandonar
                v    = measure_dbfs(ruta)
                text = f"{v} dB" if v is not None else "—"
                self.after(0, _update_cell, iid, text)

        def _update_cell(iid, text):
            if self._dbfs_render_id != render_id:
                return
            try:
                self._sec_tree.set(iid, "dbfs", text)
            except Exception:
                pass

        threading.Thread(target=_measure_all, daemon=True).start()

    def _sec_id_from_sel(self) -> int | None:
        """Devuelve el sec_id del ítem seleccionado, o None."""
        iid = self._sec_sel_iid
        if not iid:
            iid = (self._sec_tree.selection() or [None])[0]
        return self._sec_id_map.get(iid)

    # ── Acciones de eventos ────────────────────────────────────────────────────
    def _nuevo_evento(self) -> None:
        EventoForm(self, cfg=self.cfg, on_saved=self.load_eventos)

    def _edit_evento(self) -> None:
        if not self._selected_ev:
            messagebox.showinfo("Selección", "Selecciona un evento primero.")
            return
        EventoForm(self, evento_id=self._selected_ev,
                   cfg=self.cfg, on_saved=self.load_eventos)

    def _del_evento(self) -> None:
        if not self._selected_ev:
            messagebox.showinfo("Selección", "Selecciona un evento primero.")
            return
        ev = next((e for e in self._all_eventos
                   if e["id"] == self._selected_ev), None)
        if not ev:
            return
        if messagebox.askyesno("Confirmar eliminación",
                f"¿Eliminar el evento «{ev['nombre']}»?\n"
                "Las secciones asignadas NO se borran de la biblioteca."):
            db.delete_evento(self._selected_ev)
            self._selected_ev = None
            self._set_mode_biblioteca()
            self.load_eventos()

    # ── Acciones de secciones ─────────────────────────────────────────────────
    def _nueva_seccion(self) -> None:
        SeccionForm(self, cfg=self.cfg, on_saved=self._on_sec_saved)

    def _on_sec_saved(self) -> None:
        if self._sec_mode == "biblioteca":
            self._load_biblioteca()
        else:
            self._load_secciones(self._selected_ev)
        self._render_eventos(self._all_eventos)

    def _agregar_seccion(self) -> None:
        if not self._selected_ev:
            return
        ev = next((e for e in self._all_eventos
                   if e["id"] == self._selected_ev), None)
        _SeccionPickerDialog(
            self,
            evento_id=self._selected_ev,
            evento_nombre=ev["nombre"] if ev else "",
            on_added=lambda: self._load_secciones(self._selected_ev)
        )

    def _edit_seccion_sel(self) -> None:
        sec_id = self._sec_id_from_sel()
        if not sec_id:
            messagebox.showinfo("Selección", "Selecciona una sección primero.")
            return
        SeccionForm(self, seccion_id=sec_id,
                    cfg=self.cfg, on_saved=self._on_sec_saved)

    def _play_seccion_sel(self) -> None:
        sec_id = self._sec_id_from_sel()
        if not sec_id:
            messagebox.showinfo("Selección", "Selecciona una sección primero.")
            return
        self._play_seccion(sec_id)

    def _play_seccion(self, sec_id: int) -> None:
        sec = db.get_seccion_by_id(sec_id)
        if sec and sec["ruta_archivo"]:
            if Path(sec["ruta_archivo"]).is_file():
                AudioPlayerWindow(self, sec["ruta_archivo"])
            else:
                messagebox.showwarning("Archivo no encontrado",
                    f"No se encontró:\n{sec['ruta_archivo']}")
        else:
            messagebox.showinfo("Sin archivo",
                "Esta sección no tiene archivo de audio.")

    def _del_seccion_sel(self) -> None:
        sec_id = self._sec_id_from_sel()
        if not sec_id:
            return
        sec = db.get_seccion_by_id(sec_id)
        nombre = sec["nombre"] if sec else str(sec_id)
        if messagebox.askyesno("Confirmar",
                f"¿Eliminar «{nombre}» de la biblioteca?\n"
                "Se quitará de todos los eventos que la tengan."):
            db.delete_seccion(sec_id)
            self._sec_sel_iid = None
            self._load_biblioteca()
            self._render_eventos(self._all_eventos)

    def _quitar_seccion_sel(self) -> None:
        sec_id = self._sec_id_from_sel()
        if not sec_id or not self._selected_ev:
            return
        sec = db.get_seccion_by_id(sec_id)
        nombre = sec["nombre"] if sec else str(sec_id)
        if messagebox.askyesno("Confirmar",
                f"¿Quitar «{nombre}» del evento?\n"
                "La sección seguirá disponible en la biblioteca."):
            db.remove_seccion_from_evento(self._selected_ev, sec_id)
            self._sec_sel_iid = None
            self._load_secciones(self._selected_ev)
            self._render_eventos(self._all_eventos)

    def _toggle_contabilizable_sel(self) -> None:
        sec_id = self._sec_id_from_sel()
        if not sec_id or not self._selected_ev:
            return
        iid = self._sec_sel_iid or (self._sec_tree.selection() or [None])[0]
        cur = self._sec_tree.set(iid, "cont") if iid else "✓"
        new_val = 0 if cur == "✓" else 1
        db.set_contabilizable_en_evento(self._selected_ev, sec_id, new_val)
        self._load_secciones(self._selected_ev)

    def _mover_sel(self, direction: int) -> None:
        sec_id = self._sec_id_from_sel()
        if not sec_id or not self._selected_ev:
            return
        db.move_seccion_in_evento(self._selected_ev, sec_id, direction)
        self._load_secciones(self._selected_ev)

    def _transmitir(self) -> None:
        if self._selected_ev and callable(self.on_transmitir):
            self.on_transmitir(self._selected_ev)

    # ── Estado AL AIRE (llamado desde exterior) ────────────────────────────────
    def update_on_air(self, evento_id: int | None) -> None:
        self._on_air_id = evento_id
        self._render_eventos(self._all_eventos)
        if evento_id and evento_id == self._selected_ev:
            self._load_secciones(evento_id)

    def mark_active_section(self, sec_idx: int) -> None:
        items = self._sec_tree.get_children()
        for i, iid in enumerate(items):
            tags = list(self._sec_tree.item(iid, "tags"))
            # Quitar active anterior
            if "active" in tags:
                tags.remove("active")
            if i == sec_idx:
                tags.append("active")
            self._sec_tree.item(iid, tags=tags)
        if 0 <= sec_idx < len(items):
            self._sec_tree.see(items[sec_idx])

    # ── Utilidades ─────────────────────────────────────────────────────────────
    @staticmethod
    def _fmt_dur(s: float) -> str:
        s = int(max(0, s))
        return f"{s // 60}:{s % 60:02d}"
