from cryptography.fernet import Fernet
import hashlib
import os

NOMBRE_CLAVE = "clave.key"

def obtener_o_generar_clave() -> bytes:
    """Carga la clave Fernet existente o genera una nueva si no existe."""
    if os.path.exists(NOMBRE_CLAVE):
        with open(NOMBRE_CLAVE, "rb") as f:
            return f.read()
    else:
        clave = Fernet.generate_key()
        with open(NOMBRE_CLAVE, "wb") as f:
            f.write(clave)
        print(f"[CRIPTOGRAFÍA] Nueva clave generada y guardada en '{NOMBRE_CLAVE}'")
        return clave

def encriptar_bytes(datos: bytes, clave: bytes) -> bytes:
    """Encripta los bytes recibidos usando la clave Fernet."""
    f = Fernet(clave)
    return f.encrypt(datos)

def desencriptar_bytes(datos_encriptados: bytes, clave: bytes) -> bytes:
    """Desencripta los bytes encriptados usando la clave Fernet."""
    f = Fernet(clave)
    return f.decrypt(datos_encriptados)

def calcular_hash_bytes(datos: bytes) -> str:
    """Calcula el hash SHA-256 de una secuencia de bytes."""
    return hashlib.sha256(datos).hexdigest()

def calcular_hash_archivo(ruta_archivo: str) -> str:
    """Calcula el hash SHA-256 de un archivo en disco."""
    sha256 = hashlib.sha256()
    with open(ruta_archivo, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256.update(chunk)
    return sha256.hexdigest()

def enviar_mensaje_socket(sock, datos: bytes):
    """Envia primero el tamaño del mensaje (4 bytes uint) y luego el cuerpo binario."""
    tamanio = len(datos)
    sock.sendall(tamanio.to_bytes(4, byteorder='big'))
    sock.sendall(datos)

def recibir_mensaje_socket(sock) -> bytes:
    """Recibe el encabezado de 4 bytes con el tamaño y luego lee la totalidad del mensaje."""
    raw_tamanio = bytearray()
    while len(raw_tamanio) < 4:
        chunk = sock.recv(4 - len(raw_tamanio))
        if not chunk:
            return b""
        raw_tamanio.extend(chunk)
        
    tamanio = int.from_bytes(raw_tamanio, byteorder='big')
    
    datos = bytearray()
    while len(datos) < tamanio:
        packet = sock.recv(min(4096, tamanio - len(datos)))
        if not packet:
            break
        datos.extend(packet)
    return bytes(datos)

