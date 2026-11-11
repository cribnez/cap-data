"""
view_3d.py - Ventana 3: Gráficas de Dispersión Tridimensional y Espacio de Coordenadas Articulares
Estilo visual: Light Tech Biomecánico
Soporta selección libre multiseries (ej. Voluntario 1 Rep 1 vs Voluntario 2 Rep 1) y
modos de coloración dinámica: Por Repetición, Por Voluntario, Por Ejercicio.
"""
from __future__ import annotations
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set
import customtkinter as ctk
import numpy as np
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d import Axes3D

from Cap_Data.config import (
    COLORES,
    COLORES_EJERCICIOS,
    COLORES_VOLUNTARIOS,
    EJERCICIOS_DISPONIBLES,
    LISTA_CAJONES_NPZ,
    NOMBRES_LEGIBLES_CAJONES,
    CAJON_FILTRADOS_TARADOS,
    STORAGE_DIR
)
from Cap_Data.database.storage_manager import StorageManager

if TYPE_CHECKING:
    from Cap_Data.ui.app_window import AppWindow

# Paleta viva de alto contraste para diferenciar repeticiones individuales
PALETA_REPETICIONES = [
    "#0284C7",  # Azul Eléctrico
    "#10B981",  # Verde Esmeralda
    "#F59E0B",  # Ámbar Cálido
    "#8B5CF6",  # Violeta
    "#EC4899",  # Rosa
    "#06B6D4",  # Cian
    "#F97316",  # Naranja
    "#84CC16",  # Lima
    "#6366F1",  # Índigo
    "#14B8A6",  # Turquesa
    "#E11D48",  # Carmesí
    "#3B82F6",  # Azul Real
    "#D97706",  # Ocre
    "#A855F7"   # Púrpura Claro
]


