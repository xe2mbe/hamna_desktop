"""
HAMNA Desktop — Reproductor de Audio
Backend: pygame (si disponible) → MCI/WinMM nativo en Windows.

Nota MCI: Windows sólo permite UNA instancia del dispositivo mpegvideo (MP3)
por proceso.  Para reproducir múltiples archivos MP3 de forma concurrente o
secuencial sin restricciones, usa AudioPlayer(use_subprocess=True): cada
reproducción se lanza en un proceso hijo independiente, con su propio
contexto MCI.  Esto es el modo recomendado para el reproductor de pausas.
"""
import sys
import threading
import subprocess
import logging
from pathlib import Path

log = logging.getLogger(__name__)

# ── Intentar pygame ────────────────────────────────────────────────────────────
_pygame_ok = False
try:
    import pygame
    pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=2048)
    _pygame_ok = True
except Exception as e:
    log.warning(f"pygame no disponible: {e}")


# ── Backend MCI (Windows nativo) ───────────────────────────────────────────────
_mci_ok = False
if sys.platform == "win32" and not _pygame_ok:
    try:
        import ctypes
        _winmm = ctypes.windll.winmm

        def _mci(cmd: str) -> str:
            buf = ctypes.create_unicode_buffer(512)
            ret = _winmm.mciSendStringW(cmd, buf, 512, 0)
            if ret != 0:
                errbuf = ctypes.create_unicode_buffer(512)
                _winmm.mciGetErrorStringW(ret, errbuf, 512)
                log.warning("MCI error %d ('%s'): %s", ret, cmd[:60], errbuf.value)
            return buf.value.strip()

        _mci_ok = True
        log.info("Usando backend MCI (Windows nativo)")
    except Exception as e:
        log.warning(f"MCI no disponible: {e}")


# ── Script embebido para modo subprocess ───────────────────────────────────────
_SUBPROCESS_PLAYER_SCRIPT = r"""
import sys, time
filepath = sys.argv[1]

# Intentar pygame (misma instalación que el proceso padre)
try:
    import pygame
    pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=2048)
    pygame.mixer.music.load(filepath)
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        time.sleep(0.1)
    pygame.mixer.quit()
    sys.exit(0)
except Exception as e:
    sys.stderr.write(f"pygame error: {e}\n")

# Fallback: MCI nativo (WAV o mpegvideo)
try:
    import ctypes
    winmm = ctypes.windll.winmm
    buf   = ctypes.create_unicode_buffer(512)
    ext   = filepath.rsplit(".", 1)[-1].lower()
    mtype = "waveaudio" if ext == "wav" else "mpegvideo"
    ret = winmm.mciSendStringW(
        'open "' + filepath + '" type ' + mtype + ' alias p', buf, 512, 0)
    if ret != 0:
        errbuf = ctypes.create_unicode_buffer(512)
        winmm.mciGetErrorStringW(ret, errbuf, 512)
        sys.stderr.write(f"MCI open error {ret}: {errbuf.value}\n")
        sys.exit(1)
    winmm.mciSendStringW("set p time format milliseconds", buf, 512, 0)
    winmm.mciSendStringW("play p from 0", buf, 512, 0)
    b2 = ctypes.create_unicode_buffer(512)
    time.sleep(0.3)   # dar tiempo a que arranque
    while True:
        time.sleep(0.25)
        winmm.mciSendStringW("status p mode", b2, 512, 0)
        mode = b2.value.strip()
        if mode == "stopped":
            break
        if mode == "":
            sys.stderr.write("MCI mode vacío — dispositivo no disponible\n")
            break
    winmm.mciSendStringW("stop p", buf, 512, 0)
    winmm.mciSendStringW("close p", buf, 512, 0)
except Exception as e:
    sys.stderr.write(f"MCI error: {e}\n")
    sys.exit(1)
"""


# ── Registro de metadatos de audio ─────────────────────────────────────────────
def _log_audio_info(filepath: str, alias: str = "") -> None:
    """Registra en el log los metadatos del archivo de audio que se va a reproducir."""
    try:
        p = Path(filepath)
        stat = p.stat()
        size_kb = stat.st_size / 1024
        ext = p.suffix.lower()

        parts = [
            f"[AUDIO] {p.name}",
            f"ruta={p.resolve()}",
            f"formato={ext.lstrip('.').upper() or '?'}",
            f"tamaño={size_kb:.1f} KB",
        ]

        # Metadatos extendidos con mutagen
        try:
            if ext == ".mp3":
                from mutagen.mp3 import MP3
                audio = MP3(filepath)
                dur   = audio.info.length
                m, s  = divmod(int(dur), 60)
                parts.append(f"duración={m}:{s:02d} ({dur:.1f}s)")
                br = getattr(audio.info, "bitrate", 0)
                if br:
                    parts.append(f"bitrate={br // 1000} kbps")
                sr = getattr(audio.info, "sample_rate", 0)
                if sr:
                    parts.append(f"sample_rate={sr} Hz")
                ch = getattr(audio.info, "channels", 0)
                if ch:
                    parts.append(f"canales={ch}")
                # ID3 tags
                try:
                    from mutagen.id3 import ID3
                    tags = ID3(filepath)
                    title  = tags.get("TIT2")
                    artist = tags.get("TPE1")
                    album  = tags.get("TALB")
                    if title:
                        parts.append(f"título={str(title)}")
                    if artist:
                        parts.append(f"artista={str(artist)}")
                    if album:
                        parts.append(f"álbum={str(album)}")
                except Exception:
                    pass
            elif ext == ".wav":
                from mutagen.wave import WAVE
                audio = WAVE(filepath)
                dur  = audio.info.length
                m, s = divmod(int(dur), 60)
                parts.append(f"duración={m}:{s:02d} ({dur:.1f}s)")
                sr = getattr(audio.info, "sample_rate", 0)
                if sr:
                    parts.append(f"sample_rate={sr} Hz")
                ch = getattr(audio.info, "channels", 0)
                if ch:
                    parts.append(f"canales={ch}")
        except ImportError:
            pass  # mutagen no instalado
        except Exception:
            pass

        if alias:
            parts.append(f"player={alias}")

        log.info(" | ".join(parts))
    except Exception as e:
        log.debug("No se pudieron leer metadatos de %s: %s", filepath, e)


