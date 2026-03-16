"""
HAMNA Desktop — Vista de Programación
Calendario semanal + editor inline de fecha/hora + botón Transmitir.
"""
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date, datetime, timedelta, timezone
import database as db
from ui_theme import C, FONTS, HButton


class ViewProgramacion(tk.Frame):
    def __init__(self, parent, on_transmitir: callable):
        super().__init__(parent, bg=C["bg"])
        self.on_transmitir = on_transmitir
        self._on_air_id    = None
        self._selected_ev  = None
        self._all_eventos  = []
        self._schedule     = []
        self._build()
        self.load_data()

    # ── Build ─────────────────────────────────────────────────────────────────
    def _build(self) -> None:
        # Toolbar
        tb = tk.Frame(self, bg=C["surface"], padx=12, pady=8)
        tb.pack(fill=tk.X)
        tk.Frame(self, bg=C["border"], height=1).pack(fill=tk.X)

        HButton(tb, "＋ Programar Evento",
                command=self._open_prog_modal,
                variant="primary").pack(side=tk.LEFT)
        HButton(tb, "🗑 Limpiar todo",
                command=self._clear_all,
                variant="ghost").pack(side=tk.LEFT, padx=(6, 0))

        HButton(tb, "→ Sig",
                command=lambda: None,
                variant="ghost").pack(side=tk.RIGHT)
        HButton(tb, "← Ant",
                command=lambda: None,
                variant="ghost").pack(side=tk.RIGHT, padx=(0, 4))
        tk.Label(tb, text="Semana",
                 font=FONTS["body"], bg=C["surface"],
                 fg=C["text2"]).pack(side=tk.RIGHT, padx=(0, 8))

        # Stats
        stats = tk.Frame(self, bg=C["bg"], padx=14, pady=8)
        stats.pack(fill=tk.X)
        self._stat_vars = {}
        for key, lbl in [("total",   "PROGRAMADOS"),
                          ("hoy",    "HOY"),
                          ("semana", "ESTA SEMANA"),
                          ("pend",   "SIN PROGRAMAR")]:
            f = tk.Frame(stats, bg=C["surface2"], padx=14, pady=10)
            f.pack(side=tk.LEFT, padx=(0, 8), ipadx=6, fill=tk.Y)
            v = tk.StringVar(value="0")
            self._stat_vars[key] = v
            tk.Label(f, textvariable=v, font=FONTS["h2"],
                     bg=C["surface2"], fg=C["text"]).pack()
            tk.Label(f, text=lbl, font=FONTS["badge"],
                     bg=C["surface2"], fg=C["text3"]).pack()

        # ── Relojes ───────────────────────────────────────────────────────────
        clocks = tk.Frame(stats, bg=C["surface2"], padx=16, pady=8)
        clocks.pack(side=tk.LEFT, padx=(16, 0), fill=tk.Y)

        # Local
        tk.Label(clocks, text="LOCAL", font=FONTS["badge"],
                 bg=C["surface2"], fg=C["text3"]).grid(
            row=0, column=0, sticky="w")
        self._lbl_local = tk.Label(clocks, text="",
                                    font=("Consolas", 18, "bold"),
                                    bg=C["surface2"], fg=C["text"])
        self._lbl_local.grid(row=1, column=0, sticky="w")
        self._lbl_local_date = tk.Label(clocks, text="",
                                         font=FONTS["small"],
                                         bg=C["surface2"], fg=C["text2"])
        self._lbl_local_date.grid(row=2, column=0, sticky="w")

        # Separador vertical
        tk.Frame(clocks, bg=C["border"], width=1).grid(
            row=0, column=1, rowspan=3, sticky="ns", padx=16)

        # UTC
        tk.Label(clocks, text="UTC", font=FONTS["badge"],
                 bg=C["surface2"], fg=C["text3"]).grid(
            row=0, column=2, sticky="w")
        self._lbl_utc = tk.Label(clocks, text="",
                                  font=("Consolas", 18, "bold"),
                                  bg=C["surface2"], fg=C["accent"])
        self._lbl_utc.grid(row=1, column=2, sticky="w")
        self._lbl_utc_date = tk.Label(clocks, text="",
                                       font=FONTS["small"],
                                       bg=C["surface2"], fg=C["text2"])
        self._lbl_utc_date.grid(row=2, column=2, sticky="w")

        self._tick_clock()
        tk.Frame(self, bg=C["border"], height=1).pack(fill=tk.X)

        # Body split — PanedWindow redimensionable
        paned = tk.PanedWindow(self, orient=tk.HORIZONTAL,
                               bg=C["border"], sashwidth=5,
                               sashrelief="flat", bd=0)
        paned.pack(fill=tk.BOTH, expand=True)

        # Panel izquierdo — lista de eventos
        lp = tk.Frame(paned, bg=C["bg"])
        paned.add(lp, minsize=180, width=290, stretch="never")

        tk.Label(lp, text="EVENTOS", font=FONTS["badge"],
                 bg=C["surface2"], fg=C["text3"],
                 padx=12, pady=6).pack(fill=tk.X)
        tk.Frame(lp, bg=C["border"], height=1).pack(fill=tk.X)

        ev_wrap = tk.Frame(lp, bg=C["bg"])
        ev_wrap.pack(fill=tk.BOTH, expand=True)
        self._ev_canvas = tk.Canvas(ev_wrap, bg=C["bg"],
                                     highlightthickness=0)
        ev_sb = ttk.Scrollbar(ev_wrap, orient="vertical",
                               command=self._ev_canvas.yview)
        self._ev_inner = tk.Frame(self._ev_canvas, bg=C["bg"])
        self._ev_inner.bind("<Configure>",
            lambda e: self._ev_canvas.configure(
                scrollregion=self._ev_canvas.bbox("all")))
        self._ev_canvas.create_window((0, 0), window=self._ev_inner,
                                       anchor="nw")
        self._ev_canvas.configure(yscrollcommand=ev_sb.set)
        self._ev_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ev_sb.pack(side=tk.RIGHT, fill=tk.Y)

        # Panel derecho — timeline + editor
        rp = tk.Frame(paned, bg=C["bg"])
        paned.add(rp, minsize=200, stretch="always")

        # Right header
        rh = tk.Frame(rp, bg=C["bg"], padx=14, pady=8)
        rh.pack(fill=tk.X)
        tk.Label(rh, text="Programación semanal", font=FONTS["h3"],
                 bg=C["bg"], fg=C["text"]).pack(side=tk.LEFT)
        tk.Label(rh,
                 text="Selecciona un evento para editar su horario",
                 font=FONTS["small"],
                 bg=C["bg"], fg=C["text2"]).pack(side=tk.LEFT, padx=(8, 0))
        tk.Frame(rp, bg=C["border"], height=1).pack(fill=tk.X)

        # Editor inline
        self._sched_form = tk.Frame(rp, bg=C["surface"], padx=14, pady=10)
        self._sched_form.pack(fill=tk.X)
        self._sched_form.pack_forget()  # oculto hasta selección

        tk.Label(self._sched_form, text="Editando programación:",
                 font=FONTS["small"], bg=C["surface"],
                 fg=C["text2"]).grid(row=0, column=0, sticky="w")
        self._lbl_sched_ev = tk.Label(self._sched_form, text="",
            font=FONTS["h3"], bg=C["surface"], fg=C["accent"])
        self._lbl_sched_ev.grid(row=0, column=1, columnspan=3,
                                 sticky="w", padx=(6, 0))

        tk.Label(self._sched_form, text="FECHA",
                 font=FONTS["badge"], bg=C["surface"],
                 fg=C["text3"]).grid(row=1, column=0, sticky="w", pady=(8, 2))
        self._sched_date = ttk.Entry(self._sched_form, width=14)
        self._sched_date.grid(row=2, column=0, sticky="ew", padx=(0, 8))

        tk.Label(self._sched_form, text="HORA  (hora local del equipo)",
                 font=FONTS["badge"], bg=C["surface"],
                 fg=C["text3"]).grid(row=1, column=1, sticky="w", pady=(8, 2))
        self._sched_time = ttk.Entry(self._sched_form, width=10)
        self._sched_time.grid(row=2, column=1, sticky="ew", padx=(0, 8))

        tk.Label(self._sched_form, text="RECURRENCIA",
                 font=FONTS["badge"], bg=C["surface"],
                 fg=C["text3"]).grid(row=1, column=2, sticky="w",
                                     padx=(8, 0), pady=(8, 2))
        self._sched_rec = ttk.Combobox(
            self._sched_form,
            values=["ninguna", "diaria", "semanal", "lun-vie"],
            state="readonly", width=10)
        self._sched_rec.set("ninguna")
        self._sched_rec.grid(row=2, column=2, sticky="ew", padx=(8, 8))

        btn_f = tk.Frame(self._sched_form, bg=C["surface"])
        btn_f.grid(row=2, column=3, padx=(8, 0))
        HButton(btn_f, "✓ Guardar",
                command=self._save_sched,
                variant="success").pack(side=tk.LEFT)
        HButton(btn_f, "Cancelar",
                command=self._cancel_sched,
                variant="muted").pack(side=tk.LEFT, padx=(6, 0))

        self._lbl_sched_preview = tk.Label(self._sched_form, text="",
            font=FONTS["small"], bg=C["surface"], fg=C["success"])
        self._lbl_sched_preview.grid(row=3, column=0, columnspan=4,
                                      sticky="w", pady=(4, 0))

        for entry in (self._sched_date, self._sched_time):
            entry.bind("<KeyRelease>", self._update_preview)

        tk.Frame(rp, bg=C["border"], height=1).pack(fill=tk.X)

        # Timeline scroll
        tl_wrap = tk.Frame(rp, bg=C["bg"])
        tl_wrap.pack(fill=tk.BOTH, expand=True)
        self._tl_canvas = tk.Canvas(tl_wrap, bg=C["bg"],
                                     highlightthickness=0)
        tl_sb = ttk.Scrollbar(tl_wrap, orient="vertical",
                               command=self._tl_canvas.yview)
        self._tl_inner = tk.Frame(self._tl_canvas, bg=C["bg"])
        self._tl_inner.bind("<Configure>",
            lambda e: self._tl_canvas.configure(
                scrollregion=self._tl_canvas.bbox("all")))
        self._tl_canvas.create_window((0, 0), window=self._tl_inner,
                                       anchor="nw")
        self._tl_canvas.configure(yscrollcommand=tl_sb.set)
        self._tl_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tl_sb.pack(side=tk.RIGHT, fill=tk.Y)

    def _tick_clock(self) -> None:
        now_local = datetime.now()
        now_utc   = datetime.now(timezone.utc)
        self._lbl_local.config(     text=now_local.strftime("%H:%M:%S"))
        self._lbl_local_date.config(text=now_local.strftime("%Y-%m-%d"))
        self._lbl_utc.config(       text=now_utc.strftime(  "%H:%M:%S"))
        self._lbl_utc_date.config(  text=now_utc.strftime(  "%Y-%m-%d"))
        self.after(1000, self._tick_clock)

    # ── Carga de datos ────────────────────────────────────────────────────────
    def load_data(self) -> None:
        self._all_eventos = db.get_all_eventos()
        self._schedule    = db.get_all_programacion()
        self._render_ev_list()
        self._render_timeline()
        self._update_stats()

    def _render_ev_list(self) -> None:
        for w in self._ev_inner.winfo_children():
            w.destroy()
        for ev in self._all_eventos:
            sched = next((s for s in self._schedule
                          if s["evento_id"] == ev["id"]), None)
            is_on_air = self._on_air_id == ev["id"]
            self._make_prog_ev_row(ev, sched, is_on_air)

    def _make_prog_ev_row(self, ev, sched, is_on_air: bool) -> None:
        bg = C["header"] if is_on_air else C["bg"]
        row = tk.Frame(self._ev_inner, bg=bg, cursor="hand2",
                       padx=10, pady=8)
        row.pack(fill=tk.X)

        # Dot de color
        dot_color = C["danger"] if is_on_air else C["accent"]
        tk.Label(row, text="●", font=("Segoe UI", 9),
                 bg=bg, fg=dot_color).pack(side=tk.LEFT, padx=(0, 6))

        info = tk.Frame(row, bg=bg)
        info.pack(side=tk.LEFT, fill=tk.X, expand=True)
        fg = C["danger"] if is_on_air else C["text"]
        tk.Label(info, text=ev["nombre"], font=FONTS["body"],
                 bg=bg, fg=fg, anchor="w").pack(anchor="w")
        tk.Label(info, text=ev["tipo"] or "—", font=FONTS["small"],
                 bg=bg, fg=C["text3"]).pack(anchor="w")

        sched_frame = tk.Frame(row, bg=bg)
        sched_frame.pack(side=tk.RIGHT, padx=(0, 4))
        if sched:
            tk.Label(sched_frame, text=sched["hora"],
                     font=FONTS["mono_sm"], bg=bg,
                     fg=C["success"]).pack(anchor="e")
            tk.Label(sched_frame,
                     text=self._fmt_date(sched["fecha"]),
                     font=FONTS["small"], bg=bg,
                     fg=C["text3"]).pack(anchor="e")
        else:
            tk.Label(sched_frame, text="Sin horario",
                     font=FONTS["small"], bg=bg,
                     fg=C["text3"]).pack(anchor="e")

        # Contenedor fijo para botones de acción (evita que el layout se mueva)
        btn_area = tk.Frame(row, bg=bg)
        btn_area.pack(side=tk.RIGHT, padx=(4, 0))

        # Botón transmitir (oculto inicialmente, aparece en hover)
        lbl_tx = "● AL AIRE" if is_on_air else "📡 Transmitir"
        btn_tx = tk.Button(btn_area, text=lbl_tx, font=FONTS["small"],
                           bg=C["danger"] if is_on_air else bg,
                           fg="#fff" if is_on_air else C["text3"],
                           relief="flat", bd=0, padx=6, cursor="hand2",
                           activebackground=C["danger"],
                           activeforeground="#fff",
                           command=lambda eid=ev["id"]: self.on_transmitir(eid))
        btn_tx.pack(side=tk.LEFT, padx=(0, 4))
        if not is_on_air:
            btn_tx.pack_forget()

        # Botón 📅 programar (siempre visible, a la derecha de Transmitir)
        tk.Button(btn_area, text="📅", font=FONTS["body"],
                  bg=bg, fg=C["text3"],
                  relief="flat", bd=0, padx=4, cursor="hand2",
                  activebackground=C["surface"],
                  activeforeground=C["accent"],
                  command=lambda eid=ev["id"]: self._open_prog_modal(eid)
                  ).pack(side=tk.LEFT)

        all_frames = [row, info, sched_frame, btn_area]

        def _recolor(new_bg, widgets=all_frames):
            for w in widgets:
                try: w.config(bg=new_bg)
                except Exception: pass
                for child in w.winfo_children():
                    try: child.config(bg=new_bg)
                    except Exception: pass

        def _enter(e, b=btn_tx, on=is_on_air):
            _recolor(C["surface"])
            if on:
                b.config(bg=C["danger"], fg="#fff")  # mantener rojo AL AIRE
            else:
                b.config(bg=C["surface"])
            b.pack(side=tk.LEFT, padx=(0, 4))

        def _leave(e, b=btn_tx, bg_=bg, on=is_on_air):
            _recolor(bg_)
            if on:
                b.config(bg=C["danger"], fg="#fff")  # restaurar rojo AL AIRE
            else:
                b.pack_forget()

        for w in [row, info, sched_frame]:
            w.bind("<Enter>", _enter)
            w.bind("<Leave>", _leave)
            w.bind("<Button-1>",
                   lambda e, eid=ev["id"]: self._select_ev(eid))

        tk.Frame(self._ev_inner, bg=C["surface"], height=1).pack(fill=tk.X)

    def _render_timeline(self) -> None:
        for w in self._tl_inner.winfo_children():
            w.destroy()

        if not self._schedule:
            tk.Label(self._tl_inner,
                     text="Sin eventos programados.",
                     font=FONTS["body"], bg=C["bg"],
                     fg=C["text3"]).pack(pady=40)
            return

        # Agrupar por fecha
        days: dict[str, list] = {}
        for s in self._schedule:
            days.setdefault(s["fecha"], []).append(s)

        today = date.today().isoformat()
        now_h = datetime.now().strftime("%H:%M")

        for fecha in sorted(days.keys()):
            is_today = (fecha == today)

            # Cabecera del día
            dh = tk.Frame(self._tl_inner, bg=C["bg"], padx=14, pady=6)
            dh.pack(fill=tk.X)
            tk.Frame(dh, bg=C["border"], height=1).pack(
                side=tk.LEFT, fill=tk.Y, expand=True)
            tk.Label(dh,
                     text=("HOY  " if is_today else "") +
                          f"{self._day_name(fecha)}  {self._fmt_date(fecha)}",
                     font=FONTS["badge"], bg=C["bg"],
                     fg=C["text2"] if is_today else C["text3"],
                     padx=8).pack(side=tk.LEFT)
            tk.Frame(dh, bg=C["border"], height=1).pack(
                side=tk.LEFT, fill=tk.Y, expand=True)

            # Indicador AHORA
            if is_today:
                ni = tk.Frame(self._tl_inner, bg=C["bg"],
                               padx=14, pady=2)
                ni.pack(fill=tk.X)
                tk.Label(ni, text="●", font=("Segoe UI", 8),
                         bg=C["bg"], fg=C["danger"]).pack(side=tk.LEFT)
                tk.Label(ni, text=f"AHORA — {now_h}",
                         font=FONTS["badge"], bg=C["bg"],
                         fg=C["danger"]).pack(side=tk.LEFT, padx=(4, 0))
                tk.Frame(ni, bg=C["danger"], height=1).pack(
                    side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 0))

            for sched in sorted(days[fecha], key=lambda s: s["hora"]):
                ev = next((e for e in self._all_eventos
                           if e["id"] == sched["evento_id"]), None)
                if ev:
                    self._make_tl_card(ev, sched)

    def _make_tl_card(self, ev, sched) -> None:
        is_on_air = self._on_air_id == ev["id"]
        secs  = db.get_secciones_by_evento(ev["id"])
        dur   = sum(s["duracion"] for s in secs)
        color = C["danger"] if is_on_air else C["accent"]

        row = tk.Frame(self._tl_inner, bg=C["bg"],
                       padx=14, pady=3)
        row.pack(fill=tk.X)

        # Hora
        tk.Label(row, text=sched["hora"],
                 font=FONTS["mono_sm"], bg=C["bg"],
                 fg=C["text3"], width=7).pack(side=tk.LEFT)

        # Card
        card_bg = C["header"] if is_on_air else C["surface"]
        card = tk.Frame(row, bg=card_bg, padx=12, pady=8,
                        cursor="hand2")
        card.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Frame(card, bg=color, width=3).pack(
            side=tk.LEFT, fill=tk.Y)

        info = tk.Frame(card, bg=card_bg, padx=8)
        info.pack(side=tk.LEFT, fill=tk.X, expand=True)
        fg = C["danger"] if is_on_air else C["text"]
        tk.Label(info, text=ev["nombre"], font=FONTS["body"],
                 bg=card_bg, fg=fg).pack(anchor="w")

        meta = tk.Frame(info, bg=card_bg)
        meta.pack(anchor="w")
        tk.Label(meta, text="●", font=("Segoe UI", 8),
                 bg=card_bg, fg=color).pack(side=tk.LEFT)
        tk.Label(meta, text=f"  {ev['tipo'] or '—'}  ·  "
                             f"{len(secs)} secc.  ·  "
                             f"{self._fmt_dur(dur)}",
                 font=FONTS["small"], bg=card_bg,
                 fg=C["text2"]).pack(side=tk.LEFT)

        if is_on_air:
            tk.Label(card, text="● AL AIRE",
                     font=FONTS["badge"], bg=card_bg,
                     fg=C["danger"]).pack(side=tk.RIGHT, padx=(0, 4))

        # Botón transmitir (hover)
        btn_tx = tk.Button(card,
            text="📡 Transmitir ahora",
            font=FONTS["small"],
            bg=C["danger"], fg="#fff",
            relief="flat", bd=0, padx=8, pady=4,
            cursor="hand2",
            activebackground=C["danger_h"],
            activeforeground="#fff",
            command=lambda eid=ev["id"]: self.on_transmitir(eid))
        if is_on_air:
            btn_tx.pack(side=tk.RIGHT)

        def _enter(e, b=btn_tx):
            b.pack(side=tk.RIGHT, padx=(8, 0))
        def _leave(e, b=btn_tx, on=is_on_air):
            if not on:
                b.pack_forget()
        card.bind("<Enter>", _enter)
        card.bind("<Leave>", _leave)
        card.bind("<Button-1>",
                  lambda e, eid=ev["id"]: self._select_ev(eid))

        # Botones editar / eliminar
        tk.Button(card, text="✕",
                  font=FONTS["small"], bg=card_bg, fg=C["text3"],
                  relief="flat", bd=0, padx=4, cursor="hand2",
                  activeforeground=C["danger"],
                  activebackground=card_bg,
                  command=lambda sid=sched["id"]: self._del_sched(sid)
                  ).pack(side=tk.RIGHT)
        tk.Button(card, text="✏",
                  font=("Segoe UI Emoji", 11), bg=card_bg, fg=C["text2"],
                  relief="flat", bd=0, padx=4, cursor="hand2",
                  activeforeground=C["accent"],
                  activebackground=card_bg,
                  command=lambda eid=ev["id"]: self._open_prog_modal(eid)
                  ).pack(side=tk.RIGHT, padx=(0, 2))

    # ── Editor inline ─────────────────────────────────────────────────────────
    def _select_ev(self, ev_id: int) -> None:
        self._selected_ev = ev_id
        ev = next((e for e in self._all_eventos if e["id"] == ev_id), None)
        if not ev:
            return
        sched = next((s for s in self._schedule
                      if s["evento_id"] == ev_id), None)
        self._lbl_sched_ev.config(text=ev["nombre"])
        self._sched_date.delete(0, tk.END)
        self._sched_time.delete(0, tk.END)
        self._sched_date.insert(0, sched["fecha"] if sched
                                else date.today().isoformat())
        self._sched_time.insert(0, sched["hora"] if sched else "08:00")
        self._sched_rec.set(
            sched["recurrencia"] if sched and sched["recurrencia"]
            else "ninguna")
        self._sched_form.pack(fill=tk.X)
        self._update_preview()

    def _update_preview(self, event=None) -> None:
        d = self._sched_date.get().strip()
        t = self._sched_time.get().strip()
        if d and t:
            try:
                dt = datetime.strptime(f"{d} {t}", "%Y-%m-%d %H:%M")
                self._lbl_sched_preview.config(
                    text=f"📅 {self._day_name(d)} {self._fmt_date(d)} — {t}")
            except ValueError:
                self._lbl_sched_preview.config(text="")
        else:
            self._lbl_sched_preview.config(text="")

    def _save_sched(self) -> None:
        if not self._selected_ev:
            return
        d = self._sched_date.get().strip()
        t = self._sched_time.get().strip()
        if not d or not t:
            messagebox.showwarning("Incompleto",
                "Completa la fecha y hora.", parent=self)
            return
        try:
            datetime.strptime(f"{d} {t}", "%Y-%m-%d %H:%M")
        except ValueError:
            messagebox.showerror("Formato inválido",
                "Fecha: YYYY-MM-DD  Hora: HH:MM", parent=self)
            return
        rec = self._sched_rec.get() or "ninguna"
        db.insert_programacion(self._selected_ev, d, t, rec)
        self._cancel_sched()
        self.load_data()

    def _cancel_sched(self) -> None:
        self._selected_ev = None
        self._sched_form.pack_forget()

    def _del_sched(self, prog_id: int) -> None:
        db.delete_programacion(prog_id)
        self.load_data()

    def _clear_all(self) -> None:
        if messagebox.askyesno("Confirmar",
                "¿Limpiar toda la programación?"):
            for s in self._schedule:
                db.delete_programacion(s["id"])
            self.load_data()

    def _open_prog_modal(self, evento_id: int = None) -> None:
        from forms.prog_form import ProgramarForm
        sched = next((s for s in self._schedule
                      if s["evento_id"] == evento_id), None) if evento_id else None
        ProgramarForm(self, self._all_eventos,
                      on_saved=self.load_data,
                      evento_id=evento_id,
                      sched=dict(sched) if sched else None)

    # ── Stats ─────────────────────────────────────────────────────────────────
    def _update_stats(self) -> None:
        today = date.today().isoformat()
        end_week = (date.today() + timedelta(days=7)).isoformat()
        total   = len(self._schedule)
        hoy     = sum(1 for s in self._schedule if s["fecha"] == today)
        semana  = sum(1 for s in self._schedule
                      if today <= s["fecha"] <= end_week)
        prog_ev = {s["evento_id"] for s in self._schedule}
        pend    = sum(1 for e in self._all_eventos
                      if e["id"] not in prog_ev)
        self._stat_vars["total"].set(str(total))
        self._stat_vars["hoy"].set(str(hoy))
        self._stat_vars["semana"].set(str(semana))
        self._stat_vars["pend"].set(str(pend))

    def update_on_air(self, evento_id: int | None) -> None:
        self._on_air_id = evento_id
        self._render_ev_list()
        self._render_timeline()

    # ── Utilidades ────────────────────────────────────────────────────────────
    @staticmethod
    def _fmt_dur(s: float) -> str:
        s = int(max(0, s))
        return f"{s // 60}:{s % 60:02d}"

    @staticmethod
    def _fmt_date(d: str) -> str:
        try:
            return datetime.strptime(d, "%Y-%m-%d").strftime("%d/%m/%Y")
        except Exception:
            return d

    @staticmethod
    def _day_name(d: str) -> str:
        names = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
        try:
            return names[datetime.strptime(d, "%Y-%m-%d").weekday()]
        except Exception:
            return ""
