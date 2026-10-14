"""Concurrent TCP directory server for temporary P2P presence."""

from __future__ import annotations

import argparse
import json
import logging
import socket
import socketserver
import threading
from typing import Any

LOGGER = logging.getLogger("directory")
MAX_REQUEST_BYTES = 4096
MAX_USERNAME_LENGTH = 32


class DirectoryServer:
    """Keep track of logged-in peers and broadcast the current directory."""

    def __init__(self, host: str = "0.0.0.0", port: int = 9000) -> None:
        self.host = host
        self.port = port
        self._lock = threading.RLock()
        self._clients: dict[str, _ClientHandler] = {}
        self._server: _ThreadingTCPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def address(self) -> tuple[str, int]:
        if self._server is None:
            return self.host, self.port
        address = self._server.server_address
        return str(address[0]), int(address[1])

    def start(self) -> tuple[str, int]:
        """Bind the listening socket and start its accept loop in a thread."""
        if self._server is not None:
            raise RuntimeError("El servidor ya está iniciado.")
        self._server = _ThreadingTCPServer((self.host, self.port), self)
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="directory-accept",
            daemon=True,
        )
        self._thread.start()
        LOGGER.info("Directorio escuchando en %s:%s", *self.address)
        return self.address

    def close(self) -> None:
        """Stop accepting connections and close all active peer sockets."""
        server = self._server
        if server is None:
            return
        server.shutdown()
        server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=2)
        with self._lock:
            clients = list(self._clients.values())
            self._clients.clear()
        for client in clients:
            client.close_connection()
        self._server = None
        self._thread = None

    def register(self, client: _ClientHandler, username: str, p2p_port: int) -> bool:
        key = username.casefold()
        with self._lock:
            if key in self._clients:
                client.send({"type": "error", "message": "Ese usuario ya está conectado."})
                return False
            client.username = username
            client.p2p_port = p2p_port
            client.ip_address = str(client.client_address[0])
            self._clients[key] = client
            client.send(
                {
                    "type": "login_ok",
                    "username": username,
                    "users": self._users_locked(),
                }
            )
            self._broadcast_locked(exclude=client)
        LOGGER.info("Usuario conectado: %s (%s:%s)", username, client.ip_address, p2p_port)
        return True

    def unregister(self, client: _ClientHandler) -> None:
        if client.username is None:
            return
        with self._lock:
            key = client.username.casefold()
            if self._clients.get(key) is not client:
                return
            del self._clients[key]
            self._broadcast_locked()
        LOGGER.info("Usuario desconectado: %s", client.username)

    def _users_locked(self) -> list[dict[str, Any]]:
        return [
            {
                "username": client.username,
                "ip": client.ip_address,
                "port": client.p2p_port,
            }
            for client in sorted(
                self._clients.values(),
                key=lambda item: (item.username or "").casefold(),
            )
        ]

    def _broadcast_locked(self, exclude: _ClientHandler | None = None) -> None:
        message = {"type": "users", "users": self._users_locked()}
        for client in tuple(self._clients.values()):
            if client is exclude:
                continue
            try:
                client.send(message)
            except OSError:
                client.close_connection()


class _ThreadingTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True
    block_on_close = False

    def __init__(self, address: tuple[str, int], directory: DirectoryServer) -> None:
        self.directory = directory
        super().__init__(address, _ClientHandler)


class _ClientHandler(socketserver.StreamRequestHandler):
    directory: DirectoryServer

    def setup(self) -> None:
        super().setup()
        self._write_lock = threading.Lock()
        self.username: str | None = None
        self.ip_address = ""
        self.p2p_port = 0

    def handle(self) -> None:
        try:
            line = self.rfile.readline(MAX_REQUEST_BYTES + 1)
            if not line or len(line) > MAX_REQUEST_BYTES or not line.endswith(b"\n"):
                self._send_error("La solicitud está vacía o excede el tamaño permitido.")
                return
            try:
                request = json.loads(line.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                self._send_error("La solicitud debe ser JSON válido en UTF-8.")
                return
            if not isinstance(request, dict) or request.get("type") != "login":
                self._send_error("La primera solicitud debe ser de tipo login.")
                return

            username = request.get("username")
            p2p_port = request.get("p2p_port")
            if not self._valid_username(username):
                self._send_error(
                    "El usuario debe tener entre 1 y "
                    f"{MAX_USERNAME_LENGTH} caracteres y no incluir controles."
                )
                return
            if (
                isinstance(p2p_port, bool)
                or not isinstance(p2p_port, int)
                or not 1 <= p2p_port <= 65535
            ):
                self._send_error("El puerto P2P debe ser un número entre 1 y 65535.")
                return
            if not self.server.directory.register(self, username.strip(), p2p_port):
                return

            while self.rfile.readline(MAX_REQUEST_BYTES + 1):
                self._send_error("El directorio solo acepta la solicitud inicial de login.")
                return
        except (ConnectionError, OSError, TimeoutError):
            LOGGER.debug("Conexión cerrada durante el intercambio con %s", self.client_address)
        finally:
            self.server.directory.unregister(self)

    @staticmethod
    def _valid_username(value: object) -> bool:
        return (
            isinstance(value, str)
            and 1 <= len(value.strip()) <= MAX_USERNAME_LENGTH
            and not any(ord(character) < 32 or ord(character) == 127 for character in value)
        )

    def _send_error(self, message: str) -> None:
        try:
            self.send({"type": "error", "message": message})
        except OSError:
            LOGGER.debug("No se pudo devolver un error a %s", self.client_address)

    def send(self, message: dict[str, Any]) -> None:
        encoded = json.dumps(message, ensure_ascii=False).encode("utf-8") + b"\n"
        with self._write_lock:
            self.wfile.write(encoded)
            self.wfile.flush()

    def close_connection(self) -> None:
        try:
            self.request.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.request.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Servidor de directorio para la red P2P.")
    parser.add_argument("--host", default="0.0.0.0", help="Dirección de escucha (por defecto: todas)")
    parser.add_argument("--port", type=int, default=9000, help="Puerto de escucha (por defecto: 9000)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    directory = DirectoryServer(args.host, args.port)
    try:
        host, port = directory.start()
        print(f"Servidor de directorio activo en {host}:{port}. Ctrl+C para detener.")
        assert directory._thread is not None
        directory._thread.join()
    except KeyboardInterrupt:
        print("\nDeteniendo servidor...")
    finally:
        directory.close()


if __name__ == "__main__":
    main()
