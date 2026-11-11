"""
view_login.py - Ventana 1: Inicio de Sesión y Registro de Voluntarios
Estilo visual: Light Tech Biomecánico
Diseño profesional tipo Split-Hero que aprovecha toda la amplitud de la pantalla
manteniendo el botón de inicio completamente visible y con tipografía amplia.
"""
from __future__ import annotations
import datetime
from typing import TYPE_CHECKING, Optional
import customtkinter as ctk

from Cap_Data.config import (
    COLORES,
    EJERCICIOS_DISPONIBLES,
    BRAZOS_DISPONIBLES,
    REPS_OBJETIVO_DEFAULT
)

if TYPE_CHECKING:
    from Cap_Data.ui.app_window import AppWindow


class ViewLogin(ctk.CTkFrame):
    """Vista de registro inicial de voluntarios y configuración del protocolo biomecánico."""

    def __init__(self, parent: ctk.CTkFrame, app: AppWindow):
        super().__init__(parent, fg_color=COLORES["bg_main"])
        self.app = app
        self._construir_ui()

    def _construir_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # -------------------------------------------------------------
        # 1. BARRA SUPERIOR (HEADER GLOBAL)
        # -------------------------------------------------------------
        topbar = ctk.CTkFrame(
            self,
            height=52,
            fg_color=COLORES["bg_card"],
            border_width=1,
            border_color=COLORES["border"],
            corner_radius=10
        )
        topbar.grid(row=0, column=0, padx=20, pady=(12, 6), sticky="ew")
        topbar.grid_columnconfigure(1, weight=1)

        # Logo / Título
        frame_logo = ctk.CTkFrame(topbar, fg_color="transparent")
        frame_logo.grid(row=0, column=0, padx=16, pady=8, sticky="w")

        lbl_icono = ctk.CTkLabel(
            frame_logo,
            text="⚡ GONIO",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color=COLORES["hombro"]
        )
        lbl_icono.pack(side="left", padx=(0, 6))

        lbl_slash = ctk.CTkLabel(
            frame_logo,
            text="/ 3X MPU-6050",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color=COLORES["text_secondary"]
        )
        lbl_slash.pack(side="left", padx=(0, 12))

        badge_conf = ctk.CTkLabel(
            frame_logo,
            text="● Protocolo Clínico ROMDB",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=COLORES["accent_blue"]
        )
        badge_conf.pack(side="left")

        # Botones de navegación directa superiores
        frame_top_nav = ctk.CTkFrame(topbar, fg_color="transparent")
        frame_top_nav.grid(row=0, column=1, padx=16, pady=8, sticky="e")

        btn_top_historial = ctk.CTkButton(
            frame_top_nav,
            text="📋 Historial de Sesiones",
            width=160,
            height=34,
            corner_radius=6,
            fg_color=COLORES["bg_card_secondary"],
            hover_color=COLORES["border"],
            border_width=1,
            border_color=COLORES["border"],
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=COLORES["text_primary"],
            command=lambda: self.app.mostrar_vista("historial")
        )
        btn_top_historial.pack(side="left", padx=5)

        btn_top_3d = ctk.CTkButton(
            frame_top_nav,
            text="📈 Gráficas 3D",
            width=135,
            height=34,
            corner_radius=6,
            fg_color=COLORES["bg_card_secondary"],
            hover_color=COLORES["border"],
            border_width=1,
            border_color=COLORES["border"],
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=COLORES["text_primary"],
            command=lambda: self.app.mostrar_vista("3d")
        )
        btn_top_3d.pack(side="left", padx=5)

        # -------------------------------------------------------------
        # 2. CONTENEDOR HERO SPLIT-CARD (AMPLIO, ELEGANTE Y PROPORCIONADO)
        # -------------------------------------------------------------
        contenedor_central = ctk.CTkFrame(self, fg_color="transparent")
        contenedor_central.grid(row=1, column=0, padx=20, pady=(6, 16), sticky="nsew")
        contenedor_central.grid_columnconfigure(0, weight=1)
        contenedor_central.grid_rowconfigure(0, weight=1)

        # Tarjeta principal amplia con bordes redondeados y sombra sutil
        card_hero = ctk.CTkFrame(
            contenedor_central,
            fg_color=COLORES["bg_card"],
            corner_radius=14,
            border_width=1,
            border_color=COLORES["border"]
        )
        card_hero.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        card_hero.grid_columnconfigure(0, weight=4)  # Panel izquierdo (Info & Protocolo)
        card_hero.grid_columnconfigure(1, weight=6)  # Panel derecho (Formulario & Botón)
        card_hero.grid_rowconfigure(0, weight=1)

        # -------------------------------------------------------------
        # PANEL IZQUIERDO: INFORMACIÓN Y PROTOCOLO BIOMECÁNICO
        # -------------------------------------------------------------
        panel_izq = ctk.CTkFrame(
            card_hero,
            fg_color=COLORES["bg_card_secondary"],
            corner_radius=12,
            border_width=1,
            border_color=COLORES["border"]
        )
        panel_izq.grid(row=0, column=0, padx=(18, 10), pady=18, sticky="nsew")
        panel_izq.grid_columnconfigure(0, weight=1)

        lbl_badge_clinico = ctk.CTkLabel(
            panel_izq,
            text="● BIOMECÁNICA CLÍNICA ROMDB",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=COLORES["hombro"]
        )
        lbl_badge_clinico.pack(anchor="w", padx=20, pady=(22, 6))

        lbl_titulo_principal = ctk.CTkLabel(
            panel_izq,
            text="Registro de Sesión\ny Voluntario",
            font=ctk.CTkFont(family="Segoe UI", size=24, weight="bold"),
            text_color=COLORES["text_primary"],
            justify="left"
        )
        lbl_titulo_principal.pack(anchor="w", padx=20, pady=(0, 10))

        lbl_desc_protocolo = ctk.CTkLabel(
            panel_izq,
            text="Configure los parámetros articulares antes de iniciar la captura cinemática en tiempo real.",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COLORES["text_secondary"],
            justify="left",
            wraplength=280
        )
        lbl_desc_protocolo.pack(anchor="w", padx=20, pady=(0, 20))

        # Cuadro de especificaciones del sistema
        frame_specs = ctk.CTkFrame(panel_izq, fg_color="transparent")
        frame_specs.pack(fill="x", padx=20, pady=(0, 10))

        specs = [
            ("⚡ Hardware", "3x MPU-6050 (UART @ 230400 bps)"),
            ("🎯 Eje Cinemático", "Inclinación Frontal (PITCH)"),
            ("📐 Segmentador", "Detección Automática Basal"),
            ("💾 Persistencia", "MongoDB Local + Almacenamiento NPZ")
        ]

        for icono_tit, desc in specs:
            f_item = ctk.CTkFrame(frame_specs, fg_color="transparent")
            f_item.pack(fill="x", pady=4)

            lbl_itit = ctk.CTkLabel(
                f_item,
                text=icono_tit,
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                text_color=COLORES["text_primary"]
            )
            lbl_itit.pack(anchor="w")

            lbl_idesc = ctk.CTkLabel(
                f_item,
                text=desc,
                font=ctk.CTkFont(family="Segoe UI", size=11),
                text_color=COLORES["text_secondary"]
            )
            lbl_idesc.pack(anchor="w")

        # -------------------------------------------------------------
        # PANEL DERECHO: FORMULARIO AMPLIO Y BOTÓN DE ACCIÓN
        # -------------------------------------------------------------
        panel_der = ctk.CTkFrame(card_hero, fg_color="transparent")
        panel_der.grid(row=0, column=1, padx=(10, 22), pady=18, sticky="nsew")
        panel_der.grid_columnconfigure(0, weight=1)

        # 1. ID del Voluntario
        lbl_id = ctk.CTkLabel(
            panel_der,
            text="ID DEL VOLUNTARIO *",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=COLORES["text_primary"]
        )
        lbl_id.pack(anchor="w", pady=(8, 4))

        self.combo_voluntario = ctk.CTkComboBox(
            panel_der,
            values=["VOL-001", "VOL-002", "VOL-003"],
            height=38,
            corner_radius=8,
            font=ctk.CTkFont(family="Segoe UI", size=13),
            dropdown_font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color=COLORES["bg_card_secondary"],
            border_color=COLORES["border"]
        )
        self.combo_voluntario.set("VOL-001")
        self.combo_voluntario.pack(fill="x", pady=(0, 12))

        # 2. Ejercicio Clínico
        lbl_ej = ctk.CTkLabel(
            panel_der,
            text="EJERCICIO CLÍNICO A EVALUAR",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=COLORES["text_primary"]
        )
        lbl_ej.pack(anchor="w", pady=(0, 4))

        self.option_ejercicio = ctk.CTkOptionMenu(
            panel_der,
            values=EJERCICIOS_DISPONIBLES,
            height=38,
            corner_radius=8,
            font=ctk.CTkFont(family="Segoe UI", size=13),
            dropdown_font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color=COLORES["bg_card_secondary"],
            button_color=COLORES["accent_blue"],
            button_hover_color=COLORES["accent_blue_hover"],
            text_color=COLORES["text_primary"]
        )
        self.option_ejercicio.set("Flexo-Extension del codo")
        self.option_ejercicio.pack(fill="x", pady=(0, 12))

        # 3. Fila Doble: Repeticiones Objetivo + Brazo Evaluado
        f_row_params = ctk.CTkFrame(panel_der, fg_color="transparent")
        f_row_params.pack(fill="x", pady=(0, 14))
        f_row_params.grid_columnconfigure(0, weight=1)
        f_row_params.grid_columnconfigure(1, weight=1)

        # Repeticiones
        f_reps_col = ctk.CTkFrame(f_row_params, fg_color="transparent")
        f_reps_col.grid(row=0, column=0, padx=(0, 8), sticky="nsew")

        lbl_reps = ctk.CTkLabel(
            f_reps_col,
            text="REPETICIONES META",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=COLORES["text_primary"]
        )
        lbl_reps.pack(anchor="w", pady=(0, 4))

        f_reps_input = ctk.CTkFrame(f_reps_col, fg_color="transparent")
        f_reps_input.pack(fill="x")

        self.entry_reps = ctk.CTkEntry(
            f_reps_input,
            width=75,
            height=38,
            corner_radius=8,
            justify="center",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            fg_color=COLORES["bg_card_secondary"],
            border_color=COLORES["border"]
        )
        self.entry_reps.insert(0, str(REPS_OBJETIVO_DEFAULT))
        self.entry_reps.pack(side="left", padx=(0, 10))

        lbl_reps_help = ctk.CTkLabel(
            f_reps_input,
            text="por ciclo (def: 5)",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COLORES["text_secondary"]
        )
        lbl_reps_help.pack(side="left")

        # Brazo
        f_brazo_col = ctk.CTkFrame(f_row_params, fg_color="transparent")
        f_brazo_col.grid(row=0, column=1, padx=(8, 0), sticky="nsew")

        lbl_brazo = ctk.CTkLabel(
            f_brazo_col,
            text="BRAZO EVALUADO",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=COLORES["text_primary"]
        )
        lbl_brazo.pack(anchor="w", pady=(0, 4))

        self.seg_brazo = ctk.CTkSegmentedButton(
            f_brazo_col,
            values=BRAZOS_DISPONIBLES,
            height=38,
            corner_radius=8,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            selected_color=COLORES["accent_blue"],
            selected_hover_color=COLORES["accent_blue_hover"]
        )
        self.seg_brazo.set("Derecho")
        self.seg_brazo.pack(fill="x")

        # Mensaje de error/estado
        self.lbl_estado = ctk.CTkLabel(
            panel_der,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COLORES["danger"]
        )

        # Botón Principal Amplio y Prominente (Siempre visible y centrado)
        self.btn_iniciar = ctk.CTkButton(
            panel_der,
            text="▶ INICIAR SESIÓN / IR A CAPTURA",
            height=48,
            corner_radius=8,
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            fg_color=COLORES["accent_primary"],
            hover_color=COLORES["accent_hover"],
            command=self._on_iniciar_captura
        )
        self.btn_iniciar.pack(fill="x", pady=(6, 12))

        # Nota al pie
        lbl_pie = ctk.CTkLabel(
            panel_der,
            text="La sesión se registra en MongoDB únicamente al capturar la primera repetición válida.",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=COLORES["text_muted"]
        )
        lbl_pie.pack(anchor="center")

    def actualizar_lista_voluntarios(self):
        """Recupera de MongoDB los voluntarios existentes para autocompletar."""
        voluntarios = self.app.mongo.obtener_voluntarios_ids()
        if voluntarios:
            self.combo_voluntario.configure(values=voluntarios)

    def _mostrar_error(self, mensaje: str):
        self.lbl_estado.configure(text=mensaje)
        self.lbl_estado.pack(anchor="w", pady=(0, 6), before=self.btn_iniciar)

    def _limpiar_error(self):
        self.lbl_estado.configure(text="")
        self.lbl_estado.pack_forget()

    def _on_iniciar_captura(self):
        """Valida campos y transfiere el control a la Ventana 2 SIN guardar en MongoDB todavía."""
        voluntario_id = self.combo_voluntario.get().strip().upper()
        if not voluntario_id:
            self._mostrar_error("Debe ingresar o seleccionar un ID de voluntario.")
            return

        try:
            reps = int(self.entry_reps.get().strip())
            if reps <= 0 or reps > 50:
                raise ValueError()
        except ValueError:
            self._mostrar_error("Las repeticiones deben ser un número entero entre 1 y 50.")
            return

        self._limpiar_error()
        ejercicio = self.option_ejercicio.get()
        brazo = self.seg_brazo.get()

        # Generar ID de sesión basado en fecha y hora actual: YYYYMMDD_HHMMSS
        ahora = datetime.datetime.now()
        sesion_id = ahora.strftime("%Y%m%d_%H%M%S")

        # IMPORTANTE: NO se guarda nada en MongoDB ni se crea carpeta en storage/
        # hasta que se capture al menos una repetición real con datos en la Ventana de Captura.
        sesion_info = {
            "voluntario_id": voluntario_id,
            "ejercicio": ejercicio,
            "sesion_id": sesion_id,
            "brazo": brazo,
            "reps_objetivo": reps,
            "reps_completadas": 0,
            "fecha_hora": ahora.isoformat()
        }

        # Navegar a la vista de captura
        self.app.mostrar_vista("captura", sesion_info=sesion_info)
