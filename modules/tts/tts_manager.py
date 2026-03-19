"""
HAMNA Desktop — TTS Manager
Fachada unificada para pyttsx3 y Azure Cognitive Services.
"""
import os
import logging
import threading
from pathlib import Path

log = logging.getLogger(__name__)

TEMP_MP3  = Path(__file__).parent.parent.parent / "output_temp.mp3"
TEMP_WAV  = Path(__file__).parent.parent.parent / "output_temp.wav"
AUDIO_DIR = Path(__file__).parent.parent.parent / "media" / "audios"


# ── pyttsx3 ───────────────────────────────────────────────────────────────────
def convert_pyttsx3(text: str, cfg: dict,
                    output_path: Path = TEMP_MP3) -> tuple[bool, str]:
    """
    Convierte texto a audio con pyttsx3.
    Genera WAV nativo, luego intenta convertir a MP3 con pydub.
    """
    try:
        import pyttsx3
    except ImportError:
        return False, "pyttsx3 no instalado — ejecuta: pip install pyttsx3"

    rate_val   = int(cfg.get("tts_rate",   175))
    vol_val    = int(cfg.get("tts_volume", 90))
    voice_id   = cfg.get("tts_voice_id", "")
    log.info("[TTS-LOCAL] Iniciando síntesis | chars=%d | rate=%d wpm | vol=%d%% | voz=%s",
             len(text), rate_val, vol_val, voice_id or "auto-español")

    try:
        import time as _time
        _t0 = _time.monotonic()

        engine = pyttsx3.init()
        engine.setProperty("rate",   rate_val)
        engine.setProperty("volume", vol_val / 100.0)

        # Seleccionar voz
        selected_voice = voice_id
        if voice_id:
            engine.setProperty("voice", voice_id)
        else:
            # Auto: buscar voz en español
            for v in engine.getProperty("voices"):
                if any(lang in v.id.lower() for lang in ["spanish", "es_", "es-"]):
                    engine.setProperty("voice", v.id)
                    selected_voice = v.id
                    break

        # Guardar a WAV primero
        wav_path = str(TEMP_WAV)
        engine.save_to_file(text, wav_path)
        engine.runAndWait()

        if not Path(wav_path).is_file():
            log.error("[TTS-LOCAL] Error: pyttsx3 no generó el archivo de audio")
            return False, "pyttsx3 no generó el archivo de audio"

        # Intentar WAV → MP3
        final_path = _wav_to_mp3(wav_path, str(output_path))
        elapsed = _time.monotonic() - _t0

        # Calcular duración del audio generado
        try:
            from mutagen.mp3 import MP3
            from mutagen.wave import WAVE
            _fp = Path(final_path)
            if _fp.suffix.lower() == ".mp3":
                dur = MP3(final_path).info.length
            else:
                dur = WAVE(final_path).info.length
            m, s = divmod(int(dur), 60)
            log.info("[TTS-LOCAL] OK | dur_audio=%d:%02d | elapsed=%.1fs | voz=%s | archivo=%s",
                     m, s, elapsed, selected_voice or "?", final_path)
        except Exception:
            log.info("[TTS-LOCAL] OK | elapsed=%.1fs | archivo=%s", elapsed, final_path)

        return True, str(final_path)

    except Exception as e:
        log.error(f"[TTS-LOCAL] Error: {e}")
        return False, str(e)


def get_pyttsx3_voices() -> list[dict]:
    """Retorna lista de voces instaladas en el sistema."""
    try:
        import pyttsx3
        engine = pyttsx3.init()
        voices = []
        for v in engine.getProperty("voices"):
            name = v.name or v.id
            lang = ""
            if v.languages:
                lang = v.languages[0] if isinstance(v.languages[0], str) \
                    else v.languages[0].decode("utf-8", errors="ignore")
            voices.append({"id": v.id, "name": name, "lang": lang})
        engine.stop()
        return voices
    except Exception:
        return []


