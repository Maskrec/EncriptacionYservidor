"""
network_utils.py
Utilidades de red para facilitar el envio y recepcion de mensajes JSON
a traves de sockets TCP nativos de Python.
"""

import json
import socket


class ConexionJSON:
    """
    Clase sencilla que envuelve un socket TCP para enviar y recibir
    mensajes en formato JSON utilizando saltos de linea ('\n') como delimitador
    """

    def __init__(self, sock: socket.socket):
        self.sock = sock
        # Usamos makefile en modo lectura con codificacion UTF-8
        # para leer lineas completas facilmente sin lidiar con buffers manuales
        self.lector = sock.makefile("r", encoding="utf-8")

    def enviar(self, datos: dict) -> None:
        """Serializa un diccionario a JSON y lo envia con un salto de linea."""
        mensaje_str = json.dumps(datos) + "\n"
        self.sock.sendall(mensaje_str.encode("utf-8"))

    def recibir(self) -> dict | None:
        """
        Espera y lee una linea completa del socket, deserializandola de JSON a dict
        Retorna None si la conexion fue cerrada por el otro extremo
        """
        try:
            linea = self.lector.readline()
            if not linea:
                return None  # Socket cerrado o desconectado
            return json.loads(linea.strip())
        except (ConnectionResetError, ConnectionAbortedError, json.JSONDecodeError):
            return None

    def cerrar(self) -> None:
        """Cierra el lector y el socket de forma segura."""
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass
        try:
            self.lector.close()
        except Exception:
            pass
        try:
            self.sock.close()
        except Exception:
            pass
