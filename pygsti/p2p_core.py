"""
p2p_core.py
Motor de Red del Cliente P2P 
Cada nodo P2P tiene una arquitectura dual:
"""

import socket
import threading
import sys
from network_utils import ConexionJSON


class P2PNode:
    """
    Representa un nodo en la red P2P.
    Maneja la presencia en el Servidor de Directorio y las conexiones
    directas de igual a igual (peer-to-peer).
    """

    def __init__(self, username: str, p2p_port: int, server_ip: str = "127.0.0.1", server_port: int = 9000):
        self.username = username
        self.p2p_port = int(p2p_port)
        self.server_ip = server_ip
        self.server_port = int(server_port)

        # Estado del nodo
        self.en_ejecucion = False
        self.socket_escucha_p2p = None
        self.conexion_servidor = None

        # Diccionario para almacenar las conexiones P2P directas:
        # Estructura: { "nombre_peer": ConexionJSON }
        self.peers_conectados = {}
        self.lock_peers = threading.Lock()

        # Callbacks opcionales para notificar a la interfaz de usuario (GUI o consola)
        self.on_message_received = None    # callback(remitente: str, texto: str)
        self.on_peer_connected = None      # callback(remitente: str)
        self.on_peer_disconnected = None   # callback(remitente: str)

    # =========================================================================
    # 1. COMUNICACION CON EL SERVIDOR DE DIRECTORIO
    # =========================================================================

    def login(self) -> tuple[bool, str]:
        """
        Se conecta al Servidor de Directorio y registra este nodo
        con su nombre de usuario y puerto de escucha P2P.
        Retorna (exito, mensaje).
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((self.server_ip, self.server_port))
            self.conexion_servidor = ConexionJSON(sock)

            # Enviamos la peticion de registro segun el protocolo definido
            peticion = {
                "action": "register",
                "username": self.username,
                "port": self.p2p_port
            }
            self.conexion_servidor.enviar(peticion)

            respuesta = self.conexion_servidor.recibir()
            if respuesta and respuesta.get("status") == "ok":
                return True, respuesta.get("message", "Registro exitoso.")
            else:
                mensaje_error = respuesta.get("message", "Error desconocido") if respuesta else "Sin respuesta del servidor"
                self.conexion_servidor.cerrar()
                self.conexion_servidor = None
                return False, mensaje_error

        except Exception as error:
            if self.conexion_servidor:
                self.conexion_servidor.cerrar()
                self.conexion_servidor = None
            return False, f"No se pudo conectar al Servidor de Directorio: {error}"

    def get_users(self) -> dict:
        """
        Solicita al Servidor de Directorio la lista de usuarios conectados.
        Retorna un diccionario: { 'Alice': {'ip': '...', 'port': ...}, ... }
        """
        if not self.conexion_servidor:
            return {}

        try:
            self.conexion_servidor.enviar({"action": "get_users"})
            respuesta = self.conexion_servidor.recibir()

            if respuesta and respuesta.get("status") == "ok":
                return respuesta.get("users", {})
            return {}

        except Exception as error:
            print(f"[P2P - {self.username}] [ERROR] Error al consultar usuarios: {error}")
            return {}

    def logout(self) -> None:
        """Notifica al Servidor de Directorio que cerramos sesion."""
        if self.conexion_servidor:
            try:
                self.conexion_servidor.enviar({
                    "action": "logout",
                    "username": self.username
                })
            except Exception:
                pass
            finally:
                self.conexion_servidor.cerrar()
                self.conexion_servidor = None

    # =========================================================================
    # 2. ROL SERVIDOR LOCAL (ESCUCHAR OTROS PEERS)
    # =========================================================================

    def start_listening(self) -> bool:
        """
        Abre un socket TCP local en el puerto P2P especificado
        y crea un hilo en segundo plano para aceptar conexiones de otros 
        """
        try:
            self.socket_escucha_p2p = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket_escucha_p2p.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket_escucha_p2p.bind(("0.0.0.0", self.p2p_port))
            self.socket_escucha_p2p.listen()
            # Timeout de 1 segundo para verificar self.en_ejecucion periodicamente
            self.socket_escucha_p2p.settimeout(1.0)
            self.en_ejecucion = True

            # Hilo en segundo plano para no congelar el programa ni la interfaz
            hilo_escucha = threading.Thread(
                target=self._bucle_aceptar_conexiones,
                daemon=True,
                name=f"P2P-Listener-{self.p2p_port}"
            )
            hilo_escucha.start()

            print(f"[P2P - {self.username}] Escuchando peers en el puerto {self.p2p_port}...")
            return True

        except Exception as error:
            print(f"[P2P - {self.username}] [ERROR] No se pudo abrir el puerto {self.p2p_port}: {error}")
            return False

    def _bucle_aceptar_conexiones(self):
        """Bucle en segundo plano que acepta peers entrantes de forma continua."""
        while self.en_ejecucion:
            try:
                peer_sock, direccion = self.socket_escucha_p2p.accept()
                conexion = ConexionJSON(peer_sock)
                # Creamos un hilo para atender cada conexion entrante
                hilo_peer = threading.Thread(
                    target=self._atender_peer,
                    args=(conexion, direccion),
                    daemon=True
                )
                hilo_peer.start()

            except socket.timeout:
                continue
            except socket.error:
                # Ocurre al cerrar el socket de escucha durante el stop()
                break

    def _atender_peer(self, conexion: ConexionJSON, direccion: tuple, nombre_remoto_inicial: str | None = None):
        """
        Gestiona la lectura continua de mensajes recibidos desde un peer
        Se ejecuta en su propio hilo.
        """
        nombre_peer = nombre_remoto_inicial

        try:
            while self.en_ejecucion:
                mensaje = conexion.recibir()
                if mensaje is None:
                    # El peer cerro la conexion
                    break

                tipo = mensaje.get("type", "")

                # 1. Mensaje de saludo o presentacion inicial (Handshake)
                if tipo == "handshake":
                    nombre_peer = mensaje.get("sender", f"{direccion[0]}:{direccion[1]}")
                    with self.lock_peers:
                        self.peers_conectados[nombre_peer] = conexion

                    print(f"\n[P2P - {self.username}] [+] Peer conectado: '{nombre_peer}' desde {direccion}")
                    if self.on_peer_connected:
                        self.on_peer_connected(nombre_peer)

                # 2. Mensaje de texto directo
                elif tipo == "message":
                    remitente = mensaje.get("sender", nombre_peer or "Desconocido")
                    texto = mensaje.get("text", "")

                    if self.on_message_received:
                        self.on_message_received(remitente, texto)
                    else:
                        print(f"\n[P2P] [Mensaje de {remitente}]: {texto}")

        except Exception as error:
            print(f"\n[P2P - {self.username}] [AVISO] Error con peer {nombre_peer or direccion}: {error}")

        finally:
            # Limpieza cuando el peer se desconecta
            if nombre_peer:
                with self.lock_peers:
                    if nombre_peer in self.peers_conectados:
                        del self.peers_conectados[nombre_peer]

                print(f"\n[P2P - {self.username}] [-] Peer desconectado: '{nombre_peer}'")
                if self.on_peer_disconnected:
                    self.on_peer_disconnected(nombre_peer)

            conexion.cerrar()

    # =========================================================================
    # 3. ROL CLIENTE LOCAL (CONECTAR A OTROS PEERS)
    # =========================================================================

    def connect_to_peer(self, ip: str, port: int, peer_username: str | None = None) -> bool:
        """
        Inicia una conexion TCP saliente directa hacia la IP y Puerto de otro peer.
        Envia un saludo con nuestro nombre de usuario e inicia la escucha de respuestas.
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((ip, int(port)))
            conexion = ConexionJSON(sock)

            # Enviamos nuestro handshake de presentacion
            conexion.enviar({
                "type": "handshake",
                "sender": self.username
            })

            # Si ya conocemos el nombre, lo registramos inmediatamente
            nombre_clave = peer_username or f"{ip}:{port}"
            with self.lock_peers:
                self.peers_conectados[nombre_clave] = conexion

            # Iniciamos un hilo para escuchar las respuestas o mensajes de este peer
            hilo_peer = threading.Thread(
                target=self._atender_peer,
                args=(conexion, (ip, port), nombre_clave),
                daemon=True
            )
            hilo_peer.start()

            print(f"[P2P - {self.username}] Conectado exitosamente con peer '{nombre_clave}' en {ip}:{port}")
            if self.on_peer_connected and peer_username:
                self.on_peer_connected(peer_username)

            return True

        except Exception as error:
            print(f"[P2P - {self.username}] [ERROR] No se pudo conectar al peer en {ip}:{port}: {error}")
            return False

    # =========================================================================
    # 4. ENVIAR MENSAJES DIRECTOS P2P
    # =========================================================================

    def send_message(self, peer_username: str, text: str) -> bool:
        """
        Envia un mensaje de texto directamente al socket del peer especificado.
        """
        with self.lock_peers:
            conexion = self.peers_conectados.get(peer_username)

        if not conexion:
            print(f"[P2P - {self.username}] [AVISO] No hay conexion activa con '{peer_username}'.")
            return False

        try:
            conexion.enviar({
                "type": "message",
                "sender": self.username,
                "text": text
            })
            return True
        except Exception as error:
            print(f"[P2P - {self.username}] [ERROR] Error al enviar mensaje a '{peer_username}': {error}")
            return False

    # =========================================================================
    # 5. DETENER Y LIMPIAR RECURSOS
    # =========================================================================

    def stop(self) -> None:
        """Detiene el nodo, cierra todas las conexiones y notifica al servidor."""
        self.en_ejecucion = False

        # 1. Cerramos conexiones P2P activas
        with self.lock_peers:
            for peer_name, conexion in list(self.peers_conectados.items()):
                conexion.cerrar()
            self.peers_conectados.clear()

        # 2. Cerramos el socket local de escucha
        if self.socket_escucha_p2p:
            try:
                self.socket_escucha_p2p.close()
            except Exception:
                pass

        # 3. Nos desregistramos del Servidor de Directorio
        self.logout()
        print(f"[P2P - {self.username}] Nodo detenido correctamente.")


