"""
HAMNA Desktop — Modal rápido para programar un evento
"""
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date, datetime
import database as db
from ui_theme import C, FONTS, HDialog


class ProgramarForm(HDialog):
    def __init__(self, parent, eventos: list, on_saved: callable = None):
        super().__init__(parent, title="Programar Evento",
                         width=440, height=360)
        self.eventos  = eventos
        self.on_saved = on_saved
        self._build()

    def _build(self) -> None:
        self.make_header("📅 Programar Evento",
                         "Asigna fecha y hora de inicio")

        body = tk.Frame(self, bg=C["bg"], padx=24, pady=14)
        body.pack(fill=tk.BOTH, expand=True)
        body.columnconfigure(1, weight=1)

        tk.Label(body, text="EVENTO", font=FONTS["badge"],
                 bg=C["bg"], fg=C["text2"]).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))
        self._combo_ev = ttk.Combobox(
            body,
            values=[e["nombre"] for e in self.eventos],
            state="readonly")
        self._combo_ev.grid(row=1, column=0, columnspan=2,
                             sticky="ew", pady=(0, 12))

        tk.Label(body, text="FECHA  (YYYY-MM-DD)",
                 font=FONTS["badge"], bg=C["bg"],
                 fg=C["text2"]).grid(row=2, column=0, sticky="w", pady=(0, 4))
        self._e_date = ttk.Entry(body)
        self._e_date.insert(0, date.today().isoformat())
        self._e_date.grid(row=3, column=0, sticky="ew",
                           padx=(0, 10), pady=(0, 12))

        tk.Label(body, text="HORA  (HH:MM)",
                 font=FONTS["badge"], bg=C["bg"],
                 fg=C["text2"]).grid(row=2, column=1, sticky="w", pady=(0, 4))
        self._e_time = ttk.Entry(body)
        self._e_time.insert(0, "08:00")
        self._e_time.grid(row=3, column=1, sticky="ew", pady=(0, 12))

        tk.Label(body, text="RECURRENCIA",
                 font=FONTS["badge"], bg=C["bg"],
                 fg=C["text2"]).grid(row=4, column=0, columnspan=2,
                                      sticky="w", pady=(0, 4))
        self._combo_rec = ttk.Combobox(
            body,
            values=["ninguna", "diaria", "semanal", "lun-vie"],
            state="readonly")
        self._combo_rec.set("ninguna")
        self._combo_rec.grid(row=5, column=0, columnspan=2,
                              sticky="ew", pady=(0, 8))

        self._lbl_preview = tk.Label(body, text="",
            font=FONTS["small"], bg=C["bg"], fg=C["success"])
        self._lbl_preview.grid(row=6, column=0, columnspan=2, sticky="w")

        for e in (self._e_date, self._e_time, self._combo_ev):
            e.bind("<KeyRelease>", self._update_preview)
            e.bind("<<ComboboxSelected>>", self._update_preview)

        self.make_footer([
            ("Cancelar",   "muted",   self.destroy),
            ("✓ Programar", "success", self._save),
        ])

    def _update_preview(self, event=None) -> None:
        ev_name = self._combo_ev.get()
        d = self._e_date.get().strip()
        t = self._e_time.get().strip()
        if ev_name and d and t:
            try:
                datetime.strptime(f"{d} {t}", "%Y-%m-%d %H:%M")
                self._lbl_preview.config(
                    text=f"📅 {ev_name} — {d} a las {t}")
            except ValueError:
                self._lbl_preview.config(text="")

    def _save(self) -> None:
        ev_name = self._combo_ev.get()
        d = self._e_date.get().strip()
        t = self._e_time.get().strip()
        rec = self._combo_rec.get()

        if not ev_name:
            messagebox.showwarning("Campo requerido",
                "Selecciona un evento.", parent=self)
            return
        if not d or not t:
            messagebox.showwarning("Campo requerido",
                "Completa fecha y hora.", parent=self)
            return
        try:
            datetime.strptime(f"{d} {t}", "%Y-%m-%d %H:%M")
        except ValueError:
            messagebox.showerror("Formato inválido",
                "Fecha: YYYY-MM-DD  Hora: HH:MM", parent=self)
            return

        ev = next((e for e in self.eventos if e["nombre"] == ev_name), None)
        if not ev:
            return
        db.insert_programacion(ev["id"], d, t, rec)
        if callable(self.on_saved):
            self.on_saved()
        self.destroy()
