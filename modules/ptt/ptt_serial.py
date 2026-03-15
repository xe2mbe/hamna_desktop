"""
HAMNA Desktop — PTT via Serial RS-232 (RTS / DTR)
Activa el pin RTS o DTR del puerto serial para PTT.
Compatible con Windows COM1…COM255.
"""
import threading
import logging
from typing import Callable

log = logging.getLogger(__name__)

try:
    import serial
    import serial.tools.list_ports
    _SERIAL_OK = True
except ImportError:
    _SERIAL_OK = False
    log.warning("pyserial no instalado — PTT serial deshabilitado")


class PTTSerial:
    """Controla PTT activando el pin RTS o DTR de un puerto serial."""

    def __init__(self):
        self._port: serial.Serial | None = None
        self._lock = threading.Lock()
        self._ptt_on = False
        self.on_status_change: Callable[[str, str], None] | None = None
        # "status_type", "message" → "connected"|"disconnected"|"error", msg

    # ── Utilidades ────────────────────────────────────────────────────────────
    @staticmethod
    def list_ports() -> list[str]:
        if not _SERIAL_OK:
            return []
        return [p.device for p in serial.tools.list_ports.comports()]

    def is_connected(self) -> bool:
        return self._port is not None and self._port.is_open

    def is_ptt_on(self) -> bool:
        return self._ptt_on

    # ── Conexión ──────────────────────────────────────────────────────────────
    def connect(self, port: str, baudrate: int = 9600,
                pin: str = "RTS",
                invert_ptt: bool = False,
                invert_cos: bool = False) -> tuple[bool, str]:
        """
        Abre el puerto serial. PTT inactivo al conectar.
        Retorna (ok: bool, mensaje: str).
        """
        if not _SERIAL_OK:
            return False, "pyserial no está instalado"

        self._pin = pin.upper()
        self._invert_ptt = invert_ptt

        with self._lock:
            try:
                if self._port and self._port.is_open:
                    self._port.close()

                self._port = serial.Serial(
                    port=port,
                    baudrate=baudrate,
                    timeout=1,
                )
                # PTT OFF al conectar
                self._set_pin(False)
                self._ptt_on = False
                log.info(f"Serial conectado: {port} @ {baudrate} baud | pin={pin}")
                self._notify("connected", f"Conectado · {port} · {baudrate} baud")
                return True, f"Conectado a {port}"

            except serial.SerialException as e:
                msg = str(e)
                log.error(f"Error serial: {msg}")
                self._notify("error", msg)
                return False, msg

    def disconnect(self) -> None:
        with self._lock:
            if self._port and self._port.is_open:
                try:
                    self._set_pin(False)   # PTT OFF antes de cerrar
                    self._port.close()
                except Exception:
                    pass
            self._port = None
            self._ptt_on = False
            self._notify("disconnected", "Desconectado")

    # ── PTT ───────────────────────────────────────────────────────────────────
    def ptt_on(self) -> tuple[bool, str]:
        if not self.is_connected():
            return False, "Puerto no conectado"
        with self._lock:
            self._set_pin(True)
            self._ptt_on = True
            log.info("PTT ON — Serial")
            return True, "PTT ON"

    def ptt_off(self) -> tuple[bool, str]:
        if not self.is_connected():
            return False, "Puerto no conectado"
        with self._lock:
            self._set_pin(False)
            self._ptt_on = False
            log.info("PTT OFF — Serial")
            return True, "PTT OFF"

    def toggle_ptt(self) -> tuple[bool, str]:
        if self._ptt_on:
            return self.ptt_off()
        return self.ptt_on()

    # ── COS (Carrier Operated Squelch) ────────────────────────────────────────
    def read_cos(self) -> bool:
        """Lee el pin CTS como señal COS (carrier). False si no conectado."""
        if not self.is_connected():
            return False
        try:
            return self._port.cts
        except Exception:
            return False

    # ── Internos ──────────────────────────────────────────────────────────────
    def _set_pin(self, active: bool) -> None:
        """Activa/desactiva el pin RTS o DTR según configuración."""
        value = active ^ self._invert_ptt  # XOR para inversión
        try:
            if self._pin == "RTS":
                self._port.rts = value
            else:  # DTR
                self._port.dtr = value
        except Exception as e:
            log.error(f"Error al setear pin {self._pin}: {e}")

    def _notify(self, status: str, msg: str) -> None:
        if callable(self.on_status_change):
            try:
                self.on_status_change(status, msg)
            except Exception:
                pass
