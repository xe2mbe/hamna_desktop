"""
HAMNA Desktop — Medidor de nivel en vivo (vúmetro)

Dos fuentes de medición:
  • LoopbackMeter — captura lo que sale realmente por la tarjeta de audio
    (WASAPI loopback del dispositivo de salida por defecto). Ve todo: el
    programa, las pausas, sonidos de Windows y el volumen del sistema.
    Requiere el paquete pyaudiowpatch.
  • FileMeter — calcula el nivel del archivo que HAMNA está reproduciendo,
    según la posición de reproducción. Se usa si la captura no está disponible.

Todo se mide en MONO (promedio de canales), como sale al aire, con el filtro
K de ITU-R BS.1770 (la misma escala LUFS que usa la normalización):
  • momentáneo  — últimos 400 ms (la barra)
  • corto plazo — últimos 3 s   (el número en LUFS)
  • pico        — máximo de muestra en los últimos 1.5 s
"""
import logging
import subprocess
import threading
import time
from collections import deque
from dataclasses import dataclass

import numpy as np

log = logging.getLogger(__name__)

BLOCK_S        = 0.1   # bloques de 100 ms
MOMENTARY_BLKS = 4     # 400 ms
SHORT_BLKS     = 30    # 3 s
PEAK_BLKS      = 15    # 1.5 s
SILENCE_DB     = -70.0


@dataclass
class Levels:
    momentary: float   # LUFS
    short:     float   # LUFS
    peak:      float   # dBFS


def _db(x: float) -> float:
    return 20 * np.log10(x) if x > 1e-9 else SILENCE_DB


def _lufs(mean_square: float) -> float:
    return -0.691 + 10 * np.log10(mean_square) if mean_square > 1e-12 else SILENCE_DB


def _k_filters(rate: int) -> list[tuple[np.ndarray, np.ndarray]]:
    """Coeficientes del filtro K (BS.1770) para la frecuencia de muestreo dada."""
    from pyloudnorm.iirfilter import IIRfilter
    hs = IIRfilter(4.0, 1 / np.sqrt(2), 1500.0, rate, "high_shelf")
    hp = IIRfilter(0.0, 0.5, 38.0, rate, "high_pass")
    return [(hs.b, hs.a), (hp.b, hp.a)]


def _levels_from_blocks(ms: np.ndarray, pk: np.ndarray, gain: float = 1.0) -> Levels:
    if len(ms) == 0:
        return Levels(SILENCE_DB, SILENCE_DB, SILENCE_DB)
    g2 = gain * gain
    return Levels(
        momentary=_lufs(float(ms[-MOMENTARY_BLKS:].mean()) * g2),
        short=_lufs(float(ms[-SHORT_BLKS:].mean()) * g2),
        peak=_db(float(pk[-PEAK_BLKS:].max()) * gain),
    )