# =============================================================================
# MODO INTERACTIVO POR TERMINAL (DEMO / PRUEBAS DE FASE 1 Y 2)
# =============================================================================

def iniciar_cliente_interactivo():
    """Permite probar el nodo P2P desde la consola de forma sencilla."""
    print("=" * 55)
    print("      SISTEMA P2P - MODO INTERACTIVO (FASE 1 Y 2)")
    print("=" * 55)

    username = input("Ingresa tu nombre de usuario: ").strip()
    if not username:
        username = "User" + str(socket.getpid() % 1000)

    puerto_p2p_str = input("Ingresa tu puerto P2P (ej. 5050): ").strip()
    puerto_p2p = int(puerto_p2p_str) if puerto_p2p_str.isdigit() else 5050

    nodo = P2PNode(username=username, p2p_port=puerto_p2p)

    # 1. Iniciar escucha P2P
    if not nodo.start_listening():
        print("No se pudo iniciar el servidor P2P local. Saliendo.")
        return

    # 2. Registrar en Servidor de Directorio
    exito, mensaje = nodo.login()
    print(f"Estado del servidor central: {mensaje}")
    if not exito:
        print("Advertencia: No se pudo conectar al servidor de directorio.")
        print("Asegurate de que 'server.py' este ejecutandose en el puerto 9000.")

    print("\nComandos disponibles:")
    print(" [1] Ver usuarios conectados en el servidor")
    print(" [2] Conectar a un usuario")
    print(" [3] Enviar mensaje directo")
    print(" [4] Ver mis conexiones activas")
    print(" [5] Salir\n")

    try:
        while True:
            opcion = input(f"[{username}] Elige una opcion: ").strip()

            if opcion == "1":
                usuarios = nodo.get_users()
                print("\n--- USUARIOS ACTIVOS EN EL SERVIDOR ---")
                if not usuarios:
                    print("No hay otros usuarios registrados.")
                else:
                    for user, info in usuarios.items():
                        marca = " (TU)" if user == username else ""
                        print(f" * {user}{marca}: IP={info['ip']}, Puerto={info['port']}")
                print("---------------------------------------\n")

            elif opcion == "2":
                ip = input("IP del peer (ej. 127.0.0.1): ").strip() or "127.0.0.1"
                puerto = input("Puerto del peer (ej. 5051): ").strip()
                nombre = input("Nombre del peer (opcional): ").strip() or None
                if puerto.isdigit():
                    nodo.connect_to_peer(ip, int(puerto), nombre)
                else:
                    print("Puerto invalido.")

            elif opcion == "3":
                destinatario = input("A quien enviar mensaje (nombre o IP:puerto): ").strip()
                texto = input("Escribe tu mensaje: ").strip()
                if destinatario and texto:
                    nodo.send_message(destinatario, texto)

            elif opcion == "4":
                with nodo.lock_peers:
                    peers = list(nodo.peers_conectados.keys())
                print(f"\nPeers conectados directamente: {peers}\n")

            elif opcion == "5":
                break
            else:
                print("Opcion no valida.")

    except (KeyboardInterrupt, EOFError):
        print("\nCerrando...")
    finally:
        nodo.stop()


if __name__ == "__main__":
    iniciar_cliente_interactivo()
