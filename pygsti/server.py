"""
server.py
Servidor de Directorio (Signaling Server) - FASE 1

Este servidor actua como una "agenda telefonica centralizada".
Los clientes se registran aqui para informar su IP y su puerto P2P,
y pueden consultar la lista de otros usuarios activos.

No transmite mensajes de chat ni archivos: esa parte es directa P2P.
"""

import socket
import threading
from network_utils import ConexionJSON

# Configuraciones por defecto
HOST = "0.0.0.0"
PUERTO = 9000


class ServidorDirectorio:
    """
    Servidor de directorio centralizado que administra la lista
    de usuarios conectados y sus direcciones de red (IP y puerto P2P).
    """

    def __init__(self, host: str = HOST, puerto: int = PUERTO):
        self.host = host
        self.puerto = puerto
        self.socket_servidor = None
        self.en_ejecucion = False

        # Diccionario en memoria para registrar usuarios:
        # Estructura: { "username": {"ip": "127.0.0.1", "port": 5050} }
        self.usuarios = {}

        # Bloqueo (lock) para evitar problemas cuando varios hilos
        # modifican el diccionario al mismo tiempo
        self.lock = threading.Lock()

    def iniciar(self):
        """Inicia el servidor TCP y escucha conexiones entrantes."""
        self.socket_servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Permite reutilizar el puerto inmediatamente si se reinicia el servidor
        self.socket_servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            self.socket_servidor.bind((self.host, self.puerto))
            self.socket_servidor.listen()
            # Timeout de 1 segundo para que el bucle pueda verificar self.en_ejecucion
            # y apagarse limpiamente sin quedar bloqueado en Windows
            self.socket_servidor.settimeout(1.0)
            self.en_ejecucion = True
            print(f"[SERVIDOR] Servidor de Directorio iniciado en {self.host}:{self.puerto}")
            print("[SERVIDOR] Esperando conexiones de clientes...\n")

            while self.en_ejecucion:
                try:
                    cliente_sock, direccion = self.socket_servidor.accept()
                    print(f"[SERVIDOR] [CONEXION] Nuevo cliente conectado desde {direccion}")

                    # Creamos un hilo para atender a este cliente sin bloquear a los demas
                    hilo_cliente = threading.Thread(
                        target=self._atender_cliente,
                        args=(cliente_sock, direccion),
                        daemon=True
                    )
                    hilo_cliente.start()

                except socket.timeout:
                    # Timeout normal cada segundo para revisar self.en_ejecucion
                    continue
                except socket.error:
                    # Ocurre cuando el socket del servidor se cierra al detenerlo
                    break

        except Exception as error:
            print(f"[SERVIDOR] [ERROR] No se pudo iniciar el servidor: {error}")
        finally:
            self.detener()

    def _atender_cliente(self, cliente_sock: socket.socket, direccion: tuple):
        """
        Maneja la comunicacion con un cliente especifico en su propio hilo.
        Recibe peticiones en formato JSON y responde.
        """
        conexion = ConexionJSON(cliente_sock)
        ip_cliente = direccion[0]
        usuario_registrado = None

        try:
            while self.en_ejecucion:
                peticion = conexion.recibir()

                # Si recibir() devuelve None, el cliente cerro el socket
                if peticion is None:
                    break

                accion = peticion.get("action", "").lower()

                # 1. ACCION: REGISTER
                if accion == "register":
                    # Aceptamos 'user' o 'username' por flexibilidad
                    username = peticion.get("username") or peticion.get("user")
                    puerto_p2p = peticion.get("port")

                    if not username or not puerto_p2p:
                        conexion.enviar({
                            "status": "error",
                            "message": "Faltan datos obligatorios ('username' y 'port')."
                        })
                        continue

                    with self.lock:
                        # Guardamos o actualizamos al usuario en la agenda
                        self.usuarios[username] = {
                            "ip": ip_cliente,
                            "port": puerto_p2p
                        }
                        usuario_registrado = username

                    print(f"[SERVIDOR] [+] Usuario '{username}' registrado: IP={ip_cliente}, Puerto_P2P={puerto_p2p}")
                    conexion.enviar({
                        "status": "ok",
                        "message": f"Usuario '{username}' registrado exitosamente."
                    })

                # 2. ACCION: GET_USERS
                elif accion == "get_users":
                    with self.lock:
                        # Creamos una copia del diccionario para enviarla de forma segura
                        lista_usuarios = dict(self.usuarios)

                    print(f"[SERVIDOR] [?] Peticion GET_USERS atendida para {direccion}")
                    conexion.enviar({
                        "status": "ok",
                        "users": lista_usuarios
                    })

                # 3. ACCION: LOGOUT
                elif accion == "logout":
                    username = peticion.get("username") or peticion.get("user") or usuario_registrado

                    if username:
                        with self.lock:
                            self.usuarios.pop(username, None)
                        print(f"[SERVIDOR] [-] Usuario '{username}' cerro sesion voluntariamente.")

                    usuario_registrado = None
                    conexion.enviar({
                        "status": "ok",
                        "message": "Sesion cerrada exitosamente."
                    })
                    break

                # ACCION DESCONOCIDA
                else:
                    conexion.enviar({
                        "status": "error",
                        "message": f"Accion '{accion}' no reconocida."
                    })

        except Exception as error:
            print(f"[SERVIDOR] [ERROR] Ocurrio un error con el cliente {direccion}: {error}")

        finally:
            # LIMPIEZA: Si el cliente se desconecto, lo eliminamos de la lista
            if usuario_registrado:
                with self.lock:
                    if usuario_registrado in self.usuarios:
                        del self.usuarios[usuario_registrado]
                        print(f"[SERVIDOR] [-] Desconexion detectada: Usuario '{usuario_registrado}' eliminado de la lista.")

            conexion.cerrar()
            print(f"[SERVIDOR] [DESCONEXION] Cliente {direccion} desconectado.\n")

    def detener(self):
        """Detiene el servidor y cierra el socket principal."""
        self.en_ejecucion = False
        if self.socket_servidor:
            try:
                self.socket_servidor.close()
            except Exception:
                pass
        print("[SERVIDOR] Servidor detenido.")


if __name__ == "__main__":
    servidor = ServidorDirectorio(HOST, PUERTO)
    try:
        servidor.iniciar()
    except KeyboardInterrupt:
        print("\n[SERVIDOR] Deteniendo servidor por interrupcion del teclado (Ctrl+C)...")
        servidor.detener()