# ── Fuente B: salida real (loopback) ──────────────────────────────────────────
class LoopbackMeter:
    """Captura y mide lo que suena en el dispositivo de salida por defecto.
    Si cambia el dispositivo por defecto (p. ej. se desconecta el Bluetooth y
    Windows pasa a las bocinas), se vuelve a conectar al nuevo."""

    CHECK_EVERY_S = 3.0

    def __init__(self):
        self.device_name = ""
        self.error: str | None = None
        self._p = None
        self._stream = None
        self._lock = threading.Lock()
        self._blocks: deque = deque(maxlen=SHORT_BLKS)
        self._last_data = 0.0
        self._last_check = 0.0
        self._filters = []
        self._zi = []
        self._blk_len = 1
        self._acc_ss = 0.0
        self._acc_n = 0
        self._acc_pk = 0.0
        self._channels = 2

    @property
    def ok(self) -> bool:
        return self._stream is not None and self.error is None

    def retry_if_failed(self) -> None:
        """Si la captura falló, reintenta cada cierto tiempo (desde el hilo de Tk)."""
        if self.ok or time.monotonic() - getattr(self, "_last_reopen", 0.0) < 15.0:
            return
        self._last_reopen = time.monotonic()
        self._close()
        try:
            self._open()
        except Exception as e:
            self.error = str(e)

    def start(self) -> None:
        try:
            self._open()
        except Exception as e:
            self.error = str(e)
            log.warning("Medidor: captura de salida no disponible (%s) — "
                        "se medirá el archivo", e)

    def stop(self) -> None:
        self._close()

    def _open(self) -> None:
        import pyaudiowpatch as pa
        from scipy.signal import lfilter_zi
        self._p = pa.PyAudio()
        dev = self._p.get_default_wasapi_loopback()
        rate = int(dev["defaultSampleRate"])
        self._channels = max(1, int(dev["maxInputChannels"]))
        self._filters = _k_filters(rate)
        self._zi = [lfilter_zi(b, a) * 0.0 for b, a in self._filters]
        self._blk_len = int(rate * BLOCK_S)
        self._acc_ss, self._acc_n, self._acc_pk = 0.0, 0, 0.0
        with self._lock:
            self._blocks.clear()
        self._stream = self._p.open(
            format=pa.paFloat32, channels=self._channels, rate=rate,
            input=True, input_device_index=dev["index"],
            frames_per_buffer=int(rate * 0.05),
            stream_callback=self._callback)
        self.device_name = dev["name"].replace(" [Loopback]", "")
        self.error = None
        self._last_check = time.monotonic()
        log.info("Medidor: midiendo la salida '%s' (%d Hz)", self.device_name, rate)

    def _close(self) -> None:
        try:
            if self._stream is not None:
                self._stream.stop_stream()
                self._stream.close()
        except Exception:
            pass
        try:
            if self._p is not None:
                self._p.terminate()
        except Exception:
            pass
        self._stream = None
        self._p = None

    def _callback(self, in_data, frame_count, time_info, status):
        import pyaudiowpatch as pa
        from scipy.signal import lfilter
        try:
            x = np.frombuffer(in_data, dtype=np.float32)
            x = x.reshape(-1, self._channels).mean(axis=1)
            y = x.astype(np.float64)
            for i, (b, a) in enumerate(self._filters):
                y, self._zi[i] = lfilter(b, a, y, zi=self._zi[i])
            pos = 0
            n = len(y)
            while pos < n:
                take = min(self._blk_len - self._acc_n, n - pos)
                seg_y = y[pos:pos + take]
                seg_x = x[pos:pos + take]
                self._acc_ss += float(np.dot(seg_y, seg_y))
                self._acc_pk = max(self._acc_pk, float(np.abs(seg_x).max()))
                self._acc_n += take
                pos += take
                if self._acc_n >= self._blk_len:
                    with self._lock:
                        self._blocks.append((self._acc_ss / self._acc_n, self._acc_pk))
                    self._acc_ss, self._acc_n, self._acc_pk = 0.0, 0, 0.0
            self._last_data = time.monotonic()
        except Exception:
            pass
        return (None, pa.paContinue)

    def levels(self) -> Levels:
        """Niveles actuales. Revisa de vez en cuando si cambió la salida."""
        now = time.monotonic()
        if now - self._last_check > self.CHECK_EVERY_S:
            self._last_check = now
            self._check_device()
        # WASAPI no entrega datos cuando no suena nada: eso es silencio.
        if now - self._last_data > 0.5:
            return Levels(SILENCE_DB, SILENCE_DB, SILENCE_DB)
        with self._lock:
            arr = np.array(self._blocks) if self._blocks else np.zeros((0, 2))
        return _levels_from_blocks(arr[:, 0], arr[:, 1]) if len(arr) else \
            Levels(SILENCE_DB, SILENCE_DB, SILENCE_DB)

    def _check_device(self) -> None:
        """Reconecta si la captura se cayó (p. ej. se desconectó el Bluetooth).
        HAMNA mantiene abierto el audio (pygame manda silencio continuo), así
        que varios segundos sin datos también indican que algo se cayó.
        Al reconectar se vuelve a leer la lista de dispositivos, así que si
        Windows cambió de salida, el medidor pasa a la nueva."""
        try:
            active = self._stream is not None and self._stream.is_active()
        except Exception:
            active = False
        stale = time.monotonic() - self._last_data > 5.0
        if active and not stale:
            return
        if time.monotonic() - getattr(self, "_last_reopen", 0.0) < 10.0:
            return
        self._last_reopen = time.monotonic()
        old = self.device_name
        self._close()
        try:
            self._open()
            if self.device_name != old:
                log.info("Medidor: la salida cambió de '%s' a '%s'", old, self.device_name)
        except Exception as e:
            self.error = str(e)
            log.warning("Medidor: no se pudo reconectar la captura: %s", e)


