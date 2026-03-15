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

    try:
        engine = pyttsx3.init()
        engine.setProperty("rate",   int(cfg.get("tts_rate", 175)))
        engine.setProperty("volume", float(cfg.get("tts_volume", 90)) / 100.0)

        # Seleccionar voz
        voice_id = cfg.get("tts_voice_id", "")
        if voice_id:
            engine.setProperty("voice", voice_id)
        else:
            # Auto: buscar voz en español
            for v in engine.getProperty("voices"):
                if any(lang in v.id.lower() for lang in ["spanish", "es_", "es-"]):
                    engine.setProperty("voice", v.id)
                    break

        # Guardar a WAV primero
        wav_path = str(TEMP_WAV)
        engine.save_to_file(text, wav_path)
        engine.runAndWait()

        if not Path(wav_path).is_file():
            return False, "pyttsx3 no generó el archivo de audio"

        # Intentar WAV → MP3
        final_path = _wav_to_mp3(wav_path, str(output_path))
        return True, str(final_path)

    except Exception as e:
        log.error(f"pyttsx3 error: {e}")
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


# ── Azure TTS ─────────────────────────────────────────────────────────────────
def convert_azure(text: str, cfg: dict,
                  output_path: Path = TEMP_MP3) -> tuple[bool, str]:
    """Convierte texto a audio usando Azure Cognitive Services."""
    try:
        import azure.cognitiveservices.speech as speechsdk
    except ImportError:
        return False, ("azure-cognitiveservices-speech no instalado.\n"
                       "Ejecuta: pip install azure-cognitiveservices-speech")

    key    = cfg.get("azure_key", "").strip()
    region = cfg.get("azure_region", "").strip()
    if not key or not region:
        return False, "Configura la clave y región de Azure en Ajustes → Motor TTS"

    voice  = cfg.get("azure_voice",  "es-MX-DaliaNeural")
    style  = cfg.get("azure_style",  "general")
    rate   = int(cfg.get("azure_rate", 100))
    pitch  = int(cfg.get("azure_pitch", 0))

    try:
        speech_cfg = speechsdk.SpeechConfig(subscription=key, region=region)

        # Endpoint personalizado
        endpoint = cfg.get("azure_endpoint", "").strip()
        if endpoint:
            speech_cfg.endpoint_id = endpoint

        # Formato de salida
        fmt_map = {
            "audio-16khz-128kbitrate-mono-mp3": speechsdk.SpeechSynthesisOutputFormat.Audio16Khz128KBitRateMonoMp3,
            "audio-24khz-160kbitrate-mono-mp3": speechsdk.SpeechSynthesisOutputFormat.Audio24Khz160KBitRateMonoMp3,
            "audio-48khz-192kbitrate-mono-mp3": speechsdk.SpeechSynthesisOutputFormat.Audio48Khz192KBitRateMonoMp3,
            "riff-16khz-16bit-mono-pcm":        speechsdk.SpeechSynthesisOutputFormat.Riff16Khz16BitMonoPcm,
        }
        fmt_key = cfg.get("azure_format", "audio-24khz-160kbitrate-mono-mp3")
        speech_cfg.set_speech_synthesis_output_format(
            fmt_map.get(fmt_key, speechsdk.SpeechSynthesisOutputFormat.Audio24Khz160KBitRateMonoMp3)
        )

        audio_cfg = speechsdk.audio.AudioOutputConfig(filename=str(output_path))
        synth = speechsdk.SpeechSynthesizer(
            speech_config=speech_cfg, audio_config=audio_cfg
        )

        # Usar SSML si está habilitado o si hay estilo/parámetros
        use_ssml = cfg.get("azure_ssml", False) or style != "general" or rate != 100 or pitch != 0
        if use_ssml:
            rate_str  = f"+{rate-100}%" if rate >= 100 else f"-{100-rate}%"
            pitch_str = f"+{pitch}Hz" if pitch >= 0 else f"{pitch}Hz"
            ssml = (
                f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
                f'xml:lang="es-MX">'
                f'<voice name="{voice}">'
                f'<mstts:express-as xmlns:mstts="http://www.w3.org/2001/mstts" style="{style}">'
                f'<prosody rate="{rate_str}" pitch="{pitch_str}">{text}</prosody>'
                f'</mstts:express-as></voice></speak>'
            )
            result = synth.speak_ssml_async(ssml).get()
        else:
            speech_cfg.speech_synthesis_voice_name = voice
            result = synth.speak_text_async(text).get()

        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            return True, str(output_path)
        else:
            details = result.cancellation_details if hasattr(result, "cancellation_details") else ""
            return False, f"Azure TTS falló: {result.reason} {details}"

    except Exception as e:
        log.error(f"Azure TTS error: {e}")
        return False, str(e)


def get_azure_voices(key: str, region: str) -> list[dict]:
    """Retorna voces neurales disponibles para la región."""
    try:
        import azure.cognitiveservices.speech as speechsdk
        cfg = speechsdk.SpeechConfig(subscription=key, region=region)
        synth = speechsdk.SpeechSynthesizer(speech_config=cfg, audio_config=None)
        result = synth.get_voices_async().get()
        voices = []
        for v in result.voices:
            voices.append({
                "name":        v.short_name,
                "display":     v.local_name,
                "locale":      v.locale,
                "gender":      str(v.gender),
                "voice_type":  str(v.voice_type),
            })
        return sorted(voices, key=lambda x: x["locale"])
    except Exception:
        return []


# ── Fachada principal ─────────────────────────────────────────────────────────
def convert_text(text: str, cfg: dict,
                 output_path: Path = None,
                 on_done: callable = None) -> None:
    """
    Convierte texto a audio en hilo background.
    on_done(ok: bool, path_or_error: str)
    """
    if output_path is None:
        output_path = TEMP_MP3

    def _run():
        engine = cfg.get("tts_engine", "pyttsx3")
        if engine == "azure":
            ok, result = convert_azure(text, cfg, output_path)
        else:
            ok, result = convert_pyttsx3(text, cfg, output_path)
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
