import socket
from cryptography.fernet import InvalidToken
from encriptacion import obtener_o_generar_clave, desencriptar_bytes, recibir_mensaje_socket, enviar_mensaje_socket, calcular_hash_bytes

# Usar 0.0.0.0 para escuchar todas las conexiones
HOST = '0.0.0.0'
PORT = 5010

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
                    
                    try:
                        # 1. Recibir imagen encriptada enviada por el cliente
                        datos_encriptados = recibir_mensaje_socket(conn)
                        if not datos_encriptados:
                            print("servidor: no se recibieron datos del cliente.")
                            continue
                        
                        print(f"servidor: Imagen encriptada recibida correctamente. Tamaño: {len(datos_encriptados)} bytes.")
                        
                        # 2. Desencriptar autónomamente los bytes de la imagen
                        print("servidor: Desencriptando imagen con la clave Fernet...")
                        datos_desencriptados = desencriptar_bytes(datos_encriptados, clave)
                        hash_desencriptado = calcular_hash_bytes(datos_desencriptados)
                        print(f"servidor: Imagen desencriptada exitosamente. Tamaño: {len(datos_desencriptados)} bytes.")
                        print(f"servidor: Hash SHA-256 de la imagen desencriptada: {hash_desencriptado}")
                        
                        # 3. Guardar la imagen desencriptada en el servidor
                        ruta_guardado = "imagen_desencriptada_servidor.png"
                        with open(ruta_guardado, "wb") as f:
                            f.write(datos_desencriptados)
                        print(f"servidor: Imagen guardada localmente en '{ruta_guardado}'.")
                        
                        # 4. Enviar respuesta de confirmación al cliente (no los bytes de la imagen)
                        mensaje_confirmacion = "OK: Imagen recibida, desencriptada y guardada en el servidor.".encode('utf-8')
                        print("servidor: Enviando confirmación al cliente...")
                        enviar_mensaje_socket(conn, mensaje_confirmacion)
                        print("servidor: Transmisión de respuesta completada.\n")
                    except InvalidToken:
                        print("ERROR: La clave de encriptación 'clave.key' del cliente no coincide con la del servidor.")
                    except (ConnectionResetError, ConnectionAbortedError) as e:
                        print(f"servidor: Conexión interrumpida por el cliente ({e}).")
                    except Exception as e:
                        print(f"ERROR al procesar cliente: {e}")

                    print("servidor: Esperando la siguiente conexión (Presiona Ctrl+C para detener)...")
            except KeyboardInterrupt:
                print("\nDeteniendo el servidor por el usuario...")
                break
            except Exception as e:
                print(f"ERROR en el servidor: {e}")

if __name__ == "__main__":
    iniciar_servidor()
