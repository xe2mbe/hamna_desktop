"""
HAMNA Desktop — Barra de Transmisión (Now Playing Bar)
Widget permanente en la parte inferior de la ventana principal.
"""
import tkinter as tk
from tkinter import ttk
from ui_theme import C, FONTS, HButton


class NPBar(tk.Frame):
    """
    Barra de control de transmisión al aire.
    Incluye: indicador AL AIRE, progreso, controles, chips de sección, resumen.
    """

    def __init__(self, parent, on_play, on_pause, on_stop,
                 on_prev_sec, on_next_sec, on_rw, on_ff,
                 on_seek, on_volume, on_jump_sec):
        super().__init__(parent, bg=C["bg"])
        self._on_play     = on_play
        self._on_pause    = on_pause
        self._on_stop     = on_stop
        self._on_prev_sec = on_prev_sec
        self._on_next_sec = on_next_sec
        self._on_rw       = on_rw
        self._on_ff       = on_ff
        self._on_seek     = on_seek
        self._on_volume   = on_volume
        self._on_jump_sec = on_jump_sec

        self._playing     = False
        self._total_dur   = 0
        self._num_secs    = 0
        self._cur_sec_idx = 0
        self._chip_btns   : list[tk.Button] = []

        self._build()

    # ── Build ─────────────────────────────────────────────────────────────────
    def _build(self) -> None:
        # Borde superior (cambia a rojo al aire)
        self._top_border = tk.Frame(self, bg=C["border"], height=1)
        self._top_border.pack(fill=tk.X)

        # Strip: indicador + breadcrumb
        strip = tk.Frame(self, bg=C["header"], height=26)
        strip.pack(fill=tk.X)
        strip.pack_propagate(False)

        self._dot = tk.Label(strip, text="●", font=("Segoe UI", 8),
                              bg=C["header"], fg=C["text3"])
        self._dot.pack(side=tk.LEFT, padx=(14, 4))

        self._lbl_status = tk.Label(strip, text="NO SE TRANSMITE",
            font=FONTS["mono_sm"], bg=C["header"], fg=C["text3"])
        self._lbl_status.pack(side=tk.LEFT)

        self._lbl_ev = tk.Label(strip, text="", font=FONTS["small"],
                                 bg=C["header"], fg=C["text"])
        self._lbl_ev.pack(side=tk.LEFT, padx=(10, 0))

        self._lbl_arr = tk.Label(strip, text="▸", font=FONTS["small"],
                                  bg=C["header"], fg=C["text3"])
        self._lbl_arr.pack(side=tk.LEFT, padx=3)
        self._lbl_arr.pack_forget()

        self._lbl_sec = tk.Label(strip, text="", font=FONTS["small"],
                                  bg=C["header"], fg=C["text2"])
        self._lbl_sec.pack(side=tk.LEFT)

        self._hint = tk.Label(strip,
            text="Selecciona un evento y presiona Transmitir",
            font=FONTS["small"], bg=C["header"], fg=C["text3"])
        self._hint.pack(side=tk.RIGHT, padx=14)

        # Barra de progreso
        prog_frame = tk.Frame(self, bg=C["bg"], pady=2)
        prog_frame.pack(fill=tk.X, padx=16)

        self._lbl_elapsed = tk.Label(prog_frame, text="0:00",
            font=FONTS["mono_sm"], bg=C["bg"], fg=C["text2"], width=5)
        self._lbl_elapsed.pack(side=tk.LEFT)

        self._progress = ttk.Progressbar(prog_frame, mode="determinate",
                                          maximum=100, value=0)
        self._progress.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        self._progress.bind("<Button-1>", self._on_progress_click)

        self._lbl_total = tk.Label(prog_frame, text="0:00",
            font=FONTS["mono_sm"], bg=C["bg"], fg=C["text3"], width=5)
        self._lbl_total.pack(side=tk.LEFT)

        # Controles + chips
        ctrl_frame = tk.Frame(self, bg=C["bg"])
        ctrl_frame.pack(fill=tk.X, padx=10, pady=(2, 0))

        def ctrl_btn(text, cmd, size=18):
            b = tk.Button(ctrl_frame, text=text, font=("Segoe UI", size),
                          bg=C["bg"], fg=C["text2"], relief="flat",
                          bd=0, cursor="hand2", activebackground=C["surface2"],
                          activeforeground=C["text"], command=cmd,
                          highlightthickness=0, padx=4)
            b.pack(side=tk.LEFT)
            return b

        self._btn_prev_sec = ctrl_btn("⏮", self._on_prev_sec, 14)
        self._btn_rw       = ctrl_btn("↩₁₀", self._on_rw, 11)
        self._btn_play     = tk.Button(ctrl_frame, text="▶",
            font=("Segoe UI", 16), bg=C["danger"], fg="#fff",
            relief="flat", bd=0, cursor="hand2",
            activebackground=C["danger_h"], activeforeground="#fff",
            command=self._toggle_play, highlightthickness=0,
            padx=8, pady=2)
        self._btn_play.pack(side=tk.LEFT, padx=6)
        self._btn_ff       = ctrl_btn("↪₁₀", self._on_ff, 11)
        self._btn_next_sec = ctrl_btn("⏭", self._on_next_sec, 14)

        tk.Frame(ctrl_frame, bg=C["border"], width=1).pack(
            side=tk.LEFT, fill=tk.Y, padx=8)

        self._btn_stop = tk.Button(ctrl_frame, text="⏹",
            font=("Segoe UI", 14), bg=C["surface2"], fg=C["text2"],
            relief="flat", bd=0, cursor="hand2",
            activebackground=C["danger"], activeforeground="#fff",
            command=self._on_stop, highlightthickness=0, padx=4)
        self._btn_stop.pack(side=tk.LEFT)

        # Chips frame
        self._chips_frame = tk.Frame(ctrl_frame, bg=C["bg"])
        self._chips_frame.pack(side=tk.LEFT, padx=(10, 0))

        # Volumen
        vol_frame = tk.Frame(ctrl_frame, bg=C["bg"])
        vol_frame.pack(side=tk.RIGHT, padx=10)
        tk.Label(vol_frame, text="🔊", font=("Segoe UI", 11),
                 bg=C["bg"], fg=C["text3"]).pack(side=tk.LEFT)
        self._vol_scale = tk.Scale(vol_frame, from_=0, to=100, orient="horizontal",
            bg=C["bg"], fg=C["text2"], troughcolor=C["surface2"],
            highlightthickness=0, bd=0, showvalue=False, width=8,
            length=70, command=self._vol_changed)
        self._vol_scale.set(85)
        self._vol_scale.pack(side=tk.LEFT)

        # Resumen
        self._summary_frame = tk.Frame(self, bg=C["bg"], pady=4)
        self._summary_frame.pack(fill=tk.X, padx=16)
        self._sum_labels: dict[str, tk.Label] = {}
        items = [
            ("PTT",          "s_ptt"),
            ("TRANSCURRIDO", "s_elapsed"),
            ("RESTANTE",     "s_remain"),
            ("TOTAL EVENTO", "s_total"),
            ("SECCIÓN",      "s_sec_n"),
            ("DE SECCIONES", "s_sec_of"),
            ("FIN ESTIMADO", "s_fin"),
            ("HASTA PAUSA",  "s_until_pause"),
            ("EN PAUSA",     "s_pause_remain"),
        ]
        for i, (lbl, key) in enumerate(items):
            if i:
                tk.Frame(self._summary_frame, bg=C["border"], width=1).pack(
                    side=tk.LEFT, fill=tk.Y, padx=10)
            f = tk.Frame(self._summary_frame, bg=C["bg"])
            f.pack(side=tk.LEFT)
            if key == "s_ptt":
                vfg = C["text3"]
            elif key == "s_sec_n":
                vfg = C["success"]
            elif key == "s_until_pause":
                vfg = C["warning_h"]
            elif key == "s_pause_remain":
                vfg = C["danger"]
            else:
                vfg = C["text"]
            val_lbl = tk.Label(f, text="—", font=FONTS["h3"],
                                bg=C["bg"], fg=vfg)
            val_lbl.pack()
            tk.Label(f, text=lbl, font=FONTS["mono_sm"],
                     bg=C["bg"], fg=C["text3"]).pack()
            self._sum_labels[key] = val_lbl

        self._set_enabled(False)

    # ── API Pública ───────────────────────────────────────────────────────────
    def set_on_air(self, evento_nombre: str, seccion_nombre: str,
                   elapsed: float, total: float, cur_sec: int,
                   num_secs: int, sec_names: list[str]) -> None:
        self._playing   = True
        self._total_dur = total
        self._num_secs  = num_secs
        self._cur_sec_idx = cur_sec

        # Top border rojo
        self._top_border.config(bg=C["danger"])
        self.config(bg=C["header"])
        self._dot.config(fg=C["danger"], bg=C["header"])
        self._lbl_status.config(text="AL AIRE", fg=C["danger"], bg=C["header"])

        # Breadcrumb
        self._lbl_ev.config(text=evento_nombre)
        self._lbl_arr.pack(side=tk.LEFT, padx=3)
        self._lbl_sec.config(text=seccion_nombre)
        self._hint.pack_forget()

        # Progreso
        pct = (elapsed / total * 100) if total > 0 else 0
        self._progress["value"] = min(100, pct)
        self._lbl_elapsed.config(text=self._fmt(elapsed))
        self._lbl_total.config(text=self._fmt(total))

        # Play button
        self._btn_play.config(bg=C["danger"],
                               fg="#fff", activebackground=C["danger_h"])

        # Chips
        self._update_chips(sec_names, cur_sec)

        # Resumen
        remaining = max(0, total - elapsed)
        self._sum_labels["s_elapsed"].config(text=self._fmt(elapsed))
        self._sum_labels["s_remain"].config(text=self._fmt(remaining))
        self._sum_labels["s_total"].config(text=self._fmt(total))
        self._sum_labels["s_sec_n"].config(text=str(cur_sec + 1))
        self._sum_labels["s_sec_of"].config(text=str(num_secs))
        self._sum_labels["s_fin"].config(text=self._fin_time(remaining))

        self._set_enabled(True)

    def set_playing(self, playing: bool) -> None:
        self._playing = playing
        if playing:
            self._btn_play.config(text="⏸", bg=C["warning"],
                                   activebackground=C["warning_h"])
        else:
            self._btn_play.config(text="▶", bg=C["success"],
                                   activebackground=C["success_h"])

    def set_off_air(self) -> None:
        self._playing = False
        self._top_border.config(bg=C["border"])
        self.config(bg=C["bg"])
        self._dot.config(fg=C["text3"], bg=C["header"])
        self._lbl_status.config(text="NO SE TRANSMITE", fg=C["text3"],
                                  bg=C["header"])
        self._lbl_ev.config(text="")
        self._lbl_arr.pack_forget()
        self._lbl_sec.config(text="")
        self._hint.pack(side=tk.RIGHT, padx=14)
        self._progress["value"] = 0
        self._lbl_elapsed.config(text="0:00")
        self._lbl_total.config(text="0:00")
        for lbl in self._sum_labels.values():
            lbl.config(text="—")
        self._sum_labels["s_ptt"].config(fg=C["text3"])
        self._btn_play.config(text="▶", bg=C["danger"],
                               activebackground=C["danger_h"])
        for w in self._chips_frame.winfo_children():
            w.destroy()
        self._chip_btns.clear()
        self._set_enabled(False)

    def set_pause_info(self, until_pause: str | None,
                       pause_remain: str | None) -> None:
        """Actualiza los contadores de pausa automática en el resumen.
        Pasar None en cualquier argumento para mostrar '—'."""
        self._sum_labels["s_until_pause"].config(
            text=until_pause if until_pause is not None else "—")
        self._sum_labels["s_pause_remain"].config(
            text=pause_remain if pause_remain is not None else "—")

    def set_ptt_state(self, on: bool) -> None:
        """Actualiza el indicador PTT en el resumen."""
        if on:
            self._sum_labels["s_ptt"].config(text="ON",  fg=C["success"])
        else:
            self._sum_labels["s_ptt"].config(text="OFF", fg=C["text3"])

    # ── Internos ──────────────────────────────────────────────────────────────
    def _update_chips(self, names: list[str], active: int) -> None:
        for w in self._chips_frame.winfo_children():
            w.destroy()
        self._chip_btns.clear()
        for i, name in enumerate(names):
            label = f"{i+1}. {name[:10]}{'…' if len(name) > 10 else ''}"
            if i < active:
                bg, fg = C["surface"], C["text3"]
            elif i == active:
                bg, fg = C["audio_bg"], C["audio_fg"]
            else:
                bg, fg = C["surface"], C["text2"]
            idx = i  # captura
            b = tk.Button(self._chips_frame, text=label,
                          font=FONTS["mono_sm"], bg=bg, fg=fg,
                          relief="flat", bd=0, padx=6, pady=2,
                          cursor="hand2", activebackground=C["surface2"],
                          command=lambda x=idx: self._on_jump_sec(x))
            b.pack(side=tk.LEFT, padx=(0, 3))
            self._chip_btns.append(b)

    def _set_enabled(self, on: bool) -> None:
        state = "normal" if on else "disabled"
        for btn in [self._btn_prev_sec, self._btn_rw,
                    self._btn_play, self._btn_ff,
                    self._btn_next_sec, self._btn_stop]:
            btn.config(state=state)

    def _toggle_play(self) -> None:
        if self._playing:
            self._on_pause()
        else:
            self._on_play()

    def _on_progress_click(self, event) -> None:
        w = self._progress.winfo_width()
        if w > 0:
            pct = event.x / w
            self._on_seek(pct)

    def _vol_changed(self, val) -> None:
        self._on_volume(int(val))

    @staticmethod
    def _fmt(s: float) -> str:
        s = max(0, int(s))
        return f"{s // 60}:{s % 60:02d}"

    @staticmethod
    def _fin_time(remaining: float) -> str:
        import datetime
        t = datetime.datetime.now() + datetime.timedelta(seconds=max(0, remaining))
        return t.strftime("%H:%M")
