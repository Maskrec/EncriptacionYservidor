import socket
import os
from encriptacion import (
    obtener_o_generar_clave, 
    encriptar_bytes, 
    calcular_hash_bytes, 
    enviar_mensaje_socket, 
    recibir_mensaje_socket
)

DEFAULT_HOST = '127.0.0.1'
PORT = 5010

def pedir_ip_servidor() -> str: #str sirve para indicar que el valor devuelto sera una cadena de texto
    """Pide al usuario la dirección IP del servidor."""
    ip = input("Ingresa la IP del servidor (Enter para usar localhost o '127.0.0.1'): ").strip()
    return ip if ip else DEFAULT_HOST

def pedir_ruta_imagen() -> str:
    """Pide al usuario la ruta de una imagen existente en disco."""
    while True:
        ruta = input("Ingresa la ruta de la imagen (ej: foto.png o C:\\imagenes\\foto.jpg): ").strip('"\' ')
        if not ruta:
            print("no ingresaste ninguna ruta intenta de nuevo.")
            continue
        if os.path.exists(ruta) and os.path.isfile(ruta):
            return ruta
        else:
            print(f"el archivo '{ruta}' no existe intenta de nuevo.")

def ejecutar_cliente(ruta_imagen=None, host_ip=None):
    print("       ENCRIPTACIÓN Y VERIFICACIÓN DE IMAGENES   ")
    
    # Pedir IP del servidor si no fue proporcionada
    if not host_ip:
        host_ip = pedir_ip_servidor()

    # 1 seleccinar imagen
    if not ruta_imagen or not os.path.exists(ruta_imagen):
        ruta_imagen = pedir_ruta_imagen()
    
    # 2 lectura de la imagen y calcular hash original
    with open(ruta_imagen, "rb") as f:
        datos_originales = f.read()
        
    hash_original = calcular_hash_bytes(datos_originales)
    print(f"imagen cargada: '{ruta_imagen}' ({len(datos_originales)} bytes)")
    
    # 3encriptacion sincrona de la imagen
    clave = obtener_o_generar_clave()
    print("encriptando la imagen con Fernet")
    datos_encriptados = encriptar_bytes(datos_originales, clave)
    print(f"Imagen encriptada generada: {len(datos_encriptados)} bytes")
    
    # guardar copia local de la version encriptada
    with open("imagen_encriptada.enc", "wb") as f:
        f.write(datos_encriptados)
    print("guardada copia local en 'imagen_encriptada.enc'")
    
    # 4 transmision al servidor via Socket TCP
    print(f"conectando al servidor {host_ip}:{PORT}")
    datos_recibidos = b""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.connect((host_ip, PORT))
            print("enviando imagen encriptada al servidor...")
            enviar_mensaje_socket(sock, datos_encriptados)
            
            # 5 recepcion de la confirmación del servidor
            print("Esperando confirmación del servidor...")
            datos_recibidos = recibir_mensaje_socket(sock)
            
    except (ConnectionRefusedError, ConnectionResetError, OSError, socket.error) as e:
        print(f"CLIENTE ERROR No se pudo conectar al servidor Asegurate de ejecutar 'servidor.py' primero. ({e})")
        return

    if not datos_recibidos:
        print("CLIENTE ERROR No se recibió respuesta del servidor.")
        return

    # 6 procesar confirmacion
    try:
        mensaje_servidor = datos_recibidos.decode('utf-8')
        print(f"\n[RESPUESTA DEL SERVIDOR] {mensaje_servidor}")
    except UnicodeDecodeError:
        print(f"[RESPUESTA DEL SERVIDOR] (Datos binarios recibidos: {len(datos_recibidos)} bytes)")

    print("\n               RESULTADO DE LA TRANSMISIÓN")
    print(f" Hash original enviado: {hash_original}")
    print(" Transmisión completada. La imagen fue desencriptada y almacenada únicamente en el servidor.")
    print("=" * 60)

def menu_principal():
    while True:
        print("\n--- MENÚ ---")
        print("1. Enviar una imagen al servidor")
        print("2. Salir")
        opcion = input("Selecciona una opción (1-2): ").strip()
        
        if opcion == "1":
            ejecutar_cliente()
        elif opcion == "2":
            print("bye")
            break
        else:
            print("Opción no valida intenta de nuevo.")

if __name__ == "__main__":
    menu_principal()