# ── Azure TTS (REST API — sin SDK nativo, sin crashes de FFI) ─────────────────
def convert_azure(text: str, cfg: dict,
                  output_path: Path = TEMP_MP3) -> tuple[bool, str]:
    """
    Convierte texto a audio usando la API REST de Azure Speech.
    No requiere azure-cognitiveservices-speech; usa solo urllib (stdlib).
    """
    import urllib.request
    import urllib.error
    import html

    key    = cfg.get("azure_key",    "").strip()
    region = cfg.get("azure_region", "").strip()
    if not key or not region:
        return False, "Configura la clave y región de Azure en Ajustes → Motor TTS"

    voice  = cfg.get("azure_voice",  "es-MX-DaliaNeural")
    style  = cfg.get("azure_style",  "general")
    rate   = int(cfg.get("azure_rate",  100))
    pitch  = int(cfg.get("azure_pitch", 0))
    fmt    = cfg.get("azure_format", "audio-24khz-160kbitrate-mono-mp3")

    log.info("[TTS-AZURE] Iniciando síntesis | región=%s | voz=%s | estilo=%s | "
             "rate=%d%% | pitch=%d Hz | formato=%s | chars=%d",
             region, voice, style, rate, pitch, fmt, len(text))

    # Detectar locale a partir de la voz (primeros 5 chars: "es-MX")
    locale = voice[:5] if len(voice) >= 5 else "es-MX"

    # Construir SSML (siempre; permite estilo y prosody sin condicionales)
    rate_str  = f"+{rate - 100}%" if rate >= 100 else f"-{100 - rate}%"
    pitch_str = f"+{pitch}Hz"     if pitch >= 0  else f"{pitch}Hz"
    safe_text = html.escape(text)

    if style and style != "general":
        ssml = (
            f'<speak version="1.0" '
            f'xmlns="http://www.w3.org/2001/10/synthesis" '
            f'xmlns:mstts="http://www.w3.org/2001/mstts" '
            f'xml:lang="{locale}">'
            f'<voice name="{voice}">'
            f'<mstts:express-as style="{style}">'
            f'<prosody rate="{rate_str}" pitch="{pitch_str}">{safe_text}</prosody>'
            f'</mstts:express-as></voice></speak>'
        )
    else:
        ssml = (
            f'<speak version="1.0" '
            f'xmlns="http://www.w3.org/2001/10/synthesis" '
            f'xml:lang="{locale}">'
            f'<voice name="{voice}">'
            f'<prosody rate="{rate_str}" pitch="{pitch_str}">{safe_text}</prosody>'
            f'</voice></speak>'
        )

    endpoint = (cfg.get("azure_endpoint", "").strip()
                or f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1")

    headers = {
        "Ocp-Apim-Subscription-Key": key,
        "Content-Type":  "application/ssml+xml",
        "X-Microsoft-OutputFormat": fmt,
        "User-Agent": "HAMNA-Desktop/1.0",
    }

    import time as _time
    _t0 = _time.monotonic()

    try:
        req = urllib.request.Request(
            endpoint,
            data=ssml.encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            audio_bytes = resp.read()

        elapsed = _time.monotonic() - _t0
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(audio_bytes)

        # Calcular duración del MP3 generado
        try:
            from mutagen.mp3 import MP3
            dur = MP3(str(output_path)).info.length
            m, s = divmod(int(dur), 60)
            log.info("[TTS-AZURE] OK | bytes=%d | dur_audio=%d:%02d | elapsed=%.1fs | "
                     "voz=%s | estilo=%s | archivo=%s",
                     len(audio_bytes), m, s, elapsed, voice, style, output_path)
        except Exception:
            log.info("[TTS-AZURE] OK | bytes=%d | elapsed=%.1fs | voz=%s | archivo=%s",
                     len(audio_bytes), elapsed, voice, output_path)

        return True, str(output_path)

    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="ignore")[:300]
        log.error("[TTS-AZURE] HTTP %s | voz=%s | región=%s | error=%s", e.code, voice, region, body)
        return False, f"Azure TTS HTTP {e.code}: {body}"
    except Exception as e:
        log.error("[TTS-AZURE] Error | voz=%s | región=%s | %s", voice, region, e)
        return False, str(e)


def get_azure_voices(key: str, region: str) -> list[dict]:
    """Retorna voces neurales disponibles para la región (vía REST)."""
    import urllib.request
    import urllib.error
    import json

    url = f"https://{region}.tts.speech.microsoft.com/cognitiveservices/voices/list"
    req = urllib.request.Request(
        url, headers={"Ocp-Apim-Subscription-Key": key})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            voices_raw = json.loads(resp.read())
        return [
            {
                "name":       v["ShortName"],
                "display":    v.get("LocalName", v["ShortName"]),
                "locale":     v["Locale"],
                "gender":     v.get("Gender", ""),
                "voice_type": v.get("VoiceType", ""),
            }
            for v in voices_raw
        ]
    except Exception:
        return []


# ── Fachada principal ─────────────────────────────────────────────────────────
def resolve_variables(text: str, cfg: dict, ctx: dict = None) -> str:
    """
    Reemplaza tokens {variable} en el texto TTS con valores reales.
    ctx puede incluir: evento, num_secciones, duracion_total.
    """
    import datetime
    now  = datetime.datetime.now()
    dias = ["Lunes", "Martes", "Miércoles", "Jueves",
            "Viernes", "Sábado", "Domingo"]
    ctx  = ctx or {}

    # Duración en palabras para que el TTS las pronuncie correctamente
    def _fmt_seg(s):
        s = int(s)
        if s < 60:
            return f"{s} segundo{'s' if s != 1 else ''}"
        m, r = divmod(s, 60)
        mins = f"{m} minuto{'s' if m != 1 else ''}"
        return mins if r == 0 else f"{mins} con {r} segundo{'s' if r != 1 else ''}"

    replacements = {
        # Fecha y hora
        "{fecha}":           now.strftime("%d/%m/%Y"),
        "{hora}":            now.strftime("%H:%M"),
        "{dia}":             dias[now.weekday()],
        # Pausas (desde cfg)
        "{pausa_cada}":      _fmt_seg(cfg.get("pause_tx_time",    200)),
        "{pausa_duracion}":  _fmt_seg(cfg.get("pause_duration",    10)),
        "{pausa_alerta}":    _fmt_seg(cfg.get("pause_alert_before", 10)),
        # Evento (desde ctx)
        "{evento}":              str(ctx.get("evento",              "")),
        "{num_secciones}":       str(ctx.get("num_secciones",       "")),
        "{duracion_total}":      str(ctx.get("duracion_total",      "")),
        "{dur_contabilizable}":  str(ctx.get("dur_contabilizable",  "")),
    }
    for token, value in replacements.items():
        text = text.replace(token, value)
    return text


def convert_text(text: str, cfg: dict,
                 output_path: Path = None,
                 on_done: callable = None,
                 ctx: dict = None) -> None:
    """
    Convierte texto a audio en hilo background.
    ctx: contexto opcional con datos del evento para resolver variables.
    on_done(ok: bool, path_or_error: str)
    """
    if output_path is None:
        output_path = TEMP_MP3

    def _run():
        resolved = resolve_variables(text, cfg, ctx)
        engine   = cfg.get("tts_engine", "pyttsx3")
        preview  = resolved[:80] + ("…" if len(resolved) > 80 else "")
        log.info("[TTS] Motor=%s | texto='%s'", engine, preview)
        if engine == "azure":
            ok, result = convert_azure(resolved, cfg, output_path)
        else:
            ok, result = convert_pyttsx3(resolved, cfg, output_path)
        if not ok:
            log.error("[TTS] Fallo en síntesis | motor=%s | error=%s", engine, result)
        if callable(on_done):
            on_done(ok, result)

    threading.Thread(target=_run, daemon=True).start()


# ── Utilidades de audio ───────────────────────────────────────────────────────
def save_audio_file(source: str, seccion_id: int,
                    seccion_nombre: str) -> str:
    """Copia y renombra a media/audios/{id}_{nombre}.ext"""
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    import shutil
    ext  = Path(source).suffix.lower() or ".mp3"
    safe = _sanitize(seccion_nombre)
    dest = AUDIO_DIR / f"{seccion_id}_{safe}{ext}"
    shutil.copy2(source, dest)
    return str(dest)


def get_audio_duration(filepath: str) -> float:
    """Retorna duración en segundos. Usa mutagen, con fallback MCI en Windows."""
    # Intento 1: mutagen
    try:
        from mutagen.mp3  import MP3
        from mutagen.wave import WAVE
        ext = Path(filepath).suffix.lower()
        if ext == ".mp3":
            return MP3(filepath).info.length
        if ext == ".wav":
            return WAVE(filepath).info.length
    except Exception:
        pass

    # Intento 2: MCI (Windows nativo, sin dependencias)
    try:
        import sys, ctypes
        if sys.platform == "win32":
            abs_path = str(Path(filepath).resolve())
            ext = Path(filepath).suffix.lower()
            media_type = "waveaudio" if ext == ".wav" else "mpegvideo"
            alias = "hamna_dur_probe"
            buf = ctypes.create_unicode_buffer(512)
            winmm = ctypes.windll.winmm
            winmm.mciSendStringW(
                f'open "{abs_path}" type {media_type} alias {alias}',
                buf, 512, 0)
            winmm.mciSendStringW(
                f'set {alias} time format milliseconds',
                buf, 512, 0)
            winmm.mciSendStringW(
                f'status {alias} length',
                buf, 512, 0)
            length_ms = buf.value.strip()
            winmm.mciSendStringW(f'close {alias}', buf, 512, 0)
            if length_ms.isdigit():
                return int(length_ms) / 1000.0
    except Exception:
        pass

    return 0.0


def _wav_to_mp3(wav_path: str, mp3_path: str) -> str:
    """Convierte WAV → MP3 con pydub si está disponible."""
    try:
        from pydub import AudioSegment
        AudioSegment.from_wav(wav_path).export(mp3_path, format="mp3")
        return mp3_path
    except Exception:
        return wav_path   # devolver WAV si no se puede convertir


def _sanitize(name: str) -> str:
    invalid = r'\/:*?"<>| '
    return "".join(c if c not in invalid else "_" for c in name)[:50]
