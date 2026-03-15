"""
HAMNA Desktop — Vista de Eventos
Panel izquierdo: gestión de eventos.
Panel derecho: biblioteca de secciones (sin selección) o
               secciones del evento seleccionado.
"""
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
        cols = ("nombre", "tipo", "duracion")
        self._tree = ttk.Treeview(self, columns=cols, show="headings",
                                   selectmode="extended")
        self._tree.heading("nombre",   text="Nombre")
        self._tree.heading("tipo",     text="Tipo")
        self._tree.heading("duracion", text="Duración")
        self._tree.column("nombre",   width=280)
        self._tree.column("tipo",     width=80,  stretch=False)
        self._tree.column("duracion", width=80,  stretch=False)
        sb = ttk.Scrollbar(self, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=sb.set)
        self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True,
                        padx=(16, 0), pady=16)
        sb.pack(side=tk.RIGHT, fill=tk.Y, pady=16, padx=(0, 16))
        self._load()
        self.make_footer([
            ("Cancelar",              "muted",   self.destroy),
            ("Agregar seleccionadas", "primary", self._add),
        ])

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
        self._sec_rows     = []   # lista de frames para mark_active_section
        self._player       = AudioPlayer()
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
                               bg=C["border"], sashwidth=5,
                               sashrelief="flat", bd=0)
        paned.pack(fill=tk.BOTH, expand=True)

        # ── Panel izquierdo — eventos ─────────────────────────────────────────
        lp = tk.Frame(paned, bg=C["bg"])
        paned.add(lp, minsize=180, width=310, stretch="never")

        # Contenedor que unifica header y canvas para que compartan ancho
        ev_area = tk.Frame(lp, bg=C["bg"])
        ev_area.pack(fill=tk.BOTH, expand=True)

        # Scrollbar primero (lado derecho) — así el header y el canvas
        # tienen exactamente el mismo ancho disponible
        ev_sb = ttk.Scrollbar(ev_area, orient="vertical")
        ev_sb.pack(side=tk.RIGHT, fill=tk.Y)

        # Header de columnas (mismo ancho que el canvas)
        hdr_ev = tk.Frame(ev_area, bg=C["surface2"])
        hdr_ev.pack(fill=tk.X)
        hdr_ev.columnconfigure(1, weight=1)
        tk.Frame(hdr_ev, width=3, bg=C["surface2"]).grid(
            row=0, column=0, sticky="ns")                         # indicador
        tk.Label(hdr_ev, text="Nombre", font=FONTS["badge"],
                 bg=C["surface2"], fg=C["text3"],
                 anchor="w", padx=10, pady=4).grid(
            row=0, column=1, sticky="ew")                         # nombre
        tk.Label(hdr_ev, text="Tipo", font=FONTS["badge"],
                 bg=C["surface2"], fg=C["text3"],
                 width=14, anchor="w").grid(row=0, column=2)      # tipo
        tk.Label(hdr_ev, text="Dur.", font=FONTS["badge"],
                 bg=C["surface2"], fg=C["text3"],
                 width=5, anchor="e").grid(row=0, column=3,
                                           padx=(0, 40))          # dur + espacio btn

        tk.Frame(ev_area, bg=C["border"], height=1).pack(fill=tk.X)

        self._ev_canvas = tk.Canvas(ev_area, bg=C["bg"], highlightthickness=0,
                                     yscrollcommand=ev_sb.set)
        ev_sb.config(command=self._ev_canvas.yview)
        self._ev_inner = tk.Frame(self._ev_canvas, bg=C["bg"])
        self._ev_inner.bind("<Configure>",
            lambda e: self._ev_canvas.configure(
                scrollregion=self._ev_canvas.bbox("all")))
        _ev_win = self._ev_canvas.create_window((0, 0), window=self._ev_inner,
                                                 anchor="nw")
        self._ev_canvas.bind("<Configure>",
            lambda e: self._ev_canvas.itemconfig(_ev_win, width=e.width))
        self._ev_canvas.pack(fill=tk.BOTH, expand=True)

        # ── Panel derecho — secciones ─────────────────────────────────────────
        rp = tk.Frame(paned, bg=C["bg"])
        paned.add(rp, minsize=200, stretch="always")

        # Cabecera
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
                variant="ghost").pack(side=tk.RIGHT, padx=(4, 0))

        tk.Frame(rp, bg=C["border"], height=1).pack(fill=tk.X)

        # Contenedor que unifica header de columnas + canvas + scrollbar
        sec_area = tk.Frame(rp, bg=C["bg"])
        sec_area.pack(fill=tk.BOTH, expand=True)

        # Scrollbar primero (derecha) — header y canvas quedan con mismo ancho
        sec_sb = ttk.Scrollbar(sec_area, orient="vertical")
        sec_sb.pack(side=tk.RIGHT, fill=tk.Y)

        # Header de columnas (mismo ancho que el canvas)
        self._sec_col_hdr = tk.Frame(sec_area, bg=C["surface2"])
        self._sec_col_hdr.pack(fill=tk.X)
        tk.Frame(sec_area, bg=C["border"], height=1).pack(fill=tk.X)

        # Poblar el header (se reconstruye al cambiar modo)
        self._build_sec_col_hdr("biblioteca")

        # Canvas scrollable
        self._sec_canvas = tk.Canvas(sec_area, bg=C["bg"], highlightthickness=0,
                                      yscrollcommand=sec_sb.set)
        sec_sb.config(command=self._sec_canvas.yview)
        self._sec_inner = tk.Frame(self._sec_canvas, bg=C["bg"])
        self._sec_inner.bind("<Configure>",
            lambda e: self._sec_canvas.configure(
                scrollregion=self._sec_canvas.bbox("all")))
        _sec_win = self._sec_canvas.create_window((0, 0), window=self._sec_inner,
                                                   anchor="nw")
        self._sec_canvas.bind("<Configure>",
            lambda e: self._sec_canvas.itemconfig(_sec_win, width=e.width))
        self._sec_canvas.pack(fill=tk.BOTH, expand=True)

        # Footer resumen + transmitir (solo evento)
        self._footer_frame = tk.Frame(rp, bg=C["surface"], padx=10, pady=6)
        self._footer_frame.pack(fill=tk.X, side=tk.BOTTOM)
        tk.Frame(rp, bg=C["border"], height=1).pack(fill=tk.X, side=tk.BOTTOM)

        self._lbl_sec_summary = tk.Label(
            self._footer_frame, text="",
            font=FONTS["small"], bg=C["surface"], fg=C["text2"])
        self._lbl_sec_summary.pack(side=tk.LEFT)

        self._btn_transmitir = HButton(
            self._footer_frame, "📡 Transmitir ahora",
            command=self._transmitir, variant="success")
        # Se muestra solo en modo evento

    # ── Header columnas secciones ──────────────────────────────────────────────
    def _build_sec_col_hdr(self, mode: str) -> None:
        for w in self._sec_col_hdr.winfo_children():
            w.destroy()
        self._sec_col_hdr.columnconfigure(2, weight=1)

        col = 0
        # Indicador tipo (3px)
        tk.Frame(self._sec_col_hdr, width=3,
                 bg=C["surface2"]).grid(row=0, column=col, sticky="ns")
        col += 1

        # Número (solo modo evento)
        if mode == "evento":
            tk.Label(self._sec_col_hdr, text="#", font=FONTS["badge"],
                     bg=C["surface2"], fg=C["text3"],
                     width=2, anchor="e").grid(row=0, column=col,
                                               padx=(8, 2), pady=4)
            col += 1
            self._sec_col_hdr.columnconfigure(col, weight=1)
        else:
            self._sec_col_hdr.columnconfigure(col, weight=1)

        # Nombre
        tk.Label(self._sec_col_hdr, text="Nombre", font=FONTS["badge"],
                 bg=C["surface2"], fg=C["text3"],
                 anchor="w", padx=8, pady=4).grid(
            row=0, column=col, sticky="ew")
        col += 1

        # Tipo
        tk.Label(self._sec_col_hdr, text="Tipo", font=FONTS["badge"],
                 bg=C["surface2"], fg=C["text3"],
                 width=8, anchor="center").grid(row=0, column=col, padx=4)
        col += 1

        # Duración
        tk.Label(self._sec_col_hdr, text="Dur.", font=FONTS["badge"],
                 bg=C["surface2"], fg=C["text3"],
                 width=5, anchor="e").grid(row=0, column=col, padx=(4, 8))
        col += 1

        # Acciones (espacio reservado para los botones)
        n_btns = 5 if mode == "evento" else 3
        tk.Label(self._sec_col_hdr, text="Acciones", font=FONTS["badge"],
                 bg=C["surface2"], fg=C["text3"],
                 width=n_btns * 3, anchor="center").grid(
            row=0, column=col, padx=(0, 6))

    # ── Modo panel derecho ─────────────────────────────────────────────────────
    def _set_mode_biblioteca(self) -> None:
        self._sec_mode = "biblioteca"
        self._lbl_sec_panel.config(text="BIBLIOTECA DE SECCIONES")
        self._btn_agregar.pack_forget()
        self._btn_transmitir.pack_forget()
        self._build_sec_col_hdr("biblioteca")
        self._load_biblioteca()

    def _set_mode_evento(self, ev_id: int, ev_nombre: str) -> None:
        self._sec_mode = "evento"
        self._lbl_sec_panel.config(
            text=f"SECCIONES — {ev_nombre.upper()}")
        self._btn_agregar.pack(side=tk.RIGHT, padx=(4, 0))
        self._btn_transmitir.pack(side=tk.RIGHT, padx=(0, 6))
        self._build_sec_col_hdr("evento")
        self._load_secciones(ev_id)

    # ── Carga de datos ─────────────────────────────────────────────────────────
    def load_eventos(self) -> None:
        self._all_eventos = db.get_all_eventos()
        self._render_eventos(self._all_eventos)
        if self._sec_mode == "biblioteca":
            self._load_biblioteca()

    def _filter(self) -> None:
        q = self._search_var.get().lower()
        filtered = [e for e in self._all_eventos
                    if not q
                    or q in e["nombre"].lower()
                    or q in (e["tipo"] or "").lower()]
        self._render_eventos(filtered)

    # ── Render: lista de eventos ───────────────────────────────────────────────
    def _render_eventos(self, rows: list) -> None:
        for w in self._ev_inner.winfo_children():
            w.destroy()
        for ev in rows:
            secs = db.get_secciones_by_evento(ev["id"])
            dur  = sum(s["duracion"] for s in secs)
            self._make_ev_row(ev, dur,
                               getattr(self, "_on_air_id", None) == ev["id"])
        self._ev_canvas.configure(scrollregion=self._ev_canvas.bbox("all"))

    def _make_ev_row(self, ev, dur: float, is_on_air: bool) -> None:
        is_sel = self._selected_ev == ev["id"]
        bg = C["header"] if is_on_air else (C["surface"] if is_sel else C["bg"])
        handler = lambda e, eid=ev["id"]: self._select_evento(eid)

        row = tk.Frame(self._ev_inner, bg=bg, cursor="hand2")
        row.pack(fill=tk.X)
        row.columnconfigure(1, weight=1)

        # Indicador (siempre 3px para alinear con el header)
        ind_color = (C["danger"] if is_on_air
                     else C["accent"] if is_sel else bg)
        ind = tk.Frame(row, bg=ind_color, width=3)
        ind.grid(row=0, column=0, sticky="ns")

        # Nombre
        lbl_nombre = tk.Label(row, text=ev["nombre"], font=FONTS["body"],
                               bg=bg, fg=C["danger"] if is_on_air else C["text"],
                               anchor="w", padx=10, pady=8)
        lbl_nombre.grid(row=0, column=1, sticky="ew")

        # Tipo (ancho fijo para alinear con header)
        lbl_tipo = tk.Label(row, text=(ev["tipo"] or "—"),
                             font=FONTS["small"], bg=bg, fg=C["text2"],
                             width=14, anchor="w")
        lbl_tipo.grid(row=0, column=2)

        # Duración
        lbl_dur = tk.Label(row, text=self._fmt_dur(dur),
                            font=FONTS["mono_sm"], bg=bg, fg=C["text3"],
                            width=5, anchor="e")
        lbl_dur.grid(row=0, column=3, padx=(0, 4))

        # Botón transmitir
        lbl_tx = "● AL AIRE" if is_on_air else "📡"
        btn_tx = tk.Button(row, text=lbl_tx, font=FONTS["small"],
                            bg=C["danger"] if is_on_air else bg,
                            fg="#fff" if is_on_air else C["text3"],
                            relief="flat", bd=0, padx=6, width=6,
                            cursor="hand2",
                            activebackground=C["danger"],
                            activeforeground="#fff",
                            command=lambda eid=ev["id"]: self.on_transmitir(eid))
        btn_tx.grid(row=0, column=4, padx=(0, 4))
        if not is_on_air:
            btn_tx.grid_remove()

        def _enter(e, b=btn_tx, widgets=(row, ind, lbl_nombre, lbl_tipo, lbl_dur)):
            for w in widgets:
                w.config(bg=C["surface"])
            b.grid()
            b.config(bg=C["surface"])

        def _leave(e, b=btn_tx,
                   widgets=(row, ind, lbl_nombre, lbl_tipo, lbl_dur),
                   bg_=bg, on=is_on_air, sel=is_sel,
                   ind_c=ind_color):
            new_bg = C["surface"] if sel else bg_
            for w in widgets:
                w.config(bg=new_bg)
            ind.config(bg=ind_c)
            if not on:
                b.grid_remove()
            b.config(bg=C["danger"] if on else new_bg)

        # Bind a todos los widgets de la fila (incluidos labels) para selección
        for w in (row, ind, lbl_nombre, lbl_tipo, lbl_dur):
            w.bind("<Enter>",    _enter)
            w.bind("<Leave>",    _leave)
            w.bind("<Button-1>", handler)

        tk.Frame(self._ev_inner, bg=C["surface"], height=1).pack(fill=tk.X)

    def _select_evento(self, ev_id: int) -> None:
        self._selected_ev = ev_id
        ev = next((e for e in self._all_eventos if e["id"] == ev_id), None)
        if ev:
            self._set_mode_evento(ev_id, ev["nombre"])
        self._render_eventos(
            [e for e in self._all_eventos
             if not self._search_var.get()
             or self._search_var.get().lower() in e["nombre"].lower()])

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
        for w in self._sec_inner.winfo_children():
            w.destroy()
        self._sec_rows = []

        TIPO_BG = {
            "TTS":    C["tts_bg"],
            "Audio":  C["audio_bg"],
            "Sonido": C["sonido_bg"],
        }
        TIPO_FG = {
            "TTS":    C["tts_fg"],
            "Audio":  C["audio_fg"],
            "Sonido": C["sonido_fg"],
        }

        for i, sec in enumerate(secs):
            bg = C["bg"]
            row = tk.Frame(self._sec_inner, bg=bg)
            row.pack(fill=tk.X)
            self._sec_rows.append(row)

            # Indicador de tipo (barra izquierda)
            tipo = sec["tipo"] or ""
            ind_bg = TIPO_BG.get(tipo, C["border"])
            tk.Frame(row, bg=ind_bg, width=3).pack(side=tk.LEFT, fill=tk.Y)

            # Número (solo en modo evento)
            if mode == "evento":
                tk.Label(row, text=f"{i+1}", font=FONTS["mono_sm"],
                         bg=bg, fg=C["text3"], width=2,
                         anchor="e").pack(side=tk.LEFT, padx=(6, 2), pady=8)

            # Nombre
            tk.Label(row, text=sec["nombre"], font=FONTS["body"],
                     bg=bg, fg=C["text"], anchor="w").pack(
                side=tk.LEFT, padx=(8, 4), pady=8, fill=tk.X, expand=True)

            # Tipo badge
            tipo_bg = TIPO_BG.get(tipo, C["surface2"])
            tipo_fg = TIPO_FG.get(tipo, C["text2"])
            tk.Label(row, text=tipo or "—", font=FONTS["badge"],
                     bg=tipo_bg, fg=tipo_fg, padx=6, pady=2,
                     anchor="center").pack(side=tk.LEFT, padx=4)

            # Duración
            tk.Label(row, text=self._fmt_dur(sec["duracion"]),
                     font=FONTS["mono_sm"], bg=bg, fg=C["text3"],
                     width=5, anchor="e").pack(side=tk.LEFT, padx=(4, 8))

            # Botones de acción
            btns = tk.Frame(row, bg=bg)
            btns.pack(side=tk.RIGHT, padx=6)

            sec_id = sec["id"]

            if mode == "evento":
                tk.Button(btns, text="↑", font=FONTS["small"],
                          bg=C["surface2"], fg=C["text2"],
                          relief="flat", bd=0, padx=4, pady=2,
                          cursor="hand2",
                          command=lambda sid=sec_id: self._mover_seccion(sid, -1)
                          ).pack(side=tk.LEFT, padx=1)
                tk.Button(btns, text="↓", font=FONTS["small"],
                          bg=C["surface2"], fg=C["text2"],
                          relief="flat", bd=0, padx=4, pady=2,
                          cursor="hand2",
                          command=lambda sid=sec_id: self._mover_seccion(sid, 1)
                          ).pack(side=tk.LEFT, padx=1)

            tk.Button(btns, text="▶", font=FONTS["small"],
                      bg=C["surface2"], fg=C["text2"],
                      relief="flat", bd=0, padx=6, pady=2,
                      cursor="hand2",
                      command=lambda sid=sec_id: self._play_seccion(sid)
                      ).pack(side=tk.LEFT, padx=1)

            tk.Button(btns, text="✏️", font=FONTS["small"],
                      bg=C["surface2"], fg=C["text2"],
                      relief="flat", bd=0, padx=6, pady=2,
                      cursor="hand2",
                      command=lambda sid=sec_id: self._edit_seccion(sid)
                      ).pack(side=tk.LEFT, padx=1)

            if mode == "evento":
                tk.Button(btns, text="✖", font=FONTS["small"],
                          bg=C["surface2"], fg=C["danger"],
                          relief="flat", bd=0, padx=6, pady=2,
                          cursor="hand2",
                          command=lambda sid=sec_id,
                                         nm=sec["nombre"]: self._quitar_seccion(sid, nm)
                          ).pack(side=tk.LEFT, padx=1)
            else:
                tk.Button(btns, text="🗑", font=FONTS["small"],
                          bg=C["surface2"], fg=C["danger"],
                          relief="flat", bd=0, padx=6, pady=2,
                          cursor="hand2",
                          command=lambda sid=sec_id,
                                         nm=sec["nombre"]: self._del_seccion(sid, nm)
                          ).pack(side=tk.LEFT, padx=1)

            tk.Frame(self._sec_inner, bg=C["surface"], height=1).pack(fill=tk.X)

        self._sec_canvas.configure(scrollregion=self._sec_canvas.bbox("all"))

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

    def _edit_seccion(self, sec_id: int) -> None:
        SeccionForm(self, seccion_id=sec_id,
                    cfg=self.cfg, on_saved=self._on_sec_saved)

    def _del_seccion(self, sec_id: int, nombre: str) -> None:
        if messagebox.askyesno("Confirmar",
                f"¿Eliminar «{nombre}» de la biblioteca?\n"
                "Se quitará de todos los eventos que la tengan."):
            db.delete_seccion(sec_id)
            self._load_biblioteca()
            self._render_eventos(self._all_eventos)

    def _quitar_seccion(self, sec_id: int, nombre: str) -> None:
        if messagebox.askyesno("Confirmar",
                f"¿Quitar «{nombre}» del evento?\n"
                "La sección seguirá disponible en la biblioteca."):
            db.remove_seccion_from_evento(self._selected_ev, sec_id)
            self._load_secciones(self._selected_ev)
            self._render_eventos(self._all_eventos)

    def _mover_seccion(self, sec_id: int, direction: int) -> None:
        if not self._selected_ev:
            return
        db.move_seccion_in_evento(self._selected_ev, sec_id, direction)
        self._load_secciones(self._selected_ev)

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
        for i, frame in enumerate(self._sec_rows):
            if i < sec_idx:
                frame.config(bg=C["surface"])
                for w in frame.winfo_children():
                    try:
                        w.config(bg=C["surface"])
                    except Exception:
                        pass
            elif i == sec_idx:
                frame.config(bg=C["audio_bg"])
                for w in frame.winfo_children():
                    try:
                        w.config(bg=C["audio_bg"])
                    except Exception:
                        pass
                # Hacer scroll hasta la fila activa
                self._sec_canvas.update_idletasks()
                y = frame.winfo_y()
                h = self._sec_canvas.winfo_height()
                self._sec_canvas.yview_moveto(
                    max(0, y - h // 2) /
                    max(1, self._sec_inner.winfo_height()))
            else:
                frame.config(bg=C["bg"])
                for w in frame.winfo_children():
                    try:
                        w.config(bg=C["bg"])
                    except Exception:
                        pass

    # ── Utilidades ─────────────────────────────────────────────────────────────
    @staticmethod
    def _fmt_dur(s: float) -> str:
        s = int(max(0, s))
        return f"{s // 60}:{s % 60:02d}"
