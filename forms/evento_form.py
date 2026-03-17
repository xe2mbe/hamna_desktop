"""
HAMNA Desktop — Formulario Nuevo / Editar Evento
Nombre + Tipo + gestión de secciones en una sola ventana.
"""
import datetime
import tkinter as tk
from tkinter import ttk, messagebox
from tkcalendar import DateEntry
import database as db
from ui_theme import C, FONTS, HButton, HDialog
from forms.seccion_form import SeccionForm


class EventoForm(HDialog):
    def __init__(self, parent, evento_id: int = None,
                 cfg: dict = None, on_saved: callable = None):
        is_new  = evento_id is None
        title   = "Nuevo Evento" if is_new else "Editar Evento"
        super().__init__(parent, title=title, width=700, height=620)
        self.evento_id   = evento_id
        self.cfg         = cfg or {}
        self.on_saved    = on_saved
        self._tipos      = db.get_eventos_types()
        self._tipos_map  = {r["nombre"]: r["id"] for r in self._tipos}
        self._ev_data    = None
        self._pending    = []   # [{"id":..,"nombre":..,"tipo":..,"duracion":..}, ...]

        if evento_id:
            evs = db.get_all_eventos()
            row = next((e for e in evs if e["id"] == evento_id), None)
            self._ev_data = dict(row) if row else None
            # Pre-cargar secciones ya asignadas
            for sec in db.get_secciones_by_evento(evento_id):
                self._pending.append(dict(sec))

        self._build()

    # ── UI ────────────────────────────────────────────────────────────────────
    def _build(self) -> None:
        sub = ("Completa los datos y agrega las secciones del evento"
               if not self.evento_id else "Modifica el evento y sus secciones")
        self.make_header(
            "Nuevo Evento" if not self.evento_id else "Editar Evento", sub)

        # ── Datos básicos ─────────────────────────────────────────────────────
        top = tk.Frame(self, bg=C["bg"], padx=24, pady=16)
        top.pack(fill=tk.X)
        top.columnconfigure(0, weight=3)
        top.columnconfigure(1, weight=0)
        top.columnconfigure(2, weight=2)

        tk.Label(top, text="NOMBRE DEL EVENTO *", font=FONTS["badge"],
                 bg=C["bg"], fg=C["text2"]).grid(
            row=0, column=0, sticky="w", pady=(0, 4))
        self._e_nombre = ttk.Entry(top, font=FONTS["body"])
        self._e_nombre.grid(row=1, column=0, sticky="ew")

        tk.Frame(top, bg=C["bg"], width=16).grid(row=0, column=1)

        tk.Label(top, text="TIPO DE EVENTO *", font=FONTS["badge"],
                 bg=C["bg"], fg=C["text2"]).grid(
            row=0, column=2, sticky="w", pady=(0, 4))
        self._combo = ttk.Combobox(
            top, values=[r["nombre"] for r in self._tipos],
            state="readonly", font=FONTS["body"])
        self._combo.grid(row=1, column=2, sticky="ew")

        # Prefill nombre + tipo
        if self._ev_data:
            self._e_nombre.insert(0, self._ev_data["nombre"])
            self._combo.set(self._ev_data["tipo"] or "")
        elif self._tipos:
            self._combo.current(0)

        # ── Numeración de edición ─────────────────────────────────────────────
        self._chk_num_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            top, text="Asignar número de edición",
            variable=self._chk_num_var,
            bg=C["bg"], fg=C["text"], activebackground=C["bg"],
            selectcolor=C["input_bg"], font=FONTS["body"],
            command=self._on_chk_num_toggle
        ).grid(row=2, column=0, columnspan=3, sticky="w", pady=(12, 0))

        self._num_row = tk.Frame(top, bg=C["bg"])
        self._num_row.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(4, 0))
        self._num_row.grid_remove()

        tk.Label(self._num_row, text="NÚMERO #", font=FONTS["badge"],
                 bg=C["bg"], fg=C["text2"]).pack(side=tk.LEFT)
        self._spin_numero = ttk.Spinbox(self._num_row, from_=1, to=999, width=6)
        self._spin_numero.set(1)
        self._spin_numero.pack(side=tk.LEFT, padx=(4, 16))

        tk.Label(self._num_row, text="Sugerir por fecha:",
                 font=FONTS["small"], bg=C["bg"], fg=C["text3"]).pack(side=tk.LEFT)
        self._cal_fecha_num = DateEntry(
            self._num_row, width=11, date_pattern="dd/MM/yyyy",
            locale="es_MX", firstweekday="sunday",
            background="#0d6efd", foreground="white",
            headersbackground=C["surface2"], headersforeground=C["text"],
            selectbackground="#0d6efd", selectforeground="white",
            normalbackground=C["surface"], normalforeground=C["text"],
            weekendbackground=C["surface"], weekendforeground=C["text2"],
            othermonthbackground=C["bg"], othermonthforeground=C["text3"],
        )
        self._cal_fecha_num.set_date(datetime.date.today())
        self._cal_fecha_num.pack(side=tk.LEFT, padx=(4, 4))
        HButton(self._num_row, "Calcular", command=self._sugerir_numero,
                variant="ghost").pack(side=tk.LEFT)

        # Prefill numero si estamos editando
        if self._ev_data and self._ev_data.get("numero"):
            self._chk_num_var.set(True)
            self._spin_numero.set(self._ev_data["numero"])
            self._num_row.grid()

        # ── Separador + cabecera secciones ────────────────────────────────────
        tk.Frame(self, bg=C["border"], height=1).pack(fill=tk.X)

        sec_hdr = tk.Frame(self, bg=C["surface2"], padx=16, pady=8)
        sec_hdr.pack(fill=tk.X)

        tk.Label(sec_hdr, text="SECCIONES DEL EVENTO",
                 font=FONTS["badge"], bg=C["surface2"], fg=C["text3"]
                 ).pack(side=tk.LEFT)

        HButton(sec_hdr, "＋ Nueva sección",
                command=self._nueva_seccion,
                variant="ghost").pack(side=tk.RIGHT, padx=(4, 0))
        HButton(sec_hdr, "＋ Agregar de biblioteca",
                command=self._agregar_de_biblioteca,
                variant="primary").pack(side=tk.RIGHT, padx=(4, 0))

        tk.Frame(self, bg=C["border"], height=1).pack(fill=tk.X)

        # ── Footer (se empaca ANTES que el canvas para reservar su espacio) ────
        tk.Frame(self, bg=C["border"], height=1).pack(fill=tk.X, side=tk.BOTTOM)
        footer = tk.Frame(self, bg=C["bg"], pady=14)
        footer.pack(fill=tk.X, side=tk.BOTTOM)
        footer.columnconfigure(0, weight=1)
        inner = tk.Frame(footer, bg=C["bg"])
        inner.grid(row=0, column=0)
        HButton(inner, "Cancelar", command=self.destroy,
                variant="muted").pack(side=tk.LEFT, padx=6)
        HButton(inner, "Guardar evento", command=self._save,
                variant="success").pack(side=tk.LEFT, padx=6)

        # ── Lista de secciones pendientes ─────────────────────────────────────
        sec_area = tk.Frame(self, bg=C["bg"])
        sec_area.pack(fill=tk.BOTH, expand=True)

        sec_sb = ttk.Scrollbar(sec_area, orient="vertical")
        self._sec_canvas = tk.Canvas(sec_area, bg=C["bg"], highlightthickness=0,
                                      yscrollcommand=sec_sb.set)
        sec_sb.config(command=self._sec_canvas.yview)
        self._sec_inner = tk.Frame(self._sec_canvas, bg=C["bg"])
        self._sec_inner.bind("<Configure>",
            lambda e: self._sec_canvas.configure(
                scrollregion=self._sec_canvas.bbox("all")))
        self._sec_canvas.create_window((0, 0), window=self._sec_inner,
                                        anchor="nw")
        sec_sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._sec_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._render_pending()

    # ── Numeración ────────────────────────────────────────────────────────────
    def _on_chk_num_toggle(self) -> None:
        if self._chk_num_var.get():
            self._num_row.grid()
        else:
            self._num_row.grid_remove()

    def _sugerir_numero(self) -> None:
        fecha = self._cal_fecha_num.get_date()
        first = datetime.date(fecha.year, 1, 1)
        days_ahead = (fecha.weekday() - first.weekday()) % 7
        first_occ = first + datetime.timedelta(days=days_ahead)
        numero = (fecha - first_occ).days // 7 + 1 if first_occ <= fecha else 0
        self._spin_numero.set(numero)

    # ── Render lista secciones ─────────────────────────────────────────────────
    def _render_pending(self) -> None:
        for w in self._sec_inner.winfo_children():
            w.destroy()

        if not self._pending:
            tk.Label(self._sec_inner,
                     text="Sin secciones — usa los botones de arriba para agregar",
                     font=FONTS["small"], bg=C["bg"], fg=C["text3"],
                     pady=20).pack(expand=True)
            self._sec_canvas.configure(
                scrollregion=self._sec_canvas.bbox("all"))
            return

        TIPO_BG = {"TTS": C["tts_bg"], "Audio": C["audio_bg"],
                   "Sonido": C["sonido_bg"]}
        TIPO_FG = {"TTS": C["tts_fg"], "Audio": C["audio_fg"],
                   "Sonido": C["sonido_fg"]}

        for i, sec in enumerate(self._pending):
            row = tk.Frame(self._sec_inner, bg=C["bg"])
            row.pack(fill=tk.X)

            tipo = sec.get("tipo") or ""
            tk.Frame(row, bg=TIPO_BG.get(tipo, C["border"]),
                     width=3).pack(side=tk.LEFT, fill=tk.Y)

            # Número de orden
            tk.Label(row, text=f"{i+1}", font=FONTS["mono_sm"],
                     bg=C["bg"], fg=C["text3"],
                     width=2, anchor="e").pack(side=tk.LEFT, padx=(8, 4), pady=8)

            # Nombre
            tk.Label(row, text=sec["nombre"], font=FONTS["body"],
                     bg=C["bg"], fg=C["text"], anchor="w").pack(
                side=tk.LEFT, padx=(4, 8), pady=8, fill=tk.X, expand=True)

            # Tipo badge
            tk.Label(row, text=tipo or "—", font=FONTS["badge"],
                     bg=TIPO_BG.get(tipo, C["surface2"]),
                     fg=TIPO_FG.get(tipo, C["text2"]),
                     padx=6, pady=2).pack(side=tk.LEFT, padx=4)

            # Duración
            tk.Label(row, text=self._fmt(sec.get("duracion", 0)),
                     font=FONTS["mono_sm"], bg=C["bg"], fg=C["text3"],
                     width=5, anchor="e").pack(side=tk.LEFT, padx=(4, 8))

            # Botones inline
            btns = tk.Frame(row, bg=C["bg"])
            btns.pack(side=tk.RIGHT, padx=8)

            sec_id  = sec["id"]
            is_cont = sec.get("contabilizable", 1)
            tk.Button(btns, text="↑", font=FONTS["small"],
                      bg=C["surface2"], fg=C["text2"],
                      relief="flat", bd=0, padx=5, pady=2, cursor="hand2",
                      command=lambda idx=i: self._move(idx, -1)
                      ).pack(side=tk.LEFT, padx=1)
            tk.Button(btns, text="↓", font=FONTS["small"],
                      bg=C["surface2"], fg=C["text2"],
                      relief="flat", bd=0, padx=5, pady=2, cursor="hand2",
                      command=lambda idx=i: self._move(idx, 1)
                      ).pack(side=tk.LEFT, padx=1)
            tk.Button(btns,
                      text="C" if is_cont else "c",
                      font=FONTS["small"],
                      bg=C.get("success", "#3fb950") if is_cont else C["surface2"],
                      fg=C["bg"] if is_cont else C["text3"],
                      relief="flat", bd=0, padx=5, pady=2, cursor="hand2",
                      command=lambda idx=i: self._toggle_pending_cont(idx)
                      ).pack(side=tk.LEFT, padx=1)
            tk.Button(btns, text="✖", font=FONTS["small"],
                      bg=C["surface2"], fg=C["danger"],
                      relief="flat", bd=0, padx=6, pady=2, cursor="hand2",
                      command=lambda idx=i: self._remove(idx)
                      ).pack(side=tk.LEFT, padx=1)

            tk.Frame(self._sec_inner, bg=C["surface"], height=1).pack(fill=tk.X)

        self._sec_canvas.configure(scrollregion=self._sec_canvas.bbox("all"))

    # ── Acciones secciones ─────────────────────────────────────────────────────
    def _move(self, idx: int, direction: int) -> None:
        new_idx = idx + direction
        if 0 <= new_idx < len(self._pending):
            self._pending[idx], self._pending[new_idx] = \
                self._pending[new_idx], self._pending[idx]
            self._render_pending()

    def _remove(self, idx: int) -> None:
        self._pending.pop(idx)
        self._render_pending()

    def _toggle_pending_cont(self, idx: int) -> None:
        cur = self._pending[idx].get("contabilizable", 1)
        self._pending[idx]["contabilizable"] = 0 if cur else 1
        self._render_pending()

    def _agregar_de_biblioteca(self) -> None:
        """Abre un selector con las secciones de la biblioteca no agregadas aún."""
        ids_ya = {s["id"] for s in self._pending}
        disponibles = [dict(s) for s in db.get_all_secciones()
                       if s["id"] not in ids_ya]

        if not disponibles:
            messagebox.showinfo("Biblioteca vacía",
                "No hay secciones disponibles.\nCrea una con '＋ Nueva sección'.",
                parent=self)
            return

        _BibliotecaPicker(self, disponibles, self._on_secs_seleccionadas)

    def _on_secs_seleccionadas(self, secs: list) -> None:
        for sec in secs:
            if not any(p["id"] == sec["id"] for p in self._pending):
                s = dict(sec)
                s.setdefault("contabilizable", 1)
                self._pending.append(s)
        self._render_pending()

    def _nueva_seccion(self) -> None:
        """Crea una nueva sección y la añade automáticamente al evento."""
        before_ids = {s["id"] for s in db.get_all_secciones()}

        def on_saved():
            nuevas = [s for s in db.get_all_secciones()
                      if s["id"] not in before_ids]
            for sec in nuevas:
                if not any(p["id"] == sec["id"] for p in self._pending):
                    s = dict(sec)
                    s.setdefault("contabilizable", 1)
                    self._pending.append(s)
            self._render_pending()

        SeccionForm(self, cfg=self.cfg, on_saved=on_saved)

    # ── Guardar ────────────────────────────────────────────────────────────────
    def _save(self) -> None:
        nombre = self._e_nombre.get().strip()
        tipo   = self._combo.get()

        if not nombre:
            messagebox.showwarning("Campo requerido",
                "El nombre del evento es obligatorio.", parent=self)
            self._e_nombre.focus_set()
            return
        if not tipo:
            messagebox.showwarning("Campo requerido",
                "Selecciona un tipo de evento.", parent=self)
            return

        numero = None
        if self._chk_num_var.get():
            try:
                numero = int(self._spin_numero.get())
            except (ValueError, TypeError):
                numero = None

        tipo_id = self._tipos_map.get(tipo)
        try:
            if self.evento_id:
                db.update_evento(self.evento_id, nombre, tipo_id, numero)
                ev_id = self.evento_id
                # Reemplazar secciones asignadas por el orden actual
                with db.get_connection() as conn:
                    conn.execute(
                        "DELETE FROM evento_secciones WHERE evento_id=?",
                        (ev_id,))
                    conn.commit()
            else:
                ev_id = db.insert_evento(nombre, tipo_id, numero)

            for orden, sec in enumerate(self._pending, start=1):
                with db.get_connection() as conn:
                    conn.execute(
                        "INSERT OR IGNORE INTO evento_secciones "
                        "(evento_id, seccion_id, orden, contabilizable) VALUES (?,?,?,?)",
                        (ev_id, sec["id"], orden, sec.get("contabilizable", 1)))
                    conn.commit()

            if callable(self.on_saved):
                self.on_saved()
            self.destroy()

        except Exception as e:
            messagebox.showerror("Error al guardar", str(e), parent=self)

    # ── Utilidades ─────────────────────────────────────────────────────────────
    @staticmethod
    def _fmt(s: float) -> str:
        s = int(max(0, s))
        return f"{s // 60}:{s % 60:02d}"


