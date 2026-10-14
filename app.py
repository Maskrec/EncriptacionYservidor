"""PyQt6 client for signing in to and browsing the P2P directory."""

from __future__ import annotations

import json
import socket
import threading
from typing import Any

from PyQt6.QtCore import QThread, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

MAX_RESPONSE_BYTES = 65536


class DirectoryConnection(QThread):
    login_succeeded = pyqtSignal(str, list)
    users_updated = pyqtSignal(list)
    connection_failed = pyqtSignal(str)
    connection_closed = pyqtSignal()

    def __init__(
        self,
        host: str,
        directory_port: int,
        username: str,
        p2p_port: int,
    ) -> None:
        super().__init__()
        self.host = host
        self.directory_port = directory_port
        self.username = username
        self.p2p_port = p2p_port
        self._stopping = threading.Event()
        self._socket_lock = threading.Lock()
        self._socket: socket.socket | None = None

    def run(self) -> None:
        buffer = bytearray()
        authenticated = False
        try:
            connection = socket.create_connection(
                (self.host, self.directory_port),
                timeout=5,
            )
            with self._socket_lock:
                self._socket = connection
            connection.settimeout(0.5)
            request = {
                "type": "login",
                "username": self.username,
                "p2p_port": self.p2p_port,
            }
            connection.sendall(json.dumps(request).encode("utf-8") + b"\n")

            while not self._stopping.is_set():
                try:
                    chunk = connection.recv(4096)
                except socket.timeout:
                    continue
                if not chunk:
                    break
                buffer.extend(chunk)
                if len(buffer) > MAX_RESPONSE_BYTES:
                    raise ValueError("La respuesta del directorio excede el tamaño permitido.")
                while b"\n" in buffer:
                    line, _, remainder = buffer.partition(b"\n")
                    buffer = bytearray(remainder)
                    response = json.loads(line.decode("utf-8"))
                    if not isinstance(response, dict):
                        raise ValueError("El directorio devolvió una respuesta inválida.")
                    message_type = response.get("type")
                    if message_type == "error":
                        raise ValueError(str(response.get("message", "Error de acceso.")))
                    if message_type == "login_ok" and not authenticated:
                        users = self._parse_users(response.get("users"))
                        authenticated = True
                        self.login_succeeded.emit(str(response.get("username", "")), users)
                    elif message_type == "users" and authenticated:
                        self.users_updated.emit(self._parse_users(response.get("users")))
                    else:
                        raise ValueError("El directorio envió un evento inesperado.")
        except (OSError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
            if not self._stopping.is_set():
                self.connection_failed.emit(str(error))
        finally:
            with self._socket_lock:
                connection = self._socket
                self._socket = None
            if connection is not None:
                connection.close()
            if authenticated:
                self.connection_closed.emit()

    @staticmethod
    def _parse_users(value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            raise ValueError("La lista de usuarios recibida no es válida.")
        users: list[dict[str, Any]] = []
        for user in value:
            if (
                not isinstance(user, dict)
                or not isinstance(user.get("username"), str)
                or not isinstance(user.get("ip"), str)
                or isinstance(user.get("port"), bool)
                or not isinstance(user.get("port"), int)
            ):
                raise ValueError("El directorio devolvió un usuario con datos inválidos.")
            users.append(
                {
                    "username": user["username"],
                    "ip": user["ip"],
                    "port": user["port"],
                }
            )
        return users

    def stop(self) -> None:
        self._stopping.set()
        with self._socket_lock:
            connection = self._socket
        if connection is not None:
            try:
                connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            connection.close()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Red P2P | Directorio")
        self.setMinimumSize(800, 560)
        self.resize(980, 650)
        self.connection: DirectoryConnection | None = None
        self.users: list[dict[str, Any]] = []

        self.pages = QStackedWidget()
        self.login_page = self._build_login_page()
        self.directory_page = self._build_directory_page()
        self.pages.addWidget(self.login_page)
        self.pages.addWidget(self.directory_page)
        self.setCentralWidget(self.pages)

    def _build_login_page(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(40, 30, 40, 30)
        outer.addStretch()

        card = QFrame()
        card.setObjectName("card")
        card.setMaximumWidth(470)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(34, 32, 34, 30)
        layout.setSpacing(14)

        brand = QLabel("RED P2P")
        brand.setObjectName("brand")
        title = QLabel("Conéctate al directorio")
        title.setObjectName("title")
        subtitle = QLabel("Inicia sesión para descubrir los nodos disponibles.")
        subtitle.setObjectName("muted")
        subtitle.setWordWrap(True)
        layout.addWidget(brand)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        self.username_input = self._field(layout, "Nombre de usuario", "ej. Alex")
        self.host_input = self._field(layout, "IP o nombre del servidor", "127.0.0.1")
        self.directory_port_input = self._field(layout, "Puerto del directorio", "9000")
        self.p2p_port_input = self._field(layout, "Puerto local P2P", "5000")

        self.login_status = QLabel("")
        self.login_status.setObjectName("error")
        self.login_status.setWordWrap(True)
        layout.addWidget(self.login_status)

        self.login_button = QPushButton("Conectar")
        self.login_button.setObjectName("primary")
        self.login_button.clicked.connect(self._login)
        layout.addWidget(self.login_button)

        note = QLabel("El directorio solo anuncia usuarios conectados; el chat P2P se integrará después.")
        note.setObjectName("muted")
        note.setWordWrap(True)
        layout.addWidget(note)

        wrapper = QHBoxLayout()
        wrapper.addStretch()
        wrapper.addWidget(card)
        wrapper.addStretch()
        outer.addLayout(wrapper)
        outer.addStretch()
        return page

    @staticmethod
    def _field(layout: QVBoxLayout, label: str, placeholder: str) -> QLineEdit:
        field_label = QLabel(label)
        field_label.setObjectName("fieldLabel")
        field = QLineEdit()
        field.setPlaceholderText(placeholder)
        layout.addWidget(field_label)
        layout.addWidget(field)
        return field

    def _build_directory_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(26, 22, 26, 24)
        layout.setSpacing(18)

        header = QHBoxLayout()
        brand = QLabel("RED P2P")
        brand.setObjectName("brand")
        header.addWidget(brand)
        header.addStretch()
        self.current_user_label = QLabel("")
        self.current_user_label.setObjectName("onlineBadge")
        header.addWidget(self.current_user_label)
        logout_button = QPushButton("Desconectar")
        logout_button.clicked.connect(self._logout)
        header.addWidget(logout_button)
        layout.addLayout(header)

        intro = QVBoxLayout()
        title = QLabel("Nodos conectados")
        title.setObjectName("title")
        subtitle = QLabel("Usuarios registrados actualmente en este servidor de directorio.")
        subtitle.setObjectName("muted")
        intro.addWidget(title)
        intro.addWidget(subtitle)
        layout.addLayout(intro)

        body = QHBoxLayout()
        body.setSpacing(16)
        left = QFrame()
        left.setObjectName("card")
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(18, 18, 18, 18)
        left_layout.setSpacing(12)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar usuario...")
        self.search_input.textChanged.connect(self._render_users)
        left_layout.addWidget(self.search_input)
        self.user_list = QListWidget()
        self.user_list.currentItemChanged.connect(self._select_user)
        left_layout.addWidget(self.user_list)
        body.addWidget(left, 1)

        right = QFrame()
        right.setObjectName("card")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(26, 24, 26, 24)
        right_layout.addStretch()
        self.peer_name_label = QLabel("Selecciona un usuario")
        self.peer_name_label.setObjectName("peerTitle")
        self.peer_name_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.peer_address_label = QLabel("Su dirección P2P aparecerá aquí.")
        self.peer_address_label.setObjectName("muted")
        self.peer_address_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.chat_placeholder = QLabel(
            "El chat y la transferencia de archivos P2P se conectarán en una siguiente etapa."
        )
        self.chat_placeholder.setObjectName("placeholder")
        self.chat_placeholder.setWordWrap(True)
        self.chat_placeholder.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        right_layout.addWidget(self.peer_name_label)
        right_layout.addWidget(self.peer_address_label)
        right_layout.addSpacing(22)
        right_layout.addWidget(self.chat_placeholder)
        right_layout.addStretch()
        body.addWidget(right, 2)
        layout.addLayout(body, 1)

        self.directory_status = QLabel("")
        self.directory_status.setObjectName("muted")
        layout.addWidget(self.directory_status)
        return page

    def _login(self) -> None:
        if self.connection is not None and self.connection.isRunning():
            return
        username = self.username_input.text().strip()
        host = self.host_input.text().strip()
        try:
            directory_port = int(self.directory_port_input.text())
            p2p_port = int(self.p2p_port_input.text())
            if not username or not host:
                raise ValueError("Completa el usuario y la dirección del servidor.")
            if not 1 <= directory_port <= 65535 or not 1 <= p2p_port <= 65535:
                raise ValueError("Los puertos deben estar entre 1 y 65535.")
        except ValueError as error:
            self.login_status.setText(str(error))
            return

        self.login_status.setText("Conectando...")
        self.login_button.setEnabled(False)
        self.connection = DirectoryConnection(host, directory_port, username, p2p_port)
        self.connection.login_succeeded.connect(self._login_succeeded)
        self.connection.users_updated.connect(self._set_users)
        self.connection.connection_failed.connect(self._connection_failed)
        self.connection.connection_closed.connect(self._connection_closed)
        self.connection.finished.connect(self._thread_finished)
        self.connection.start()

    def _login_succeeded(self, username: str, users: list) -> None:
        self.current_user_label.setText(f"●  {username} · En línea")
        self.directory_status.setText("Conectado al servidor de directorio.")
        self.pages.setCurrentWidget(self.directory_page)
        self._set_users(users)

    def _set_users(self, users: list) -> None:
        self.users = users
        self._render_users()

    def _render_users(self) -> None:
        selected_username = None
        current = self.user_list.currentItem()
        if current is not None:
            selected_username = current.data(Qt.ItemDataRole.UserRole)
        needle = self.search_input.text().casefold()
        self.user_list.clear()
        selected_item = None
        for user in self.users:
            username = str(user["username"])
            if needle not in username.casefold():
                continue
            item = QListWidgetItem(f"●  {username}\n     {user['ip']}:{user['port']}")
            item.setData(Qt.ItemDataRole.UserRole, username)
            item.setData(Qt.ItemDataRole.UserRole + 1, user)
            self.user_list.addItem(item)
            if username == selected_username:
                selected_item = item
        if selected_item is not None:
            self.user_list.setCurrentItem(selected_item)
        elif self.user_list.count():
            self.user_list.setCurrentRow(0)
        else:
            self.peer_name_label.setText("No hay usuarios")
            self.peer_address_label.setText("Cuando alguien inicie sesión aparecerá aquí.")
        count = len(self.users)
        self.directory_status.setText(
            f"{count} usuario{'s' if count != 1 else ''} conectado{'s' if count != 1 else ''}"
        )

    def _select_user(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        if current is None:
            return
        user = current.data(Qt.ItemDataRole.UserRole + 1)
        self.peer_name_label.setText(str(user["username"]))
        self.peer_address_label.setText(f"{user['ip']}:{user['port']}")

    def _connection_failed(self, message: str) -> None:
        if self.pages.currentWidget() == self.login_page:
            self.login_status.setText(message)
        else:
            self.directory_status.setText(f"Conexión interrumpida: {message}")

    def _connection_closed(self) -> None:
        if self.pages.currentWidget() == self.directory_page:
            self.directory_status.setText("Se perdió la conexión con el directorio.")
            self.current_user_label.setText("Desconectado")

    def _thread_finished(self) -> None:
        self.login_button.setEnabled(True)

    def _logout(self) -> None:
        self._stop_connection()
        self.users.clear()
        self.pages.setCurrentWidget(self.login_page)
        self.login_status.clear()

    def _stop_connection(self) -> None:
        connection = self.connection
        self.connection = None
        if connection is not None:
            connection.stop()
            connection.wait(1500)

    def closeEvent(self, event: Any) -> None:
        self._stop_connection()
        event.accept()


def main() -> None:
    app = QApplication([])
    app.setStyle("Fusion")
    app.setStyleSheet(
        """
        QWidget { background: #f7f4ef; color: #292722; font-family: "Segoe UI"; font-size: 10pt; }
        QFrame#card { background: #ffffff; border: 1px solid #e8e2da; border-radius: 12px; }
        QLabel#brand { color: #c5470b; font-size: 11pt; font-weight: 800; letter-spacing: 1px; }
        QLabel#title { font-size: 23pt; font-weight: 700; }
        QLabel#peerTitle { font-size: 20pt; font-weight: 650; }
        QLabel#muted { color: #79756e; }
        QLabel#fieldLabel { color: #4b4741; font-weight: 600; margin-top: 4px; }
        QLabel#error { color: #b42318; }
        QLabel#onlineBadge { color: #217346; font-weight: 600; }
        QLabel#placeholder { color: #777168; background: #f7f4ef; border-radius: 8px; padding: 20px; }
        QLineEdit { background: #fff; border: 1px solid #ded8cf; border-radius: 7px; padding: 10px; }
        QLineEdit:focus { border: 1px solid #c5470b; }
        QPushButton { background: #fff; border: 1px solid #ded8cf; border-radius: 7px; padding: 9px 14px; }
        QPushButton:hover { background: #f2eee8; }
        QPushButton#primary { background: #c5470b; border: none; color: white; font-weight: 700; padding: 12px; }
        QPushButton#primary:hover { background: #a83a08; }
        QPushButton#primary:disabled { background: #d9a58f; }
        QListWidget { background: #fff; border: none; outline: none; }
        QListWidget::item { border-radius: 7px; padding: 12px 8px; margin: 2px 0; }
        QListWidget::item:selected { background: #fff0e7; color: #86320a; }
        """
    )
    window = MainWindow()
    window.show()
    app.exec()


if __name__ == "__main__":
    main()
