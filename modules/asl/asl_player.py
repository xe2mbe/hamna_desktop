"""
HAMNA Desktop — ASL Player
Sube audio a un nodo AllStarLink via SFTP y lo reproduce con rpt localplay.
El comando rpt localplay maneja el keying/unkeying del radio automáticamente.
"""
import logging
import socket
import threading
import time
from pathlib import Path

log = logging.getLogger(__name__)

# Tiempo extra en segundos después de la duración estimada antes de on_finished
_FINISH_BUFFER = 0.8


class ASLPlayer:
    """
    Flujo por sección:
      1. Convierte audio a WAV 8 kHz 16-bit mono (formato nativo Asterisk)
      2. Sube el WAV al nodo via SFTP → {remote_path}/{nombre}.wav
      3. Envía AMI Command: rpt localplay {node} {remote_path}/{nombre}
      4. Espera la duración del audio + buffer y llama on_finished
    """

    def __init__(self):
        self.node         = ""
        self.sftp_host    = ""
        self.sftp_port    = 22
        self.sftp_user    = ""
        self.sftp_pass    = ""
        self.remote_path  = "/tmp/hamna"
        self.ami_host     = ""
        self.ami_port     = 5038
        self.ami_user     = ""
        self.ami_pass     = ""

        self.on_finished  : callable | None = None
        self.on_status    : callable | None = None

        self._playing     = False
        self._stop_flag   = False

    # ── Conversión de audio ───────────────────────────────────────────────────
    def _to_asterisk_wav(self, path: Path) -> Path:
        """Convierte el archivo a WAV 8 kHz 16-bit mono (Asterisk nativo).
        Devuelve la ruta del WAV resultante."""
        out = path.parent / (path.stem + "_asl8k.wav")
        try:
            from pydub import AudioSegment
            audio = (AudioSegment.from_file(str(path))
                     .set_frame_rate(8000)
                     .set_channels(1)
                     .set_sample_width(2))
            audio.export(str(out), format="wav")
            log.info("[ASL] Convertido a WAV 8kHz mono → %s", out.name)
            return out
        except Exception as e:
            log.warning("[ASL] No se pudo convertir a 8kHz (%s) — usando original", e)
            return path

    # ── SFTP ─────────────────────────────────────────────────────────────────
    def _sftp_upload(self, local_path: Path) -> tuple[bool, str]:
        """Convierte y sube el archivo. Devuelve (ok, ruta_remota_sin_extension)."""
        try:
            import paramiko
        except ImportError:
            return False, "paramiko no instalado"

        wav = self._to_asterisk_wav(local_path)

        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(
                self.sftp_host, port=self.sftp_port,
                username=self.sftp_user, password=self.sftp_pass,
                timeout=15, banner_timeout=15)

            # Crear directorio remoto si no existe
            stdin, stdout, stderr = ssh.exec_command(
                f"mkdir -p {self.remote_path}")
            stdout.read()

            sftp = ssh.open_sftp()
            remote_file = f"{self.remote_path}/{wav.name}"
            sftp.put(str(wav), remote_file)
            sftp.close()
            ssh.close()

            # Ruta sin extensión (convención de Asterisk para Playback/rpt localplay)
            remote_no_ext = remote_file.rsplit(".", 1)[0]
            log.info("[ASL] SFTP upload OK → %s", remote_file)
            return True, remote_no_ext

        except Exception as e:
            log.error("[ASL] SFTP error: %s", e)
            return False, str(e)

    # ── AMI ──────────────────────────────────────────────────────────────────
    def _ami_send(self, command: str) -> tuple[bool, str]:
        """Abre conexión AMI, hace login, envía un Command y cierra."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(10)
            s.connect((self.ami_host, self.ami_port))

            # Banner
            s.recv(1024)

            # Login
            s.sendall(
                f"Action: Login\r\n"
                f"Username: {self.ami_user}\r\n"
                f"Secret: {self.ami_pass}\r\n\r\n"
                .encode())
            resp = s.recv(4096).decode(errors="ignore")
            if "Success" not in resp:
                s.close()
                return False, f"Login AMI fallido: {resp[:120]}"

            # Enviar Command
            s.sendall(
                f"Action: Command\r\n"
                f"Command: {command}\r\n\r\n"
                .encode())
            time.sleep(0.4)
            resp = s.recv(4096).decode(errors="ignore")
            s.close()

            log.info("[ASL] AMI cmd='%s' resp='%s'", command, resp[:80].strip())
            return True, resp

        except Exception as e:
            log.error("[ASL] AMI error: %s", e)
            return False, str(e)

    # ── Playback público ──────────────────────────────────────────────────────
    def play(self, filepath: str, duration: float,
             on_finished: callable = None) -> tuple[bool, str]:
        """
        Sube el archivo y lo reproduce en el nodo ASL.
        duration: duración en segundos del audio (para saber cuándo termina).
        on_finished: callback llamado al terminar (igual que AudioPlayer).
        """
        self.on_finished = on_finished
        self._stop_flag  = False
        self._playing    = True

        def _run():
            # 1. Upload
            self._notify("uploading", "Subiendo audio al nodo ASL…")
            ok, remote = self._sftp_upload(Path(filepath))
            if not ok:
                self._playing = False
                self._notify("error", f"SFTP: {remote}")
                return

            if self._stop_flag:
                self._playing = False
                return

            # 2. rpt localplay
            self._notify("playing", f"Reproduciendo en nodo {self.node}…")
            cmd = f"rpt localplay {self.node} {remote}"
            ok, msg = self._ami_send(cmd)
            if not ok:
                self._playing = False
                self._notify("error", f"AMI: {msg}")
                return

            # 3. Esperar duración + buffer
            wait    = max(duration, 1.0) + _FINISH_BUFFER
            elapsed = 0.0
            log.info("[ASL] Esperando %.1fs (dur=%.1f + buffer=%.1f)",
                     wait, duration, _FINISH_BUFFER)
            while elapsed < wait and not self._stop_flag:
                time.sleep(0.25)
                elapsed += 0.25

            self._playing = False
            if not self._stop_flag:
                self._notify("idle", "Reproducción completada")
                if callable(self.on_finished):
                    try:
                        self.on_finished()
                    except Exception:
                        pass

        threading.Thread(target=_run, daemon=True).start()
        return True, "Iniciando reproducción ASL"

    def stop(self) -> None:
        self._stop_flag = True
        self._playing   = False

    def is_playing(self) -> bool:
        return self._playing

    # ── Tests de conectividad ─────────────────────────────────────────────────
    def test_sftp(self) -> tuple[bool, str]:
        """Verifica SSH/SFTP y crea la carpeta remota."""
        try:
            import paramiko
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(
                self.sftp_host, port=self.sftp_port,
                username=self.sftp_user, password=self.sftp_pass,
                timeout=8)
            stdin, stdout, stderr = ssh.exec_command(
                f"mkdir -p {self.remote_path} && echo OK")
            out = stdout.read().decode().strip()
            ssh.close()
            if out == "OK":
                return True, f"SSH OK — {self.sftp_host}:{self.sftp_port}  carpeta: {self.remote_path}"
            return False, f"Error al crear carpeta: {stderr.read().decode()}"
        except Exception as e:
            return False, str(e)

    def test_ami(self) -> tuple[bool, str]:
        """Verifica conexión AMI y obtiene versión de Asterisk."""
        ok, resp = self._ami_send("core show version")
        if ok:
            # Extraer línea con la versión
            for line in resp.splitlines():
                if "Asterisk" in line or "AllStar" in line.lower():
                    return True, line.strip()
            return True, "AMI OK"
        return False, resp

    def test_localplay(self, test_file: str = None) -> tuple[bool, str]:
        """Envía un rpt localplay de prueba (con archivo de beep si no se especifica)."""
        audio = test_file or "beep"   # beep es un sonido estándar de Asterisk
        cmd = f"rpt localplay {self.node} {audio}"
        ok, msg = self._ami_send(cmd)
        return ok, msg[:120] if ok else msg

    # ── Helper ────────────────────────────────────────────────────────────────
    def _notify(self, status: str, msg: str) -> None:
        log.info("[ASL] status=%s  %s", status, msg)
        if callable(self.on_status):
            try:
                self.on_status(status, msg)
            except Exception:
                pass

    # ── Factory ───────────────────────────────────────────────────────────────
    @classmethod
    def from_cfg(cls, cfg: dict) -> "ASLPlayer":
        p = cls()
        p.node        = str(cfg.get("asl_node",        ""))
        p.sftp_host   = cfg.get("asl_sftp_host",        "")
        p.sftp_port   = int(cfg.get("asl_sftp_port",    22))
        p.sftp_user   = cfg.get("asl_sftp_user",        "")
        p.sftp_pass   = cfg.get("asl_sftp_pass",        "")
        p.remote_path = cfg.get("asl_remote_path",      "/tmp/hamna")
        p.ami_host    = cfg.get("asl_ami_host",          "")
        p.ami_port    = int(cfg.get("asl_ami_port",      5038))
        p.ami_user    = cfg.get("asl_ami_user",          "")
        p.ami_pass    = cfg.get("asl_ami_pass",          "")
        return p
