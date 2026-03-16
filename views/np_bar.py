"""
HAMNA Desktop — Barra de Transmisión (Now Playing Bar)
Widget permanente en la parte inferior de la ventana principal.
"""
import datetime
import tkinter as tk
from tkinter import ttk
from ui_theme import C, FONTS, HSlider


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

        self._playing   = False
        self._chip_btns : list[tk.Button] = []

        self._build()

    # ── Build ─────────────────────────────────────────────────────────────────
    def _build(self) -> None:
        # Borde superior (cambia a rojo al aire)
        self._top_border = tk.Frame(self, bg=C["border"], height=1)
        self._top_border.pack(fill=tk.X)

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

        # Controles + chips — height fijo para que ningún hijo expanda NPBar en horizontal
        ctrl_frame = tk.Frame(self, bg=C["bg"], height=36)
        ctrl_frame.pack_propagate(False)
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

        # Chips frame — ocupa el espacio sobrante pero NO puede expandir ctrl_frame
        self._chips_frame = tk.Frame(ctrl_frame, bg=C["bg"], height=30)
        self._chips_frame.pack_propagate(False)   # chips no empujan el frame hacia afuera
        self._chips_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 0))

        # ── Separador entre controles y contadores ───────────────────────────────
        tk.Frame(self, bg=C["border"], height=1).pack(fill=tk.X, padx=10)

        # ── Sección de contadores — frame independiente con altura fija ──────────
        counter_frame = tk.Frame(self, bg=C["bg"], height=68)
        counter_frame.pack_propagate(False)
        counter_frame.pack(fill=tk.X, padx=10, pady=(0, 4))

        # Volumen — primero a la DERECHA para que siempre sea visible
        vol_frame = tk.Frame(counter_frame, bg=C["bg"], padx=8)
        vol_frame.pack(side=tk.RIGHT, fill=tk.Y)
        tk.Label(vol_frame, text="🔊", font=("Segoe UI", 10),
                 bg=C["bg"], fg=C["text3"]).pack(side=tk.LEFT, pady=(0, 2))
        self._vol_scale = HSlider(vol_frame, from_=0, to=100,
            bg=C["bg"], command=self._vol_changed, width=100)
        self._vol_scale.set(85)
        self._vol_scale.pack(side=tk.LEFT, pady=(0, 2))

        tk.Frame(counter_frame, bg=C["border"], width=1).pack(
            side=tk.RIGHT, fill=tk.Y, pady=4)

        # Contadores — Canvas garantiza clipping duro en los bordes.
        # Los Label normales en Windows pueden pintar fuera de sus bounds.
        _col_defs = [
            ("PTT",          "s_ptt",          "",       C["text3"]),
            ("TRANSCURRIDO", "s_elapsed",       "m:ss",   C["text"]),
            ("RESTANTE",     "s_remain",        "m:ss",   C["text"]),
            ("REST. SEC",    "s_sec_remain",    "seg",    C["tts_fg"]),
            ("TOTAL",        "s_total",         "m:ss",   C["text"]),
            ("SECCIÓN",      "s_sec_n",         "#",      C["success"]),
            ("SECCIONES",    "s_sec_of",        "#",      C["text"]),
            ("FIN EST.",     "s_fin",           "hh:mm",  C["text"]),
            ("HASTA PAUSA",  "s_until_pause",   "seg",    C["warning_h"]),
            ("EN PAUSA",     "s_pause_remain",  "seg",    C["danger"]),
        ]
        self._col_defs                        = _col_defs
        self._counter_vals:   dict[str, str]  = {k: "—"    for _, k, _, _     in _col_defs}
        self._counter_colors: dict[str, str]  = {k: color  for _, k, _, color in _col_defs}
        self._canvas_val_ids: dict[str, int]  = {}

        self._sum_canvas = tk.Canvas(counter_frame, bg=C["bg"],
                                      highlightthickness=0, bd=0)
        self._sum_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._sum_canvas.bind("<Configure>", self._draw_counters)

        self._set_enabled(False)

    # ── API Pública ───────────────────────────────────────────────────────────
    def set_on_air(self, evento_nombre: str, seccion_nombre: str,
                   elapsed: float, total: float, cur_sec: int,
                   num_secs: int, sec_names: list[str],
                   sec_elapsed: float = 0.0, sec_total: float = 0.0) -> None:
        self._playing = True

        # Top border rojo al aire
        self._top_border.config(bg=C["danger"])

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
        sec_remaining = max(0, sec_total - sec_elapsed) if sec_total > 0 else 0.0
        self._set_counter("s_elapsed",    self._fmt(elapsed))
        self._set_counter("s_remain",     self._fmt(remaining))
        self._set_counter("s_sec_remain",
            f"{int(sec_remaining)} / {int(sec_total)}" if sec_total > 0 else "—")
        self._set_counter("s_total",      self._fmt(total))
        self._set_counter("s_sec_n",      str(cur_sec + 1))
        self._set_counter("s_sec_of",     str(num_secs))
        self._set_counter("s_fin",        self._fin_time(remaining))

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
        self._progress["value"] = 0
        self._lbl_elapsed.config(text="0:00")
        self._lbl_total.config(text="0:00")
        for _, key, _, orig_color in self._col_defs:
            self._set_counter(key, "—", orig_color)
        self._btn_play.config(text="▶", bg=C["danger"],
                               activebackground=C["danger_h"])
        for w in self._chips_frame.winfo_children():
            w.destroy()
        self._chip_btns.clear()
        self._set_enabled(False)

    def set_pause_info(self, until_pause: str | None,
                       pause_remain: str | None) -> None:
        """Actualiza los contadores de pausa automática en el resumen."""
        self._set_counter("s_until_pause",
                          until_pause  if until_pause  is not None else "—")
        self._set_counter("s_pause_remain",
                          pause_remain if pause_remain is not None else "—")

    def set_ptt_state(self, on: bool) -> None:
        """Actualiza el indicador PTT en el resumen."""
        if on:
            self._set_counter("s_ptt", "ON",  C["success"])
        else:
            self._set_counter("s_ptt", "OFF", C["text3"])

    # ── Internos ──────────────────────────────────────────────────────────────
    def _draw_counters(self, event=None) -> None:
        """Dibuja (o redibuja) el canvas de contadores desde cero."""
        c = self._sum_canvas
        w = c.winfo_width()
        h = c.winfo_height()
        if w <= 1 or h <= 1:
            return
        c.configure(scrollregion=(0, 0, w, h))
        c.delete("all")
        self._canvas_val_ids.clear()
        n   = len(self._col_defs)
        cw  = w / n
        for i, (lbl, key, unit, color) in enumerate(self._col_defs):
            cx = i * cw + cw / 2
            if i > 0:
                c.create_line(i * cw, h * 0.1, i * cw, h * 0.9,
                              fill=C["border"], width=1)
            tid = c.create_text(cx, h * 0.28,
                                text=self._counter_vals.get(key, "—"),
                                fill=self._counter_colors.get(key, C["text"]),
                                font=("Consolas", 13, "bold"), anchor="center")
            self._canvas_val_ids[key] = tid
            c.create_text(cx, h * 0.68, text=lbl,
                          fill=C["text3"], font=("Consolas", 9), anchor="center")
            if unit:
                c.create_text(cx, h * 0.90, text=unit,
                              fill=C["text3"], font=("Consolas", 9), anchor="center")

    def _set_counter(self, key: str, val: str, color: str = None) -> None:
        """Actualiza el valor de un contador; redibuja sólo ese ítem del canvas."""
        self._counter_vals[key] = val
        if color is not None:
            self._counter_colors[key] = color
        tid = self._canvas_val_ids.get(key)
        if tid:
            kw: dict = {"text": val}
            if color is not None:
                kw["fill"] = color
            self._sum_canvas.itemconfig(tid, **kw)

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
            b = tk.Button(self._chips_frame, text=label,
                          font=FONTS["mono_sm"], bg=bg, fg=fg,
                          relief="flat", bd=0, padx=6, pady=2,
                          cursor="hand2", activebackground=C["surface2"],
                          command=lambda x=i: self._on_jump_sec(x))
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
        t = datetime.datetime.now() + datetime.timedelta(seconds=max(0, remaining))
        return t.strftime("%H:%M")
