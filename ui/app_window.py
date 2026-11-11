"""
app_window.py - Coordinador principal de navegación y ciclo de vida de la aplicación Cap_Data
"""
from __future__ import annotations
from typing import Any, Dict, Optional
import customtkinter as ctk

from Cap_Data.config import COLORES
from Cap_Data.database.mongo_manager import MongoManager
from Cap_Data.core.serial_reader import SerialReader
from Cap_Data.ui.view_login import ViewLogin
from Cap_Data.ui.view_capture import ViewCapture
from Cap_Data.ui.view_3d import View3D
from Cap_Data.ui.view_history import ViewHistory


class AppWindow(ctk.CTk):
    """Ventana principal de la aplicación con gestor de 4 vistas integradas."""

    def __init__(self):
        super().__init__()

        # Configuración de apariencia (Estilo Light Tech Biomecánico)
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")

        self.title("Cap_Data — Suite de Biomecánica Articular & MongoDB (ROMDB)")
        self.geometry("1280x820")
        self.minsize(800, 480)
        self.configure(fg_color=COLORES["bg_main"])

        # Gestores de persistencia y hardware compartidos
        self.mongo = MongoManager()
        self.serial = SerialReader()

        # Contenedor dinámico de vistas tipo SPA (Single Page Application)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.contenedor_vistas = ctk.CTkFrame(self, fg_color="transparent")
        self.contenedor_vistas.grid(row=0, column=0, sticky="nsew")
        self.contenedor_vistas.grid_columnconfigure(0, weight=1)
        self.contenedor_vistas.grid_rowconfigure(0, weight=1)

        # Instanciar las 4 vistas requeridas
        self.vistas: Dict[str, ctk.CTkFrame] = {}
        self.vista_actual: Optional[ctk.CTkFrame] = None

        self.view_login = ViewLogin(self.contenedor_vistas, self)
        self.view_capture = ViewCapture(self.contenedor_vistas, self)
        self.view_3d = View3D(self.contenedor_vistas, self)
        self.view_history = ViewHistory(self.contenedor_vistas, self)

        self.vistas["login"] = self.view_login
        self.vistas["captura"] = self.view_capture
        self.vistas["3d"] = self.view_3d
        self.vistas["historial"] = self.view_history

        # Mostrar por defecto la Ventana 1: Inicio de Sesión
        self.mostrar_vista("login")

        # Protocolo de cierre limpio de ventanas
        self.protocol("WM_DELETE_WINDOW", self._on_cerrar_app)

    def mostrar_vista(
        self,
        nombre: str,
        sesion_info: Optional[Dict[str, Any]] = None,
        modo_recaptura: bool = False,
        rep_a_recapturar: Optional[int] = None
    ):
        """Alterna instantáneamente entre las 4 ventanas del sistema."""
        if nombre not in self.vistas:
            print(f"[AppWindow] Vista desconocida: {nombre}")
            return

        # Ocultar vista actual si existe
        if self.vista_actual is not None:
            self.vista_actual.grid_forget()

        vista_nueva = self.vistas[nombre]

        # Inicializaciones contextuales
        if nombre == "login":
            self.view_login.actualizar_lista_voluntarios()

        elif nombre == "captura":
            if sesion_info is not None:
                self.view_capture.cargar_contexto_sesion(
                    sesion_info=sesion_info,
                    modo_recaptura=modo_recaptura,
                    rep_a_recapturar=rep_a_recapturar
                )

        elif nombre == "3d":
            self.view_3d.recargar_datos_disponibles()

        elif nombre == "historial":
            self.view_history.cargar_sesiones()

        # Mostrar la nueva vista en pantalla completa
        vista_nueva.grid(row=0, column=0, sticky="nsew")
        self.vista_actual = vista_nueva

    def _on_cerrar_app(self):
        """Detiene la conexión serial y libera recursos antes de salir."""
        try:
            if self.serial.esta_conectado():
                self.serial.desconectar()
        except Exception:
            pass
        self.destroy()