class AudioPlayer:
    """Reproductor de audio.

    Parámetros:
        alias          – alias MCI (ignorado en modo subprocess).
        use_subprocess – si True, cada reproducción se ejecuta en un proceso
                         hijo Python independiente; esto evita la limitación
                         de una sola instancia mpegvideo por proceso en MCI.
                         Recomendado para el reproductor de pausas/anuncios.
    """

    def __init__(self, alias: str = "hamna_media",
                 use_subprocess: bool = False):
        self.ALIAS          = alias
        self._use_subprocess = use_subprocess
        self._playing       = False
        self._paused        = False
        self._current       : str | None = None
        self._lock          = threading.Lock()
        self.on_finished    : callable | None = None
        self.on_error       : callable | None = None
        self._monitor_thread: threading.Thread | None = None
        self._subproc       : subprocess.Popen | None = None  # modo subprocess

    # ── API pública ────────────────────────────────────────────────────────────
    def play_from_ms(self, filepath: str, start_ms: int,
                     on_finished: callable = None) -> tuple[bool, str]:
        """Como play(), pero comienza desde start_ms milisegundos."""
        if not Path(filepath).is_file():
            err = f"Archivo no encontrado: {filepath}"
            log.error(err)
            return False, err
        _log_audio_info(filepath, self.ALIAS)
        self.stop()
        self._current    = filepath
        self.on_finished = on_finished
        if self._use_subprocess:
            return self._play_subprocess(filepath)   # subprocess no soporta seek
        if _pygame_ok:
            try:
                pygame.mixer.music.load(filepath)
                pygame.mixer.music.play(start=start_ms / 1000.0)
                self._playing = True
                self._paused  = False
                t = threading.Thread(target=self._monitor_pygame, daemon=True)
                t.start()
                return True, "Reproduciendo"
            except Exception as e:
                log.error(f"pygame play_from_ms error: {e}")
                return False, str(e)
        if _mci_ok:
            return self._play_mci(filepath, start_ms=start_ms)
        return False, "No hay backend de audio disponible"

    def play(self, filepath: str, on_finished: callable = None) -> tuple[bool, str]:
        if not Path(filepath).is_file():
            err = f"Archivo no encontrado: {filepath}"
            log.error(err)
            return False, err
        _log_audio_info(filepath, self.ALIAS)
        self.stop()
        self._current    = filepath
        self.on_finished = on_finished

        if self._use_subprocess:
            return self._play_subprocess(filepath)
        if _pygame_ok:
            return self._play_pygame(filepath)
        if _mci_ok:
            return self._play_mci(filepath)
        return False, "No hay backend de audio disponible"

    def stop(self) -> None:
        self._playing    = False
        self._paused     = False
        self.on_finished = None
        if self._use_subprocess:
            self._stop_subprocess()
            return
        if _pygame_ok:
            try:
                pygame.mixer.music.stop()
            except Exception:
                pass
        elif _mci_ok:
            try:
                _mci(f"stop {self.ALIAS}")
            except Exception:
                pass
            try:
                _mci(f"close {self.ALIAS}")
            except Exception:
                pass
        self._current = None

    def pause(self) -> None:
        if not self._playing or self._paused:
            return
        self._paused = True
        if self._use_subprocess:
            return  # subprocess no soporta pausa
        if _pygame_ok:
            try:
                pygame.mixer.music.pause()
            except Exception:
                pass
        elif _mci_ok:
            try:
                _mci(f"pause {self.ALIAS}")
            except Exception:
                pass

    def resume(self) -> None:
        if not self._paused:
            return
        self._paused = False
        if self._use_subprocess:
            return
        if _pygame_ok:
            try:
                pygame.mixer.music.unpause()
            except Exception:
                pass
        elif _mci_ok:
            try:
                _mci(f"resume {self.ALIAS}")
            except Exception:
                pass

    def is_playing(self) -> bool:
        if self._paused:
            return False
        if _pygame_ok:
            try:
                return pygame.mixer.music.get_busy()
            except Exception:
                pass
        return self._playing

    def get_pos_ms(self) -> int:
        """Posición actual en milisegundos."""
        if self._use_subprocess:
            return 0  # no disponible en modo subprocess
        if _pygame_ok:
            try:
                pos = pygame.mixer.music.get_pos()
                return max(0, pos)
            except Exception:
                pass
        elif _mci_ok:
            try:
                val = _mci(f"status {self.ALIAS} position")
                return int(val) if val.isdigit() else 0
            except Exception:
                pass
        return 0

    def get_length_ms(self) -> int:
        """Duración total en milisegundos (solo MCI)."""
        if _mci_ok and not self._use_subprocess:
            try:
                val = _mci(f"status {self.ALIAS} length")
                return int(val) if val.isdigit() else 0
            except Exception:
                pass
        return 0

    def set_volume(self, pct: int) -> None:
        """pct: 0–100"""
        pct = max(0, min(100, pct))
        if self._use_subprocess:
            return  # no disponible en modo subprocess
        if _pygame_ok:
            try:
                pygame.mixer.music.set_volume(pct / 100.0)
            except Exception:
                pass
        elif _mci_ok:
            try:
                vol = pct * 10   # MCI escala 0-1000
                _mci(f"setaudio {self.ALIAS} volume to {vol}")
            except Exception:
                pass

    # ── Backend subprocess ─────────────────────────────────────────────────────
    def _play_subprocess(self, filepath: str) -> tuple[bool, str]:
        """Lanza un proceso Python hijo para reproducir el archivo.
        Cada proceso tiene su propio contexto de audio, evitando conflictos."""
        try:
            abs_path = str(Path(filepath).resolve())
            cf = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            self._subproc = subprocess.Popen(
                [sys.executable, "-c", _SUBPROCESS_PLAYER_SCRIPT, abs_path],
                creationflags=cf,
                stderr=subprocess.PIPE,
            )
            self._playing = True
            self._paused  = False
            cb = self.on_finished  # capturar antes del hilo
            t = threading.Thread(
                target=self._monitor_subprocess, args=(self._subproc, cb),
                daemon=True)
            t.start()
            return True, "Reproduciendo"
        except Exception as e:
            log.error(f"Subprocess play error: {e}")
            return False, str(e)

    def _stop_subprocess(self) -> None:
        if self._subproc and self._subproc.poll() is None:
            try:
                self._subproc.terminate()
            except Exception:
                pass
        self._subproc = None
        self._current = None

    def _monitor_subprocess(self, proc: subprocess.Popen,
                             cb: callable) -> None:
        """Espera a que el proceso hijo termine y dispara on_finished."""
        proc.wait()
        if proc.stderr:
            err = proc.stderr.read().decode("utf-8", errors="replace").strip()
            if err:
                log.warning("Subprocess player: %s", err)
        self._playing = False
        if callable(cb):
            try:
                cb()
            except Exception:
                pass

    # ── Backend pygame ─────────────────────────────────────────────────────────
    def _play_pygame(self, filepath: str) -> tuple[bool, str]:
        try:
            pygame.mixer.music.load(filepath)
            pygame.mixer.music.play()
            self._playing = True
            self._paused  = False
            t = threading.Thread(target=self._monitor_pygame, daemon=True)
            t.start()
            return True, "Reproduciendo"
        except Exception as e:
            log.error(f"pygame play error: {e}")
            return False, str(e)

    def _monitor_pygame(self) -> None:
        import time
        while pygame.mixer.music.get_busy():
            time.sleep(0.2)
        self._playing = False
        if callable(self.on_finished):
            try:
                self.on_finished()
            except Exception:
                pass

    # ── Backend MCI ────────────────────────────────────────────────────────────
    def _play_mci(self, filepath: str, start_ms: int = 0) -> tuple[bool, str]:
        try:
            abs_path = str(Path(filepath).resolve())
            ext = Path(filepath).suffix.lower()
            media_type = "waveaudio" if ext == ".wav" else "mpegvideo"
            _mci(f'open "{abs_path}" type {media_type} alias {self.ALIAS}')
            _mci(f"set {self.ALIAS} time format milliseconds")
            _mci(f"play {self.ALIAS} from {start_ms}")
            self._playing = True
            self._paused  = False
            t = threading.Thread(target=self._monitor_mci, daemon=True)
            t.start()
            return True, "Reproduciendo"
        except Exception as e:
            log.error(f"MCI play error: {e}")
            return False, str(e)

    def _monitor_mci(self) -> None:
        import time
        while True:
            time.sleep(0.3)
            if not self._playing:
                break
            if self._paused:
                continue
            try:
                mode = _mci(f"status {self.ALIAS} mode")
                if mode in ("stopped", ""):
                    self._playing = False
                    if mode == "stopped" and callable(self.on_finished):
                        try:
                            self.on_finished()
                        except Exception:
                            pass
                    break
            except Exception:
                break
