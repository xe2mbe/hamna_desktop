"""
HAMNA Desktop — Formulario de Sección (Agregar / Editar)
Las secciones son objetos independientes de la biblioteca.
"""
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import database as db
from ui_theme import C, FONTS, HButton, HDialog
from modules.tts.tts_manager import (
    convert_text, save_audio_file, get_audio_duration
)
from modules.audio.audio_player import AudioPlayer
from forms.audio_player_window import AudioPlayerWindow


class SeccionForm(HDialog):
    """Modal para agregar o editar una sección de la biblioteca."""

    def __init__(self, parent, seccion_id: int = None,
                 cfg: dict = None, on_saved: callable = None):
        mode = "Editar" if seccion_id else "Nueva"
        super().__init__(parent, title=f"{mode} Sección", width=600, height=540)
        self.seccion_id    = seccion_id
        self.cfg           = cfg or {}
        self.on_saved      = on_saved

        self._player       = AudioPlayer()
        self._tts_done     = False
        self._tts_path     = None
        self._tts_slot     = 0   # alterna entre tts_form_0.mp3 y tts_form_1.mp3
        self._selected_file: str | None = None
        self._sec_data     = None

        if seccion_id:
            row = db.get_seccion_by_id(seccion_id)
            self._sec_data = dict(row) if row else None

        self._build()
        if self._sec_data:
            self._prefill()

    # ── Build UI ──────────────────────────────────────────────────────────────
    def _build(self) -> None:
        subtitle = "Edita los datos de la sección" if self.seccion_id \
            else "Crea una sección para la biblioteca de audio"
        self.make_header(
            "Nueva Sección" if not self.seccion_id else "Editar Sección",
            subtitle
        )

        # Footer (se empaca ANTES que el canvas para que reserve su espacio)
        tk.Frame(self, bg=C["border"], height=1).pack(fill=tk.X, side=tk.BOTTOM)
        self._footer = tk.Frame(self, bg=C["bg"])
        self._footer.pack(fill=tk.X, side=tk.BOTTOM)

        # Barra de estado TTS — siempre visible, entre contenido y footer
        tk.Frame(self, bg=C["border"], height=1).pack(fill=tk.X, side=tk.BOTTOM)
        self._status_bar = tk.Frame(self, bg=C["surface"], padx=14, pady=6)
        self._status_bar.pack(fill=tk.X, side=tk.BOTTOM)
        self._status_lbl = tk.Label(self._status_bar, text="",
                                     font=FONTS["small"],
                                     bg=C["surface"], fg=C["text2"])
        self._status_lbl.pack(anchor="w")
        self._status_prog = ttk.Progressbar(self._status_bar,
                                             mode="indeterminate")
        self._status_bar.pack_forget()   # oculta hasta que se use

        # Área scrollable
        scroll_area = tk.Frame(self, bg=C["bg"])
        scroll_area.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(scroll_area, bg=C["bg"], highlightthickness=0)
        sb = ttk.Scrollbar(scroll_area, orient="vertical", command=canvas.yview)
        self._body = tk.Frame(canvas, bg=C["bg"])
        self._body.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self._body, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        body = self._body
        body.columnconfigure(0, weight=1)
        pad = dict(padx=24)

        # Nombre
        fields = tk.Frame(body, bg=C["bg"])
        fields.pack(fill=tk.X, **pad, pady=(16, 0))
        fields.columnconfigure(0, weight=1)
        tk.Label(fields, text="NOMBRE DE LA SECCIÓN *",
                 font=FONTS["badge"], bg=C["bg"], fg=C["text2"]).grid(
            row=0, column=0, sticky="w")
        self._e_nombre = ttk.Entry(fields)
        self._e_nombre.grid(row=1, column=0, sticky="ew", pady=(4, 0))

        # Título
        tk.Label(fields, text="TÍTULO",
                 font=FONTS["badge"], bg=C["bg"], fg=C["text2"]).grid(
            row=2, column=0, sticky="w", pady=(12, 0))
        self._e_titulo = ttk.Entry(fields)
        self._e_titulo.grid(row=3, column=0, sticky="ew", pady=(4, 0))

        # Descripción
        tk.Label(fields, text="DESCRIPCIÓN",
                 font=FONTS["badge"], bg=C["bg"], fg=C["text2"]).grid(
            row=4, column=0, sticky="w", pady=(12, 0))
        desc_frame = tk.Frame(fields, bg=C["border"], padx=1, pady=1)
        desc_frame.grid(row=5, column=0, sticky="ew", pady=(4, 0))
        desc_frame.columnconfigure(0, weight=1)
        self._e_descripcion = tk.Text(desc_frame, height=3,
                                       bg=C["input_bg"], fg=C["text"],
                                       insertbackground=C["text"],
                                       relief="flat", wrap="word",
                                       font=FONTS["body"], padx=8, pady=6)
        self._e_descripcion.grid(row=0, column=0, sticky="ew")

        # Tipo
        tipos = db.get_tipos_seccion()
        self._tipos_map = {r["nombre"]: r["id"] for r in tipos}
        tk.Label(fields, text="TIPO DE SECCIÓN *",
                 font=FONTS["badge"], bg=C["bg"], fg=C["text2"]).grid(
            row=6, column=0, sticky="w", pady=(12, 0))
        self._combo_tipo = ttk.Combobox(
            fields, values=[r["nombre"] for r in tipos],
            state="readonly" if not self.seccion_id else "disabled"
        )
        self._combo_tipo.grid(row=7, column=0, sticky="ew", pady=(4, 0))
        self._combo_tipo.bind("<<ComboboxSelected>>", self._on_tipo_change)

        # Panel dinámico
        self._dyn = tk.Frame(body, bg=C["bg"])
        self._dyn.pack(fill=tk.BOTH, expand=True, **pad, pady=(8, 0))
        self._dyn.columnconfigure(0, weight=1)

    # ── Pre-llenado (edición) ─────────────────────────────────────────────────
    def _prefill(self) -> None:
        self._e_nombre.insert(0, self._sec_data["nombre"])
        if self._sec_data.get("titulo"):
            self._e_titulo.insert(0, self._sec_data["titulo"])
        if self._sec_data.get("descripcion"):
            self._e_descripcion.insert("1.0", self._sec_data["descripcion"])
        self._combo_tipo.set(self._sec_data["tipo"] or "")
        if self._sec_data["ruta_archivo"]:
            self._selected_file = self._sec_data["ruta_archivo"]
        self._on_tipo_change()

    # ── Cambio de tipo ────────────────────────────────────────────────────────
    def _on_tipo_change(self, event=None) -> None:
        tipo = self._combo_tipo.get()
        for w in self._dyn.winfo_children():
            w.destroy()
        for w in self._footer.winfo_children():
            w.destroy()
        self._tts_done = False
        self._tts_path = None

        if tipo == "TTS":
            self._build_tts()
        elif tipo == "Audio":
            self._build_audio()
        elif tipo == "Sonido":
            self._build_sonido()

    # ── Panel TTS ─────────────────────────────────────────────────────────────
    def _build_tts(self) -> None:
        d = self._dyn
        self._badge(d, "🗣️  TTS — Convierte texto a audio con el motor configurado",
                    C["tts_bg"], C["tts_fg"])

        # Opción: regenerar antes de transmitir
        self._regen_var = tk.BooleanVar(
            value=bool(self._sec_data.get("regenerar_antes", 0))
            if self._sec_data else False)
        regen_row = tk.Frame(d, bg=C["bg"])
        regen_row.pack(fill=tk.X, pady=(6, 0))
        tk.Checkbutton(regen_row, text="Regenerar audio antes de transmitir",
                       variable=self._regen_var,
                       bg=C["bg"], fg=C["text"], activebackground=C["bg"],
                       selectcolor=C["input_bg"],
                       font=FONTS["body"]).pack(side=tk.LEFT)
        tk.Label(regen_row, text="(útil si el texto tiene variables)",
                 font=FONTS["small"], bg=C["bg"], fg=C["text3"]).pack(
            side=tk.LEFT, padx=(4, 0))

        tk.Label(d, text="TEXTO A CONVERTIR", font=FONTS["badge"],
                 bg=C["bg"], fg=C["text2"]).pack(anchor="w", pady=(8, 4))

        tf = tk.Frame(d, bg=C["border"], padx=1, pady=1)
        tf.pack(fill=tk.X)
        tf.columnconfigure(0, weight=1)
        self._tts_text = tk.Text(tf, height=6, bg=C["input_bg"], fg=C["text"],
                                  insertbackground=C["text"], relief="flat",
                                  wrap="word", font=FONTS["body"],
                                  padx=10, pady=8)
        self._tts_text.grid(row=0, column=0, sticky="ew")
        if self._sec_data and self._sec_data["texto_tts"]:
            self._tts_text.insert("1.0", self._sec_data["texto_tts"])

        # ── Paleta de variables ───────────────────────────────────────────
        tk.Label(d, text="INSERTAR VARIABLE", font=FONTS["badge"],
                 bg=C["bg"], fg=C["text2"]).pack(anchor="w", pady=(10, 4))

        _var_groups = [
            ("📋 Sección", [
                ("{titulo}",      "Título de esta sección"),
                ("{descripcion}", "Descripción de esta sección"),
            ]),
            ("📅 Fecha/Hora", [
                ("{fecha}",           "Fecha (DD/MM/YYYY)"),
                ("{hora}",            "Hora (HH:MM)"),
                ("{dia}",             "Día de la semana"),
            ]),
            ("⏸ Pausas", [
                ("{pausa_cada}",      "Pausa cada"),
                ("{pausa_duracion}",  "Duración pausa"),
                ("{pausa_alerta}",    "Alerta antes de pausa"),
            ]),
            ("📻 Evento", [
                ("{evento}",             "Nombre del evento"),
                ("{num_secciones}",      "Cantidad de secciones contabilizables"),
                ("{duracion_total}",     "Duración total de la transmisión"),
                ("{dur_contabilizable}", "Duración solo de secciones contabilizables"),
            ]),
        ]

        for group_label, vars_list in _var_groups:
            row = tk.Frame(d, bg=C["surface"], padx=8, pady=4)
            row.pack(fill=tk.X, pady=(0, 3))
            tk.Label(row, text=group_label, font=FONTS["badge"],
                     bg=C["surface"], fg=C["text3"],
                     width=14, anchor="w").pack(side=tk.LEFT)
            for token, tooltip in vars_list:
                btn = tk.Button(row, text=token,
                                font=("Consolas", 8), bg=C["surface2"],
                                fg=C["tts_fg"], relief="flat", bd=0,
                                cursor="hand2", padx=6, pady=2,
                                activebackground=C["border"],
                                command=lambda t=token: self._insert_var(t))
                btn.pack(side=tk.LEFT, padx=(0, 4))

        # ── Evento de referencia (para resolver variables de evento) ─────────
        ev_row = tk.Frame(d, bg=C["bg"])
        ev_row.pack(fill=tk.X, pady=(8, 0))
        tk.Label(ev_row, text="EVENTO DE REFERENCIA", font=FONTS["badge"],
                 bg=C["bg"], fg=C["text2"]).pack(side=tk.LEFT)
        tk.Label(ev_row, text="(para {evento}, {num_secciones}, {duracion_total})",
                 font=FONTS["small"], bg=C["bg"], fg=C["text3"]).pack(
            side=tk.LEFT, padx=(6, 0))

        eventos = db.get_all_eventos()
        self._ev_ctx_map = {}
        ev_names = ["(ninguno)"]
        for e in eventos:
            num = e["numero"]
            label = f"{e['nombre']} #{num}" if num else e["nombre"]
            self._ev_ctx_map[label] = e
            ev_names.append(label)
        self._ev_ctx_var = tk.StringVar(value="(ninguno)")
        ttk.Combobox(d, textvariable=self._ev_ctx_var,
                     values=ev_names, state="readonly").pack(
            fill=tk.X, pady=(4, 0))

        # ── Velocidad de conversión ───────────────────────────────────────
        engine = self.cfg.get("tts_engine", "pyttsx3")
        if engine == "azure":
            rate_min, rate_max = 50, 200
            rate_default = int(self.cfg.get("azure_rate", 100))
            rate_label   = "VELOCIDAD (%)"
        else:
            rate_min, rate_max = 50, 300
            rate_default = int(self.cfg.get("tts_rate", 175))
            rate_label   = "VELOCIDAD (palabras/min)"

        speed_row = tk.Frame(d, bg=C["bg"])
        speed_row.pack(fill=tk.X, pady=(10, 0))
        tk.Label(speed_row, text=rate_label, font=FONTS["badge"],
                 bg=C["bg"], fg=C["text2"]).pack(side=tk.LEFT)
        self._rate_val_lbl = tk.Label(speed_row,
                                      text=str(rate_default),
                                      font=FONTS["badge"],
                                      bg=C["bg"], fg=C["tts_fg"], width=4)
        self._rate_val_lbl.pack(side=tk.RIGHT)

        self._rate_var = tk.IntVar(value=rate_default)
        tk.Scale(d, variable=self._rate_var,
                 from_=rate_min, to=rate_max,
                 orient="horizontal", resolution=1,
                 bg=C["bg"], fg=C["text"], troughcolor=C["surface2"],
                 highlightthickness=0, showvalue=False,
                 command=lambda v: self._rate_val_lbl.config(
                     text=str(int(float(v))))
                 ).pack(fill=tk.X)

        self._centered_footer([
            ("Cancelar",      "muted",   self._cancel),
            ("Vista previa",  "ghost",   self._preview_vars),
            ("Convertir",     "warning", self._convert_tts),
            ("Reproducir",    "primary", self._play_tts),
            ("💾 Exportar",   "info",    self._export_tts),
            ("Guardar",       "success", self._save_tts),
        ])

    def _build_ctx(self) -> dict:
        """Construye el contexto de variables de evento a partir del selector."""
        nombre_val = self._e_nombre.get().strip()
        titulo_val = self._e_titulo.get().strip() or nombre_val
        ctx = {
            "titulo":      titulo_val,
            "descripcion": self._e_descripcion.get("1.0", tk.END).strip(),
        }

        ev_label = self._ev_ctx_var.get()
        if ev_label == "(ninguno)" or ev_label not in self._ev_ctx_map:
            return ctx
        ev = self._ev_ctx_map[ev_label]
        secs = db.get_secciones_by_evento(ev["id"])
        dur_total = sum(s["duracion"] or 0 for s in secs)
        dur_cont  = sum(s["duracion"] or 0 for s in secs if s["contabilizable"])
        num_cont  = sum(1 for s in secs if s["contabilizable"])

        def _fmt(seg):
            m, s = divmod(int(seg), 60)
            return f"{m} minutos con {s} segundos" if s else f"{m} minutos"

        ctx.update({
            "evento":            ev["nombre"],
            "num_secciones":     str(num_cont),
            "duracion_total":    _fmt(dur_total),
            "dur_contabilizable": _fmt(dur_cont),
        })
        return ctx

    def _preview_vars(self) -> None:
        """Muestra el texto con variables resueltas tal como lo recibirá el TTS."""
        from modules.tts.tts_manager import resolve_variables

        raw = self._tts_text.get("1.0", tk.END).strip()
        if not raw:
            messagebox.showinfo("Vista previa", "El texto está vacío.", parent=self)
            return

        resolved = resolve_variables(raw, self.cfg, self._build_ctx())

        win = tk.Toplevel(self)
        win.title("Vista previa — texto resuelto")
        win.geometry("520x260")
        win.configure(bg=C["bg"])
        win.resizable(False, False)
        win.grab_set()

        tk.Label(win, text="Texto que recibirá el motor TTS:",
                 font=FONTS["badge"], bg=C["bg"], fg=C["text2"]).pack(
            anchor="w", padx=16, pady=(14, 4))

        box = tk.Text(win, height=7, wrap="word", font=FONTS["body"],
                      bg=C["input_bg"], fg=C["text"], relief="flat",
                      padx=10, pady=8, state="normal")
        box.pack(fill=tk.X, padx=16)
        box.insert("1.0", resolved)
        box.config(state="disabled")

        HButton(win, "Cerrar", command=win.destroy,
                variant="muted").pack(pady=10)

    def _insert_var(self, token: str) -> None:
        """Inserta un token de variable en la posición actual del cursor."""
        self._tts_text.insert(tk.INSERT, token)
        self._tts_text.focus_set()

    def _set_converting(self, converting: bool) -> None:
        """Muestra/oculta la barra de estado y bloquea/desbloquea botones."""
        if converting:
            self._status_bar.pack(fill=tk.X, side=tk.BOTTOM,
                                   before=self._footer)
            self._status_prog.pack(fill=tk.X, pady=(4, 0))
            self._status_prog.start(12)
        else:
            self._status_prog.stop()
            self._status_prog.pack_forget()
        # Bloquear / desbloquear todos los botones del footer
        for w in self._footer.winfo_children():
            for child in w.winfo_children():
                try:
                    child.config(state="disabled" if converting else "normal")
                except Exception:
                    pass

    def _convert_tts(self) -> None:
        text = self._tts_text.get("1.0", tk.END).strip()
        if not text:
            self._status_bar.pack(fill=tk.X, side=tk.BOTTOM,
                                   before=self._footer)
            self._status_lbl.config(text="⚠  Ingresa el texto a convertir",
                                     fg=C["warning"])
            return
        self._status_lbl.config(text="⏳  Convirtiendo texto a audio…",
                                 fg=C["warning"])
        self._set_converting(True)

        def done(ok, result):
            self._set_converting(False)
            if ok:
                self._tts_done = True
                self._tts_path = result
                self._status_lbl.config(
                    text=f"✅  Audio generado: {Path(result).name}",
                    fg=C["success"])
            else:
                self._status_lbl.config(text=f"❌  {result}", fg=C["danger"])

        # Archivo temporal exclusivo del form — no colisiona con el reproductor
        _out = Path(__file__).parent.parent / f"tts_form_{self._tts_slot}.mp3"
        self._tts_slot = 1 - self._tts_slot

        # Aplicar velocidad del slider sin modificar la configuración global
        rate_val = int(self._rate_var.get())
        cfg_conv = dict(self.cfg)
        if cfg_conv.get("tts_engine", "pyttsx3") == "azure":
            cfg_conv["azure_rate"] = rate_val
        else:
            cfg_conv["tts_rate"] = rate_val

        convert_text(self._tts_text.get("1.0", tk.END).strip(),
                     cfg_conv, _out,
                     on_done=lambda ok, r: self.after(0, done, ok, r),
                     ctx=self._build_ctx())

    def _play_tts(self) -> None:
        if not self._tts_path or not Path(self._tts_path).is_file():
            messagebox.showinfo("Sin audio", "Primero convierte el texto.",
                                parent=self)
            return
        AudioPlayerWindow(self, self._tts_path)

    def _export_tts(self) -> None:
        """Exporta el audio TTS generado a una ubicación elegida por el usuario."""
        import shutil
        if not self._tts_path or not Path(self._tts_path).is_file():
            messagebox.showinfo("Sin audio", "Primero convierte el texto.",
                                parent=self)
            return
        nombre = self._e_nombre.get().strip()
        ext    = Path(self._tts_path).suffix or ".mp3"
        sugerido = f"{nombre}{ext}" if nombre else f"tts_export{ext}"
        dest = filedialog.asksaveasfilename(
            parent=self,
            title="Exportar audio TTS",
            initialfile=sugerido,
            defaultextension=ext,
            filetypes=[("Audio MP3", "*.mp3"), ("Audio WAV", "*.wav"),
                       ("Todos los archivos", "*.*")],
        )
        if not dest:
            return
        try:
            shutil.copy2(self._tts_path, dest)
            messagebox.showinfo("Exportado",
                                f"Archivo guardado en:\n{dest}", parent=self)
        except Exception as e:
            messagebox.showerror("Error al exportar", str(e), parent=self)

    def _save_tts(self) -> None:
        nombre = self._e_nombre.get().strip()
        if not nombre:
            messagebox.showwarning("Campo requerido",
                                   "Ingresa el nombre.", parent=self)
            return
        if not self._tts_done or not self._tts_path:
            messagebox.showwarning("Sin audio", "Convierte el texto primero.",
                                   parent=self)
            return
        texto     = self._tts_text.get("1.0", tk.END).strip()
        tipo_id   = self._tipos_map["TTS"]
        dur       = get_audio_duration(self._tts_path)
        regen     = self._regen_var.get()
        titulo    = self._e_titulo.get().strip() or None
        descrip   = self._e_descripcion.get("1.0", tk.END).strip() or None
        try:
            if self.seccion_id:
                db.update_seccion(self.seccion_id, nombre,
                                   texto_tts=texto, duracion=dur,
                                   regenerar_antes=regen,
                                   titulo=titulo, descripcion=descrip)
                dest = save_audio_file(self._tts_path,
                                       self.seccion_id, nombre)
                db.update_seccion_ruta(self.seccion_id, dest)
            else:
                sec_id = db.insert_seccion(nombre, tipo_id,
                                            texto_tts=texto, duracion=dur,
                                            regenerar_antes=regen,
                                            titulo=titulo, descripcion=descrip)
                dest = save_audio_file(self._tts_path, sec_id, nombre)
                db.update_seccion_ruta(sec_id, dest)
            self._finish(nombre)
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)

    # ── Panel Audio ───────────────────────────────────────────────────────────
    def _build_audio(self) -> None:
        self._build_file_panel("audio")

    # ── Panel Sonido ──────────────────────────────────────────────────────────
    def _build_sonido(self) -> None:
        self._build_file_panel("sonido")

    def _build_file_panel(self, mode: str) -> None:
        d = self._dyn
        is_sonido = (mode == "sonido")
        if is_sonido:
            self._badge(d, "🔔  Sonido — Máximo 3 segundos de duración",
                        C["sonido_bg"], C["sonido_fg"])
        else:
            self._badge(d, "🎧  Audio — Selecciona un archivo .mp3, .wav o .m4a",
                        C["audio_bg"], C["audio_fg"])

        tk.Label(d, text="ARCHIVO DE AUDIO", font=FONTS["badge"],
                 bg=C["bg"], fg=C["text2"]).pack(anchor="w", pady=(8, 4))

        ff = tk.Frame(d, bg=C["bg"])
        ff.pack(fill=tk.X)
        ff.columnconfigure(0, weight=1)
        self._lbl_file = tk.Label(ff,
            text=Path(self._selected_file).name
                 if self._selected_file else "Ningún archivo seleccionado",
            font=FONTS["small"], bg=C["surface"], fg=C["text2"],
            anchor="w", padx=10, pady=8)
        self._lbl_file.grid(row=0, column=0, sticky="ew")
        HButton(ff, "Examinar…", command=self._browse_file,
                variant="ghost").grid(row=0, column=1, padx=(8, 0))

        self._lbl_dur = tk.Label(d, text="", font=FONTS["small"],
                                  bg=C["bg"], fg=C["text2"])
        self._lbl_dur.pack(anchor="w", pady=(6, 0))

        if self._selected_file:
            self._update_duration_label(self._selected_file, is_sonido)

        self._centered_footer([
            ("Cancelar",   "muted",   self.destroy),
            ("Reproducir", "primary", self._play_file),
            ("Guardar",    "success", lambda: self._save_audio(is_sonido=is_sonido)),
        ])

    def _browse_file(self) -> None:
        path = filedialog.askopenfilename(
            parent=self,
            title="Seleccionar Archivo de Audio",
            filetypes=[("Audio", "*.mp3 *.wav *.m4a *.MP3 *.WAV *.M4A"),
                       ("Todos", "*.*")]
        )
        if path:
            self._selected_file = path
            self._lbl_file.config(text=Path(path).name, fg=C["text"])
            is_sonido = self._combo_tipo.get() == "Sonido"
            self._update_duration_label(path, is_sonido)

    def _update_duration_label(self, path: str, is_sonido: bool) -> None:
        dur = get_audio_duration(path)
        if is_sonido:
            ok = dur <= 3.0
            color = C["success"] if ok else C["danger"]
            self._lbl_dur.config(
                text=f"⏱ Duración: {dur:.2f}s  {'✅ OK' if ok else '❌ Excede 3 segundos'}",
                fg=color)
        else:
            self._lbl_dur.config(
                text=f"⏱ Duración: {dur:.2f}s", fg=C["text2"])

    def _play_file(self) -> None:
        if not self._selected_file or not Path(self._selected_file).is_file():
            messagebox.showinfo("Sin archivo",
                                "Selecciona un archivo primero.", parent=self)
            return
        AudioPlayerWindow(self, self._selected_file)

    def _save_audio(self, is_sonido: bool = False) -> None:
        nombre = self._e_nombre.get().strip()
        if not nombre:
            messagebox.showwarning("Campo requerido",
                                   "Ingresa el nombre.", parent=self)
            return
        if not self._selected_file or not Path(self._selected_file).is_file():
            messagebox.showwarning("Sin archivo",
                                   "Selecciona un archivo de audio.", parent=self)
            return
        if is_sonido:
            dur = get_audio_duration(self._selected_file)
            if dur > 3.0:
                messagebox.showerror(
                    "Duración excedida",
                    f"El sonido dura {dur:.2f}s.\nEl máximo permitido es 3 segundos.",
                    parent=self)
                return

        tipo_key = self._combo_tipo.get()
        tipo_id  = self._tipos_map[tipo_key]
        titulo   = self._e_titulo.get().strip() or None
        descrip  = self._e_descripcion.get("1.0", tk.END).strip() or None
        try:
            src_stem = Path(self._selected_file).stem
            if self.seccion_id:
                dur = get_audio_duration(self._selected_file)
                db.update_seccion(self.seccion_id, nombre,
                                   ruta_archivo=self._selected_file,
                                   duracion=dur,
                                   titulo=titulo, descripcion=descrip)
                dest = save_audio_file(self._selected_file,
                                       self.seccion_id, src_stem)
                db.update_seccion_ruta(self.seccion_id, dest)
            else:
                dur = get_audio_duration(self._selected_file)
                sec_id = db.insert_seccion(nombre, tipo_id, duracion=dur,
                                            titulo=titulo, descripcion=descrip)
                dest = save_audio_file(self._selected_file, sec_id, src_stem)
                db.update_seccion_ruta(sec_id, dest)
            self._finish(nombre)
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)

    # ── Footer centrado ───────────────────────────────────────────────────────
    def _centered_footer(self, buttons: list) -> None:
        """Reconstruye el footer con botones centrados."""
        for w in self._footer.winfo_children():
            w.destroy()
        self._footer.config(pady=14)
        self._footer.columnconfigure(0, weight=1)
        inner = tk.Frame(self._footer, bg=C["bg"])
        inner.grid(row=0, column=0)
        for text, variant, cmd in buttons:
            HButton(inner, text=text, command=cmd,
                    variant=variant).pack(side=tk.LEFT, padx=6)

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _badge(self, parent: tk.Frame, text: str, bg: str, fg: str) -> None:
        f = tk.Frame(parent, bg=bg, padx=12, pady=8)
        f.pack(fill=tk.X, pady=(0, 4))
        tk.Label(f, text=text, font=FONTS["h3"], bg=bg, fg=fg).pack(anchor="w")

    def _cancel(self) -> None:
        self._cleanup_temp()
        self.destroy()

    def _cleanup_temp(self) -> None:
        for slot in (0, 1):
            p = Path(__file__).parent.parent / f"tts_form_{slot}.mp3"
            try:
                p.unlink(missing_ok=True)
            except Exception:
                pass

    def _finish(self, nombre: str) -> None:
        self._cleanup_temp()
        messagebox.showinfo("Guardado",
            f"Sección «{nombre}» guardada correctamente.", parent=self)
        if callable(self.on_saved):
            self.on_saved()
        self.destroy()
