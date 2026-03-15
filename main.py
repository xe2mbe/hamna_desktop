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


def main() -> None:
    log.info("HAMNA Desktop iniciando — Python %s", sys.version.split()[0])

    from main_window import MainWindow
    app = MainWindow()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    log.info("Ventana principal lista")
    app.mainloop()
    log.info("HAMNA Desktop cerrado")


if __name__ == "__main__":
    main()
