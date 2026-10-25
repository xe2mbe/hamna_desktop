"""
HAMNA Desktop — Punto de entrada
Ejecutar: python main.py
"""
import os
import sys
import logging

# ── Path root ──────────────────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# ── Usar siempre el Python del .venv ───────────────────────────────────────
# Si se abre con "python main.py" sin activar el .venv, Windows usa el Python
# del sistema, que no tiene pygame, pydub, pyaudiowpatch, etc. (sin ellos no
# funcionan la normalización, el medidor ni el PTT serie). En ese caso se
# vuelve a abrir HAMNA con el Python del .venv.
_VENV_DIR = os.path.join(ROOT, ".venv")
_VENV_PY  = os.path.join(_VENV_DIR, "Scripts", "python.exe")
if (os.path.isfile(_VENV_PY)
        and os.path.normcase(os.path.realpath(sys.prefix))
            != os.path.normcase(os.path.realpath(_VENV_DIR))
        and not os.environ.get("HAMNA_SIN_VENV")):
    import subprocess
    print(f"HAMNA: se abrió con {sys.executable}; reabriendo con el .venv…")
    sys.exit(subprocess.call([_VENV_PY, os.path.abspath(__file__), *sys.argv[1:]]))

# ── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(ROOT, "hamna.log"),
                            encoding="utf-8"),
    ]
)
log = logging.getLogger("hamna")


def _ensure_deps() -> None:
    """Instala dependencias opcionales si no están presentes."""
    optional = [
        ("pyloudnorm", "pyloudnorm>=0.1.1"),
        ("numpy",      "numpy>=1.24.0"),
    ]
    missing = []
    for module, pkg in optional:
        try:
            __import__(module)
        except ImportError:
            missing.append(pkg)

    if not missing:
        return

    log.info("Instalando dependencias faltantes: %s", ", ".join(missing))
    try:
        import subprocess
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--quiet"] + missing,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        log.info("Dependencias instaladas correctamente.")
    except Exception as exc:
        log.warning("No se pudieron instalar dependencias automáticamente: %s", exc)


def main() -> None:
    log.info("HAMNA Desktop iniciando — Python %s", sys.version.split()[0])
    _ensure_deps()

    # Aplicar paleta de color antes de crear cualquier widget
    import settings as cfg_mod
    import i18n as _i18n
    from ui_theme import apply_palette
    _cfg = cfg_mod.load()
    _i18n.set_language(_cfg.get("language", "es"))
    apply_palette(_cfg.get("theme", "dark"))
    from ui_theme import apply_fonts
    apply_fonts(int(_cfg.get("font_size", 10)))

    from main_window import MainWindow
    app = MainWindow()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    log.info("Ventana principal lista")
    app.mainloop()
    log.info("HAMNA Desktop cerrado")


if __name__ == "__main__":
    main()
