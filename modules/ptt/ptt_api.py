"""
HAMNA Desktop — PTT via API HTTP REST
Envía peticiones GET/POST al servidor de hardware existente.
"""
import threading
import logging
from typing import Callable

log = logging.getLogger(__name__)

try:
    import requests
    _REQUESTS_OK = True
except ImportError:
    _REQUESTS_OK = False
    log.warning("requests no instalado — PTT API deshabilitado")


class PTTApi:
    """Controla PTT enviando peticiones HTTP a un servidor existente."""

    def __init__(self):
        self._ptt_on = False
        self._connected = False
        self._lock = threading.Lock()
        self.on_status_change: Callable[[str, str], None] | None = None

        # Configuración
        self.base_url = "http://192.168.1.37"
        self.route_on  = "/ptt_on"
        self.route_off = "/ptt_off"
        self.method    = "GET"   # GET | POST | PUT
        self.api_key   = ""
        self.timeout   = 5       # segundos

    # ── Estado ────────────────────────────────────────────────────────────────
    def is_connected(self) -> bool:
        return self._connected

    def is_ptt_on(self) -> bool:
        return self._ptt_on

    def url_on(self) -> str:
        return self.base_url.rstrip("/") + self.route_on

    def url_off(self) -> str:
        return self.base_url.rstrip("/") + self.route_off

    # ── Test ──────────────────────────────────────────────────────────────────
    def test_connection(self, base_url: str, route_on: str, route_off: str,
                        method: str = "GET", api_key: str = "",
                        timeout: int = 5) -> tuple[bool, str]:
        self.base_url  = base_url
        self.route_on  = route_on
        self.route_off = route_off
        self.method    = method
        self.api_key   = api_key
        self.timeout   = timeout

        if not _REQUESTS_OK:
            return False, "requests no instalado"

        try:
            url = self.url_on()
            r = self._request(url)
            if r.ok or r.status_code in (200, 201, 202, 204):
                self._connected = True
                msg = f"Conectado · {base_url} · HTTP {r.status_code}"
                self._notify("connected", msg)
                return True, msg
            else:
                msg = f"HTTP {r.status_code}: {r.text[:60]}"
                self._notify("error", msg)
                return False, msg
        except Exception as e:
            msg = str(e)
            self._notify("error", msg)
            return False, msg

    # ── PTT ───────────────────────────────────────────────────────────────────
    def ptt_on(self) -> tuple[bool, str]:
        ok, msg = self._send(self.url_on())
        if ok:
            self._ptt_on = True
            log.info(f"PTT ON — API → {self.url_on()}")
        return ok, msg

    def ptt_off(self) -> tuple[bool, str]:
        ok, msg = self._send(self.url_off())
        if ok:
            self._ptt_on = False
            log.info(f"PTT OFF — API → {self.url_off()}")
        return ok, msg

    def toggle_ptt(self) -> tuple[bool, str]:
        return self.ptt_off() if self._ptt_on else self.ptt_on()

    # ── Internos ──────────────────────────────────────────────────────────────
    def _send(self, url: str) -> tuple[bool, str]:
        if not _REQUESTS_OK:
            return False, "requests no instalado"
        try:
            r = self._request(url)
            if r.ok or r.status_code in (200, 201, 202, 204):
                return True, f"HTTP {r.status_code}"
            return False, f"HTTP {r.status_code}: {r.text[:60]}"
        except Exception as e:
            return False, str(e)

    def _request(self, url: str):
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
            headers["X-API-Key"] = self.api_key

        method = self.method.upper()
        if method == "GET":
            return requests.get(url, headers=headers, timeout=self.timeout)
        elif method == "POST":
            return requests.post(url, headers=headers, timeout=self.timeout)
        elif method == "PUT":
            return requests.put(url, headers=headers, timeout=self.timeout)
        else:
            return requests.get(url, headers=headers, timeout=self.timeout)

    def _notify(self, status: str, msg: str) -> None:
        if callable(self.on_status_change):
            try:
                self.on_status_change(status, msg)
            except Exception:
                pass
