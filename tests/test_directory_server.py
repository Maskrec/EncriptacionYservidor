from __future__ import annotations

import json
import socket
import unittest

from directory_server import DirectoryServer


def receive_message(connection: socket.socket, buffer: bytearray) -> dict:
    while b"\n" not in buffer:
        chunk = connection.recv(4096)
        if not chunk:
            raise ConnectionError("El servidor cerró la conexión.")
        buffer.extend(chunk)
    line, _, remainder = buffer.partition(b"\n")
    buffer[:] = remainder
    return json.loads(line.decode("utf-8"))


class DirectoryServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = DirectoryServer("127.0.0.1", 0)
        self.host, self.port = self.directory.start()
        self.connections: list[socket.socket] = []

    def tearDown(self) -> None:
        for connection in self.connections:
            connection.close()
        self.directory.close()

    def connect(self, username: str, p2p_port: int = 5000) -> tuple[socket.socket, bytearray]:
        connection = socket.create_connection((self.host, self.port), timeout=2)
        connection.settimeout(2)
        self.connections.append(connection)
        request = {"type": "login", "username": username, "p2p_port": p2p_port}
        connection.sendall(json.dumps(request).encode("utf-8") + b"\n")
        return connection, bytearray()

    def test_login_and_live_roster_updates(self) -> None:
        first, first_buffer = self.connect("Alex", 5001)
        login = receive_message(first, first_buffer)
        self.assertEqual(login["type"], "login_ok")
        self.assertEqual(login["users"][0]["username"], "Alex")
        self.assertEqual(login["users"][0]["ip"], "127.0.0.1")

        second, second_buffer = self.connect("Sam", 5002)
        second_login = receive_message(second, second_buffer)
        self.assertEqual(second_login["type"], "login_ok")
        self.assertEqual({user["username"] for user in second_login["users"]}, {"Alex", "Sam"})
        self.assertEqual(receive_message(first, first_buffer)["type"], "users")

        second.close()
        self.assertEqual(
            {user["username"] for user in receive_message(first, first_buffer)["users"]},
            {"Alex"},
        )

    def test_duplicate_user_names_are_rejected_case_insensitively(self) -> None:
        first, first_buffer = self.connect("Alex")
        self.assertEqual(receive_message(first, first_buffer)["type"], "login_ok")
        duplicate, duplicate_buffer = self.connect("alex")
        response = receive_message(duplicate, duplicate_buffer)
        self.assertEqual(response["type"], "error")
        self.assertIn("ya está conectado", response["message"])

    def test_invalid_port_is_rejected(self) -> None:
        connection = socket.create_connection((self.host, self.port), timeout=2)
        connection.settimeout(2)
        self.connections.append(connection)
        connection.sendall(
            json.dumps({"type": "login", "username": "Alex", "p2p_port": 70000}).encode()
            + b"\n"
        )
        response = receive_message(connection, bytearray())
        self.assertEqual(response["type"], "error")
        self.assertIn("puerto P2P", response["message"])


if __name__ == "__main__":
    unittest.main()
