import sys
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLineEdit, QPushButton, 
    QVBoxLayout, QFormLayout, QGroupBox, QMessageBox
)

class LoginInt(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('Inicio de Sesión')
        self.setFixedSize(360, 240)

        # Layout principal
        main_layout = QVBoxLayout()

        # Contenedor de Credenciales
        cred_group = QGroupBox("Credenciales de Acceso")
        cred_layout = QFormLayout()

        self.user_input = QLineEdit()
        self.user_input.setPlaceholderText("Nombre de usuario")

        self.pass_input = QLineEdit()
        self.pass_input.setPlaceholderText("Contraseña")
        self.pass_input.setEchoMode(QLineEdit.EchoMode.Password)

        cred_layout.addRow("Usuario:", self.user_input)
        cred_layout.addRow("Contraseña:", self.pass_input)

        cred_group.setLayout(cred_layout)

        # Botón de Iniciar Sesión
        self.login_btn = QPushButton("Iniciar Sesión")
        self.login_btn.clicked.connect(self.DespsLogin)

        # Ensamblado del layout
        main_layout.addWidget(cred_group)
        main_layout.addWidget(self.login_btn)

        self.setLayout(main_layout)

        # Llamada requerida para aplicar los estilos visuales
        self.Estilitos()

    def Estilitos(self):
        # Hojas de estilo envueltas correctamente en comillas triples (""")
        self.setStyleSheet("""
            QWidget {
                background-color: #120b1e;
                color: #cdd6f4;
                font-size: 14px;
            }

            
            QGroupBox {
                font-weight: bold;
                border: 2px solid #5b21b6;
                border-radius: 8px;
                margin-top: 15px;
                padding-top: 12px;
            }

            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 3px 10px;
                background-color: #5b21b6;
                color: #ffffff;
                border-radius: 4px;
            }

            QLineEdit {
                background-color: #313244;
                border: 1px solid #45475a;
                border-radius: 5px;
                padding: 6px;
                color: #ffffff;
            }

            QLineEdit:focus {
                border: 1px solid #5b21b6;
            }

            QPushButton {
                background-color: #5b21b6;
                color: #ffffff;
                font-weight: bold;
                border-radius: 6px;
                padding: 9px;
            }

            QPushButton:hover {
                background-color: #120b1e;
            }

            QPushButton:pressed {
                background-color: #74c7ec;
            }
        """)

    def DespsLogin(self):
        user = self.user_input.text().strip()
        password = self.pass_input.text().strip()

        # Validación simple de campos vacíos
        if not user or not password:
            QMessageBox.warning(
                self, 
                "Campos incompletos", 
                "Por favor ingresa tu usuario y contraseña."
            )
            return

        # Mensaje de bienvenida tras un inicio de sesión correcto
        QMessageBox.information(
            self, 
            "Inicio de Sesión", 
            f"Has iniciado sesión correctamente.\nHola, {user}"
        )

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ventan = LoginInt()
    ventan.show()
    sys.exit(app.exec())