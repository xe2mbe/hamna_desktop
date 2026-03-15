"""
HAMNA Desktop — PTT Manager
Fachada única que delega al método activo (Serial / AMI / API).
"""
import logging
from typing import Callable
from .ptt_serial import PTTSerial
from .ptt_ami    import PTTAmi
from .ptt_api    import PTTApi

log = logging.getLogger(__name__)


class PTTManager:
    """
    Punto de entrada unificado para el control PTT.
    Uso:
        mgr = PTTManager(settings)
        mgr.ptt_on()
        mgr.ptt_off()
    """

    def __init__(self, cfg: dict):
        self.serial = PTTSerial()
        self.ami    = PTTAmi()
        self.api    = PTTApi()
        self._cfg   = cfg
        self.on_ptt_change: Callable[[bool], None] | None = None
        self._apply_cfg(cfg)

    # ── Configurar desde settings ─────────────────────────────────────────────
    def _apply_cfg(self, cfg: dict) -> None:
        # Serial
        self.serial.on_status_change = self._fwd_serial_status

        # AMI
        self.ami.host     = cfg.get("ami_host",    "127.0.0.1")
        self.ami.port     = int(cfg.get("ami_port", 5038))
        self.ami.user     = cfg.get("ami_user",    "admin")
        self.ami.password = cfg.get("ami_password", "")
        self.ami.channel  = cfg.get("ami_channel", "SIP/radio")
        self.ami.context  = cfg.get("ami_context", "ptt-control")
        self.ami.on_status_change = self._fwd_ami_status

        # API
        self.api.base_url  = cfg.get("api_url",     "http://192.168.1.37")
        self.api.route_on  = cfg.get("api_ptt_on",  "/ptt_on")
        self.api.route_off = cfg.get("api_ptt_off", "/ptt_off")
        self.api.method    = cfg.get("api_method",  "GET")
        self.api.api_key   = cfg.get("api_key",     "")
        self.api.on_status_change = self._fwd_api_status

    def reload_cfg(self, cfg: dict) -> None:
        self._cfg = cfg
        self._apply_cfg(cfg)

    # ── PTT activo ────────────────────────────────────────────────────────────
    def _active_method(self) -> str:
        return self._cfg.get("ptt_method", "serial")

    def ptt_on(self) -> tuple[bool, str]:
        method = self._active_method()
        ok, msg = False, "Ningún método PTT activo"
        if method == "serial":
            ok, msg = self.serial.ptt_on()
        elif method == "ami":
            ok, msg = self.ami.ptt_on()
        elif method == "api":
            ok, msg = self.api.ptt_on()
        if ok and callable(self.on_ptt_change):
            self.on_ptt_change(True)
        return ok, msg

    def ptt_off(self) -> tuple[bool, str]:
        method = self._active_method()
        ok, msg = False, "Ningún método PTT activo"
        if method == "serial":
            ok, msg = self.serial.ptt_off()
        elif method == "ami":
            ok, msg = self.ami.ptt_off()
        elif method == "api":
            ok, msg = self.api.ptt_off()
        if ok and callable(self.on_ptt_change):
            self.on_ptt_change(False)
        return ok, msg

    def is_ptt_on(self) -> bool:
        method = self._active_method()
        if method == "serial": return self.serial.is_ptt_on()
        if method == "ami":    return self.ami.is_ptt_on()
        if method == "api":    return self.api.is_ptt_on()
        return False

    def is_connected(self) -> bool:
        method = self._active_method()
        if method == "serial": return self.serial.is_connected()
        if method == "ami":    return self.ami.is_connected()
        if method == "api":    return self.api.is_connected()
        return False

    # ── Callbacks de estado por método ────────────────────────────────────────
    # Los callbacks se pueden asignar desde la vista de Ajustes
    on_serial_status: Callable[[str, str], None] | None = None
    on_ami_status:    Callable[[str, str], None] | None = None
    on_api_status:    Callable[[str, str], None] | None = None

    def _fwd_serial_status(self, s, m):
        if callable(self.on_serial_status): self.on_serial_status(s, m)

    def _fwd_ami_status(self, s, m):
        if callable(self.on_ami_status): self.on_ami_status(s, m)

    def _fwd_api_status(self, s, m):
        if callable(self.on_api_status): self.on_api_status(s, m)
