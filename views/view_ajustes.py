"""
HAMNA Desktop — Vista de Ajustes
TTS (pyttsx3 + Azure), PTT (Serial / AMI / API), Audio, DB, Logs.
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import shutil
from pathlib import Path

# Carpeta local donde se almacenan los audios de pausa
_SONIDOS_DIR = Path(__file__).parent.parent / "media" / "sonidos"
import settings as cfg_mod
from ui_theme import C, FONTS, HButton, HSlider, apply_theme
from modules.ptt.ptt_manager import PTTManager


class ViewAjustes(tk.Frame):
    def __init__(self, parent, cfg: dict, ptt_manager: PTTManager,
                 on_cfg_saved: callable = None):
        super().__init__(parent, bg=C["bg"])
        self.cfg         = cfg
        self.ptt         = ptt_manager
        self.on_cfg_saved = on_cfg_saved
        self._build()
        self._show_panel("tts")

    # ── Build layout ──────────────────────────────────────────────────────────
    def _build(self) -> None:
        # Sidebar
        sidebar = tk.Frame(self, bg=C["bg"], width=190)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)
        tk.Frame(self, bg=C["border"], width=1).pack(
            side=tk.LEFT, fill=tk.Y)

        # Content
        self._content = tk.Frame(self, bg=C["bg"])
        self._content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Nav items
        self._nav_btns: dict[str, tk.Label] = {}
        sections = [
            ("GENERAL",       [("general", "🔧  General")]),
            ("MOTOR DE VOZ",  [("tts",     "🗣️  Motor TTS")]),
            ("TRANSMISIÓN",   [("ptt",     "📡  Control PTT"),
                               ("audio",   "🔊  Dispositivos Audio"),
                               ("pauses",  "⏸  Tiempos y Pausas")]),
            ("DATOS",         [("db",      "🗄️  Base de Datos"),
                               ("logs",    "📋  Logs del Sistema")]),
        ]
        for section_lbl, items in sections:
            tk.Label(sidebar, text=section_lbl, font=FONTS["badge"],
                     bg=C["bg"], fg=C["text3"],
                     padx=16, pady=(10)).pack(fill=tk.X, anchor="w")
            for key, lbl in items:
                btn = tk.Label(sidebar, text=lbl, font=FONTS["body"],
                               bg=C["bg"], fg=C["text2"],
                               padx=16, pady=8, anchor="w",
                               cursor="hand2")
                btn.pack(fill=tk.X)
                btn.bind("<Button-1>", lambda e, k=key: self._show_panel(k))
                btn.bind("<Enter>",
                         lambda e, b=btn: b.config(bg=C["surface"]))
                btn.bind("<Leave>",
                         lambda e, b=btn, k=key:
                             b.config(bg=C["accent"] if
                                      self._active_panel == k
                                      else C["bg"]))
                self._nav_btns[key] = btn

        # Panels
        self._panels: dict[str, tk.Frame] = {}
        self._active_panel = ""
        for key in ["general", "tts", "ptt", "audio", "pauses", "db", "logs"]:
            f = tk.Frame(self._content, bg=C["bg"])
            self._panels[key] = f
        self._build_tts_panel()
        self._build_ptt_panel()
        self._build_audio_panel()
        self._build_pauses_panel()
        self._build_db_panel()
        self._build_logs_panel()
        self._build_general_panel()

    def _show_panel(self, key: str) -> None:
        for k, f in self._panels.items():
            f.pack_forget()
        self._panels[key].pack(fill=tk.BOTH, expand=True)
        for k, btn in self._nav_btns.items():
            btn.config(bg=C["accent"] if k == key else C["bg"],
                       fg=C["text"] if k == key else C["text2"])
        self._active_panel = key

    # ── Helpers de layout ─────────────────────────────────────────────────────
    def _scrollable(self, parent: tk.Frame) -> tk.Frame:
        canvas = tk.Canvas(parent, bg=C["bg"], highlightthickness=0)
        sb = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=C["bg"])
        inner.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        return inner

    def _card(self, parent: tk.Frame, title: str,
              icon: str = "") -> tk.Frame:
        outer = tk.Frame(parent, bg=C["surface"],
                         padx=0, pady=0)
        outer.pack(fill=tk.X, padx=18, pady=(0, 12))
        hdr = tk.Frame(outer, bg=C["surface2"], padx=14, pady=10)
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text=f"{icon}  {title}" if icon else title,
                 font=FONTS["h3"], bg=C["surface2"],
                 fg=C["text"]).pack(side=tk.LEFT)
        tk.Frame(outer, bg=C["border"], height=1).pack(fill=tk.X)
        body = tk.Frame(outer, bg=C["surface"], padx=16, pady=14)
        body.pack(fill=tk.X)
        return body

    def _lbl(self, parent, text: str) -> None:
        tk.Label(parent, text=text, font=FONTS["badge"],
                 bg=C["surface"], fg=C["text3"]).pack(
            anchor="w", pady=(8, 3))

    def _entry(self, parent: tk.Frame, key: str,
               show: str = "") -> ttk.Entry:
        e = ttk.Entry(parent, show=show)
        e.insert(0, str(self.cfg.get(key, "")))
        e.pack(fill=tk.X, pady=(0, 4))
        return e

    def _combo_row(self, parent: tk.Frame, key: str,
                   values: list[str]) -> ttk.Combobox:
        cb = ttk.Combobox(parent, values=values, state="readonly")
        v = str(self.cfg.get(key, values[0] if values else ""))
        if v in values:
            cb.set(v)
        elif values:
            cb.current(0)
        cb.pack(fill=tk.X, pady=(0, 4))
        return cb

    def _slider(self, parent: tk.Frame, key: str,
                from_: int, to: int) -> "HSlider":
        sl = HSlider(parent, from_=from_, to=to)
        sl.set(int(self.cfg.get(key, from_)))
        sl.pack(fill=tk.X, pady=(0, 4))
        return sl

    def _status_badge(self, parent: tk.Frame,
                      text: str, color: str) -> tk.Label:
        lbl = tk.Label(parent,
                       text=f"●  {text}",
                       font=FONTS["small"],
                       bg=C["surface"], fg=color,
                       anchor="w")
        lbl.pack(anchor="w", pady=(0, 8))
        return lbl

    # ══════════════════════════════════════════════════════════════════════════
    # PANEL GENERAL
    # ══════════════════════════════════════════════════════════════════════════
    def _build_general_panel(self) -> None:
        p = self._panels["general"]
        inner = self._scrollable(p)
        self._ph(inner, "General", "Preferencias generales de la aplicación")
        body = self._card(inner, "Apariencia", "🎨")

        self._lbl(body, "TAMAÑO DE LETRA")
        self._font_size_combo = self._combo_row(
            body, "font_size",
            ["8 — Muy pequeño", "9 — Pequeño", "10 — Normal",
             "11 — Grande", "12 — Muy grande"])
        # Map display values to int
        self._FONT_SIZE_MAP = {
            "8 — Muy pequeño": 8, "9 — Pequeño": 9,
            "10 — Normal": 10,    "11 — Grande": 11,
            "12 — Muy grande": 12,
        }
        self._FONT_SIZE_RMAP = {v: k for k, v in self._FONT_SIZE_MAP.items()}
        # Set current value
        cur_size = int(self.cfg.get("font_size", 10))
        cur_label = self._FONT_SIZE_RMAP.get(cur_size, "10 — Normal")
        self._font_size_combo.set(cur_label)

        self._lbl(body, "TEMA")
        self._theme_combo = self._combo_row(body, "theme", ["dark", "light"])

        # Nota de reinicio para el tema
        self._theme_note = tk.Label(body,
            text="⚠  Reinicia la aplicación para aplicar el nuevo tema.",
            font=FONTS["small"], bg=C["surface"], fg=C["warning_h"])

        self._lbl(body, "IDIOMA")
        self._language_combo = self._combo_row(body, "language", ["es", "en"])
        tk.Label(body,
            text="ℹ  El soporte de idioma adicional estará disponible próximamente.",
            font=FONTS["small"], bg=C["surface"], fg=C["text3"]).pack(anchor="w", pady=(0, 8))

        self._start_minimized_var = tk.BooleanVar(
            value=self.cfg.get("start_minimized", False))
        tk.Checkbutton(body,
            text="Iniciar minimizado en bandeja del sistema",
            variable=self._start_minimized_var,
            font=FONTS["body"], bg=C["surface"], fg=C["text"],
            selectcolor=C["surface2"],
            activebackground=C["surface"]).pack(anchor="w")

        self._confirm_close_var = tk.BooleanVar(
            value=self.cfg.get("confirm_close", True))
        tk.Checkbutton(body,
            text="Confirmar al cerrar con transmisión activa",
            variable=self._confirm_close_var,
            font=FONTS["body"], bg=C["surface"], fg=C["text"],
            selectcolor=C["surface2"],
            activebackground=C["surface"]).pack(anchor="w", pady=(4, 0))

        HButton(body, "Guardar", command=self._save_general,
                variant="success").pack(anchor="w", pady=(10, 0))

    def _save_general(self) -> None:
        old_theme = self.cfg.get("theme", "dark")
        old_size  = int(self.cfg.get("font_size", 10))

        self.cfg["theme"]           = self._theme_combo.get()
        self.cfg["language"]        = self._language_combo.get()
        self.cfg["start_minimized"] = bool(self._start_minimized_var.get())
        self.cfg["confirm_close"]   = bool(self._confirm_close_var.get())
        # font size: map label back to int
        size_label = self._font_size_combo.get()
        self.cfg["font_size"] = self._FONT_SIZE_MAP.get(size_label, 10)

        cfg_mod.save(self.cfg)
        if callable(self.on_cfg_saved):
            self.on_cfg_saved(self.cfg)

        needs_restart = (self.cfg["theme"] != old_theme or
                         self.cfg["font_size"] != old_size)
        if needs_restart:
            self._theme_note.pack(anchor="w", pady=(0, 6))
            messagebox.showinfo("Reinicio necesario",
                "El tema y/o tamaño de letra se aplicarán la próxima vez "
                "que inicies HAMNA Desktop.")
        else:
            messagebox.showinfo("Guardado", "Configuración general guardada.")

    # ══════════════════════════════════════════════════════════════════════════
    # PANEL TTS
    # ══════════════════════════════════════════════════════════════════════════
    def _build_tts_panel(self) -> None:
        p = self._panels["tts"]
        inner = self._scrollable(p)
        self._ph(inner, "Motor TTS",
                 "Configuración de síntesis de voz para secciones TTS")

        body = self._card(inner, "Text to Speech Engine", "🗣️")

        # Selector de motor
        self._lbl(body, "MOTOR")
        engine_row = tk.Frame(body, bg=C["surface"])
        engine_row.pack(fill=tk.X, pady=(0, 12))
        self._tts_engine_var = tk.StringVar(
            value=self.cfg.get("tts_engine", "pyttsx3"))
        for val, lbl in [("pyttsx3", "🔇 pyttsx3 (offline)"),
                         ("azure",   "☁️ Azure Cognitive Services")]:
            tk.Radiobutton(engine_row, text=lbl, variable=self._tts_engine_var,
                           value=val, font=FONTS["body"],
                           bg=C["surface"], fg=C["text"],
                           selectcolor=C["surface2"],
                           activebackground=C["surface"],
                           command=self._toggle_tts_engine).pack(
                side=tk.LEFT, padx=(0, 16))

        # pyttsx3 frame
        self._pyttsx3_frame = tk.Frame(body, bg=C["surface"])
        self._pyttsx3_frame.pack(fill=tk.X)

        self._lbl(self._pyttsx3_frame, "VELOCIDAD (palabras/min)")
        self._py_rate = self._slider(self._pyttsx3_frame, "tts_rate", 80, 300)

        self._lbl(self._pyttsx3_frame, "VOLUMEN (%)")
        self._py_vol = self._slider(self._pyttsx3_frame, "tts_volume", 0, 100)

        self._lbl(self._pyttsx3_frame, "TONO")
        self._py_pitch = self._slider(self._pyttsx3_frame, "tts_pitch", -10, 10)

        # Azure frame
        self._azure_frame = tk.Frame(body, bg=C["surface"])

        info = tk.Frame(self._azure_frame, bg=C["tts_bg"],
                        padx=12, pady=8)
        info.pack(fill=tk.X, pady=(0, 10))
        tk.Label(info,
                 text="ℹ️  Azure Cognitive Services requiere conexión a internet "
                      "y suscripción de Azure.",
                 font=FONTS["small"], bg=C["tts_bg"],
                 fg=C["tts_fg"], wraplength=420,
                 justify="left").pack(anchor="w")

        row1 = tk.Frame(self._azure_frame, bg=C["surface"])
        row1.pack(fill=tk.X)
        row1.columnconfigure(0, weight=1)
        row1.columnconfigure(1, weight=1)

        lf = tk.Frame(row1, bg=C["surface"])
        lf.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self._lbl(lf, "SUBSCRIPTION KEY *")
        self._az_key = ttk.Entry(lf, show="*")
        self._az_key.insert(0, self.cfg.get("azure_key", ""))
        self._az_key.pack(fill=tk.X)

        rf = tk.Frame(row1, bg=C["surface"])
        rf.grid(row=0, column=1, sticky="ew")
        self._lbl(rf, "REGIÓN *")
        regions = ["eastus", "eastus2", "westus2", "northeurope",
                   "westeurope", "mexicocentral", "southeastasia"]
        self._az_region = ttk.Combobox(rf, values=regions)
        v = self.cfg.get("azure_region", "")
        if v: self._az_region.set(v)
        self._az_region.pack(fill=tk.X)

        row2 = tk.Frame(self._azure_frame, bg=C["surface"])
        row2.pack(fill=tk.X, pady=(8, 0))
        row2.columnconfigure(0, weight=1)
        row2.columnconfigure(1, weight=1)

        lf2 = tk.Frame(row2, bg=C["surface"])
        lf2.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self._lbl(lf2, "IDIOMA")
        langs = ["es-MX", "es-ES", "es-AR", "es-CO",
                 "en-US", "en-GB", "pt-BR", "fr-FR"]
        self._az_lang = ttk.Combobox(lf2, values=langs, state="readonly")
        self._az_lang.set(self.cfg.get("azure_voice",
                                        "es-MX-DaliaNeural")[:5])
        self._az_lang.pack(fill=tk.X)
        self._az_lang.bind("<<ComboboxSelected>>", self._filter_az_voices)

        rf2 = tk.Frame(row2, bg=C["surface"])
        rf2.grid(row=0, column=1, sticky="ew")
        self._lbl(rf2, "VOZ NEURONAL")
        self._az_voice = ttk.Combobox(rf2,
            values=["es-MX-DaliaNeural", "es-MX-JorgeNeural",
                    "es-MX-CarlotaNeural"],
            state="readonly")
        v2 = self.cfg.get("azure_voice", "es-MX-DaliaNeural")
        self._az_voice.set(v2)
        self._az_voice.pack(fill=tk.X)

        row3 = tk.Frame(self._azure_frame, bg=C["surface"])
        row3.pack(fill=tk.X, pady=(8, 0))
        row3.columnconfigure(0, weight=1)
        row3.columnconfigure(1, weight=1)

        lf3 = tk.Frame(row3, bg=C["surface"])
        lf3.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self._lbl(lf3, "ESTILO")
        self._az_style = ttk.Combobox(lf3, state="readonly",
            values=["general", "newscast", "cheerful",
                    "empathetic", "calm", "customerservice"])
        self._az_style.set(self.cfg.get("azure_style", "general"))
        self._az_style.pack(fill=tk.X)

        rf3 = tk.Frame(row3, bg=C["surface"])
        rf3.grid(row=0, column=1, sticky="ew")
        self._lbl(rf3, "FORMATO DE AUDIO")
        self._az_format = ttk.Combobox(rf3, state="readonly",
            values=["audio-16khz-128kbitrate-mono-mp3",
                    "audio-24khz-160kbitrate-mono-mp3",
                    "audio-48khz-192kbitrate-mono-mp3",
                    "riff-16khz-16bit-mono-pcm"])
        self._az_format.set(self.cfg.get(
            "azure_format", "audio-24khz-160kbitrate-mono-mp3"))
        self._az_format.pack(fill=tk.X)

        az_sliders = tk.Frame(self._azure_frame, bg=C["surface"])
        az_sliders.pack(fill=tk.X, pady=(8, 0))
        az_sliders.columnconfigure(0, weight=1)
        az_sliders.columnconfigure(1, weight=1)

        lf4 = tk.Frame(az_sliders, bg=C["surface"])
        lf4.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self._lbl(lf4, "VELOCIDAD (%)")
        self._az_rate = self._slider(lf4, "azure_rate", 50, 200)

        rf4 = tk.Frame(az_sliders, bg=C["surface"])
        rf4.grid(row=0, column=1, sticky="ew")
        self._lbl(rf4, "TONO (Hz)")
        self._az_pitch = self._slider(rf4, "azure_pitch", -20, 20)

        self._az_status = self._status_badge(
            self._azure_frame, "Sin verificar", C["warning"])

        # Estado
        self._az_status = tk.Label(self._azure_frame,
            text="●  Sin verificar",
            font=FONTS["small"], bg=C["surface"],
            fg=C["warning"])
        self._az_status.pack(anchor="w", pady=(8, 0))

        # Botones
        btn_row = tk.Frame(body, bg=C["surface"])
        btn_row.pack(fill=tk.X, pady=(12, 0))
        HButton(btn_row, "▶ Probar voz",
                command=self._test_tts,
                variant="ghost").pack(side=tk.LEFT)
        self._btn_az_test = HButton(btn_row, "☁️ Test Azure",
                command=self._test_azure,
                variant="ghost")
        HButton(btn_row, "Guardar",
                command=self._save_tts,
                variant="success").pack(side=tk.RIGHT)

        self._toggle_tts_engine()

    def _toggle_tts_engine(self) -> None:
        engine = self._tts_engine_var.get()
        if engine == "azure":
            self._pyttsx3_frame.pack_forget()
            self._azure_frame.pack(fill=tk.X)
            self._btn_az_test.pack(side=tk.LEFT, padx=(6, 0))
        else:
            self._azure_frame.pack_forget()
            self._pyttsx3_frame.pack(fill=tk.X)
            self._btn_az_test.pack_forget()

    def _filter_az_voices(self, event=None) -> None:
        lang = self._az_lang.get()
        voice_db = {
            "es-MX": ["es-MX-DaliaNeural", "es-MX-JorgeNeural",
                      "es-MX-CarlotaNeural", "es-MX-NuriaNeural"],
            "es-ES": ["es-ES-ElviraNeural", "es-ES-AlvaroNeural"],
            "en-US": ["en-US-JennyNeural", "en-US-GuyNeural",
                      "en-US-AriaNeural"],
            "pt-BR": ["pt-BR-FranciscaNeural", "pt-BR-AntonioNeural"],
        }
        voices = voice_db.get(lang, [])
        self._az_voice.config(values=voices)
        if voices:
            self._az_voice.current(0)

    def _test_tts(self) -> None:
        messagebox.showinfo("TTS", "Prueba de voz iniciada (ver consola).")

    def _test_azure(self) -> None:
        self._az_status.config(text="●  Verificando...", fg=C["warning"])
        key    = self._az_key.get().strip()
        region = self._az_region.get().strip()
        def run():
            try:
                import azure.cognitiveservices.speech as sdk
                cfg = sdk.SpeechConfig(subscription=key, region=region)
                self.after(0, lambda: self._az_status.config(
                    text="●  Conectado", fg=C["success"]))
            except Exception as e:
                self.after(0, lambda: self._az_status.config(
                    text=f"●  Error: {e}", fg=C["danger"]))
        threading.Thread(target=run, daemon=True).start()

    def _save_tts(self) -> None:
        engine = self._tts_engine_var.get()
        self.cfg["tts_engine"]  = engine
        self.cfg["tts_rate"]    = int(self._py_rate.get())
        self.cfg["tts_volume"]  = int(self._py_vol.get())
        self.cfg["tts_pitch"]   = int(self._py_pitch.get())
        if engine == "azure":
            self.cfg["azure_key"]    = self._az_key.get().strip()
            self.cfg["azure_region"] = self._az_region.get().strip()
            self.cfg["azure_voice"]  = self._az_voice.get()
            self.cfg["azure_style"]  = self._az_style.get()
            self.cfg["azure_format"] = self._az_format.get()
            self.cfg["azure_rate"]   = int(self._az_rate.get())
            self.cfg["azure_pitch"]  = int(self._az_pitch.get())
        cfg_mod.save(self.cfg)
        if callable(self.on_cfg_saved):
            self.on_cfg_saved(self.cfg)
        messagebox.showinfo("Guardado", "Configuración TTS guardada.")

    # ══════════════════════════════════════════════════════════════════════════
    # PANEL PTT
    # ══════════════════════════════════════════════════════════════════════════
    def _build_ptt_panel(self) -> None:
        p = self._panels["ptt"]
        inner = self._scrollable(p)
        self._ph(inner, "Control PTT",
                 "Método de activación Push-To-Talk para la transmisión")

        # Banner método activo
        self._ptt_banner = tk.Frame(inner, bg=C["audio_bg"],
                                     padx=14, pady=8)
        self._ptt_banner.pack(fill=tk.X, padx=18, pady=(0, 12))
        tk.Label(self._ptt_banner, text="●",
                 font=("Segoe UI", 10),
                 bg=C["audio_bg"], fg=C["success"]).pack(side=tk.LEFT)
        tk.Label(self._ptt_banner, text="Método activo:",
                 font=FONTS["small"],
                 bg=C["audio_bg"], fg=C["success"]).pack(
            side=tk.LEFT, padx=(4, 8))
        self._lbl_active_method = tk.Label(self._ptt_banner, text="Serial RS-232",
            font=FONTS["h3"], bg=C["audio_bg"], fg=C["text"])
        self._lbl_active_method.pack(side=tk.LEFT)
        self._lbl_active_status = tk.Label(self._ptt_banner, text="No conectado",
            font=FONTS["small"], bg=C["audio_bg"], fg=C["text2"])
        self._lbl_active_status.pack(side=tk.RIGHT)

        # Tabs de método
        tab_row = tk.Frame(inner, bg=C["surface2"])
        tab_row.pack(fill=tk.X, padx=18, pady=(0, 2))
        self._ptt_method_var = tk.StringVar(
            value=self.cfg.get("ptt_method", "serial"))
        self._ptt_tab_btns: dict[str, tk.Label] = {}
        for val, lbl in [("serial", "🔌 Serial RS-232"),
                         ("ami",    "☎️ AMI (Asterisk)"),
                         ("api",    "🌐 API HTTP")]:
            b = tk.Label(tab_row, text=lbl, font=FONTS["body"],
                         bg=C["surface2"], fg=C["text2"],
                         padx=16, pady=8, cursor="hand2")
            b.pack(side=tk.LEFT)
            b.bind("<Button-1>",
                   lambda e, v=val: self._switch_ptt_method(v))
            self._ptt_tab_btns[val] = b

        # Frames de cada método
        self._ptt_frames: dict[str, tk.Frame] = {}
        for key in ["serial", "ami", "api"]:
            f = tk.Frame(inner, bg=C["bg"])
            self._ptt_frames[key] = f

        self._build_serial_panel(self._ptt_frames["serial"], inner)
        self._build_ami_panel(self._ptt_frames["ami"], inner)
        self._build_api_panel(self._ptt_frames["api"], inner)

        active = self.cfg.get("ptt_method", "serial")
        self._switch_ptt_method(active)

    def _switch_ptt_method(self, method: str) -> None:
        self.cfg["ptt_method"] = method
        for k, f in self._ptt_frames.items():
            f.pack_forget()
        self._ptt_frames[method].pack(fill=tk.BOTH, expand=True)
        for k, b in self._ptt_tab_btns.items():
            b.config(bg=C["accent"] if k == method else C["surface2"],
                     fg=C["text"] if k == method else C["text2"])
        names = {"serial": "Serial RS-232",
                 "ami":    "AMI (Asterisk)",
                 "api":    "API HTTP"}
        self._lbl_active_method.config(text=names.get(method, method))
        self.ptt.reload_cfg(self.cfg)

    # ── Serial ────────────────────────────────────────────────────────────────
    def _build_serial_panel(self, parent: tk.Frame,
                             inner: tk.Frame) -> None:
        body = self._card(parent, "Serial RS-232 / USB-UART", "🔌")
        parent.pack(fill=tk.X, padx=18, pady=(0, 12))

        # Puerto + Refresh
        self._lbl(body, "PUERTO")
        port_row = tk.Frame(body, bg=C["surface"])
        port_row.pack(fill=tk.X, pady=(0, 8))
        from modules.ptt.ptt_serial import PTTSerial
        ports = PTTSerial.list_ports() or ["COM1", "COM2", "COM3"]
        self._ser_port = ttk.Combobox(port_row, values=ports)
        self._ser_port.set(self.cfg.get("serial_port", "COM1"))
        self._ser_port.pack(side=tk.LEFT, fill=tk.X, expand=True)
        HButton(port_row, "↺ Refresh",
                command=self._refresh_ports,
                variant="ghost").pack(side=tk.LEFT, padx=(6, 0))

        self._lbl(body, "BAUDRATE")
        bauds = ["1200","2400","4800","9600","19200",
                 "38400","57600","115200"]
        self._ser_baud = ttk.Combobox(body, values=bauds, state="readonly")
        self._ser_baud.set(str(self.cfg.get("serial_baud", 9600)))
        self._ser_baud.pack(fill=tk.X, pady=(0, 8))

        self._lbl(body, "PIN PTT")
        self._ser_pin = ttk.Combobox(body,
            values=["RTS", "DTR"], state="readonly")
        self._ser_pin.set(self.cfg.get("serial_pin", "RTS"))
        self._ser_pin.pack(fill=tk.X, pady=(0, 10))

        # Indicadores
        ind_row = tk.Frame(body, bg=C["surface2"],
                           padx=12, pady=8)
        ind_row.pack(fill=tk.X, pady=(0, 10))

        self._cos_var = tk.StringVar(value="INACTIVE")
        self._ptt_var = tk.StringVar(value="OFF")

        for txt, var, key in [("COS", self._cos_var, "cos"),
                               ("PTT", self._ptt_var, "ptt")]:
            f = tk.Frame(ind_row, bg=C["surface2"])
            f.pack(side=tk.LEFT, padx=(0, 16))
            self._cos_dot = tk.Label(f, text="●", font=("Segoe UI", 9),
                                      bg=C["surface2"], fg=C["text3"])
            self._cos_dot.pack(side=tk.LEFT, padx=(0, 4))
            tk.Label(f, text=txt, font=FONTS["badge"],
                     bg=C["surface2"], fg=C["text3"]).pack(side=tk.LEFT)
            tk.Label(f, textvariable=var,
                     font=FONTS["mono_sm"],
                     bg=C["surface2"], fg=C["text2"]).pack(
                side=tk.LEFT, padx=(4, 0))

        self._ser_status = tk.Label(body,
            text="●  Disconnected",
            font=FONTS["small"], bg=C["surface"], fg=C["text3"])
        self._ser_status.pack(anchor="w", pady=(0, 10))

        btn_row = tk.Frame(body, bg=C["surface"])
        btn_row.pack(fill=tk.X)
        self._btn_ser_conn = HButton(btn_row, "Connect",
            command=self._connect_serial, variant="success")
        self._btn_ser_conn.pack(side=tk.LEFT)
        self._btn_ser_ptt = HButton(btn_row, "PTT ON",
            command=self._toggle_serial_ptt, variant="on_air")
        self._btn_ser_ptt.pack(side=tk.LEFT, padx=(8, 0))
        self._btn_ser_ptt.config(state="disabled")

        # Invertir
        sep = tk.Frame(body, bg=C["border"], height=1)
        sep.pack(fill=tk.X, pady=10)
        check_row = tk.Frame(body, bg=C["surface"])
        check_row.pack(fill=tk.X)
        self._inv_ptt_var = tk.BooleanVar(
            value=self.cfg.get("serial_invert_ptt", False))
        self._inv_cos_var = tk.BooleanVar(
            value=self.cfg.get("serial_invert_cos", False))
        for text, var in [("Invert PTT", self._inv_ptt_var),
                          ("Invert COS", self._inv_cos_var)]:
            tk.Checkbutton(check_row, text=text, variable=var,
                           font=FONTS["body"],
                           bg=C["surface"], fg=C["text"],
                           selectcolor=C["surface2"],
                           activebackground=C["surface"]).pack(
                side=tk.LEFT, padx=(0, 16))

        HButton(body, "Guardar Serial",
                command=self._save_serial,
                variant="success").pack(anchor="w", pady=(10, 0))

        # Callbacks del manager
        def _ser_status_cb(status: str, msg: str) -> None:
            color = (C["success"] if status == "connected"
                     else C["danger"] if status == "error"
                     else C["text3"])
            self.after(0, lambda: self._ser_status.config(
                text=f"●  {msg}", fg=color))
        self.ptt.on_serial_status = _ser_status_cb

    def _refresh_ports(self) -> None:
        from modules.ptt.ptt_serial import PTTSerial
        ports = PTTSerial.list_ports()
        self._ser_port.config(values=ports or ["COM1"])

    def _connect_serial(self) -> None:
        if self.ptt.serial.is_connected():
            self.ptt.serial.disconnect()
            self._btn_ser_conn.config(text="Connect")
            self._btn_ser_conn.set_variant("success")
            self._btn_ser_ptt.config(state="disabled")
        else:
            self._save_serial()
            ok, msg = self.ptt.serial.connect(
                port=self.cfg.get("serial_port", "COM1"),
                baudrate=int(self.cfg.get("serial_baud", 9600)),
                pin=self.cfg.get("serial_pin", "RTS"),
                invert_ptt=self.cfg.get("serial_invert_ptt", False),
            )
            if ok:
                self._btn_ser_conn.config(text="Disconnect")
                self._btn_ser_conn.set_variant("danger")
                self._btn_ser_ptt.config(state="normal")
            else:
                messagebox.showerror("Error de conexión", msg)

    def _toggle_serial_ptt(self) -> None:
        if self.ptt.serial.is_ptt_on():
            self.ptt.serial.ptt_off()
            self._btn_ser_ptt.config(text="PTT ON")
            self._btn_ser_ptt.set_variant("on_air")
            self._ptt_var.set("OFF")
        else:
            self.ptt.serial.ptt_on()
            self._btn_ser_ptt.config(text="PTT OFF")
            self._btn_ser_ptt.set_variant("ghost")
            self._ptt_var.set("ON")

    def _save_serial(self) -> None:
        self.cfg["serial_port"]       = self._ser_port.get()
        self.cfg["serial_baud"]       = int(self._ser_baud.get())
        self.cfg["serial_pin"]        = self._ser_pin.get()
        self.cfg["serial_invert_ptt"] = bool(self._inv_ptt_var.get())
        self.cfg["serial_invert_cos"] = bool(self._inv_cos_var.get())
        cfg_mod.save(self.cfg)

    # ── AMI ───────────────────────────────────────────────────────────────────
    def _build_ami_panel(self, parent: tk.Frame,
                          inner: tk.Frame) -> None:
        body = self._card(parent, "AMI Settings — Asterisk Manager Interface", "☎️")
        parent.pack(fill=tk.X, padx=18, pady=(0, 12))

        row = tk.Frame(body, bg=C["surface"])
        row.pack(fill=tk.X)
        row.columnconfigure(0, weight=1)
        row.columnconfigure(1, weight=1)

        lf = tk.Frame(row, bg=C["surface"])
        lf.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self._lbl(lf, "HOST")
        self._ami_host = ttk.Entry(lf)
        self._ami_host.insert(0, self.cfg.get("ami_host", "127.0.0.1"))
        self._ami_host.pack(fill=tk.X)

        rf = tk.Frame(row, bg=C["surface"])
        rf.grid(row=0, column=1, sticky="ew")
        self._lbl(rf, "PORT")
        self._ami_port = ttk.Entry(rf)
        self._ami_port.insert(0, str(self.cfg.get("ami_port", 5038)))
        self._ami_port.pack(fill=tk.X)

        row2 = tk.Frame(body, bg=C["surface"])
        row2.pack(fill=tk.X, pady=(8, 0))
        row2.columnconfigure(0, weight=1)
        row2.columnconfigure(1, weight=1)

        lf2 = tk.Frame(row2, bg=C["surface"])
        lf2.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self._lbl(lf2, "USERNAME")
        self._ami_user = ttk.Entry(lf2)
        self._ami_user.insert(0, self.cfg.get("ami_user", "admin"))
        self._ami_user.pack(fill=tk.X)

        rf2 = tk.Frame(row2, bg=C["surface"])
        rf2.grid(row=0, column=1, sticky="ew")
        self._lbl(rf2, "CONTRASEÑA")
        self._ami_pass = ttk.Entry(rf2, show="*")
        self._ami_pass.insert(0, self.cfg.get("ami_password", ""))
        self._ami_pass.pack(fill=tk.X)

        row3 = tk.Frame(body, bg=C["surface"])
        row3.pack(fill=tk.X, pady=(8, 0))
        row3.columnconfigure(0, weight=1)
        row3.columnconfigure(1, weight=1)

        lf3 = tk.Frame(row3, bg=C["surface"])
        lf3.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self._lbl(lf3, "CANAL ORIGINATE")
        self._ami_channel = ttk.Entry(lf3)
        self._ami_channel.insert(0, self.cfg.get("ami_channel", "SIP/radio"))
        self._ami_channel.pack(fill=tk.X)

        rf3 = tk.Frame(row3, bg=C["surface"])
        rf3.grid(row=0, column=1, sticky="ew")
        self._lbl(rf3, "CONTEXTO")
        self._ami_context = ttk.Entry(rf3)
        self._ami_context.insert(0, self.cfg.get("ami_context", "ptt-control"))
        self._ami_context.pack(fill=tk.X)

        self._ami_status = tk.Label(body,
            text="●  Disconnected", font=FONTS["small"],
            bg=C["surface"], fg=C["text3"])
        self._ami_status.pack(anchor="w", pady=(10, 6))

        btn_row = tk.Frame(body, bg=C["surface"])
        btn_row.pack(fill=tk.X)
        HButton(btn_row, "Test Connection",
                command=self._test_ami, variant="ghost").pack(side=tk.LEFT)
        HButton(btn_row, "Save",
                command=self._save_ami, variant="success").pack(
            side=tk.LEFT, padx=(6, 0))

        def _ami_cb(status, msg):
            color = (C["success"] if status == "connected"
                     else C["danger"] if status == "error" else C["text3"])
            self.after(0, lambda: self._ami_status.config(
                text=f"●  {msg}", fg=color))
        self.ptt.on_ami_status = _ami_cb

    def _test_ami(self) -> None:
        self._save_ami()
        self._ami_status.config(text="●  Probando...", fg=C["warning"])
        def run():
            ok, msg = self.ptt.ami.connect(
                host=self.cfg.get("ami_host", "127.0.0.1"),
                port=int(self.cfg.get("ami_port", 5038)),
                user=self.cfg.get("ami_user", "admin"),
                password=self.cfg.get("ami_password", ""),
                channel=self.cfg.get("ami_channel", "SIP/radio"),
                context=self.cfg.get("ami_context", "ptt-control"),
            )
        threading.Thread(target=run, daemon=True).start()

    def _save_ami(self) -> None:
        self.cfg["ami_host"]     = self._ami_host.get().strip()
        self.cfg["ami_port"]     = int(self._ami_port.get().strip() or 5038)
        self.cfg["ami_user"]     = self._ami_user.get().strip()
        self.cfg["ami_password"] = self._ami_pass.get()
        self.cfg["ami_channel"]  = self._ami_channel.get().strip()
        self.cfg["ami_context"]  = self._ami_context.get().strip()
        cfg_mod.save(self.cfg)
        self.ptt.reload_cfg(self.cfg)

    # ── API ───────────────────────────────────────────────────────────────────
    def _build_api_panel(self, parent: tk.Frame,
                          inner: tk.Frame) -> None:
        body = self._card(parent, "API Settings — HTTP REST", "🌐")
        parent.pack(fill=tk.X, padx=18, pady=(0, 12))

        self._lbl(body, "URL BASE")
        self._api_url = ttk.Entry(body)
        self._api_url.insert(0, self.cfg.get("api_url",
                                               "http://192.168.1.37"))
        self._api_url.pack(fill=tk.X, pady=(0, 8))

        row = tk.Frame(body, bg=C["surface"])
        row.pack(fill=tk.X)
        row.columnconfigure(0, weight=1)
        row.columnconfigure(1, weight=1)

        lf = tk.Frame(row, bg=C["surface"])
        lf.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self._lbl(lf, "RUTA PTT ON")
        self._api_on = ttk.Entry(lf)
        self._api_on.insert(0, self.cfg.get("api_ptt_on", "/ptt_on"))
        self._api_on.pack(fill=tk.X)

        rf = tk.Frame(row, bg=C["surface"])
        rf.grid(row=0, column=1, sticky="ew")
        self._lbl(rf, "RUTA PTT OFF")
        self._api_off = ttk.Entry(rf)
        self._api_off.insert(0, self.cfg.get("api_ptt_off", "/ptt_off"))
        self._api_off.pack(fill=tk.X)

        row2 = tk.Frame(body, bg=C["surface"])
        row2.pack(fill=tk.X, pady=(8, 0))
        row2.columnconfigure(0, weight=1)
        row2.columnconfigure(1, weight=1)

        lf2 = tk.Frame(row2, bg=C["surface"])
        lf2.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self._lbl(lf2, "API KEY (opcional)")
        self._api_key = ttk.Entry(lf2, show="*")
        self._api_key.insert(0, self.cfg.get("api_key", ""))
        self._api_key.pack(fill=tk.X)

        rf2 = tk.Frame(row2, bg=C["surface"])
        rf2.grid(row=0, column=1, sticky="ew")
        self._lbl(rf2, "MÉTODO HTTP")
        self._api_method = ttk.Combobox(rf2,
            values=["GET", "POST", "PUT"], state="readonly")
        self._api_method.set(self.cfg.get("api_method", "GET"))
        self._api_method.pack(fill=tk.X)

        # Preview
        prev = tk.Frame(body, bg=C["surface2"], padx=10, pady=8)
        prev.pack(fill=tk.X, pady=(10, 0))
        tk.Label(prev, text="PREVIEW", font=FONTS["badge"],
                 bg=C["surface2"], fg=C["text3"]).pack(anchor="w")
        self._api_prev_on = tk.Label(prev, text="",
            font=FONTS["mono_sm"], bg=C["surface2"], fg=C["success"])
        self._api_prev_on.pack(anchor="w")
        self._api_prev_off = tk.Label(prev, text="",
            font=FONTS["mono_sm"], bg=C["surface2"], fg=C["danger"])
        self._api_prev_off.pack(anchor="w")

        for e in (self._api_url, self._api_on, self._api_off):
            e.bind("<KeyRelease>", self._update_api_preview)
        self._update_api_preview()

        self._api_status = tk.Label(body,
            text="●  Disconnected", font=FONTS["small"],
            bg=C["surface"], fg=C["text3"])
        self._api_status.pack(anchor="w", pady=(10, 6))

        btn_row = tk.Frame(body, bg=C["surface"])
        btn_row.pack(fill=tk.X)
        HButton(btn_row, "Probar Conexión",
                command=self._test_api, variant="ghost").pack(side=tk.LEFT)
        HButton(btn_row, "Guardar",
                command=self._save_api, variant="success").pack(
            side=tk.LEFT, padx=(6, 0))
        HButton(btn_row, "PTT ON",
                command=lambda: self.ptt.api.ptt_on(),
                variant="on_air").pack(side=tk.RIGHT)
        HButton(btn_row, "PTT OFF",
                command=lambda: self.ptt.api.ptt_off(),
                variant="muted").pack(side=tk.RIGHT, padx=(0, 6))

        def _api_cb(status, msg):
            color = (C["success"] if status == "connected"
                     else C["danger"] if status == "error" else C["text3"])
            self.after(0, lambda: self._api_status.config(
                text=f"●  {msg}", fg=color))
        self.ptt.on_api_status = _api_cb

    def _update_api_preview(self, event=None) -> None:
        url = self._api_url.get().rstrip("/")
        on  = self._api_on.get()
        off = self._api_off.get()
        self._api_prev_on.config(text=f"ON  → {url}{on}")
        self._api_prev_off.config(text=f"OFF → {url}{off}")

    def _test_api(self) -> None:
        self._save_api()
        self._api_status.config(text="●  Probando...", fg=C["warning"])
        def run():
            ok, msg = self.ptt.api.test_connection(
                base_url=self.cfg.get("api_url", ""),
                route_on=self.cfg.get("api_ptt_on", "/ptt_on"),
                route_off=self.cfg.get("api_ptt_off", "/ptt_off"),
                method=self.cfg.get("api_method", "GET"),
                api_key=self.cfg.get("api_key", ""),
            )
        threading.Thread(target=run, daemon=True).start()

    def _save_api(self) -> None:
        self.cfg["api_url"]     = self._api_url.get().strip()
        self.cfg["api_ptt_on"]  = self._api_on.get().strip()
        self.cfg["api_ptt_off"] = self._api_off.get().strip()
        self.cfg["api_method"]  = self._api_method.get()
        self.cfg["api_key"]     = self._api_key.get()
        cfg_mod.save(self.cfg)
        self.ptt.reload_cfg(self.cfg)
        self._update_api_preview()

    # ══════════════════════════════════════════════════════════════════════════
    # PANEL AUDIO
    # ══════════════════════════════════════════════════════════════════════════
    def _build_audio_panel(self) -> None:
        p = self._panels["audio"]
        inner = self._scrollable(p)
        self._ph(inner, "Dispositivos de Audio",
                 "Entrada y salida de audio para reproducción de secciones")
        body = self._card(inner, "Salida de Audio", "🔊")
        self._lbl(body, "DISPOSITIVO DE SALIDA")
        devices = ["Sistema por defecto"]
        try:
            import pygame
            pygame.mixer.init()
            devices += [f"Dispositivo {i}"
                        for i in range(pygame.mixer.get_num_channels())]
        except Exception:
            pass
        self._audio_dev = ttk.Combobox(body, values=devices)
        self._audio_dev.set(self.cfg.get("audio_device") or devices[0])
        self._audio_dev.pack(fill=tk.X, pady=(0, 10))
        self._lbl(body, "VOLUMEN MASTER (%)")
        self._audio_vol = self._slider(body, "audio_volume", 0, 100)
        HButton(body, "▶ Probar audio",
                command=lambda: None, variant="ghost").pack(
            side=tk.LEFT, pady=(8, 0))
        HButton(body, "Guardar",
                command=self._save_audio,
                variant="success").pack(side=tk.LEFT, padx=(8, 0),
                                        pady=(8, 0))

    def _save_audio(self) -> None:
        self.cfg["audio_device"] = self._audio_dev.get()
        self.cfg["audio_volume"] = int(self._audio_vol.get())
        cfg_mod.save(self.cfg)
        messagebox.showinfo("Guardado", "Configuración de audio guardada.")

    # ══════════════════════════════════════════════════════════════════════════
    # PANEL TIEMPOS Y PAUSAS
    # ══════════════════════════════════════════════════════════════════════════
    def _build_pauses_panel(self) -> None:
        p = self._panels["pauses"]
        inner = self._scrollable(p)
        self._ph(inner, "Tiempos y Pausas",
                 "Configura pausas automáticas durante la transmisión")

        # ── Activar ────────────────────────────────────────────────────────
        body_en = self._card(inner, "Estado", "⏸")
        self._pause_enabled_var = tk.BooleanVar(
            value=self.cfg.get("pause_enabled", False))
        tk.Checkbutton(body_en,
            text="Activar pausas automáticas durante la transmisión",
            variable=self._pause_enabled_var,
            font=FONTS["body"], bg=C["surface"], fg=C["text"],
            selectcolor=C["surface2"],
            activebackground=C["surface"],
            command=self._toggle_pauses_state).pack(anchor="w")
        info = tk.Frame(body_en, bg=C["warning"], padx=10, pady=6)
        info.pack(fill=tk.X, pady=(10, 0))
        tk.Label(info,
            text="⚠  Al activar, la transmisión pausará automáticamente "
                 "cada cierto tiempo, reproduciendo los anuncios configurados.",
            font=FONTS["small"], bg=C["warning"], fg="#fff",
            wraplength=460, justify="left").pack(anchor="w")

        # ── Tiempos ────────────────────────────────────────────────────────
        self._pauses_body = tk.Frame(inner, bg=C["bg"])
        self._pauses_body.pack(fill=tk.X)

        body_t = self._card(self._pauses_body, "Tiempos", "⏱")
        body_t.columnconfigure(0, weight=1)
        body_t.columnconfigure(1, weight=1)
        body_t.columnconfigure(2, weight=1)

        row = tk.Frame(body_t, bg=C["surface"])
        row.pack(fill=tk.X)
        row.columnconfigure(0, weight=1)
        row.columnconfigure(1, weight=1)
        row.columnconfigure(2, weight=1)

        for col, (lbl, key, lo, hi) in enumerate([
            ("TIEMPO DE TX ANTES DE PAUSA (seg)", "pause_tx_time",     10,  3600),
            ("DURACIÓN DE PAUSA (seg)",            "pause_duration",     5,   600),
            ("ALERTA ANTES DE PAUSA (seg)",        "pause_alert_before", 0,    60),
        ]):

            f = tk.Frame(row, bg=C["surface"])
            f.grid(row=0, column=col, sticky="ew",
                   padx=(0 if col == 0 else 8, 0))
            tk.Label(f, text=lbl, font=FONTS["badge"],
                     bg=C["surface"], fg=C["text3"],
                     wraplength=140, justify="left").pack(anchor="w", pady=(0, 4))
            sp = tk.Spinbox(f, from_=lo, to=hi, width=8,
                            bg=C["input_bg"], fg=C["text"],
                            buttonbackground=C["surface2"],
                            relief="flat", font=FONTS["body"],
                            highlightthickness=1,
                            highlightcolor=C["border"],
                            highlightbackground=C["border"])
            sp.delete(0, "end")
            sp.insert(0, str(self.cfg.get(key, lo)))
            sp.pack(anchor="w")
            setattr(self, f"_pause_sp_{key}", sp)

        # ── Retardo PTT ON ─────────────────────────────────────────────────
        row2 = tk.Frame(body_t, bg=C["surface"])
        row2.pack(fill=tk.X, pady=(12, 0))
        tk.Frame(body_t, bg=C["border"], height=1).pack(fill=tk.X, pady=(8, 0))
        row3 = tk.Frame(body_t, bg=C["surface"])
        row3.pack(fill=tk.X, pady=(8, 0))

        f_ptt = tk.Frame(row3, bg=C["surface"])
        f_ptt.pack(side="left")
        tk.Label(f_ptt, text="RETARDO PTT ON (seg)",
                 font=FONTS["badge"], bg=C["surface"], fg=C["text3"]
                 ).pack(anchor="w", pady=(0, 4))
        sp_ptt = tk.Spinbox(f_ptt, from_=0, to=10, width=8,
                            bg=C["input_bg"], fg=C["text"],
                            buttonbackground=C["surface2"],
                            relief="flat", font=FONTS["body"],
                            highlightthickness=1,
                            highlightcolor=C["border"],
                            highlightbackground=C["border"])
        sp_ptt.delete(0, "end")
        sp_ptt.insert(0, str(self.cfg.get("ptt_on_delay", 0)))
        sp_ptt.pack(anchor="w")
        self._pause_sp_ptt_on_delay = sp_ptt

        tk.Label(row3,
                 text="Silencio entre PTT ON y el inicio del audio. "
                      "Compensa la latencia del sistema de transmisión (0 = sin retardo).",
                 font=FONTS["small"], bg=C["surface"], fg=C["text3"],
                 wraplength=340, justify="left").pack(side="left", padx=(16, 0))

        # ── Archivos de audio ──────────────────────────────────────────────
        body_a = self._card(self._pauses_body, "Archivos de Audio", "🔊")

        for lbl, key, icon in [
            ("ALERTA DE PAUSA",       "pause_alert_file",        "🔔"),
            ("ANUNCIO DE PAUSA",      "pause_announcement_file", "⏸"),
            ("ANUNCIO DE CONTINUAMOS","pause_resume_file",       "▶"),
        ]:
            tk.Label(body_a, text=f"{icon}  {lbl}",
                     font=FONTS["badge"], bg=C["surface"],
                     fg=C["text3"]).pack(anchor="w", pady=(8, 3))

            row_a = tk.Frame(body_a, bg=C["surface"])
            row_a.pack(fill=tk.X, pady=(0, 4))
            row_a.columnconfigure(0, weight=1)

            path_var = tk.StringVar(value=self.cfg.get(key, ""))
            e = ttk.Entry(row_a, textvariable=path_var)
            e.grid(row=0, column=0, sticky="ew")

            HButton(row_a, "Examinar",
                    command=lambda pv=path_var: self._browse_pause_audio(pv),
                    variant="ghost").grid(row=0, column=1, padx=(6, 0))
            HButton(row_a, "✖",
                    command=lambda pv=path_var: pv.set(""),
                    variant="muted").grid(row=0, column=2, padx=(4, 0))

            setattr(self, f"_pause_path_{key}", path_var)

        # ── Guardar ────────────────────────────────────────────────────────
        HButton(self._pauses_body, "Guardar configuración de pausas",
                command=self._save_pauses,
                variant="success").pack(anchor="w", padx=18, pady=(4, 12))

        self._toggle_pauses_state()

    def _toggle_pauses_state(self) -> None:
        enabled = self._pause_enabled_var.get()
        state = "normal" if enabled else "disabled"
        for w in self._pauses_body.winfo_children():
            try:
                w.config(state=state)
            except Exception:
                pass

    def _browse_pause_audio(self, path_var: tk.StringVar) -> None:
        path = filedialog.askopenfilename(
            title="Seleccionar archivo de audio",
            filetypes=[("Audio", "*.mp3 *.wav *.MP3 *.WAV"), ("Todos", "*.*")])
        if not path:
            return
        # Copiar el archivo a media/sonidos/ para que la app sea portable
        try:
            _SONIDOS_DIR.mkdir(parents=True, exist_ok=True)
            dest = _SONIDOS_DIR / Path(path).name
            shutil.copy2(path, dest)
            path_var.set(str(dest))
        except Exception as e:
            messagebox.showwarning("Advertencia",
                f"No se pudo copiar a media/sonidos/:\n{e}\n\n"
                "Se usará la ruta original.")
            path_var.set(path)

    def _save_pauses(self) -> None:
        self.cfg["pause_enabled"] = bool(self._pause_enabled_var.get())
        for key in ("pause_tx_time", "pause_duration", "pause_alert_before",
                    "ptt_on_delay"):
            try:
                sp = getattr(self, f"_pause_sp_{key}")
                self.cfg[key] = int(sp.get())
            except Exception:
                pass
        for key in ("pause_alert_file", "pause_announcement_file",
                    "pause_resume_file"):
            pv = getattr(self, f"_pause_path_{key}")
            self.cfg[key] = pv.get().strip()
        cfg_mod.save(self.cfg)
        if callable(self.on_cfg_saved):
            self.on_cfg_saved(self.cfg)
        messagebox.showinfo("Guardado",
            "Configuración de tiempos y pausas guardada.")

    # ══════════════════════════════════════════════════════════════════════════
    # PANEL DB
    # ══════════════════════════════════════════════════════════════════════════
    def _build_db_panel(self) -> None:
        from pathlib import Path
        p = self._panels["db"]
        inner = self._scrollable(p)
        self._ph(inner, "Base de Datos",
                 "Rutas de archivos y mantenimiento de hamna.db")
        body = self._card(inner, "SQLite", "🗄️")

        import database
        db_path    = str(database.DB_PATH)
        media_path = str(Path(database.DB_PATH).parent / "media" / "audios")

        for lbl_text, val in [
            ("RUTA BASE DE DATOS",   db_path),
            ("CARPETA DE AUDIOS",    media_path),
            ("TEMPORAL TTS",
             str(Path(database.DB_PATH).parent / "output_temp.mp3")),
        ]:
            self._lbl(body, lbl_text)
            e = ttk.Entry(body)
            e.insert(0, val)
            e.config(state="readonly")
            e.pack(fill=tk.X, pady=(0, 8))

        btn_row = tk.Frame(body, bg=C["surface"])
        btn_row.pack(fill=tk.X, pady=(4, 0))
        HButton(btn_row, "📂 Abrir carpeta",
                command=lambda: self._open_folder(media_path),
                variant="ghost").pack(side=tk.LEFT)
        HButton(btn_row, "🗑 Limpiar DB",
                command=self._clear_db,
                variant="danger").pack(side=tk.LEFT, padx=(8, 0))

    def _open_folder(self, path: str) -> None:
        import subprocess, os
        try:
            os.makedirs(path, exist_ok=True)
            subprocess.Popen(f'explorer "{path}"')
        except Exception:
            pass

    def _clear_db(self) -> None:
        if messagebox.askyesno("Confirmar",
                "¿Eliminar TODOS los datos de la base de datos?"):
            import database
            database.DB_PATH.unlink(missing_ok=True)
            database.init_db()
            messagebox.showinfo("Limpiado",
                "Base de datos reiniciada.\n"
                "Reinicia la aplicación para ver los cambios.")

    # ══════════════════════════════════════════════════════════════════════════
    # PANEL LOGS
    # ══════════════════════════════════════════════════════════════════════════
    def _build_logs_panel(self) -> None:
        p = self._panels["logs"]
        inner = self._scrollable(p)
        self._ph(inner, "Logs del Sistema",
                 "Registro de eventos y transmisiones de HAMNA Desktop")
        body = self._card(inner, "Log reciente", "📋")

        self._log_text = tk.Text(body, height=14,
                                  bg=C["input_bg"], fg=C["success"],
                                  font=FONTS["mono"], relief="flat",
                                  state="disabled", padx=8, pady=6)
        self._log_text.pack(fill=tk.X)

        btn_row = tk.Frame(body, bg=C["surface"])
        btn_row.pack(fill=tk.X, pady=(8, 0))
        HButton(btn_row, "Limpiar log",
                command=self._clear_log,
                variant="danger").pack(side=tk.LEFT)
        HButton(btn_row, "↺ Actualizar",
                command=self.refresh_logs,
                variant="ghost").pack(side=tk.LEFT, padx=(6, 0))
        self.refresh_logs()

    def refresh_logs(self) -> None:
        """Carga los últimos registros del log de Python."""
        import logging
        self._log_text.config(state="normal")
        self._log_text.delete("1.0", tk.END)
        self._log_text.insert(tk.END,
            "[Sistema] HAMNA Desktop iniciado\n"
            "[Base de datos] hamna.db cargada\n")
        self._log_text.config(state="disabled")

    def append_log(self, msg: str) -> None:
        self._log_text.config(state="normal")
        self._log_text.insert(tk.END, msg + "\n")
        self._log_text.see(tk.END)
        self._log_text.config(state="disabled")

    def _clear_log(self) -> None:
        self._log_text.config(state="normal")
        self._log_text.delete("1.0", tk.END)
        self._log_text.config(state="disabled")

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _ph(self, parent: tk.Frame, title: str, sub: str = "") -> None:
        """Page header."""
        hdr = tk.Frame(parent, bg=C["bg"], padx=18, pady=14)
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text=title, font=FONTS["h2"],
                 bg=C["bg"], fg=C["text"]).pack(anchor="w")
        if sub:
            tk.Label(hdr, text=sub, font=FONTS["small"],
                     bg=C["bg"], fg=C["text2"]).pack(anchor="w", pady=(2, 0))
        tk.Frame(parent, bg=C["border"], height=1).pack(
            fill=tk.X, padx=0, pady=(0, 12))
