"""
HAMNA Desktop — Modal para programar un evento
"""
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date, datetime, timezone, timedelta
import database as db
from ui_theme import C, FONTS, HDialog

try:
    from tkcalendar import DateEntry
    _HAS_CAL = True
except ImportError:
    _HAS_CAL = False

try:
    from zoneinfo import ZoneInfo
    _HAS_ZONEINFO = True
except Exception:
    _HAS_ZONEINFO = False

# Zonas y sus offsets de respaldo (sin DST) cuando zoneinfo no está disponible
_ZONES = [
    ("UTC",       "UTC",                timedelta(0),       C["accent"]),
    ("CDMX",      "America/Mexico_City", timedelta(hours=-6), C["text"]),
    ("PACÍFICO",  "America/Tijuana",     timedelta(hours=-7), C["tts_fg"]),
    ("SURESTE",   "America/Cancun",      timedelta(hours=-5), C["audio_fg"]),
]


class ProgramarForm(HDialog):
    def __init__(self, parent, eventos: list,
                 on_saved: callable = None,
                 evento_id: int = None,
                 sched: dict = None):
        super().__init__(parent, title="Programar Evento",
                         width=560, height=630)
        self.eventos    = eventos
        self.on_saved   = on_saved
        self._preset_id = evento_id
        self._sched     = sched
        self._build()

    def _build(self) -> None:
        self.make_header("📅 Programar Evento",
                         "Asigna fecha, hora y recurrencia — hora local del equipo")

        body = tk.Frame(self, bg=C["bg"], padx=28, pady=14)
        body.pack(fill=tk.BOTH, expand=True)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=2)

        # ── Evento ─────────────────────────────────────────────────────────
        tk.Label(body, text="EVENTO", font=FONTS["badge"],
                 bg=C["bg"], fg=C["text2"]).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))
        self._combo_ev = ttk.Combobox(
            body, values=[e["nombre"] for e in self.eventos],
            state="readonly", font=FONTS["body"])
        self._combo_ev.grid(row=1, column=0, columnspan=2,
                             sticky="ew", pady=(0, 12))
        if self._preset_id:
            ev = next((e for e in self.eventos
                       if e["id"] == self._preset_id), None)
            if ev:
                self._combo_ev.set(ev["nombre"])
                self._combo_ev.config(state="disabled")

        # ── Fecha ──────────────────────────────────────────────────────────
        tk.Label(body, text="FECHA", font=FONTS["badge"],
                 bg=C["bg"], fg=C["text2"]).grid(
            row=2, column=0, sticky="w", pady=(0, 4))

        if _HAS_CAL:
            self._date_entry = DateEntry(
                body, date_pattern="yyyy-mm-dd",
                firstweekday="monday", locale="es_ES",
                showweeknumbers=False, font=FONTS["body"], width=14,
                background="#0d6efd", foreground="white", borderwidth=0,
                headersbackground=C["surface"], headersforeground=C["text2"],
                selectbackground="#0d6efd", selectforeground="white",
                normalbackground=C["surface"],  normalforeground=C["text"],
                weekendbackground=C["surface"],  weekendforeground=C["tts_fg"],
                othermonthbackground=C["surface2"], othermonthforeground=C["text3"],
            )
            self._date_entry.set_date(date.today())
            self._date_entry.grid(row=3, column=0, sticky="w",
                                   padx=(0, 16), pady=(0, 12), ipady=4)
        else:
            self._date_entry = ttk.Entry(body, font=FONTS["body"], width=14)
            self._date_entry.insert(0, date.today().isoformat())
            self._date_entry.grid(row=3, column=0, sticky="ew",
                                   padx=(0, 16), pady=(0, 12))

        # ── Hora ───────────────────────────────────────────────────────────
        tk.Label(body, text="HORA  (local)", font=FONTS["badge"],
                 bg=C["bg"], fg=C["text2"]).grid(
            row=2, column=1, sticky="w", pady=(0, 4))

        time_f = tk.Frame(body, bg=C["bg"])
        time_f.grid(row=3, column=1, sticky="w", pady=(0, 12))

        # Estilo uniforme para los tres spinboxes de hora
        _ts = ttk.Style()
        _ts.configure("Time.TSpinbox", padding=(4, 6, 4, 6),
                       arrowsize=14)

        self._spin_h = ttk.Spinbox(time_f, from_=1, to=12,
                                    width=3, font=FONTS["body"],
                                    wrap=True, style="Time.TSpinbox",
                                    command=self._update_preview)
        self._spin_h.set("08")
        self._spin_h.pack(side=tk.LEFT)

        tk.Label(time_f, text=":", font=("Consolas", 14, "bold"),
                 bg=C["bg"], fg=C["text"]).pack(side=tk.LEFT, padx=2)

        self._spin_m = ttk.Spinbox(time_f, from_=0, to=59,
                                    width=3, font=FONTS["body"],
                                    wrap=True, style="Time.TSpinbox",
                                    command=self._update_preview)
        self._spin_m.set("00")
        self._spin_m.pack(side=tk.LEFT)

        self._ampm_var = tk.StringVar(value="AM")
        self._spin_ampm = ttk.Spinbox(time_f, values=("AM", "PM"),
                                       textvariable=self._ampm_var,
                                       width=4, font=FONTS["body"],
                                       wrap=True, state="readonly",
                                       style="Time.TSpinbox",
                                       command=self._update_preview)
        self._spin_ampm.pack(side=tk.LEFT, padx=(8, 0))

        # ── Recurrencia ────────────────────────────────────────────────────
        tk.Label(body, text="RECURRENCIA", font=FONTS["badge"],
                 bg=C["bg"], fg=C["text2"]).grid(
            row=4, column=0, columnspan=2, sticky="w", pady=(0, 4))
        self._combo_rec = ttk.Combobox(
            body, values=["ninguna", "diaria", "semanal", "lun-vie"],
            state="readonly", font=FONTS["body"])
        self._combo_rec.set("ninguna")
        self._combo_rec.grid(row=5, column=0, columnspan=2,
                              sticky="ew", pady=(0, 8))

        # ── Preview ────────────────────────────────────────────────────────
        self._lbl_preview = tk.Label(body, text="",
            font=FONTS["small"], bg=C["bg"], fg=C["success"])
        self._lbl_preview.grid(row=6, column=0, columnspan=2,
                                sticky="w", pady=(0, 8))

        # ── Separador ──────────────────────────────────────────────────────
        tk.Frame(body, bg=C["border"], height=1).grid(
            row=7, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        # ── Relojes de referencia ──────────────────────────────────────────
        clocks_outer = tk.Frame(body, bg=C["surface2"], padx=12, pady=10)
        clocks_outer.grid(row=8, column=0, columnspan=2,
                           sticky="ew", pady=(0, 4))
        clocks_outer.columnconfigure(tuple(range(len(_ZONES))), weight=1)

        tk.Label(clocks_outer, text="RELOJES DE REFERENCIA",
                 font=FONTS["badge"], bg=C["surface2"],
                 fg=C["text3"]).grid(row=0, column=0, columnspan=len(_ZONES),
                                     sticky="w", pady=(0, 6))

        self._clock_labels: dict[str, tk.Label] = {}
        for col, (name, tz_id, _off, color) in enumerate(_ZONES):
            if col > 0:
                tk.Frame(clocks_outer, bg=C["border"], width=1).grid(
                    row=1, column=col, rowspan=2, sticky="ns", padx=(0, 8))
            tk.Label(clocks_outer, text=name, font=FONTS["badge"],
                     bg=C["surface2"], fg=C["text3"]).grid(
                row=1, column=col, sticky="w")
            lbl = tk.Label(clocks_outer, text="--:--:--",
                           font=("Consolas", 13, "bold"),
                           bg=C["surface2"], fg=color)
            lbl.grid(row=2, column=col, sticky="w")
            self._clock_labels[tz_id] = lbl

        self._tick_clocks()

        # ── Bindings ───────────────────────────────────────────────────────
        for w in (self._spin_h, self._spin_m, self._combo_ev, self._combo_rec):
            w.bind("<KeyRelease>",         self._update_preview)
            w.bind("<<ComboboxSelected>>", self._update_preview)
            w.bind("<<Increment>>",        self._update_preview)
            w.bind("<<Decrement>>",        self._update_preview)
        self._spin_ampm.bind("<<Increment>>", self._update_preview)
        self._spin_ampm.bind("<<Decrement>>", self._update_preview)
        if _HAS_CAL:
            self._date_entry.bind("<<DateEntrySelected>>", self._update_preview)
        else:
            self._date_entry.bind("<KeyRelease>", self._update_preview)

        # Pre-rellenar si se está editando una programación existente
        if self._sched:
            self._prefill_sched(self._sched)

        self._update_preview()

        self.make_footer([
            ("Cancelar",    "muted",   self.destroy),
            ("✓ Guardar",   "success", self._save),
        ])

    # ── Pre-relleno al editar ─────────────────────────────────────────────────
    def _prefill_sched(self, sched: dict) -> None:
        # Fecha
        d = sched.get("fecha", "")
        if d:
            if _HAS_CAL:
                try:
                    self._date_entry.set_date(
                        datetime.strptime(d, "%Y-%m-%d").date())
                except Exception:
                    pass
            else:
                self._date_entry.delete(0, tk.END)
                self._date_entry.insert(0, d)

        # Hora — convertir 24h → 12h + AM/PM
        hora = sched.get("hora", "")
        if hora:
            try:
                h24, m = map(int, hora.split(":"))
                ampm = "AM" if h24 < 12 else "PM"
                h12  = h24 % 12
                if h12 == 0:
                    h12 = 12
                self._spin_h.set(f"{h12:02d}")
                self._spin_m.set(f"{m:02d}")
                self._ampm_var.set(ampm)
            except Exception:
                pass

        # Recurrencia
        rec = sched.get("recurrencia") or "ninguna"
        self._combo_rec.set(rec)

    # ── Relojes en vivo ───────────────────────────────────────────────────────
    def _tick_clocks(self) -> None:
        if not self.winfo_exists():
            return
        now_utc = datetime.now(timezone.utc)
        for _name, tz_id, offset, _color in _ZONES:
            lbl = self._clock_labels.get(tz_id)
            if not lbl:
                continue
            try:
                if _HAS_ZONEINFO:
                    from zoneinfo import ZoneInfo
                    t = now_utc.astimezone(ZoneInfo(tz_id))
                else:
                    t = now_utc + offset
                lbl.config(text=t.strftime("%H:%M:%S"))
            except Exception:
                t = now_utc + offset
                lbl.config(text=t.strftime("%H:%M:%S"))
        self.after(1000, self._tick_clocks)

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _get_date_str(self) -> str:
        if _HAS_CAL:
            return self._date_entry.get_date().isoformat()
        return self._date_entry.get().strip()

    def _get_time_str(self) -> str:
        try:
            h = int(self._spin_h.get())
        except ValueError:
            h = 8
        m = self._spin_m.get().zfill(2)
        ampm = self._ampm_var.get()
        if ampm == "PM" and h != 12:
            h += 12
        elif ampm == "AM" and h == 12:
            h = 0
        return f"{h:02d}:{m}"

    def _update_preview(self, event=None) -> None:
        ev_name = self._combo_ev.get()
        d = self._get_date_str()
        t = self._get_time_str()
        rec = self._combo_rec.get()
        rec_lbl = {"diaria": " · repite diario",
                   "semanal": " · repite semanal",
                   "lun-vie": " · lun–vie"}.get(rec, "")
        if ev_name and d and t:
            try:
                datetime.strptime(f"{d} {t}", "%Y-%m-%d %H:%M")
                self._lbl_preview.config(
                    text=f"📅  {ev_name} — {d}  a las  {t}{rec_lbl}")
            except ValueError:
                self._lbl_preview.config(text="")
        else:
            self._lbl_preview.config(text="")

    def _save(self) -> None:
        ev_name = self._combo_ev.get()
        d   = self._get_date_str()
        t   = self._get_time_str()
        rec = self._combo_rec.get()

        if not ev_name:
            messagebox.showwarning("Campo requerido",
                "Selecciona un evento.", parent=self)
            return
        try:
            datetime.strptime(f"{d} {t}", "%Y-%m-%d %H:%M")
        except ValueError:
            messagebox.showerror("Formato inválido",
                "Fecha o hora incorrecta.", parent=self)
            return

        ev = next((e for e in self.eventos if e["nombre"] == ev_name), None)
        if not ev:
            return
        db.insert_programacion(ev["id"], d, t, rec)
        if callable(self.on_saved):
            self.on_saved()
        self.destroy()
