import socket
from encriptacion import obtener_o_generar_clave, desencriptar_bytes, recibir_mensaje_socket, enviar_mensaje_socket

# Usar 0.0.0.0 para escuchar todas las conexiones
HOST = '0.0.0.0'
PORT = 5000

def iniciar_servidor():
    clave = obtener_o_generar_clave()
    

    print("      SERVIDOR TCP DE DESENCRIPTACION DE IMAGENES")
   
    print(f"servidor escuchando en {HOST}:{PORT}...")
    
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        # Permitir reutilizar la dirección local en reinicios
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((HOST, PORT))
        server_socket.listen()
        
        print("Servidor iniciado correctamente. Esperando conexiones...\n")
        
        while True:
            try:
                conn, addr = server_socket.accept()
                with conn:
                    print(f"Cliente conectado desde: {addr[0]}:{addr[1]}")
                    
                    # 1. Recibir imagen encriptada enviada por el cliente
                    datos_encriptados = recibir_mensaje_socket(conn)
                    if not datos_encriptados:
                        print("servidor: no se recibieron datos del cliente.")
                        continue
                    
                    print(f"servidor: Imagen encriptada recibida correctamente. Tamaño: {len(datos_encriptados)} bytes.")
                    
                    # 2. Desencriptar autónomamente los bytes de la imagen
                    print("servidor: Desencriptando imagen con la clave Fernet...")
                    datos_desencriptados = desencriptar_bytes(datos_encriptados, clave)
                    print(f"servidor: Imagen desencriptada exitosamente. Tamaño final: {len(datos_desencriptados)} bytes.")
                    
                    # 3. Retornar autónomamente la imagen desencriptada al cliente
                    print("servidor: Enviando imagen desencriptada de regreso al cliente...")
                    enviar_mensaje_socket(conn, datos_desencriptados)
                    print("servidor: Transmision de respuesta completada.\n")
                    print("servidor: Esperando la siguiente conexión (Presiona Ctrl+C para detener)...")
            except KeyboardInterrupt:
                print("\nDeteniendo el servidor por el usuario...")
                break
            except Exception as e:
                print(f"ERROR en el servidor: {e}")

if __name__ == "__main__":
    iniciar_servidor()