# ── Picker interno de biblioteca ───────────────────────────────────────────────
class _BibliotecaPicker(HDialog):
    """Selector de secciones con dos paneles: disponibles y seleccionadas con orden."""

    TIPO_BG = {"TTS": "#1c2a3a", "Audio": "#1a2d1a", "Sonido": "#2d2114"}
    TIPO_FG = {"TTS": "#388bfd", "Audio": "#3fb950", "Sonido": "#d29922"}

    def __init__(self, parent, disponibles: list, on_selected: callable):
        super().__init__(parent, title="Agregar desde biblioteca",
                         width=740, height=500)
        self._disponibles = list(disponibles)
        self._seleccionadas = []        # orden de reproducción
        self._on_selected  = on_selected
        self._build()

    def _build(self) -> None:
        self.make_header(
            "Seleccionar secciones",
            "Elige secciones de la biblioteca y ordénalas antes de agregar"
        )

        # ── Footer (empaquetado ANTES que el cuerpo para que sea visible) ─────
        tk.Frame(self, bg=C["border"], height=1).pack(fill=tk.X, side=tk.BOTTOM)
        footer = tk.Frame(self, bg=C["bg"], pady=12)
        footer.pack(fill=tk.X, side=tk.BOTTOM)
        footer.columnconfigure(0, weight=1)
        inner_f = tk.Frame(footer, bg=C["bg"])
        inner_f.grid(row=0, column=0)
        HButton(inner_f, "Cancelar",
                command=self.destroy, variant="muted").pack(side=tk.LEFT, padx=6)
        HButton(inner_f, "Agregar al evento",
                command=self._confirm, variant="success").pack(side=tk.LEFT, padx=6)

        # ── Cuerpo: dos paneles ───────────────────────────────────────────────
        body = tk.Frame(self, bg=C["bg"])
        body.pack(fill=tk.BOTH, expand=True)

        # Panel izquierdo — biblioteca disponible
        lp = tk.Frame(body, bg=C["bg"])
        lp.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tk.Label(lp, text="BIBLIOTECA DISPONIBLE", font=FONTS["badge"],
                 bg=C["surface2"], fg=C["text3"],
                 anchor="w", padx=10, pady=6).pack(fill=tk.X)
        tk.Frame(lp, bg=C["border"], height=1).pack(fill=tk.X)

        sb_l = ttk.Scrollbar(lp, orient="vertical")
        sb_l.pack(side=tk.RIGHT, fill=tk.Y)
        cols = ("nombre", "tipo", "dur")
        self._tree_disp = ttk.Treeview(lp, columns=cols, show="headings",
                                        selectmode="extended",
                                        yscrollcommand=sb_l.set)
        sb_l.config(command=self._tree_disp.yview)
        self._tree_disp.heading("nombre", text="Nombre")
        self._tree_disp.heading("tipo",   text="Tipo")
        self._tree_disp.heading("dur",    text="Dur.")
        self._tree_disp.column("nombre", width=160)
        self._tree_disp.column("tipo",   width=70, stretch=False)
        self._tree_disp.column("dur",    width=50, stretch=False)
        self._tree_disp.pack(fill=tk.BOTH, expand=True)
        self._tree_disp.bind("<Double-1>", lambda e: self._mover_a_sel())

        for sec in self._disponibles:
            self._tree_disp.insert("", tk.END, iid=str(sec["id"]),
                values=(sec["nombre"], sec["tipo"] or "—",
                        self._fmt(sec.get("duracion", 0))))

        # Panel central — botones de transferencia
        mid = tk.Frame(body, bg=C["bg"], padx=6)
        mid.pack(side=tk.LEFT, fill=tk.Y)
        tk.Frame(mid, bg=C["bg"]).pack(expand=True, fill=tk.Y)  # spacer top
        HButton(mid, "›", command=self._mover_a_sel,
                variant="primary").pack(pady=3)
        tk.Frame(mid, bg=C["bg"]).pack(expand=True, fill=tk.Y)  # spacer bot

        # Panel derecho — secciones seleccionadas con orden
        rp = tk.Frame(body, bg=C["bg"])
        rp.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tk.Label(rp, text="ORDEN DE REPRODUCCIÓN", font=FONTS["badge"],
                 bg=C["surface2"], fg=C["text3"],
                 anchor="w", padx=10, pady=6).pack(fill=tk.X)
        tk.Frame(rp, bg=C["border"], height=1).pack(fill=tk.X)

        sb_r = ttk.Scrollbar(rp, orient="vertical")
        sb_r.pack(side=tk.RIGHT, fill=tk.Y)
        self._sel_canvas = tk.Canvas(rp, bg=C["bg"], highlightthickness=0,
                                      yscrollcommand=sb_r.set)
        sb_r.config(command=self._sel_canvas.yview)
        self._sel_inner = tk.Frame(self._sel_canvas, bg=C["bg"])
        self._sel_inner.bind("<Configure>",
            lambda e: self._sel_canvas.configure(
                scrollregion=self._sel_canvas.bbox("all")))
        _win = self._sel_canvas.create_window((0, 0), window=self._sel_inner,
                                               anchor="nw")
        self._sel_canvas.bind("<Configure>",
            lambda e: self._sel_canvas.itemconfig(_win, width=e.width))
        self._sel_canvas.pack(fill=tk.BOTH, expand=True)

        self._render_sel()

    # ── Transferencia ──────────────────────────────────────────────────────────
    def _mover_a_sel(self) -> None:
        sel = self._tree_disp.selection()
        if not sel:
            return
        ids_ya = {s["id"] for s in self._seleccionadas}
        for iid in sel:
            sec_id = int(iid)
            if sec_id not in ids_ya:
                sec = next((s for s in self._disponibles
                            if s["id"] == sec_id), None)
                if sec:
                    self._seleccionadas.append(dict(sec))
        self._render_sel()

    def _quitar_de_sel(self, idx: int = None) -> None:
        if idx is not None:
            self._seleccionadas.pop(idx)
        self._render_sel()

    def _move_sel(self, idx: int, direction: int) -> None:
        new_idx = idx + direction
        if 0 <= new_idx < len(self._seleccionadas):
            self._seleccionadas[idx], self._seleccionadas[new_idx] = \
                self._seleccionadas[new_idx], self._seleccionadas[idx]
        self._render_sel()

    # ── Render panel derecho ───────────────────────────────────────────────────
    def _render_sel(self) -> None:
        for w in self._sel_inner.winfo_children():
            w.destroy()

        if not self._seleccionadas:
            tk.Label(self._sel_inner,
                     text="Doble clic o › para agregar",
                     font=FONTS["small"], bg=C["bg"], fg=C["text3"],
                     pady=20).pack(expand=True)
            self._sel_canvas.configure(
                scrollregion=self._sel_canvas.bbox("all"))
            return

        for i, sec in enumerate(self._seleccionadas):
            tipo = sec.get("tipo") or ""
            bg = C["bg"]
            row = tk.Frame(self._sel_inner, bg=bg)
            row.pack(fill=tk.X)

            tk.Frame(row, bg=self.TIPO_BG.get(tipo, C["border"]),
                     width=3).pack(side=tk.LEFT, fill=tk.Y)
            tk.Label(row, text=f"{i+1}", font=FONTS["mono_sm"],
                     bg=bg, fg=C["text3"], width=2,
                     anchor="e").pack(side=tk.LEFT, padx=(6, 2), pady=6)
            tk.Label(row, text=sec["nombre"], font=FONTS["body"],
                     bg=bg, fg=C["text"], anchor="w").pack(
                side=tk.LEFT, padx=(4, 6), fill=tk.X, expand=True)
            tk.Label(row, text=self._fmt(sec.get("duracion", 0)),
                     font=FONTS["mono_sm"], bg=bg, fg=C["text3"],
                     width=5, anchor="e").pack(side=tk.LEFT, padx=4)

            btns = tk.Frame(row, bg=bg)
            btns.pack(side=tk.RIGHT, padx=6)
            for txt, cmd in [
                ("↑", lambda idx=i: self._move_sel(idx, -1)),
                ("↓", lambda idx=i: self._move_sel(idx,  1)),
                ("✖", lambda idx=i: self._quitar_de_sel(idx)),
            ]:
                tk.Button(btns, text=txt, font=FONTS["small"],
                          bg=C["surface2"],
                          fg=C["danger"] if txt == "✖" else C["text2"],
                          relief="flat", bd=0, padx=5, pady=2,
                          cursor="hand2", command=cmd
                          ).pack(side=tk.LEFT, padx=1)

            tk.Frame(self._sel_inner, bg=C["surface"],
                     height=1).pack(fill=tk.X)

        self._sel_canvas.configure(scrollregion=self._sel_canvas.bbox("all"))

    # ── Confirmar ──────────────────────────────────────────────────────────────
    def _confirm(self) -> None:
        if not self._seleccionadas:
            messagebox.showinfo("Sin secciones",
                "Agrega al menos una sección al orden de reproducción.",
                parent=self)
            return
        if callable(self._on_selected):
            self._on_selected(self._seleccionadas)
        self.destroy()

    @staticmethod
    def _fmt(s: float) -> str:
        s = int(max(0, s))
        return f"{s // 60}:{s % 60:02d}"
