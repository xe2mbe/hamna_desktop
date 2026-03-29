"""
HAMNA Desktop — Diálogo de exportación de evento a archivo de audio
Permite seleccionar, ordenar y combinar las secciones de un evento.
"""
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path

import database as db
from ui_theme import C, FONTS, HButton, HDialog


class ExportForm(HDialog):
    """Ventana de exportación: selección + orden + parámetros → archivo MP3/WAV."""

    _TARGET_DBFS = -18.0   # nivel de normalización estándar broadcast

    def __init__(self, parent, evento_id: int, evento_nombre: str, cfg: dict):
        super().__init__(parent,
                         title=f"Exportar — {evento_nombre}",
                         width=680, height=600)
        self.evento_id     = evento_id
        self.evento_nombre = evento_nombre
        self.cfg           = cfg
        self._secs: list[dict] = []   # orden editable, cada item tiene "included"
        self._exporting    = False
        self._build()
        self._load_secs()

    # ── Construcción ──────────────────────────────────────────────────────────
    def _build(self) -> None:
        self.make_header(
            f"Exportar: {self.evento_nombre}",
            "Selecciona y ordena las secciones · ajusta parámetros · elige destino"
        )

        # Footer primero (pack from bottom)
        self.make_footer([
            ("Cancelar",    "muted",   self.destroy),
            ("📤 Exportar", "primary", self._start_export),
        ])

        # Barra de progreso — siempre visible, vacía hasta que inicia exportación
        prog_frame = tk.Frame(self, bg=C["bg"], padx=14, pady=4)
        prog_frame.pack(fill=tk.X, side=tk.BOTTOM)
        self._lbl_prog = tk.Label(prog_frame, text="",
                                   font=FONTS["small"],
                                   bg=C["bg"], fg=C["text2"])
        self._lbl_prog.pack(anchor="w")
        self._progressbar = ttk.Progressbar(prog_frame, mode="determinate",
                                             maximum=1, value=0)
        self._progressbar.pack(fill=tk.X, pady=(2, 0))

        # ── Parámetros ────────────────────────────────────────────────────────
        tk.Frame(self, bg=C["border"], height=1).pack(fill=tk.X, side=tk.BOTTOM)
        params = tk.Frame(self, bg=C["surface"], padx=14, pady=10)
        params.pack(fill=tk.X, side=tk.BOTTOM)

        # Silencio entre secciones
        tk.Label(params, text="Silencio entre secciones:",
                 font=FONTS["small"], bg=C["surface"],
                 fg=C["text2"]).grid(row=0, column=0, sticky="w")
        self._silence_var = tk.IntVar(value=5)
        sb = tk.Spinbox(params, from_=0, to=30,
                        textvariable=self._silence_var,
                        width=4, font=FONTS["body"],
                        bg=C["input_bg"], fg=C["text"],
                        insertbackground=C["text"],
                        buttonbackground=C["surface2"],
                        relief="flat", bd=1,
                        highlightthickness=1,
                        highlightcolor=C["border"],
                        highlightbackground=C["border"])
        sb.grid(row=0, column=1, padx=(6, 2), sticky="w")
        tk.Label(params, text="seg",
                 font=FONTS["small"], bg=C["surface"],
                 fg=C["text3"]).grid(row=0, column=2, sticky="w", padx=(0, 20))

        # Normalizar
        self._norm_var = tk.BooleanVar(value=False)
        tk.Checkbutton(params, text="Normalizar audio",
                       variable=self._norm_var,
                       font=FONTS["body"],
                       bg=C["surface"], fg=C["text"],
                       selectcolor=C["input_bg"],
                       activebackground=C["surface"],
                       activeforeground=C["text"],
                       command=self._toggle_norm_target
                       ).grid(row=0, column=3, sticky="w", padx=(0, 8))

        # Target dBFS (solo visible si normalizar está activo)
        self._norm_target_frame = tk.Frame(params, bg=C["surface"])
        self._norm_target_frame.grid(row=0, column=4, sticky="w", padx=(0, 20))
        tk.Label(self._norm_target_frame, text="Target:",
                 font=FONTS["small"], bg=C["surface"],
                 fg=C["text2"]).pack(side=tk.LEFT)
        self._target_var = tk.DoubleVar(value=self._TARGET_DBFS)
        tk.Spinbox(self._norm_target_frame,
                   from_=-30, to=-6, increment=0.5,
                   textvariable=self._target_var,
                   width=6, font=FONTS["body"],
                   bg=C["input_bg"], fg=C["text"],
                   insertbackground=C["text"],
                   buttonbackground=C["surface2"],
                   relief="flat", bd=1,
                   highlightthickness=1,
                   highlightcolor=C["border"],
                   highlightbackground=C["border"]
                   ).pack(side=tk.LEFT, padx=(4, 2))
        tk.Label(self._norm_target_frame, text="dBFS",
                 font=FONTS["small"], bg=C["surface"],
                 fg=C["text3"]).pack(side=tk.LEFT)
        self._norm_target_frame.grid_remove()   # oculto por defecto

        # Formato
        tk.Label(params, text="Formato:",
                 font=FONTS["small"], bg=C["surface"],
                 fg=C["text2"]).grid(row=0, column=5, sticky="w", padx=(0, 4))
        self._fmt_var = tk.StringVar(value="mp3")
        ttk.Combobox(params, textvariable=self._fmt_var,
                     values=["mp3", "wav"],
                     state="readonly", width=6
                     ).grid(row=0, column=6, sticky="w")

        # ── Toolbar de la lista ───────────────────────────────────────────────
        tk.Frame(self, bg=C["border"], height=1).pack(fill=tk.X)
        ltb = tk.Frame(self, bg=C["surface2"], padx=10, pady=6)
        ltb.pack(fill=tk.X)

        HButton(ltb, "▲ Subir",  command=self._move_up,   variant="ghost"
                ).pack(side=tk.LEFT)
        HButton(ltb, "▼ Bajar",  command=self._move_down, variant="ghost"
                ).pack(side=tk.LEFT, padx=(4, 12))
        tk.Frame(ltb, bg=C["border"], width=1).pack(side=tk.LEFT, fill=tk.Y, padx=4)
        HButton(ltb, "✓ Todas",  command=self._select_all,   variant="ghost"
                ).pack(side=tk.LEFT, padx=(4, 0))
        HButton(ltb, "✗ Ninguna", command=self._deselect_all, variant="ghost"
                ).pack(side=tk.LEFT, padx=(4, 0))

        self._lbl_dur_total = tk.Label(ltb, text="",
                                        font=FONTS["small"],
                                        bg=C["surface2"], fg=C["text3"])
        self._lbl_dur_total.pack(side=tk.RIGHT, padx=(0, 4))

        tk.Frame(self, bg=C["border"], height=1).pack(fill=tk.X)

        # ── Treeview de secciones ────────────────────────────────────────────
        area = tk.Frame(self, bg=C["surface"])
        area.pack(fill=tk.BOTH, expand=True)

        tree_sb = ttk.Scrollbar(area, orient="vertical")
        tree_sb.pack(side=tk.RIGHT, fill=tk.Y)

        cols = ("orden", "incl", "nombre", "tipo", "dur", "archivo")
        self._tree = ttk.Treeview(
            area, columns=cols, show="headings",
            yscrollcommand=tree_sb.set, selectmode="browse")
        tree_sb.config(command=self._tree.yview)

        self._tree.heading("orden",   text="#",        anchor="center")
        self._tree.heading("incl",    text="✓",        anchor="center")
        self._tree.heading("nombre",  text="Nombre",   anchor="w")
        self._tree.heading("tipo",    text="Tipo",     anchor="center")
        self._tree.heading("dur",     text="Duración", anchor="e")
        self._tree.heading("archivo", text="Archivo",  anchor="w")

        self._tree.column("orden",   anchor="center", minwidth=28,  width=32,  stretch=False)
        self._tree.column("incl",    anchor="center", minwidth=28,  width=32,  stretch=False)
        self._tree.column("nombre",  anchor="w",      minwidth=100, width=180, stretch=True)
        self._tree.column("tipo",    anchor="center", minwidth=60,  width=75,  stretch=False)
        self._tree.column("dur",     anchor="e",      minwidth=60,  width=75,  stretch=False)
        self._tree.column("archivo", anchor="w",      minwidth=100, width=180, stretch=True)

        self._tree.tag_configure("included",    foreground=C["text"])
        self._tree.tag_configure("excluded",    foreground=C["text3"])
        self._tree.tag_configure("no_file",     foreground=C["warning"])

        self._tree.pack(fill=tk.BOTH, expand=True)
        self._tree.bind("<Button-1>",  self._on_tree_click)
        self._tree.bind("<space>",     lambda _: self._toggle_selected())

    # ── Carga de datos ────────────────────────────────────────────────────────
    def _load_secs(self) -> None:
        rows = db.get_secciones_by_evento(self.evento_id)
        self._secs = []
        for r in rows:
            self._secs.append({
                "id":           r["id"],
                "nombre":       r["nombre"],
                "tipo":         r["tipo"] or "",
                "duracion":     r["duracion"] or 0,
                "ruta_archivo": r["ruta_archivo"] or "",
                "included":     True,
            })
        self._refresh_tree()

    def _refresh_tree(self) -> None:
        sel_iid = (self._tree.selection() or [None])[0]
        self._tree.delete(*self._tree.get_children())
        for idx, s in enumerate(self._secs):
            ruta = s["ruta_archivo"]
            has_file = bool(ruta) and Path(ruta).is_file()
            archivo  = Path(ruta).name if ruta else "—"
            dur      = self._fmt(s["duracion"])
            incl_sym = "✓" if s["included"] else "—"

            if not has_file:
                tag = "no_file"
            elif s["included"]:
                tag = "included"
            else:
                tag = "excluded"

            self._tree.insert("", "end",
                iid=str(idx),
                values=(idx + 1, incl_sym, s["nombre"],
                        s["tipo"] or "—", dur, archivo),
                tags=(tag,))

        # Restaurar selección
        children = self._tree.get_children()
        if sel_iid and sel_iid in children:
            self._tree.selection_set(sel_iid)
        elif children:
            self._tree.selection_set(children[0])

        self._update_dur_total()

    def _update_dur_total(self) -> None:
        silence_s  = self._silence_var.get()
        included   = [s for s in self._secs if s["included"]]
        dur_audio  = sum(s["duracion"] for s in included)
        n_gaps     = max(0, len(included) - 1)
        dur_total  = dur_audio + n_gaps * silence_s
        self._lbl_dur_total.config(
            text=f"Incluidas: {len(included)} · Duración aprox.: {self._fmt(dur_total)}")

    # ── Acciones lista ────────────────────────────────────────────────────────
    def _selected_idx(self) -> int | None:
        sel = self._tree.selection()
        return int(sel[0]) if sel else None

    def _on_tree_click(self, event) -> None:
        """Clic en columna ✓ → toggle; clic en otra columna → selección normal."""
        row = self._tree.identify_row(event.y)
        col = self._tree.identify_column(event.x)
        if not row:
            return
        if col == "#2":   # columna "incl"
            self._tree.selection_set(row)
            self._toggle_selected()
            return "break"

    def _toggle_selected(self) -> None:
        idx = self._selected_idx()
        if idx is None:
            return
        self._secs[idx]["included"] = not self._secs[idx]["included"]
        self._refresh_tree()
        self._tree.selection_set(str(idx))

    def _select_all(self) -> None:
        for s in self._secs:
            s["included"] = True
        self._refresh_tree()

    def _deselect_all(self) -> None:
        for s in self._secs:
            s["included"] = False
        self._refresh_tree()

    def _move_up(self) -> None:
        idx = self._selected_idx()
        if idx is None or idx == 0:
            return
        self._secs[idx], self._secs[idx - 1] = self._secs[idx - 1], self._secs[idx]
        self._refresh_tree()
        self._tree.selection_set(str(idx - 1))

    def _move_down(self) -> None:
        idx = self._selected_idx()
        if idx is None or idx >= len(self._secs) - 1:
            return
        self._secs[idx], self._secs[idx + 1] = self._secs[idx + 1], self._secs[idx]
        self._refresh_tree()
        self._tree.selection_set(str(idx + 1))

    def _toggle_norm_target(self) -> None:
        if self._norm_var.get():
            self._norm_target_frame.grid()
        else:
            self._norm_target_frame.grid_remove()

    # ── Exportación ───────────────────────────────────────────────────────────
    def _start_export(self) -> None:
        if self._exporting:
            return

        included = [s for s in self._secs if s["included"]]
        if not included:
            messagebox.showwarning("Sin secciones",
                "Selecciona al menos una sección para exportar.", parent=self)
            return

        # Validar archivos
        missing = [s["nombre"] for s in included
                   if not s["ruta_archivo"] or not Path(s["ruta_archivo"]).is_file()]
        if missing:
            names = "\n".join(f"  • {n}" for n in missing)
            if not messagebox.askyesno(
                    "Archivos faltantes",
                    f"Las siguientes secciones no tienen archivo de audio y serán "
                    f"omitidas:\n{names}\n\n¿Continuar de todas formas?",
                    parent=self):
                return
            included = [s for s in included
                        if s["ruta_archivo"] and Path(s["ruta_archivo"]).is_file()]
            if not included:
                return

        # Pedir destino
        fmt  = self._fmt_var.get()
        ext  = "." + fmt
        dest = filedialog.asksaveasfilename(
            parent=self,
            title="Guardar exportación como…",
            defaultextension=ext,
            filetypes=[(fmt.upper(), f"*{ext}"), ("Todos los archivos", "*.*")],
            initialfile=f"{self.evento_nombre}_export{ext}",
        )
        if not dest:
            return

        silence_ms = self._silence_var.get() * 1000
        normalize  = self._norm_var.get()
        target_db  = float(self._target_var.get())

        self._exporting = True
        self._show_progress(len(included))

        threading.Thread(
            target=self._do_export,
            args=(included, dest, fmt, silence_ms, normalize, target_db),
            daemon=True
        ).start()

    def _do_export(self, secs: list, dest: str, fmt: str,
                   silence_ms: int, normalize: bool, target_db: float) -> None:
        import traceback
        try:
            from pydub import AudioSegment
        except ImportError:
            self.after(0, lambda: messagebox.showerror(
                "Dependencia faltante",
                "pydub no está instalado.\n\npip install pydub",
                parent=self))
            self.after(0, self._reset_progress)
            return

        try:
            combined = AudioSegment.empty()
            silence  = AudioSegment.silent(duration=silence_ms)
            total    = len(secs)

            for i, s in enumerate(secs):
                self.after(0, self._update_progress, i, total,
                           f"({i+1}/{total})  {s['nombre']}…")
                audio = AudioSegment.from_file(s["ruta_archivo"])
                if normalize:
                    audio = audio.apply_gain(target_db - audio.dBFS)
                combined += audio
                if i < total - 1:
                    combined += silence

            self.after(0, self._update_progress, total - 1, total,
                       "Escribiendo archivo…")
            combined.export(dest, format=fmt)
            dest_name = Path(dest).name
            self.after(0, self._on_export_done, dest_name)

        except Exception as exc:
            err = traceback.format_exc()
            self.after(0, lambda e=err: messagebox.showerror(
                "Error al exportar", e, parent=self))
            self.after(0, self._reset_progress)

    # ── Progreso ──────────────────────────────────────────────────────────────
    def _show_progress(self, total: int) -> None:
        self._progressbar.config(maximum=total, value=0)
        self._lbl_prog.config(text="Iniciando exportación…",
                               fg=C["text2"])

    def _update_progress(self, value: int, total: int, msg: str) -> None:
        self._progressbar.config(maximum=total, value=value)
        self._lbl_prog.config(text=msg, fg=C["text2"])

    def _reset_progress(self) -> None:
        self._progressbar.config(maximum=1, value=0)
        self._lbl_prog.config(text="", fg=C["text2"])
        self._exporting = False

    def _on_export_done(self, filename: str) -> None:
        self._reset_progress()
        messagebox.showinfo(
            "Exportación completa",
            f"Archivo guardado exitosamente:\n{filename}",
            parent=self)
        self.destroy()

    # ── Utilidad ──────────────────────────────────────────────────────────────
    @staticmethod
    def _fmt(s: float) -> str:
        s = int(max(0, s))
        return f"{s // 60}:{s % 60:02d}"