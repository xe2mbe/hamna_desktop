"""
HAMNA Desktop — Reproductor de Audio
Backend: pygame (si disponible) → MCI/WinMM nativo en Windows.

Nota MCI: Windows sólo permite UNA instancia del dispositivo mpegvideo (MP3)
por proceso.  Para reproducir múltiples archivos MP3 de forma concurrente o
secuencial sin restricciones, usa AudioPlayer(use_subprocess=True): cada
reproducción se lanza en un proceso hijo independiente, con su propio
contexto MCI.  Esto es el modo recomendado para el reproductor de pausas.
"""
import os
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


def measure_dbfs(filepath: str, sample_ms: int = 10_000) -> float | None:
    """Mide el nivel de loudness promedio de un archivo de audio.

    Analiza los primeros *sample_ms* milisegundos (por defecto 10 seg) para
    mantener bajo el tiempo de carga en archivos largos.
    Devuelve dBFS como float (ej. -18.5) o None si falla / pydub no disponible.
    """
    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_file(filepath)
        if sample_ms and len(audio) > sample_ms:
            audio = audio[:sample_ms]
        dbfs = audio.dBFS
        if dbfs == float("-inf"):
            return None          # archivo silencioso
        return round(dbfs, 1)
    except Exception as exc:
        log.debug("measure_dbfs('%s'): %s", filepath, exc)
        return None


def measure_lufs(filepath: str) -> float | None:
    """Mide el loudness integrado (LUFS / LKFS) según ITU-R BS.1770-4.

    Requiere pyloudnorm + pydub.  Devuelve float (ej. -23.5) o None si
    pyloudnorm no está disponible, el archivo es silencioso o falla.
    """
    try:
        import pyloudnorm as pyln
        import numpy as np
        from pydub import AudioSegment

        audio   = AudioSegment.from_file(filepath)
        samples = np.array(audio.get_array_of_samples(), dtype=np.float32)
        samples /= 2 ** (audio.sample_width * 8 - 1)   # normalizar a [-1, 1]
        if audio.channels == 2:
            samples = samples.reshape((-1, 2))

        meter = pyln.Meter(audio.frame_rate)
        lufs  = meter.integrated_loudness(samples)

        if lufs != lufs or lufs == float("-inf"):   # NaN o silencio total
            return None
        return round(lufs, 1)
    except Exception as exc:
        log.debug("measure_lufs('%s'): %s", filepath, exc)
        return None


def lufs_available() -> bool:
    """Devuelve True si pyloudnorm está instalado."""
    try:
        import pyloudnorm  # noqa: F401
        return True
    except ImportError:
        return False


def normalize_audio_file(filepath: str, target: float,
                          cache_dir: "Path | str | None" = None) -> str:
    """Normaliza un archivo de audio al nivel *target* y devuelve la ruta
    del archivo resultante (cacheado).

    Usa LUFS (ITU-R BS.1770) si pyloudnorm está disponible; de lo contrario
    usa dBFS (RMS pydub).  Incluye limitador de true-peak a −0.5 dBTP para
    evitar clipping.

    *cache_dir* — directorio de caché; si es None usa el mismo directorio
    del archivo fuente.  Devuelve *filepath* original ante cualquier fallo.
    """
    src = Path(filepath)
    if not src.is_file():
        return filepath

    _cache_dir = Path(cache_dir) if cache_dir else src.parent
    _cache_dir.mkdir(parents=True, exist_ok=True)

    use_lufs = lufs_available()
    method   = "lufs" if use_lufs else "dbfs"
    t_tag    = str(target).replace("-", "n").replace(".", "d")
    cache_path = _cache_dir / f"_norm_{src.stem}_{method}_{t_tag}{src.suffix}"

    src_mtime = src.stat().st_mtime
    if cache_path.is_file() and cache_path.stat().st_mtime >= src_mtime:
        return str(cache_path)

    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_file(str(src))

        # Medir nivel actual
        if use_lufs:
            current = measure_lufs(str(src))
            if current is None:                     # archivo muy corto → dBFS
                current = audio.dBFS
        else:
            current = audio.dBFS

        if current is None or current == float("-inf"):
            return filepath

        change_dB = target - current
        # Nunca boostar más de +20 dB para evitar saturación extrema
        change_dB = min(change_dB, 20.0)
        normalized = audio.apply_gain(change_dB)

        # Limitador de true-peak: retrocede si hay clipping
        peak = normalized.max_dBFS
        if peak > -0.5:
            normalized = normalized.apply_gain(-0.5 - peak)

        fmt = src.suffix.lstrip(".").lower() or "mp3"
        if fmt == "m4a":
            fmt = "mp4"
        normalized.export(str(cache_path), format=fmt)
        os.utime(str(cache_path), (src_mtime, src_mtime))
        log.info("Normalizado (%s): %s  %.1f → %.1f  (cache: %s)",
                 method.upper(), src.name, current, target, cache_path.name)
        return str(cache_path)

    except Exception as exc:
        log.warning("Error normalizando '%s': %s", filepath, exc)
        return filepath


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