# ── Fuente A: el archivo que se reproduce ─────────────────────────────────────
class FileMeter:
    """Calcula el nivel del archivo en reproducción a partir de su posición.
    Analiza cada archivo una vez (en segundo plano) y guarda el resultado."""

    RATE = 24000
    MAX_CACHE = 30

    def __init__(self):
        self._cache: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        self._pending: set[str] = set()
        self._lock = threading.Lock()

    def prepare(self, path: str) -> None:
        """Analiza *path* en segundo plano si todavía no se ha hecho."""
        with self._lock:
            if not path or path in self._cache or path in self._pending:
                return
            self._pending.add(path)
        threading.Thread(target=self._analyze, args=(path,), daemon=True).start()

    def levels(self, path: str, pos_ms: int, volume: float = 1.0) -> Levels | None:
        """Niveles en la posición *pos_ms*. None si aún no está analizado."""
        with self._lock:
            env = self._cache.get(path)
        if env is None:
            self.prepare(path)
            return None
        ms, pk = env
        i = int(pos_ms / (BLOCK_S * 1000)) + 1
        i = max(0, min(i, len(ms)))
        lo = max(0, i - SHORT_BLKS)
        return _levels_from_blocks(ms[lo:i], pk[lo:i], volume)

    def _analyze(self, path: str) -> None:
        try:
            from scipy.signal import lfilter
            from pydub import AudioSegment
            info = subprocess.run(
                ["ffprobe", "-v", "error", "-select_streams", "a:0",
                 "-show_entries", "stream=channels", "-of", "csv=p=0", path],
                capture_output=True, text=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            ch = int((info.stdout.strip() or "1").split(",")[0])
            # Mezcla a mono con promedio exacto (igual que la normalización)
            pan = "pan=mono|c0=c0" if ch == 1 else \
                "pan=mono|c0=" + "+".join(f"{1 / ch:.6f}*c{i}" for i in range(ch))
            raw = subprocess.run(
                [AudioSegment.converter or "ffmpeg", "-v", "error", "-i", path,
                 "-af", pan, "-ar", str(self.RATE), "-f", "f32le", "-"],
                capture_output=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
            x = np.frombuffer(raw, dtype=np.float32)
            y = x.astype(np.float64)
            for b, a in _k_filters(self.RATE):
                y = lfilter(b, a, y)
            blk = int(self.RATE * BLOCK_S)
            n = len(y) // blk
            ms = (y[:n * blk].reshape(n, blk) ** 2).mean(axis=1)
            pk = np.abs(x[:n * blk]).reshape(n, blk).max(axis=1)
            with self._lock:
                if len(self._cache) >= self.MAX_CACHE:
                    self._cache.pop(next(iter(self._cache)))
                self._cache[path] = (ms, pk)
        except Exception as e:
            log.warning("Medidor: no se pudo analizar '%s': %s", path, e)
        finally:
            with self._lock:
                self._pending.discard(path)
