"""
HAMNA Desktop — Ventana Principal
Orquesta todas las vistas, la barra NP y el motor de transmisión.
"""
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import logging
from pathlib import Path

log = logging.getLogger(__name__)
import database as db
import settings as cfg_mod
from ui_theme import C, FONTS, HButton, apply_theme
from modules.ptt.ptt_manager import PTTManager
from modules.audio.audio_player import AudioPlayer
from modules.asl.asl_player import ASLPlayer
from views.np_bar import NPBar
from views.view_eventos import ViewEventos
from views.view_secciones import ViewSecciones
from views.view_programacion import ViewProgramacion
from views.view_ajustes import ViewAjustes


class MainWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("HAMNA Desktop")
        self.geometry("1200x720")
        self.minsize(960, 600)
        self.configure(bg=C["bg"])
        apply_theme(self)

        # Inicializar
        db.init_db()
        self.cfg        = cfg_mod.load()
        self.ptt          = PTTManager(self.cfg)
        self._player       = AudioPlayer(alias="hamna_main")
        self._pause_player = AudioPlayer(alias="hamna_pause", use_subprocess=True)
        self._asl: ASLPlayer | None = None

        # Estado de transmisión
        self._tx_evento_id: int | None = None
        self._tx_secciones: list      = []
        self._tx_cur_sec:   int       = 0
        self._tx_elapsed:   float     = 0.0
        self._tx_sec_elapsed: float   = 0.0
        self._tx_total_dur: float     = 0.0
        self._tx_playing:   bool      = False
        self._tx_thread:    threading.Thread | None = None
        self._tx_lock       = threading.Lock()
        self._tx_stop_flag  = False

        # Estado de pausa automática
        # "tx" | "pausing" | "paused" | "resuming"
        self._tx_pause_state     = "tx"
        self._tx_seg_elapsed     = 0.0    # tiempo desde el último reset de pausa
        self._tx_alert_played    = False
        self._tx_pause_remaining = 0.0
        self._tx_section_start_ms = 0     # offset dentro de la sección actual

        self._build()
        self._center()
        self._sched_fired: set[int] = set()   # ids ya disparados en este minuto
        self._check_schedule()

    # ── Build ─────────────────────────────────────────────────────────────────
    def _build(self) -> None:
        self._build_header()
        self._build_nav()
        # Statusbar al fondo (debe empaquetarse antes del área expand=True)
        self._build_statusbar()
        # PanedWindow vertical: vistas arriba, reproductor abajo
        self._v_paned = tk.PanedWindow(self, orient=tk.VERTICAL,
                                        bg=C["border"], sashwidth=4,
                                        sashrelief="flat", bd=0)
        self._v_paned.pack(fill=tk.BOTH, expand=True)
        self._build_views()
        self._build_np_bar()

    def _build_header(self) -> None:
        hf = tk.Frame(self, bg=C["header"], height=50)
        hf.pack(fill=tk.X)
        hf.pack_propagate(False)
        tk.Label(hf, text="📻", font=("Segoe UI", 20),
                 bg=C["header"]).pack(side=tk.LEFT, padx=(16, 6))
        tk.Label(hf, text="HAMNA Desktop",
                 font=FONTS["h1"], bg=C["header"],
                 fg=C.get("header_fg", C["text"])).pack(side=tk.LEFT)
        tk.Label(hf, text="Amateur Radio Net Automation System",
                 font=FONTS["small"], bg=C["header"],
                 fg=C.get("header_fg", C["text2"])).pack(side=tk.LEFT, padx=(10, 0))

        # Logo FMRE A.C. al lado derecho
        try:
            from PIL import Image, ImageTk
            from pathlib import Path
            logo_path = Path(__file__).parent / "media" / "fmre_logo.png"
            if logo_path.is_file():
                img = Image.open(logo_path).convert("RGBA")
                img = img.resize((40, 40), Image.LANCZOS)
                self._fmre_img = ImageTk.PhotoImage(img)
                tk.Label(hf, image=self._fmre_img,
                         bg=C["header"]).pack(side=tk.RIGHT, padx=(0, 16))
        except Exception:
            pass

        tk.Frame(self, bg=C["border"], height=1).pack(fill=tk.X)

    def _build_nav(self) -> None:
        nav = tk.Frame(self, bg=C["surface"], height=38)
        nav.pack(fill=tk.X)
        nav.pack_propagate(False)
        tk.Frame(self, bg=C["border"], height=1).pack(fill=tk.X)

        self._nav_btns: dict[str, tuple] = {}
        self._badge_vars: dict[str, tk.StringVar] = {}
        self._active_tab: str = ""

        tabs_left = [
            ("secciones", "🎵  Secciones"),
            ("eventos",   "📂  Eventos"),
            ("prog",      "📅  Programación"),
        ]
        tabs_right = [
            ("settings",  "⚙  Ajustes"),
        ]

        def _sep(side=tk.LEFT):
            tk.Frame(nav, bg=C["border"], width=1).pack(
                side=side, fill=tk.Y, pady=5)

        def _make_tab(key, lbl, side):
            f = tk.Frame(nav, bg=C["surface"])
            f.pack(side=side)
            btn = tk.Label(f, text=lbl, font=FONTS["body"],
                           bg=C["surface"], fg=C["text2"],
                           padx=16, pady=7, cursor="hand2")
            btn.pack(side=tk.LEFT)
            btn.bind("<Button-1>", lambda _, k=key: self._switch_tab(k))
            btn.bind("<Enter>",    lambda _, b=btn, k=key:
                     b.config(fg=C["accent"] if self._active_tab == k else C["text"]))
            btn.bind("<Leave>",    lambda _, b=btn, k=key:
                     b.config(fg=C["accent"] if self._active_tab == k else C["text2"]))
            indicator = tk.Frame(f, bg=C["surface"], height=3)
            indicator.pack(fill=tk.X)
            self._nav_btns[key] = (btn, indicator)

        for i, (key, lbl) in enumerate(tabs_left):
            if i > 0:
                _sep(tk.LEFT)
            _make_tab(key, lbl, tk.LEFT)

        _sep(tk.RIGHT)           # separa Ajustes del grupo izquierdo
        for key, lbl in tabs_right:
            _make_tab(key, lbl, tk.RIGHT)

        # Badge de programación
        bv = tk.StringVar(value="0")
        self._badge_vars["prog"] = bv

    def _build_views(self) -> None:
        self._view_container = tk.Frame(self._v_paned, bg=C["bg"])
        self._v_paned.add(self._view_container, minsize=200, stretch="always")

        self._views: dict[str, tk.Frame] = {}

        self._views["eventos"] = ViewEventos(
            self._view_container,
            cfg=self.cfg,
            on_transmitir=self._start_transmision)

        self._views["secciones"] = ViewSecciones(
            self._view_container,
            cfg=self.cfg)

        self._views["prog"] = ViewProgramacion(
            self._view_container,
            on_transmitir=self._start_transmision)

        self._views["settings"] = ViewAjustes(
            self._view_container,
            cfg=self.cfg,
            ptt_manager=self.ptt,
            on_cfg_saved=self._on_cfg_saved)

        self._switch_tab("secciones")

    def _build_np_bar(self) -> None:
        np_pane = tk.Frame(self._v_paned, bg=C["bg"])
        self._v_paned.add(np_pane, minsize=110, height=175, stretch="never")
        self._np = NPBar(
            np_pane,
            on_play     = self._tx_resume,
            on_pause    = self._tx_pause,
            on_stop     = self._tx_stop,
            on_prev_sec = self._tx_prev_sec,
            on_next_sec = self._tx_next_sec,
            on_rw       = lambda: self._tx_seek_rel(-10),
            on_ff       = lambda: self._tx_seek_rel(10),
            on_seek     = self._tx_seek_pct,
            on_volume   = self._player.set_volume,
            on_jump_sec = self._tx_jump_sec,
        )
        self._np.pack(fill=tk.BOTH, expand=True)

    def _build_statusbar(self) -> None:
        tk.Frame(self, bg=C["border"], height=1).pack(fill=tk.X, side=tk.BOTTOM)
        sb = tk.Frame(self, bg=C["surface"], height=22)
        sb.pack(fill=tk.X, side=tk.BOTTOM)
        sb.pack_propagate(False)
        self._status_lbl = tk.Label(sb, text="Listo",
            font=FONTS["small"], bg=C["surface"], fg=C["text2"])
        self._status_lbl.pack(side=tk.LEFT, padx=12)

        tk.Label(sb, text="HAMNA Desktop v1.1.0  |  by Radio Club Guadiana A.C.",
                 font=FONTS["small"], bg=C["surface"],
                 fg=C["text3"]).pack(side=tk.RIGHT, padx=(0, 12))

        tk.Label(sb, text="|", font=FONTS["small"],
                 bg=C["surface"], fg=C["border"]).pack(side=tk.RIGHT, padx=4)

        self._lbl_utc = tk.Label(sb, text="", font=FONTS["small"],
                                  bg=C["surface"], fg=C["text3"])
        self._lbl_utc.pack(side=tk.RIGHT)

        tk.Label(sb, text="UTC:", font=FONTS["small"],
                 bg=C["surface"], fg=C["text3"]).pack(side=tk.RIGHT, padx=(8, 2))

        tk.Label(sb, text="|", font=FONTS["small"],
                 bg=C["surface"], fg=C["border"]).pack(side=tk.RIGHT, padx=4)

        self._lbl_local = tk.Label(sb, text="", font=FONTS["small"],
                                    bg=C["surface"], fg=C["text2"])
        self._lbl_local.pack(side=tk.RIGHT)

        tk.Label(sb, text="Local:", font=FONTS["small"],
                 bg=C["surface"], fg=C["text3"]).pack(side=tk.RIGHT, padx=(8, 2))

        self._tick_clock()

    def _tick_clock(self) -> None:
        from datetime import datetime, timezone
        now_local = datetime.now()
        now_utc   = datetime.now(timezone.utc)
        self._lbl_local.config(text=now_local.strftime("%Y-%m-%d  %H:%M:%S"))
        self._lbl_utc.config(  text=now_utc.strftime(  "%Y-%m-%d  %H:%M:%S"))
        self.after(1000, self._tick_clock)

    def _check_schedule(self) -> None:
        """Revisa cada 15 s si hay un evento programado para iniciar ahora."""
        from datetime import datetime
        now   = datetime.now()
        today = now.strftime("%Y-%m-%d")
        hhmm  = now.strftime("%H:%M")
        dow   = now.weekday()          # 0=lun … 6=dom

        try:
            schedule = db.get_all_programacion()
        except Exception as e:
            log.error("Error leyendo programacion: %s", e)
            self.after(15_000, self._check_schedule)
            return

        # Limpiar disparos de minutos anteriores
        current_min_keys = {
            (r["id"], today, hhmm) for r in schedule
        }
        self._sched_fired = {k for k in self._sched_fired
                             if k in current_min_keys}

        for row in schedule:
            rec   = (row["recurrencia"] or "ninguna").lower()
            fecha = row["fecha"] or ""
            hora  = row["hora"]  or ""

            # ¿Corresponde hoy?
            if rec == "ninguna":
                if fecha != today:
                    continue
            elif rec == "diaria":
                pass  # siempre aplica
            elif rec == "semanal":
                # mismo día de la semana que la fecha original
                try:
                    orig_dow = datetime.strptime(fecha, "%Y-%m-%d").weekday()
                    if dow != orig_dow:
                        continue
                except ValueError:
                    continue
            elif rec == "lun-vie":
                if dow > 4:   # sab=5, dom=6
                    continue
            else:
                continue

            # ¿Coincide el HH:MM?
            if hora[:5] != hhmm:
                continue

            fire_key = (row["id"], today, hhmm)
            if fire_key in self._sched_fired:
                continue   # ya lo disparamos este minuto

            self._sched_fired.add(fire_key)
            ev_id = row["evento_id"]
            log.info("Scheduler: iniciando evento id=%d '%s' a las %s",
                     ev_id, row["evento_nombre"], hhmm)
            # No iniciar si ya está transmitiendo el mismo evento
            if not self._tx_playing or self._tx_evento_id != ev_id:
                self._start_transmision(ev_id)

        self.after(15_000, self._check_schedule)

    # ── Navegación ────────────────────────────────────────────────────────────
    def _switch_tab(self, key: str) -> None:
        self._active_tab = key
        for k, view in self._views.items():
            view.pack_forget()
        self._views[key].pack(fill=tk.BOTH, expand=True)

        for k, (btn, ind) in self._nav_btns.items():
            active = (k == key)
            btn.config(
                fg=C["accent"] if active else C["text2"],
                font=(*FONTS["body"], "bold") if active else FONTS["body"])
            ind.config(bg=C["accent"] if active else C["surface"])

        if key == "prog":
            self._views["prog"].load_data()

    # ── Motor de transmisión ──────────────────────────────────────────────────
    def _start_transmision(self, evento_id: int) -> None:
        from modules.tts.tts_manager import get_audio_duration

        raw_secs = db.get_secciones_by_evento(evento_id)
        if not raw_secs:
            messagebox.showinfo("Sin secciones",
                "Este evento no tiene secciones.")
            return

        # Convertir a dicts y rellenar duraciones faltantes desde el archivo
        secs = []
        for sec in raw_secs:
            s = dict(sec)
            if s["duracion"] <= 0 and s["ruta_archivo"] \
                    and Path(s["ruta_archivo"]).is_file():
                dur = get_audio_duration(s["ruta_archivo"])
                if dur > 0:
                    s["duracion"] = dur
                    db.update_seccion(s["id"], s["nombre"], duracion=dur)
            secs.append(s)

        # Detener transmisión anterior si existe
        self._tx_stop(silent=True)

        # Inicializar/reinicializar ASLPlayer si está habilitado
        if self.cfg.get("asl_enabled", False):
            self._asl = ASLPlayer.from_cfg(self.cfg)
            log.info("ASL habilitado — nodo %s", self.cfg.get("asl_node", ""))
        else:
            self._asl = None

        self._tx_evento_id       = evento_id
        self._tx_secciones       = secs
        self._tx_cur_sec         = 0
        self._tx_elapsed         = 0.0
        self._tx_sec_elapsed     = 0.0
        self._tx_total_dur       = sum(s["duracion"] for s in secs)
        self._tx_playing         = True
        self._tx_stop_flag       = False
        self._tx_pause_state      = "tx"
        self._tx_seg_elapsed      = 0.0
        self._tx_alert_played     = False
        self._tx_pause_remaining  = 0.0
        self._tx_resume_ms        = 0
        self._tx_section_start_ms = 0

        # PTT ON → retardo configurable → audio
        self.ptt.ptt_on()
        self._np.set_ptt_state(True)
        ptt_ms = self._ptt_delay_ms()
        if ptt_ms > 0:
            self.after(ptt_ms, self._play_current_section)
            self.after(ptt_ms, self._tx_tick)
        else:
            self._play_current_section()
            self._tx_tick()

        # Actualizar vistas y NP bar inmediatamente (sin esperar _tx_tick)
        self._views["eventos"].update_on_air(evento_id)
        self._views["prog"].update_on_air(evento_id)
        ev = next((e for e in db.get_all_eventos()
                   if e["id"] == evento_id), None)
        name = ev["nombre"] if ev else str(evento_id)
        self._np.set_on_air(
            evento_nombre  = name,
            seccion_nombre = secs[0]["nombre"] if secs else "",
            elapsed        = 0.0,
            total          = self._tx_total_dur,
            cur_sec        = 0,
            num_secs       = len(secs),
            sec_names      = [s["nombre"] for s in secs],
            sec_elapsed    = 0.0,
            sec_total      = secs[0]["duracion"] if secs else 0.0,
        )
        self._set_status(f"📡 Transmitiendo: {name}")

    def _play_current_section(self) -> None:
        if self._tx_cur_sec >= len(self._tx_secciones):
            return
        sec = self._tx_secciones[self._tx_cur_sec]

        # Si la sección pide regenerar antes de transmitir, hacerlo ahora
        if sec.get("regenerar_antes") and sec.get("texto_tts"):
            self._regenerar_y_reproducir(sec)
            return

        if sec["ruta_archivo"]:
            if Path(sec["ruta_archivo"]).is_file():
                self._tx_section_start_ms = 0
                self._player.play(
                    sec["ruta_archivo"],
                    on_finished=lambda: self.after(0, self._on_sec_audio_finished)
                )
                self._asl_play(sec["ruta_archivo"], sec["duracion"])

    def _regenerar_y_reproducir(self, sec: dict) -> None:
        """Regenera el TTS de la sección con variables actuales y luego la reproduce."""
        from modules.tts.tts_manager import convert_text

        ev = next((e for e in db.get_all_eventos()
                   if e["id"] == self._tx_evento_id), None)
        ctx = {}
        if ev:
            secs  = self._tx_secciones
            dur_t = sum(s["duracion"] or 0 for s in secs)
            m, s2 = divmod(int(dur_t), 60)
            num_cont  = sum(1 for s in secs if s.get("contabilizable", 1))
            dur_cont  = sum(s["duracion"] or 0 for s in secs
                            if s.get("contabilizable", 1))
            dc_m, dc_s = divmod(int(dur_cont), 60)
            ctx = {
                "evento":            ev["nombre"],
                "num_secciones":     str(num_cont),
                "duracion_total":    f"{m} minutos con {s2} segundos" if s2
                                     else f"{m} minutos",
                "dur_contabilizable": f"{dc_m} minutos con {dc_s} segundos" if dc_s
                                      else f"{dc_m} minutos",
            }

        # Siempre escribir a un archivo regen separado para evitar bloquear
        # el archivo original (puede estar bloqueado por OneDrive o por el player)
        out = Path("media/audios") / f"regen_{sec['id']}.mp3"

        # Deshabilitar avance por timer durante la generación TTS:
        # duracion=0 impide que _tx_tick_body avance la sección mientras el
        # hilo TTS trabaja. on_done restaura la duración real al terminar.
        _prev_dur = sec["duracion"]
        sec["duracion"] = 0
        if self._tx_cur_sec < len(self._tx_secciones):
            self._tx_secciones[self._tx_cur_sec]["duracion"] = 0

        def on_done(ok: bool, result: str) -> None:
            # on_done viene de un hilo de fondo — usar after(0) para ejecutar
            # todo en el hilo principal de Tkinter y evitar condiciones de carrera
            # con _tx_tick y con el subsistema de audio de Windows.
            def _apply() -> None:
                if not self._tx_playing or self._tx_stop_flag:
                    return
                if ok:
                    from modules.tts.tts_manager import get_audio_duration
                    dur = get_audio_duration(result)
                    if dur > 0:
                        sec["duracion"] = dur
                        if self._tx_cur_sec < len(self._tx_secciones):
                            self._tx_secciones[self._tx_cur_sec]["duracion"] = dur
                    self._tx_sec_elapsed      = 0.0
                    self._tx_section_start_ms = 0
                    self._player.play(
                        result,
                        on_finished=lambda: self.after(0, self._on_sec_audio_finished)
                    )
                    self._asl_play(result, dur if dur > 0 else 0)
                else:
                    log.error("Regeneración TTS falló: %s — reproduciendo versión guardada", result)
                    if sec.get("ruta_archivo") and Path(sec["ruta_archivo"]).is_file():
                        sec["duracion"] = _prev_dur
                        if self._tx_cur_sec < len(self._tx_secciones):
                            self._tx_secciones[self._tx_cur_sec]["duracion"] = _prev_dur
                        self._tx_sec_elapsed = 0.0
                        self._player.play(
                            sec["ruta_archivo"],
                            on_finished=lambda: self.after(0, self._on_sec_audio_finished)
                        )
                    else:
                        self.after(0, self._on_sec_audio_finished)

            self.after(0, _apply)

        convert_text(sec["texto_tts"], self.cfg, out, on_done=on_done, ctx=ctx)

    def _on_sec_audio_finished(self) -> None:
        """Llamado por el reproductor cuando un archivo termina naturalmente.
        Siempre avanza a la siguiente sección: PTT OFF → gap → PTT ON → siguiente."""
        if not self._tx_playing or self._tx_stop_flag:
            return
        self._advance_section()

    def _advance_section(self) -> None:
        """Avanza a la siguiente sección con pausa breve + PTT OFF entre ellas."""
        # No interrumpir si la pausa automática está activa o ya hay un gap en curso
        if self._tx_pause_state in ("pausing", "paused", "section_gap"):
            log.debug("_advance_section ignorado — pause_state=%s", self._tx_pause_state)
            return
        if self._tx_cur_sec < len(self._tx_secciones) - 1:
            self._tx_cur_sec     += 1
            self._tx_sec_elapsed  = 0.0
            self._tx_pause_state  = "section_gap"
            # PTT OFF durante el intervalo entre secciones
            self.ptt.ptt_off()
            self._np.set_ptt_state(False)
            self._views["eventos"].mark_active_section(self._tx_cur_sec)
            gap_ms = int(float(self.cfg.get("pause_duration", 10)) * 1000)
            self.after(gap_ms, self._start_next_section)
        else:
            self._tx_stop()

    def _start_next_section(self) -> None:
        """Tras el intervalo entre secciones: PTT ON → retardo → audio."""
        if self._tx_stop_flag:
            return
        self._tx_sec_elapsed  = 0.0
        self._tx_seg_elapsed  = 0.0   # reiniciar contador de pausa al iniciar nueva sección
        self._tx_alert_played = False
        self._tx_pause_state  = "tx"
        self.ptt.ptt_on()
        self._np.set_ptt_state(True)
        ptt_ms = self._ptt_delay_ms()
        if ptt_ms > 0:
            self.after(ptt_ms, self._play_current_section)
        else:
            self._play_current_section()

    def _tx_tick(self) -> None:
        """Tick de 250ms — actualiza progreso y avanza sección (si tiene duración)."""
        if not self._tx_playing or self._tx_stop_flag:
            return

        try:
            self._tx_tick_body()
        except Exception as e:
            log.error("Error en _tx_tick: %s", e, exc_info=True)
            self.after(250, self._tx_tick)

    def _tx_tick_body(self) -> None:
        TICK = 0.25

        # Durante intervalo entre secciones: solo programar el siguiente tick
        if self._tx_pause_state == "section_gap":
            self.after(250, self._tx_tick)
            return

        self._tx_sec_elapsed += TICK

        # ── Lógica de pausa automática ──────────────────────────────────────
        if self.cfg.get("pause_enabled", False) and self._tx_pause_state == "tx":
            self._tx_seg_elapsed += TICK
            pause_tx_time = float(self.cfg.get("pause_tx_time", 120))
            alert_before  = float(self.cfg.get("pause_alert_before", 10))

            if not self._tx_alert_played and alert_before > 0:
                if self._tx_seg_elapsed >= pause_tx_time - alert_before:
                    self._tx_alert_played = True
                    alert_file = self.cfg.get("pause_alert_file", "")
                    if alert_file and Path(alert_file).is_file():
                        # Alerta: subprocess con pygame, no interrumpe el evento
                        self._pause_player.play(alert_file)

            if self._tx_seg_elapsed >= pause_tx_time:
                self._begin_pause_sequence()
                return  # el ciclo se reanuda en _on_resume_announced

            # Mostrar cuenta regresiva hasta pausa en NPBar (formato: "restante / total")
            secs_left = max(0.0, pause_tx_time - self._tx_seg_elapsed)
            self._np.set_pause_info(
                f"{int(secs_left)} / {int(pause_tx_time)}", None)
        # ────────────────────────────────────────────────────────────────────

        cur_sec = (self._tx_secciones[self._tx_cur_sec]
                   if self._tx_cur_sec < len(self._tx_secciones) else None)

        # Usar posición real del reproductor (posición absoluta en la sección)
        pos_ms = self._player.get_pos_ms()
        if pos_ms > 0 and cur_sec and cur_sec["duracion"] > 0:
            self._tx_sec_elapsed = (self._tx_section_start_ms + pos_ms) / 1000.0

        # Calcular elapsed total: duraciones de secciones anteriores + posición actual
        acc = sum(s["duracion"] for s in self._tx_secciones[:self._tx_cur_sec])
        self._tx_elapsed = acc + self._tx_sec_elapsed
        if self._tx_total_dur > 0:
            self._tx_elapsed = min(self._tx_elapsed, self._tx_total_dur)

        # Actualizar barra NP (siempre, antes de evaluar avance)
        sec_names = [s["nombre"] for s in self._tx_secciones]
        ev = next((e for e in db.get_all_eventos()
                   if e["id"] == self._tx_evento_id), None)

        self._np.set_on_air(
            evento_nombre  = ev["nombre"] if ev else "",
            seccion_nombre = cur_sec["nombre"] if cur_sec else "",
            elapsed        = self._tx_elapsed,
            total          = self._tx_total_dur,
            cur_sec        = self._tx_cur_sec,
            num_secs       = len(self._tx_secciones),
            sec_names      = sec_names,
            sec_elapsed    = self._tx_sec_elapsed,
            sec_total      = cur_sec["duracion"] if cur_sec else 0.0,
        )
        self._np.set_playing(self._tx_playing)

        # Avanzar sección por timer solo si tiene duración conocida (>0)
        # y no hay una secuencia de pausa activa
        if self._tx_pause_state == "tx" \
                and cur_sec and cur_sec["duracion"] > 0 \
                and self._tx_sec_elapsed >= cur_sec["duracion"]:
            self._advance_section()
            if self._tx_stop_flag:
                return

        # Programar próximo tick
        self.after(250, self._tx_tick)

    def _tx_pause(self) -> None:
        self._tx_playing = False
        self._player.pause()
        self._np.set_playing(False)
        try:
            ok, msg = self.ptt.ptt_off()
            log.info("PTT OFF (pausa manual) — ok=%s msg=%s", ok, msg)
        except Exception as e:
            log.error("Error enviando PTT OFF en pausa: %s", e)
        self._np.set_ptt_state(False)
        self._set_status("En pausa")

    def _tx_resume(self) -> None:
        self._tx_playing = True
        self.ptt.ptt_on()
        self._np.set_ptt_state(True)
        self._player.resume()
        self._np.set_playing(True)
        self._tx_tick()
        self._set_status("Transmitiendo...")

    def _ptt_delay_ms(self) -> int:
        """Retardo en ms entre PTT ON y el inicio del audio (configurado en Ajustes)."""
        return max(0, int(float(self.cfg.get("ptt_on_delay", 0)) * 1000))

    def _tx_stop(self, silent: bool = False) -> None:
        self._tx_stop_flag   = True
        self._tx_playing     = False
        self._tx_pause_state = "tx"
        self._player.stop()
        if self._asl:
            self._asl.stop()

        # PTT OFF
        self.ptt.ptt_off()
        self._np.set_ptt_state(False)

        ev_id = self._tx_evento_id
        self._tx_evento_id = None
        self._np.set_off_air()
        self._views["eventos"].update_on_air(None)
        self._views["prog"].update_on_air(None)
        if not silent:
            self._set_status("Transmisión detenida")

    def _tx_seek_rel(self, secs: float) -> None:
        """Adelanta/retrocede N segundos."""
        new_elapsed = max(0, min(self._tx_total_dur,
                                  self._tx_elapsed + secs))
        self._tx_seek_to(new_elapsed)

    def _tx_seek_pct(self, pct: float) -> None:
        """Salta a una posición proporcional (0–1)."""
        self._tx_seek_to(pct * self._tx_total_dur)

    def _tx_seek_to(self, target: float) -> None:
        self._tx_elapsed = target
        # Recalcular sección actual
        acc = 0.0
        for i, sec in enumerate(self._tx_secciones):
            if target < acc + sec["duracion"]:
                self._tx_cur_sec     = i
                self._tx_sec_elapsed = target - acc
                break
            acc += sec["duracion"]
        self._play_current_section()

    def _tx_jump_sec(self, idx: int) -> None:
        """Salta directamente a la sección idx."""
        acc = sum(s["duracion"] for s in self._tx_secciones[:idx])
        self._tx_cur_sec     = idx
        self._tx_sec_elapsed = 0.0
        self._tx_elapsed     = acc
        self._play_current_section()

    def _tx_prev_sec(self) -> None:
        if self._tx_sec_elapsed > 3:
            self._tx_jump_sec(self._tx_cur_sec)
        elif self._tx_cur_sec > 0:
            self._tx_jump_sec(self._tx_cur_sec - 1)

    def _tx_next_sec(self) -> None:
        if self._tx_cur_sec < len(self._tx_secciones) - 1:
            self._tx_jump_sec(self._tx_cur_sec + 1)

    # ── Secuencia de pausa automática ─────────────────────────────────────────
    def _begin_pause_sequence(self) -> None:
        """Detiene el reproductor (libera MCI) y reproduce el anuncio de pausa.
        PTT permanece ON mientras se reproduce el anuncio; se apaga al terminar."""
        from modules.tts.tts_manager import get_audio_duration
        self._tx_pause_state = "pausing"
        # Posición absoluta = offset de inicio + tiempo reproducido desde ese inicio
        self._tx_resume_ms = self._tx_section_start_ms + self._player.get_pos_ms()
        log.info("Pausa automática — posición guardada: %d ms", self._tx_resume_ms)
        # Detener (no sólo pausar) para liberar el dispositivo MCI mpegvideo
        self._player.stop()
        # PTT sigue ON — se apagará en _finish_pause_announcement
        self._np.set_playing(False)
        self._set_status("Pausa automática — anunciando…")

        delay_ms = 0
        ann_file = self.cfg.get("pause_announcement_file", "")
        log.info("Anuncio de pausa: '%s' — existe=%s", ann_file, Path(ann_file).is_file() if ann_file else False)
        if ann_file and Path(ann_file).is_file():
            ok, msg = self._player.play(ann_file)
            log.info("play(anuncio_pausa) → ok=%s msg=%s", ok, msg)
            dur = get_audio_duration(ann_file)
            delay_ms = int(dur * 1000) + 400 if dur > 0 else 1000
            log.info("Duración anuncio pausa: %.2fs — espera %dms", dur, delay_ms)
        else:
            log.warning("Archivo de anuncio de pausa no encontrado: '%s'", ann_file)

        self.after(delay_ms, self._finish_pause_announcement)

    def _finish_pause_announcement(self) -> None:
        """Tras el anuncio de pausa: PTT OFF y comenzar cuenta regresiva."""
        if self._tx_stop_flag:
            return
        # Si la secuencia de pausa fue interrumpida (p.ej. por avance de sección),
        # no ejecutar PTT OFF ni iniciar la espera.
        if self._tx_pause_state != "pausing":
            log.debug("_finish_pause_announcement ignorado — pause_state=%s", self._tx_pause_state)
            return
        self._player.stop()  # detener anuncio, liberar MCI
        self.ptt.ptt_off()
        self._np.set_ptt_state(False)
        self._start_pause_wait()

    def _start_pause_wait(self) -> None:
        """Comienza la cuenta regresiva de la pausa."""
        if self._tx_stop_flag:
            return
        self._tx_pause_state     = "paused"
        self._tx_pause_remaining = float(self.cfg.get("pause_duration", 30))
        self._set_status(f"En pausa — {int(self._tx_pause_remaining)}s restantes")
        self._np.set_pause_info(None, str(int(self._tx_pause_remaining)))
        self.after(1000, self._tx_pause_tick)

    def _tx_pause_tick(self) -> None:
        """Cuenta regresiva durante la pausa automática (cada 1 segundo)."""
        if self._tx_stop_flag or self._tx_pause_state != "paused":
            return
        self._tx_pause_remaining -= 1
        if self._tx_pause_remaining > 0:
            self._set_status(f"En pausa — {int(self._tx_pause_remaining)}s restantes")
            self._np.set_pause_info(None, str(int(self._tx_pause_remaining)))
            self.after(1000, self._tx_pause_tick)
        else:
            self._np.set_pause_info(None, "0")
            self._end_pause_sequence()

    def _end_pause_sequence(self) -> None:
        """PTT ON → retardo configurable → anuncio de regreso → reanuda evento."""
        self._tx_pause_state = "resuming"
        self.ptt.ptt_on()
        self._np.set_ptt_state(True)
        self._set_status("Reanudando transmisión — anunciando…")
        self._np.set_pause_info(None, "▶")
        self.after(self._ptt_delay_ms(), self._play_resume_announcement)

    def _play_resume_announcement(self) -> None:
        """Reproduce el anuncio de continuamos y programa la reanudación del evento."""
        if self._tx_stop_flag:
            return
        from modules.tts.tts_manager import get_audio_duration
        delay_ms = 0
        res_file = self.cfg.get("pause_resume_file", "")
        log.info("Anuncio de continuamos: '%s' — existe=%s",
                 res_file, Path(res_file).is_file() if res_file else False)
        if res_file and Path(res_file).is_file():
            ok, msg = self._player.play(res_file)
            log.info("play(anuncio_continuamos) → ok=%s msg=%s", ok, msg)
            dur = get_audio_duration(res_file)
            delay_ms = int(dur * 1000) + 400 if dur > 0 else 1000
            log.info("Duración anuncio continuamos: %.2fs — espera %dms", dur, delay_ms)
        else:
            log.warning("Archivo anuncio continuamos no encontrado: '%s'", res_file)
        self.after(delay_ms, self._on_resume_announced)

    def _on_resume_announced(self) -> None:
        """Detiene el anuncio y reanuda el evento desde la posición guardada."""
        if self._tx_stop_flag:
            return
        self._player.stop()  # detener anuncio de regreso, liberar MCI
        # Reanudar sección desde la posición en que se pausó
        cur_sec = (self._tx_secciones[self._tx_cur_sec]
                   if self._tx_cur_sec < len(self._tx_secciones) else None)
        # Establecer estado tx ANTES de play para que la callback
        # _on_sec_audio_finished no se encuentre en estado "resuming"
        self._tx_pause_state  = "tx"
        self._tx_seg_elapsed  = 0.0
        if cur_sec and cur_sec.get("ruta_archivo") and \
                Path(cur_sec["ruta_archivo"]).is_file():
            cb = lambda: self.after(0, self._on_sec_audio_finished)

            # Calcular posición de reanudación aplicando retroceso si está activo
            resume_ms = self._tx_resume_ms
            if self.cfg.get("retroceso_enabled", False) and resume_ms > 0:
                rewind_ms = int(float(self.cfg.get("retroceso_secs", 5)) * 1000)
                resume_ms = max(0, resume_ms - rewind_ms)
                log.info("Retroceso: %d ms — reanudando desde %d ms (antes: %d ms)",
                         rewind_ms, resume_ms, self._tx_resume_ms)

            if resume_ms > 0:
                self._tx_section_start_ms = resume_ms
                self._tx_sec_elapsed      = resume_ms / 1000.0
                self._player.play_from_ms(cur_sec["ruta_archivo"],
                                          resume_ms, on_finished=cb)
            else:
                self._tx_section_start_ms = 0
                self._tx_sec_elapsed      = 0.0
                self._player.play(cur_sec["ruta_archivo"], on_finished=cb)
        self._tx_alert_played = False
        self._tx_playing      = True
        self._np.set_playing(True)
        self._np.set_pause_info(None, None)
        self._set_status("Transmitiendo…")
        self._tx_tick()  # reanudar el loop de tick

    # ── ASL helper ────────────────────────────────────────────────────────────
    def _asl_play(self, filepath: str, duration: float) -> None:
        """Envía el audio al nodo ASL en paralelo con el reproductor local."""
        if not self._asl:
            return

        def _on_asl_status(status: str, msg: str) -> None:
            log.info("[ASL] status=%s  %s", status, msg)

        self._asl.on_status = _on_asl_status
        ok, msg = self._asl.play(filepath, duration)
        log.info("[ASL] play iniciado — ok=%s  %s", ok, msg)

    # ── Callbacks ─────────────────────────────────────────────────────────────
    def _on_cfg_saved(self, new_cfg: dict) -> None:
        self.cfg = new_cfg
        self.ptt.reload_cfg(new_cfg)

    def _set_status(self, msg: str) -> None:
        self._status_lbl.config(text=msg)

    # ── Utilidades ────────────────────────────────────────────────────────────
    def _center(self) -> None:
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        sw   = self.winfo_screenwidth()
        sh   = self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

    def on_close(self) -> None:
        if self._tx_playing and self.cfg.get("confirm_close", True):
            if not messagebox.askyesno("Cerrar",
                    "Hay una transmisión activa. ¿Cerrar de todas formas?"):
                return
        self._tx_stop(silent=True)
        # PTT OFF de seguridad a TODOS los métodos antes de desconectar
        self.ptt.ptt_off_all()
        self.ptt.serial.disconnect()
        self.ptt.ami.disconnect()
        self.destroy()
