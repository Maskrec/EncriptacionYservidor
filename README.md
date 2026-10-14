# Red P2P: directorio y acceso

Primera etapa del sistema de mensajería: un directorio TCP que publica los nodos conectados y una interfaz PyQt6 para iniciar sesión y consultar sus direcciones. El servidor conserva la presencia solo en memoria; al desconectarse o cerrar la aplicación, el usuario deja de aparecer.

## Requisitos

- Python 3.10 o posterior
- PyQt6 para la interfaz (`pip install -r requirements.txt`)

## Iniciar el directorio

```powershell
python directory_server.py --host 0.0.0.0 --port 9000
```

Para probarlo en una sola computadora, se puede usar `--host 127.0.0.1`. En una red local, los clientes deben indicar la IP del equipo que ejecuta el servidor y el puerto `9000`. El firewall debe permitir conexiones TCP entrantes a ese puerto.

## Iniciar la interfaz

```powershell
python app.py
```

En el formulario, cada cliente indica su nombre, la dirección y el puerto del directorio, además del puerto P2P en el que su futuro cliente escuchará conexiones. El servidor identifica la IP de origen de la conexión y anuncia la combinación IP/puerto a todos los usuarios conectados.

## Protocolo de directorio

El cliente envía un objeto JSON terminado en salto de línea:

```json
{"type":"login","username":"Alex","p2p_port":5000}
```

El servidor responde con `login_ok` y la lista inicial, y después envía eventos `users` cuando cambia la presencia. Solo puede existir una sesión activa por nombre (sin distinguir mayúsculas). El registro no persiste, no usa contraseñas y esta etapa no envuelve la conexión del directorio en TLS; no debe exponerse a redes no confiables. La lista de presencia no es un mecanismo de autenticación para las conexiones P2P.

## Pruebas

```powershell
python -m unittest discover -s tests -v
```

El chat P2P, el intercambio de mensajes y archivos, y su integración con el TLS mencionado en los requisitos quedan para una etapa posterior.
