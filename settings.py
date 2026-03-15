"""
HAMNA Desktop — Gestión de configuración (settings.json)
"""
import json
import os
from pathlib import Path

SETTINGS_PATH = Path(__file__).parent / "settings.json"

DEFAULTS: dict = {
    # TTS
    "tts_engine":      "pyttsx3",   # "pyttsx3" | "azure"
    "tts_rate":        175,
    "tts_volume":      90,
    "tts_pitch":       0,
    "tts_voice_id":    "",
    "azure_key":       "",
    "azure_region":    "",
    "azure_voice":     "es-MX-DaliaNeural",
    "azure_style":     "general",
    "azure_rate":      100,
    "azure_pitch":     0,
    "azure_format":    "audio-24khz-160kbitrate-mono-mp3",
    "azure_cache":     True,
    "azure_ssml":      False,
    "azure_endpoint":  "",

    # PTT método activo
    "ptt_method":      "serial",    # "serial" | "ami" | "api"

    # PTT Serial
    "serial_enabled":  True,
    "serial_port":     "COM1",
    "serial_baud":     9600,
    "serial_pin":      "RTS",       # "RTS" | "DTR"
    "serial_invert_ptt": False,
    "serial_invert_cos": False,

    # PTT AMI
    "ami_enabled":     False,
    "ami_host":        "127.0.0.1",
    "ami_port":        5038,
    "ami_user":        "admin",
    "ami_password":    "",
    "ami_channel":     "SIP/radio",
    "ami_context":     "ptt-control",

    # PTT API
    "api_enabled":     False,
    "api_url":         "http://192.168.1.37",
    "api_ptt_on":      "/ptt_on",
    "api_ptt_off":     "/ptt_off",
    "api_method":      "GET",
    "api_key":         "",

    # Audio
    "audio_device":    "",
    "audio_volume":    85,

    # General
    "theme":           "dark",
    "language":        "es",
    "start_minimized": False,
    "confirm_close":   True,

    # Tiempos y Pausas
    "pause_enabled":           False,
    "pause_tx_time":           120,   # segundos de TX antes de pausar
    "pause_duration":          30,    # segundos de pausa
    "pause_alert_before":      10,    # segundos antes de pausa para alerta
    "pause_alert_file":        "",    # ruta audio alerta
    "pause_announcement_file": "",    # ruta audio "en pausa"
    "pause_resume_file":       "",    # ruta audio "continuamos"
}


def load() -> dict:
    cfg = DEFAULTS.copy()
    if SETTINGS_PATH.is_file():
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                stored = json.load(f)
                cfg.update(stored)
        except Exception:
            pass
    return cfg


def save(cfg: dict) -> None:
    merged = DEFAULTS.copy()
    merged.update(cfg)
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2, ensure_ascii=False)
