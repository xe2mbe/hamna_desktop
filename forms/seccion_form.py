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
    convert_text, save_audio_file, get_audio_duration, TEMP_MP3
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
        self._selected_file: str | None = None
        self._sec_data     = None

        if seccion_id:
            self._sec_data = db.get_seccion_by_id(seccion_id)

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

        # Tipo
        tipos = db.get_tipos_seccion()
        self._tipos_map = {r["nombre"]: r["id"] for r in tipos}
        tk.Label(fields, text="TIPO DE SECCIÓN *",
                 font=FONTS["badge"], bg=C["bg"], fg=C["text2"]).grid(
            row=2, column=0, sticky="w", pady=(12, 0))
        self._combo_tipo = ttk.Combobox(
            fields, values=[r["nombre"] for r in tipos],
            state="readonly" if not self.seccion_id else "disabled"
        )
        self._combo_tipo.grid(row=3, column=0, sticky="ew", pady=(4, 0))
        self._combo_tipo.bind("<<ComboboxSelected>>", self._on_tipo_change)

        # Panel dinámico
        self._dyn = tk.Frame(body, bg=C["bg"])
        self._dyn.pack(fill=tk.BOTH, expand=True, **pad, pady=(8, 0))
        self._dyn.columnconfigure(0, weight=1)

    # ── Pre-llenado (edición) ─────────────────────────────────────────────────
    def _prefill(self) -> None:
        self._e_nombre.insert(0, self._sec_data["nombre"])
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

        self._tts_status = tk.Label(d, text="", font=FONTS["small"],
                                     bg=C["bg"], fg=C["text2"])
        self._tts_status.pack(anchor="w", pady=(4, 0))

        self._tts_progress = ttk.Progressbar(d, mode="indeterminate")

        self._centered_footer([
            ("Cancelar",   "muted",   self.destroy),
            ("Convertir",  "warning", self._convert_tts),
            ("Reproducir", "primary", self._play_tts),
            ("Guardar",    "success", self._save_tts),
        ])

    def _convert_tts(self) -> None:
        text = self._tts_text.get("1.0", tk.END).strip()
        if not text:
            self._tts_status.config(text="⚠ Ingresa el texto a convertir",
                                     fg=C["warning"])
            return
        self._tts_status.config(text="⏳ Convirtiendo...", fg=C["warning"])
        self._tts_progress.pack(fill=tk.X, pady=(4, 0))
        self._tts_progress.start(10)

        def done(ok, result):
            self._tts_progress.stop()
            self._tts_progress.pack_forget()
            if ok:
                self._tts_done = True
                self._tts_path = result
                self._tts_status.config(
                    text=f"✅ Audio generado: {Path(result).name}",
                    fg=C["success"])
            else:
                self._tts_status.config(text=f"❌ {result}", fg=C["danger"])

        convert_text(self._tts_text.get("1.0", tk.END).strip(),
                     self.cfg,
                     on_done=lambda ok, r: self.after(0, done, ok, r))

    def _play_tts(self) -> None:
        if not self._tts_path or not Path(self._tts_path).is_file():
            messagebox.showinfo("Sin audio", "Primero convierte el texto.",
                                parent=self)
            return
        AudioPlayerWindow(self, self._tts_path)

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
        texto = self._tts_text.get("1.0", tk.END).strip()
        tipo_id = self._tipos_map["TTS"]
        dur = get_audio_duration(self._tts_path)
        try:
            if self.seccion_id:
                db.update_seccion(self.seccion_id, nombre,
                                   texto_tts=texto, duracion=dur)
                dest = save_audio_file(self._tts_path,
                                       self.seccion_id, nombre)
                db.update_seccion_ruta(self.seccion_id, dest)
            else:
                sec_id = db.insert_seccion(nombre, tipo_id,
                                            texto_tts=texto, duracion=dur)
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
            self._badge(d, "🎧  Audio — Selecciona un archivo .mp3 o .wav",
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
            filetypes=[("Audio", "*.mp3 *.wav *.MP3 *.WAV"),
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
        try:
            if self.seccion_id:
                dur = get_audio_duration(self._selected_file)
                db.update_seccion(self.seccion_id, nombre,
                                   ruta_archivo=self._selected_file,
                                   duracion=dur)
                dest = save_audio_file(self._selected_file,
                                       self.seccion_id, nombre)
                db.update_seccion_ruta(self.seccion_id, dest)
            else:
                dur = get_audio_duration(self._selected_file)
                sec_id = db.insert_seccion(nombre, tipo_id, duracion=dur)
                dest = save_audio_file(self._selected_file, sec_id, nombre)
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

    def _finish(self, nombre: str) -> None:
        messagebox.showinfo("Guardado",
            f"Sección «{nombre}» guardada correctamente.", parent=self)
        if callable(self.on_saved):
            self.on_saved()
        self.destroy()