class View3D(ctk.CTkFrame):
    """
    Visualizador 3D interactivo para análisis de nubes de dispersión cinemática articular.
    Ejes espaciales: X = Hombro (MPU1 Pitch), Y = Codo (MPU2 Pitch), Z = Muñeca (MPU3 Pitch).
    Permite selección libre e ilimitada de cualquier repetición de cualquier voluntario y ejercicio.
    """

    def __init__(self, parent: ctk.CTkFrame, app: AppWindow):
        super().__init__(parent, fg_color=COLORES["bg_main"])
        self.app = app

        # Catálogo general de repeticiones indexadas
        self.repeticiones_disponibles: List[Dict[str, Any]] = []
        # Conjunto de IDs seleccionados para graficar (persiste entre cambios de filtro)
        self.seleccionadas_ids: Set[str] = set()

        # Variables de control de checkboxes de la lista visible
        self._check_vars: Dict[str, ctk.BooleanVar] = {}

        self._construir_ui()
        self.recargar_datos_disponibles()

    def _construir_ui(self):
        self.grid_columnconfigure(0, weight=0)  # Panel izquierdo de filtros y selección
        self.grid_columnconfigure(1, weight=1)  # Lienzo 3D principal
        self.grid_rowconfigure(0, weight=1)

        # -------------------------------------------------------------
        # PANEL LATERAL IZQUIERDO DE CONTROLES Y SELECCIÓN MULTISERIE
        # -------------------------------------------------------------
        panel_izq = ctk.CTkScrollableFrame(
            self,
            width=380,
            fg_color=COLORES["bg_card"],
            corner_radius=10,
            border_width=1,
            border_color=COLORES["border"]
        )
        panel_izq.grid(row=0, column=0, padx=(14, 8), pady=14, sticky="nsew")

        # Título y encabezado
        lbl_titulo = ctk.CTkLabel(
            panel_izq,
            text="Explorador Cinemático 3D",
            font=ctk.CTkFont(family="Segoe UI", size=17, weight="bold"),
            text_color=COLORES["text_primary"]
        )
        lbl_titulo.pack(anchor="w", padx=12, pady=(10, 2))

        lbl_desc = ctk.CTkLabel(
            panel_izq,
            text="Ejes espaciales (Inclinación Frontal / Pitch):\n• X = Hombro (MPU1)   • Y = Codo (MPU2)   • Z = Muñeca (MPU3)",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=COLORES["text_secondary"],
            justify="left"
        )
        lbl_desc.pack(anchor="w", padx=12, pady=(0, 10))

        # 1. Selector de Cajón del Archivo .NPZ
        lbl_cajon = ctk.CTkLabel(
            panel_izq,
            text="FUENTE DE DATOS (.NPZ):",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color=COLORES["hombro"]
        )
        lbl_cajon.pack(anchor="w", padx=12, pady=(0, 3))

        self.combo_cajon = ctk.CTkComboBox(
            panel_izq,
            values=[NOMBRES_LEGIBLES_CAJONES[k] for k in LISTA_CAJONES_NPZ],
            height=32,
            corner_radius=6,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            dropdown_font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color=COLORES["bg_card_secondary"]
        )
        self.combo_cajon.set(NOMBRES_LEGIBLES_CAJONES[CAJON_FILTRADOS_TARADOS])
        self.combo_cajon.pack(fill="x", padx=12, pady=(0, 12))

        # 2. Modo de Coloración Dinámica (SOLICITADO POR EL USUARIO)
        lbl_color_mode = ctk.CTkLabel(
            panel_izq,
            text="MODO DE COLORACIÓN DE PUNTOS:",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color=COLORES["codo"]
        )
        lbl_color_mode.pack(anchor="w", padx=12, pady=(0, 3))

        self.seg_modo_color = ctk.CTkSegmentedButton(
            panel_izq,
            values=["Por Repetición", "Por Voluntario", "Por Ejercicio"],
            height=30,
            corner_radius=6,
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            selected_color=COLORES["accent_blue"]
        )
        self.seg_modo_color.set("Por Repetición")
        self.seg_modo_color.pack(fill="x", padx=12, pady=(0, 12))

        # Separador sutil
        sep1 = ctk.CTkFrame(panel_izq, height=1, fg_color=COLORES["border"])
        sep1.pack(fill="x", padx=12, pady=(0, 10))

        # 3. Filtros Rápidos de Exploración
        lbl_filtros = ctk.CTkLabel(
            panel_izq,
            text="FILTRAR LISTA DE REPETICIONES:",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color=COLORES["text_secondary"]
        )
        lbl_filtros.pack(anchor="w", padx=12, pady=(0, 4))

        # Filtro Voluntario
        self.combo_filtro_vol = ctk.CTkComboBox(
            panel_izq,
            values=["Todos"],
            height=30,
            corner_radius=6,
            fg_color=COLORES["bg_card_secondary"],
            font=ctk.CTkFont(family="Segoe UI", size=11),
            dropdown_font=ctk.CTkFont(family="Segoe UI", size=11),
            command=self._on_filtro_cambiado
        )
        self.combo_filtro_vol.set("Todos")
        self.combo_filtro_vol.pack(fill="x", padx=12, pady=(0, 6))

        # Filtro Ejercicio
        self.combo_filtro_ej = ctk.CTkComboBox(
            panel_izq,
            values=["Todos"] + EJERCICIOS_DISPONIBLES,
            height=30,
            corner_radius=6,
            fg_color=COLORES["bg_card_secondary"],
            font=ctk.CTkFont(family="Segoe UI", size=11),
            dropdown_font=ctk.CTkFont(family="Segoe UI", size=11),
            command=self._on_filtro_cambiado
        )
        self.combo_filtro_ej.set("Todos")
        self.combo_filtro_ej.pack(fill="x", padx=12, pady=(0, 8))

        # Botones de Acción de Selección Rápida
        frame_acciones_sel = ctk.CTkFrame(panel_izq, fg_color="transparent")
        frame_acciones_sel.pack(fill="x", padx=12, pady=(0, 6))
        frame_acciones_sel.grid_columnconfigure((0, 1), weight=1)

        btn_marcar_todas = ctk.CTkButton(
            frame_acciones_sel,
            text="☑️ Marcar Visibles",
            height=28,
            corner_radius=5,
            font=ctk.CTkFont(family="Segoe UI", size=10),
            fg_color=COLORES["bg_card_secondary"],
            hover_color=COLORES["border"],
            border_width=1,
            border_color=COLORES["border"],
            text_color=COLORES["text_primary"],
            command=self._marcar_visibles
        )
        btn_marcar_todas.grid(row=0, column=0, padx=(0, 4), sticky="ew")

        btn_desmarcar_todas = ctk.CTkButton(
            frame_acciones_sel,
            text="⬜ Desmarcar Todas",
            height=28,
            corner_radius=5,
            font=ctk.CTkFont(family="Segoe UI", size=10),
            fg_color=COLORES["bg_card_secondary"],
            hover_color=COLORES["border"],
            border_width=1,
            border_color=COLORES["border"],
            text_color=COLORES["text_primary"],
            command=self._desmarcar_todas
        )
        btn_desmarcar_todas.grid(row=0, column=1, padx=(4, 0), sticky="ew")

        # Contador de repeticiones seleccionadas
        self.lbl_contador_sel = ctk.CTkLabel(
            panel_izq,
            text="Seleccionadas: 0 repeticiones",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=COLORES["accent_blue"]
        )
        self.lbl_contador_sel.pack(anchor="w", padx=12, pady=(2, 6))

        # 4. Contenedor de Checkboxes de Repeticiones (Permite libertad absoluta)
        self.frame_checklist = ctk.CTkFrame(
            panel_izq,
            fg_color=COLORES["bg_card_secondary"],
            corner_radius=8,
            border_width=1,
            border_color=COLORES["border"],
            height=180
        )
        self.frame_checklist.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        # 5. Opciones de Trazo
        frame_trazos = ctk.CTkFrame(panel_izq, fg_color="transparent")
        frame_trazos.pack(fill="x", padx=12, pady=(0, 8))

        self.chk_scatter = ctk.CTkCheckBox(
            frame_trazos,
            text="Puntos (Scatter)",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COLORES["text_primary"],
            fg_color=COLORES["accent_blue"]
        )
        self.chk_scatter.select()
        self.chk_scatter.pack(side="left", padx=(0, 12))

        self.chk_lineas = ctk.CTkCheckBox(
            frame_trazos,
            text="Trayectoria (Líneas)",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COLORES["text_primary"],
            fg_color=COLORES["accent_blue"]
        )
        self.chk_lineas.select()
        self.chk_lineas.pack(side="left")

        # 6. Botones de Acción Gráfica
        btn_graficar = ctk.CTkButton(
            panel_izq,
            text="🎨 Graficar Selección 3D",
            height=38,
            corner_radius=6,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color=COLORES["accent_blue"],
            hover_color=COLORES["accent_blue_hover"],
            command=self.graficar
        )
        btn_graficar.pack(fill="x", padx=12, pady=(0, 6))

        frame_limp_rec = ctk.CTkFrame(panel_izq, fg_color="transparent")
        frame_limp_rec.pack(fill="x", padx=12, pady=(0, 12))
        frame_limp_rec.grid_columnconfigure((0, 1), weight=1)

        btn_limpiar = ctk.CTkButton(
            frame_limp_rec,
            text="🧹 Limpiar",
            height=30,
            corner_radius=6,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color=COLORES["bg_card_secondary"],
            hover_color=COLORES["border"],
            border_width=1,
            border_color=COLORES["border"],
            text_color=COLORES["text_primary"],
            command=self.limpiar_grafica
        )
        btn_limpiar.grid(row=0, column=0, padx=(0, 4), sticky="ew")

        btn_recargar = ctk.CTkButton(
            frame_limp_rec,
            text="🔄 Recargar",
            height=30,
            corner_radius=6,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color=COLORES["bg_card_secondary"],
            hover_color=COLORES["border"],
            border_width=1,
            border_color=COLORES["border"],
            text_color=COLORES["text_primary"],
            command=self.recargar_datos_disponibles
        )
        btn_recargar.grid(row=0, column=1, padx=(4, 0), sticky="ew")

        # Separador inferior
        sep2 = ctk.CTkFrame(panel_izq, height=1, fg_color=COLORES["border"])
        sep2.pack(fill="x", padx=12, pady=(0, 10))

        # 7. Botones de Navegación Directa requeridos por el usuario
        lbl_nav = ctk.CTkLabel(
            panel_izq,
            text="NAVEGACIÓN DIRECTA:",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color=COLORES["text_muted"]
        )
        lbl_nav.pack(anchor="w", padx=12, pady=(0, 4))

        btn_ir_inicio = ctk.CTkButton(
            panel_izq,
            text="🏠 Inicio de Sesión",
            height=32,
            corner_radius=6,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color=COLORES["bg_card_secondary"],
            hover_color=COLORES["border"],
            border_width=1,
            border_color=COLORES["border"],
            text_color=COLORES["text_primary"],
            command=lambda: self.app.mostrar_vista("login")
        )
        btn_ir_inicio.pack(fill="x", padx=12, pady=(0, 5))

        btn_ir_captura = ctk.CTkButton(
            panel_izq,
            text="⚡ Captura en Tiempo Real",
            height=32,
            corner_radius=6,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color=COLORES["bg_card_secondary"],
            hover_color=COLORES["border"],
            border_width=1,
            border_color=COLORES["border"],
            text_color=COLORES["text_primary"],
            command=lambda: self.app.mostrar_vista("captura")
        )
        btn_ir_captura.pack(fill="x", padx=12, pady=(0, 5))

        btn_ir_historial = ctk.CTkButton(
            panel_izq,
            text="📋 Historial de Sesiones",
            height=32,
            corner_radius=6,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color=COLORES["bg_card_secondary"],
            hover_color=COLORES["border"],
            border_width=1,
            border_color=COLORES["border"],
            text_color=COLORES["text_primary"],
            command=lambda: self.app.mostrar_vista("historial")
        )
        btn_ir_historial.pack(fill="x", padx=12, pady=(0, 10))

        # -------------------------------------------------------------
        # ÁREA DERECHA: LIENZO 3D MATPLOTLIB CON TOOLBAR Y ESTILO LIGHT TECH
        # -------------------------------------------------------------
        frame_derecho = ctk.CTkFrame(
            self,
            fg_color=COLORES["bg_card"],
            corner_radius=10,
            border_width=1,
            border_color=COLORES["border"]
        )
        frame_derecho.grid(row=0, column=1, padx=(0, 14), pady=14, sticky="nsew")
        frame_derecho.grid_rowconfigure(1, weight=1)
        frame_derecho.grid_columnconfigure(0, weight=1)

        # Barra superior del lienzo 3D
        barra_info = ctk.CTkFrame(frame_derecho, fg_color="transparent", height=38)
        barra_info.grid(row=0, column=0, padx=14, pady=(10, 0), sticky="ew")
        barra_info.grid_columnconfigure(0, weight=1)

        self.lbl_status_grafica = ctk.CTkLabel(
            barra_info,
            text="Seleccione repeticiones a la izquierda y presione 'Graficar Selección 3D'",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COLORES["text_secondary"]
        )
        self.lbl_status_grafica.grid(row=0, column=0, sticky="w")

        # Lienzo 3D
        self._crear_lienzo_3d(frame_derecho)

    def _crear_lienzo_3d(self, contenedor: ctk.CTkFrame):
        """Crea la figura 3D interactiva de Matplotlib con estética Light Tech."""
        self.figura = Figure(figsize=(7, 6), dpi=100, facecolor="#FFFFFF")
        self.ax = self.figura.add_subplot(111, projection='3d')
        self._configurar_ejes_3d()

        self.canvas_3d = FigureCanvasTkAgg(self.figura, master=contenedor)
        widget_canvas = self.canvas_3d.get_tk_widget()
        widget_canvas.grid(row=1, column=0, sticky="nsew", padx=8, pady=(4, 0))

        # Toolbar nativo para rotación libre 3D, paneo y zoom
        frame_toolbar = ctk.CTkFrame(contenedor, fg_color="#FFFFFF", height=35)
        frame_toolbar.grid(row=2, column=0, sticky="ew", padx=8, pady=4)
        self.toolbar = NavigationToolbar2Tk(self.canvas_3d, frame_toolbar)
        self.toolbar.config(background="#FFFFFF")
        self.toolbar.update()

    def _configurar_ejes_3d(self):
        """Aplica la estética Light Tech con paredes suaves y etiquetas contrastadas."""
        self.ax.clear()
        self.ax.set_facecolor("#FFFFFF")

        # Color de paneles / paredes 3D (gris ultra sutil)
        try:
            self.ax.xaxis.set_pane_color((0.97, 0.98, 1.0, 1.0))
            self.ax.yaxis.set_pane_color((0.97, 0.98, 1.0, 1.0))
            self.ax.zaxis.set_pane_color((0.97, 0.98, 1.0, 1.0))
        except Exception:
            pass

        self.ax.grid(True, linestyle="--", alpha=0.45, color="#CBD5E1")

        self.ax.set_xlabel("Hombro (MPU1) - Pitch (°)", color=COLORES["hombro"], fontsize=9, fontweight="bold", labelpad=8)
        self.ax.set_ylabel("Codo (MPU2) - Pitch (°)", color=COLORES["codo"], fontsize=9, fontweight="bold", labelpad=8)
        self.ax.set_zlabel("Muñeca (MPU3) - Pitch (°)", color=COLORES["muneca"], fontsize=9, fontweight="bold", labelpad=8)

        self.ax.tick_params(colors=COLORES["text_secondary"], labelsize=8)
        self.ax.set_title("Espacio Cinemático Articular 3D (Flexo-Extensión Pitch)", color=COLORES["text_primary"], fontsize=12, fontweight="bold", pad=12)

    def recargar_datos_disponibles(self):
        """
        Escanea MongoDB y almacenamiento local para indexar todas las repeticiones disponibles.
        Preserva las selecciones existentes del usuario.
        """
        reps_map: Dict[str, Dict[str, Any]] = {}

        # 1. Recuperar de MongoDB
        reps_mongo = self.app.mongo.obtener_todas_repeticiones_validas()
        for r in reps_mongo:
            ruta_npz = str(r.get("archivo_npz", ""))
            vol = str(r.get("voluntario_id", "VOL-001")).strip().upper()
            sesion = str(r.get("sesion_id", "SES"))
            ej = str(r.get("ejercicio", EJERCICIOS_DISPONIBLES[0]))
            num_rep = int(r.get("num_rep", 1))

            rep_id = f"{vol}_{sesion}_R{num_rep}"
            reps_map[rep_id] = {
                "id": rep_id,
                "voluntario_id": vol,
                "sesion_id": sesion,
                "ejercicio": ej,
                "num_rep": num_rep,
                "archivo_npz": ruta_npz,
                "duracion_s": float(r.get("duracion_s", 0.0))
            }

        # 2. Escaneo en disco local (para incluir repeticiones en modo offline o backups)
        archivos_npz = list(STORAGE_DIR.glob("**/*.npz"))
        for p in archivos_npz:
            if p.name.endswith(".bak"):
                continue

            ruta_str = str(p)
            partes = p.parts
            vol_id = "VOL-001"
            ej = EJERCICIOS_DISPONIBLES[0]
            sesion = "SES-LOCAL"

            # Parsear carpeta V_{voluntario}/{sesion_ejercicio}/rep_X.npz
            for parte in partes:
                if parte.startswith("V_"):
                    vol_id = parte.replace("V_", "").upper()
                for e in EJERCICIOS_DISPONIBLES:
                    if e.replace(" ", "_") in parte or e in parte:
                        ej = e

            try:
                num_rep = int(p.stem.replace("rep_", ""))
            except Exception:
                num_rep = 1

            rep_id = f"{vol_id}_{p.parent.name}_R{num_rep}"
            if rep_id not in reps_map:
                reps_map[rep_id] = {
                    "id": rep_id,
                    "voluntario_id": vol_id,
                    "sesion_id": p.parent.name,
                    "ejercicio": ej,
                    "num_rep": num_rep,
                    "archivo_npz": ruta_str,
                    "duracion_s": 0.0
                }

        # Ordenar repeticiones alfabéticamente por voluntario, ejercicio y repetición
        lista_ordenada = sorted(
            reps_map.values(),
            key=lambda item: (item["voluntario_id"], item["ejercicio"], item["num_rep"])
        )
        self.repeticiones_disponibles = lista_ordenada

        # Actualizar opciones de filtros desplegables
        voluntarios_unicos = sorted(list(set(r["voluntario_id"] for r in lista_ordenada)))
        if not voluntarios_unicos:
            voluntarios_unicos = ["Sin datos"]
        val_vol_actual = self.combo_filtro_vol.get()
        self.combo_filtro_vol.configure(values=["Todos"] + voluntarios_unicos)
        if val_vol_actual in voluntarios_unicos or val_vol_actual == "Todos":
            self.combo_filtro_vol.set(val_vol_actual)
        else:
            self.combo_filtro_vol.set("Todos")

        # Reconstruir listado visible con checkboxes
        self._actualizar_checklist()

    def _on_filtro_cambiado(self, _eleccion: str = ""):
        """Actualiza el listado visible preservando la selección acumulada."""
        self._actualizar_checklist()

    def _actualizar_checklist(self):
        """Renderiza los checkboxes de las repeticiones que cumplen el filtro activo."""
        # Limpiar widgets previos del contenedor
        for widget in self.frame_checklist.winfo_children():
            widget.destroy()

        self._check_vars.clear()

        vol_sel = self.combo_filtro_vol.get()
        ej_sel = self.combo_filtro_ej.get()

        # Filtrar repeticiones visibles
        visibles = [
            r for r in self.repeticiones_disponibles
            if (vol_sel == "Todos" or r["voluntario_id"] == vol_sel) and
               (ej_sel == "Todos" or r["ejercicio"] == ej_sel)
        ]

        if not visibles:
            lbl_vacio = ctk.CTkLabel(
                self.frame_checklist,
                text="No hay repeticiones con este filtro",
                font=ctk.CTkFont(family="Segoe UI", size=10, slant="italic"),
                text_color=COLORES["text_muted"]
            )
            lbl_vacio.pack(padx=10, pady=20)
            self._actualizar_contador_seleccion()
            return

        # Frame scrollable interno para las filas de selección
        scroll = ctk.CTkScrollableFrame(
            self.frame_checklist,
            fg_color="transparent",
            height=200
        )
        scroll.pack(fill="both", expand=True, padx=4, pady=4)

        for r in visibles:
            r_id = r["id"]
            esta_seleccionada = r_id in self.seleccionadas_ids
            var = ctk.BooleanVar(value=esta_seleccionada)
            self._check_vars[r_id] = var

            fila = ctk.CTkFrame(scroll, fg_color="transparent")
            fila.pack(fill="x", padx=4, pady=2)

            chk = ctk.CTkCheckBox(
                fila,
                text=f"{r['voluntario_id']} | {r['ejercicio']} | Rep {r['num_rep']}",
                variable=var,
                font=ctk.CTkFont(family="Segoe UI", size=11),
                text_color=COLORES["text_primary"],
                fg_color=COLORES["accent_blue"],
                command=lambda rid=r_id, v=var: self._on_checkbox_toggled(rid, v)
            )
            chk.pack(side="left", padx=4, pady=2)

        self._actualizar_contador_seleccion()

    def _on_checkbox_toggled(self, rep_id: str, var: ctk.BooleanVar):
        """Añade o retira la repetición del conjunto global de selecciones."""
        if var.get():
            self.seleccionadas_ids.add(rep_id)
        else:
            self.seleccionadas_ids.discard(rep_id)
        self._actualizar_contador_seleccion()

    def _marcar_visibles(self):
        """Selecciona todas las repeticiones que se muestran actualmente."""
        for rep_id, var in self._check_vars.items():
            var.set(True)
            self.seleccionadas_ids.add(rep_id)
        self._actualizar_contador_seleccion()

    def _desmarcar_todas(self):
        """Limpia todas las selecciones (visibles y no visibles)."""
        for var in self._check_vars.values():
            var.set(False)
        self.seleccionadas_ids.clear()
        self._actualizar_contador_seleccion()

    def _actualizar_contador_seleccion(self):
        """Actualiza la etiqueta de conteo de repeticiones marcadas."""
        n = len(self.seleccionadas_ids)
        total = len(self.repeticiones_disponibles)
        self.lbl_contador_sel.configure(text=f"Seleccionadas: {n} de {total} repetición(es)")

    def _obtener_clave_cajon_seleccionado(self) -> str:
        """Traduce la etiqueta legible del combo al nombre interno del objeto NPZ."""
        texto = self.combo_cajon.get()
        for k, v in NOMBRES_LEGIBLES_CAJONES.items():
            if v == texto:
                return k
        return CAJON_FILTRADOS_TARADOS

    def limpiar_grafica(self):
        """Limpia el espacio 3D."""
        self._configurar_ejes_3d()
        self.lbl_status_grafica.configure(
            text="Lienzo 3D limpio. Seleccione repeticiones y presione 'Graficar Selección 3D'."
        )
        self.canvas_3d.draw()

    def graficar(self):
        """
        Carga y grafica simultáneamente todas las repeticiones seleccionadas por el usuario.
        Aplica la coloración dinámica configurada (Por Repetición, Por Voluntario, Por Ejercicio).
        """
        self._configurar_ejes_3d()

        if not self.seleccionadas_ids:
            self.ax.text(
                0, 0, 0,
                "No hay repeticiones seleccionadas.\nMarque al menos una en la lista lateral.",
                color=COLORES["warning"],
                ha="center",
                va="center",
                fontsize=11
            )
            self.canvas_3d.draw()
            self.lbl_status_grafica.configure(text="⚠️ Seleccione al menos una repetición para graficar.")
            return

        cajon_clave = self._obtener_clave_cajon_seleccionado()
        modo_color = self.seg_modo_color.get()
        trazar_scatter = self.chk_scatter.get()
        trazar_lineas = self.chk_lineas.get()

        # Filtrar objetos de repetición correspondientes a los IDs seleccionados
        reps_a_graficar = [
            r for r in self.repeticiones_disponibles
            if r["id"] in self.seleccionadas_ids
        ]

        if not reps_a_graficar:
            return

        # Construir mapeo de colores para el modo 'Por Voluntario'
        voluntarios_en_grafica = sorted(list(set(r["voluntario_id"] for r in reps_a_graficar)))
        color_por_voluntario: Dict[str, str] = {}
        for idx_v, vol in enumerate(voluntarios_en_grafica):
            color_por_voluntario[vol] = COLORES_VOLUNTARIOS[idx_v % len(COLORES_VOLUNTARIOS)]

        total_puntos = 0
        series_graficadas = 0

        for idx, rep in enumerate(reps_a_graficar):
            ruta_npz = rep.get("archivo_npz", "")
            if not ruta_npz or not Path(ruta_npz).exists():
                continue

            datos_npz = StorageManager.cargar_repeticion_npz(ruta_npz)
            if not datos_npz or cajon_clave not in datos_npz:
                continue

            matriz = datos_npz[cajon_clave]
            # Matriz shape: (N, 4) -> [tiempo, hombro_pitch, codo_pitch, muneca_pitch]
            if len(matriz) == 0:
                continue

            x = matriz[:, 1]  # Hombro (MPU1 Pitch)
            y = matriz[:, 2]  # Codo (MPU2 Pitch)
            z = matriz[:, 3]  # Muñeca (MPU3 Pitch)
            total_puntos += len(x)
            series_graficadas += 1

            # Asignación de Color según el Modo Activo
            vol_id = rep.get("voluntario_id", "VOL")
            ej_nombre = rep.get("ejercicio", "")
            num_rep = rep.get("num_rep", 1)

            if modo_color == "Por Repetición":
                color = PALETA_REPETICIONES[idx % len(PALETA_REPETICIONES)]
                etiqueta = f"{vol_id} | {ej_nombre} [R{num_rep}]"

            elif modo_color == "Por Voluntario":
                color = color_por_voluntario.get(vol_id, PALETA_REPETICIONES[0])
                etiqueta = f"{vol_id} (R{num_rep} - {ej_nombre})"

            elif modo_color == "Por Ejercicio":
                color = COLORES_EJERCICIOS.get(ej_nombre, COLORES["accent_blue"])
                etiqueta = f"{ej_nombre} ({vol_id} R{num_rep})"

            else:
                color = PALETA_REPETICIONES[idx % len(PALETA_REPETICIONES)]
                etiqueta = f"{vol_id} - R{num_rep}"

            # 1. Nube de dispersión (Scatter)
            if trazar_scatter:
                # Si no se trazan líneas, usar el scatter para la leyenda
                self.ax.scatter(
                    x, y, z,
                    color=color,
                    alpha=0.65,
                    s=14,
                    label=etiqueta if not trazar_lineas else ""
                )

            # 2. Trayectoria continua (Línea conectora)
            if trazar_lineas:
                self.ax.plot(
                    x, y, z,
                    color=color,
                    linewidth=1.8,
                    alpha=0.85,
                    label=etiqueta
                )

        # Configurar leyenda interactiva y actualizar estado
        if series_graficadas > 0:
            try:
                leg = self.ax.legend(
                    facecolor="#FFFFFF",
                    edgecolor=COLORES["border"],
                    fontsize=8,
                    loc="upper right"
                )
                for text in leg.get_texts():
                    text.set_color(COLORES["text_primary"])
            except Exception:
                pass

            self.lbl_status_grafica.configure(
                text=f"✓ {series_graficadas} serie(s) trazadas ({total_puntos} puntos en total) — Modo: {modo_color}"
            )
        else:
            self.lbl_status_grafica.configure(
                text="⚠️ No se encontraron datos válidos en los archivos de las repeticiones seleccionadas."
            )

        self.canvas_3d.draw()
