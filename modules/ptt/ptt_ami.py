"""
HAMNA Desktop — PTT via Asterisk AMI (Manager Interface)
Protocolo AMI con socket TCP puro — sin dependencias externas.
Envía Action: Originate para PTT ON / OFF.
"""
import socket
import threading
import logging
import time

log = logging.getLogger(__name__)

_AMI_TIMEOUT = 5  # segundos


class PTTAmi:
    """Controla PTT enviando acciones AMI a Asterisk."""

    def __init__(self):
        self._sock: socket.socket | None = None
        self._lock = threading.Lock()
        self._connected = False
        self._ptt_on = False
        self.on_status_change = None  # Callable[[str, str], None]

        # Configuración
        self.host = "127.0.0.1"
        self.port = 5038
        self.user = "admin"
        self.password = ""
        self.channel = "SIP/radio"
        self.context = "ptt-control"

    # ── Estado ────────────────────────────────────────────────────────────────
    def is_connected(self) -> bool:
        return self._connected

    def is_ptt_on(self) -> bool:
        return self._ptt_on

    # ── Conexión ──────────────────────────────────────────────────────────────
    def connect(self, host: str, port: int, user: str,
                password: str, channel: str = "SIP/radio",
                context: str = "ptt-control") -> tuple[bool, str]:
        self.host, self.port, self.user = host, port, user
        self.password, self.channel, self.context = password, channel, context

        with self._lock:
            try:
                self._close_socket()
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(_AMI_TIMEOUT)
                s.connect((host, port))

                # Leer banner
                banner = s.recv(1024).decode("utf-8", errors="ignore").strip()
                if "Asterisk" not in banner:
                    s.close()
                    return False, f"Banner inesperado: {banner[:60]}"

                # Login
                login_action = (
                    f"Action: Login\r\n"
                    f"Username: {user}\r\n"
                    f"Secret: {password}\r\n"
                    f"\r\n"
                )
                s.sendall(login_action.encode())
                response = self._read_response(s)

                if "Success" not in response and "Authentication accepted" not in response:
                    s.close()
                    return False, f"Login fallido: {response[:80]}"

                self._sock = s
                self._connected = True
                log.info(f"AMI conectado: {host}:{port}")
                self._notify("connected", f"Conectado · {host}:{port}")
                return True, f"Conectado a {host}:{port}"

            except (socket.timeout, ConnectionRefusedError, OSError) as e:
                msg = str(e)
                log.error(f"AMI error: {msg}")
                self._notify("error", msg)
                return False, msg

    def disconnect(self) -> None:
        with self._lock:
            try:
                if self._sock:
                    self._sock.sendall(b"Action: Logoff\r\n\r\n")
                    time.sleep(0.1)
            except Exception:
                pass
            self._close_socket()
            self._connected = False
            self._ptt_on = False
            self._notify("disconnected", "Desconectado")

    # ── PTT ───────────────────────────────────────────────────────────────────
    def ptt_on(self) -> tuple[bool, str]:
        ok, msg = self._originate("ptt-on")
        if ok:
            self._ptt_on = True
            log.info("PTT ON — AMI")
        return ok, msg

    def ptt_off(self) -> tuple[bool, str]:
        ok, msg = self._originate("ptt-off")
        if ok:
            self._ptt_on = False
            log.info("PTT OFF — AMI")
        return ok, msg

    def toggle_ptt(self) -> tuple[bool, str]:
        return self.ptt_off() if self._ptt_on else self.ptt_on()

    # ── Test de conexión (sin login completo) ─────────────────────────────────
    def test_connection(self, host: str, port: int,
                        user: str, password: str) -> tuple[bool, str]:
        return self.connect(host, port, user, password)

    # ── Internos ──────────────────────────────────────────────────────────────
    def _originate(self, exten: str) -> tuple[bool, str]:
        if not self._connected or not self._sock:
            return False, "AMI no conectado"
        action = (
            f"Action: Originate\r\n"
            f"Channel: {self.channel}\r\n"
            f"Context: {self.context}\r\n"
            f"Exten: {exten}\r\n"
            f"Priority: 1\r\n"
            f"Async: true\r\n"
            f"\r\n"
        )
        with self._lock:
            try:
                self._sock.sendall(action.encode())
                response = self._read_response(self._sock)
                if "Error" in response:
                    return False, response[:100]
                return True, "OK"
            except Exception as e:
                self._connected = False
                self._notify("error", str(e))
                return False, str(e)

    def _read_response(self, sock: socket.socket, timeout: float = 3.0) -> str:
        """Lee hasta encontrar doble CRLF (fin de paquete AMI)."""
        buf = b""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                buf += chunk
                if b"\r\n\r\n" in buf:
                    break
            except socket.timeout:
                break
        return buf.decode("utf-8", errors="ignore")

    def _close_socket(self) -> None:
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None

    def _notify(self, status: str, msg: str) -> None:
        if callable(self.on_status_change):
            try:
                self.on_status_change(status, msg)
            except Exception:
                pass
