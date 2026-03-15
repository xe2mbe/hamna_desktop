"""
HAMNA Desktop — Ventana de Reproductor de Audio
Controles de reproducción: play/pausa, stop, progreso y volumen.
"""
import tkinter as tk
from tkinter import ttk
from pathlib import Path
from ui_theme import C, FONTS, HButton, HDialog, HSlider
from modules.audio.audio_player import AudioPlayer
from modules.tts.tts_manager import get_audio_duration


class AudioPlayerWindow(HDialog):
    """Ventana modal con controles completos de reproducción."""

    def __init__(self, parent, filepath: str):
        fname = Path(filepath).name
        super().__init__(parent, title=f"Reproduciendo — {fname}",
                         width=460, height=240)
        self.filepath  = filepath
        self._duration = get_audio_duration(filepath)
        self._player   = AudioPlayer()
        self._polling  = False
        self._paused   = False
        self._build()
        self._start_play()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── UI ─────────────────────────────────────────────────────────────────────
    def _build(self) -> None:
        self.make_header("▶  Reproduciendo audio", Path(self.filepath).name)

        body = tk.Frame(self, bg=C["bg"], padx=30, pady=20)
        body.pack(fill=tk.BOTH, expand=True)

        self._lbl_time = tk.Label(
            body, text=f"0:00 / {self._fmt(self._duration)}",
            font=FONTS["mono"], bg=C["bg"], fg=C["text2"])
        self._lbl_time.pack(anchor="center")

        self._progress = ttk.Progressbar(
            body, mode="determinate", maximum=100, value=0)
        self._progress.pack(fill=tk.X, pady=(8, 0))

        btn_frame = tk.Frame(body, bg=C["bg"])
        btn_frame.pack(pady=(16, 8), anchor="center")

        self._btn_playpause = HButton(
            btn_frame, "⏸  Pausar",
            command=self._toggle_playpause,
            variant="primary")
        self._btn_playpause.pack(side=tk.LEFT, padx=6)

        HButton(btn_frame, "⏹  Detener",
                command=self._stop,
                variant="danger").pack(side=tk.LEFT, padx=6)

        HButton(btn_frame, "✖  Cerrar",
                command=self._on_close,
                variant="muted").pack(side=tk.LEFT, padx=6)

        # Volumen
        vol_frame = tk.Frame(body, bg=C["bg"])
        vol_frame.pack(anchor="center")
        tk.Label(vol_frame, text="🔊", font=FONTS["body"],
                 bg=C["bg"], fg=C["text2"]).pack(side=tk.LEFT)
        self._vol_slider = HSlider(vol_frame, from_=0, to=100, bg=C["bg"],
                                   command=lambda v: self._player.set_volume(v),
                                   width=220)
        self._vol_slider.set(80)
        self._vol_slider.pack(side=tk.LEFT, padx=8)

    # ── Reproducción ───────────────────────────────────────────────────────────
    def _start_play(self) -> None:
        self._player.set_volume(self._vol_slider.get())
        ok, msg = self._player.play(
            self.filepath,
            on_finished=lambda: self.after(0, self._on_finished)
        )
        if ok:
            self._polling = True
            self._poll()

    def _poll(self) -> None:
        if not self._polling:
            return
        if not self._paused and self._duration > 0:
            pos_ms = self._player.get_pos_ms()
            if pos_ms >= 0:
                elapsed = pos_ms / 1000
                pct = min(100, elapsed / self._duration * 100)
                self._progress["value"] = pct
                self._lbl_time.config(
                    text=f"{self._fmt(elapsed)} / {self._fmt(self._duration)}")
        self.after(200, self._poll)

    def _toggle_playpause(self) -> None:
        if self._paused:
            self._player.resume()
            self._paused = False
            self._btn_playpause.config(text="⏸  Pausar")
            self._btn_playpause.set_variant("primary")
        else:
            self._player.pause()
            self._paused = True
            self._btn_playpause.config(text="▶  Reanudar")
            self._btn_playpause.set_variant("success")

    def _stop(self) -> None:
        self._polling = False
        self._paused  = False
        self._player.stop()
        self._progress["value"] = 0
        self._lbl_time.config(text=f"0:00 / {self._fmt(self._duration)}")
        self._btn_playpause.config(text="▶  Reproducir")
        self._btn_playpause.set_variant("primary")

    def _on_finished(self) -> None:
        self._polling = False
        self._paused  = False
        try:
            self._progress["value"] = 100
            self._lbl_time.config(
                text=f"{self._fmt(self._duration)} / {self._fmt(self._duration)}")
            self._btn_playpause.config(text="▶  Reproducir")
            self._btn_playpause.set_variant("primary")
        except Exception:
            pass

    def _on_close(self) -> None:
        self._polling = False
        self._player.stop()
        self.destroy()

    @staticmethod
    def _fmt(s: float) -> str:
        s = int(max(0, s))
        return f"{s // 60}:{s % 60:02d}"
