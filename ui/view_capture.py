"""
view_capture.py - Ventana 2: Captura en Tiempo Real y Segmentación Automática de Repeticiones
"""
from __future__ import annotations
import math
import time
from typing import TYPE_CHECKING, Any, Dict, Optional
import customtkinter as ctk
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from Cap_Data.config import (
    COLORES,
    VARIABLES_CLINICAS,
    ETIQUETAS_SENSORES,
    BAUDRATES_DISPONIBLES,
    SERIAL_DEFAULT_BAUDRATE,
    EJE_ARTICULAR_DEFECTO
)
from Cap_Data.core.segmenter import EstadoSegmentador, RepetitionSegmenter

if TYPE_CHECKING:
    from Cap_Data.ui.app_window import AppWindow


class TarjetaAngular(ctk.CTkFrame):
    """Widget de tarjeta angular con dial orbital Canvas y valor numérico."""

    def __init__(self, parent: ctk.CTkFrame, articulacion: str, color_acento: str, etiqueta: str):
        super().__init__(
            parent,
            fg_color=COLORES["bg_card"],
            corner_radius=10,
            border_width=1,
            border_color=COLORES["border"]
        )
        self.articulacion = articulacion
        self.color_acento = color_acento

        # Grid interno
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)

        # Nombre de articulación
        self.lbl_nombre = ctk.CTkLabel(
            self,
            text=etiqueta.upper(),
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=color_acento
        )
        self.lbl_nombre.grid(row=0, column=0, padx=12, pady=(10, 0), sticky="w")

        # Subtexto de offset de tara
        self.lbl_offset = ctk.CTkLabel(
            self,
            text="Tara: 0.0°",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=COLORES["text_secondary"]
        )
        self.lbl_offset.grid(row=1, column=0, padx=12, pady=(0, 2), sticky="w")

        # Valor numérico principal
        self.lbl_valor = ctk.CTkLabel(
            self,
            text="0.0°",
            font=ctk.CTkFont(family="Segoe UI", size=26, weight="bold"),
            text_color=COLORES["text_primary"]
        )
        self.lbl_valor.grid(row=2, column=0, padx=12, pady=(0, 10), sticky="w")

        # Canvas para dial orbital
        self.canvas_dial = ctk.CTkCanvas(
            self,
            width=70,
            height=70,
            bg=COLORES["bg_card"],
            highlightthickness=0
        )
        self.canvas_dial.grid(row=0, column=1, rowspan=3, padx=(0, 12), pady=10)
        self.actualizar_dial(0.0)

    def actualizar_dial(self, angulo: float):
        """Redibuja el arco orbital y la aguja en el Canvas."""
        self.canvas_dial.delete("all")
        cx, cy, r = 35, 35, 26
        
        # Círculo base gris
        self.canvas_dial.create_oval(
            cx - r, cy - r, cx + r, cy + r,
            outline=COLORES["border"],
            width=4
        )

        # Ángulo normalizado para visualización
        rad = math.radians(angulo - 90)
        px = cx + (r - 2) * math.cos(rad)
        py = cy + (r - 2) * math.sin(rad)

        # Arco activo
        extent = max(-180, min(180, angulo))
        self.canvas_dial.create_arc(
            cx - r, cy - r, cx + r, cy + r,
            start=90,
            extent=-extent,
            outline=self.color_acento,
            width=4,
            style="arc"
        )

        # Marcador orbital
        self.canvas_dial.create_oval(
            px - 4, py - 4, px + 4, py + 4,
            fill=self.color_acento,
            outline=COLORES["text_primary"],
            width=1
        )

    def actualizar(self, angulo: float, offset_tara: float = 0.0):
        """Actualiza el texto y el dial."""
        self.lbl_valor.configure(text=f"{angulo:+.1f}°")
        self.lbl_offset.configure(text=f"Tara: {offset_tara:+.1f}°")
        self.actualizar_dial(angulo)


class ViewCapture(ctk.CTkFrame):
    """Vista de captura de movimiento en tiempo real con tara obligatoria y segmentación de repeticiones."""

    def __init__(self, parent: ctk.CTkFrame, app: AppWindow):
        super().__init__(parent, fg_color=COLORES["bg_main"])
        self.app = app
        self.sesion_info: Dict[str, Any] = {}
        self.modo_recaptura: bool = False
        self.rep_a_recapturar: Optional[int] = None
        self.tarado_realizado: bool = False

        # Segmentador automático
        self.segmentador = RepetitionSegmenter(
            mongo_mgr=self.app.mongo,
            on_estado_cambio=self._on_segmentador_estado_cambio,
            on_rep_guardada=self._on_repeticion_guardada,
            on_sesion_fin=self._on_sesion_finalizada
        )

        # ARQUITECTURA DESACOPLADA: Conectar el segmentador directamente al hilo serial
        # Esto garantiza que el 100% de las tramas (70-100+ Hz) sean procesadas
        # sin omitir ninguna muestra, independientemente de los 30 FPS de la gráfica.
        self.app.serial.callback_muestra = self._on_muestra_serial_recibida

        self._construir_ui()
        self._iniciar_loop_interfaz()

    def _on_muestra_serial_recibida(self, frame: Dict[str, Any]):
        """Procesa cada trama entrante a velocidad completa de hardware en el hilo serial."""
        self.segmentador.procesar_muestra(frame)

    def _construir_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # -------------------------------------------------------------
        # 1. ENCABEZADO Y CONEXIÓN
        # -------------------------------------------------------------
        frame_header = ctk.CTkFrame(
            self,
            fg_color=COLORES["bg_card"],
            corner_radius=10,
            border_width=1,
            border_color=COLORES["border"]
        )
        frame_header.grid(row=0, column=0, padx=16, pady=(12, 8), sticky="ew")
        frame_header.grid_columnconfigure(1, weight=1)

        # Panel izquierdo de información del voluntario
        frame_vol_info = ctk.CTkFrame(frame_header, fg_color="transparent")
        frame_vol_info.grid(row=0, column=0, padx=14, pady=10, sticky="w")

        self.lbl_vol_badge = ctk.CTkLabel(
            frame_vol_info,
            text="VOLUNTARIO: VOL-001 | EJERCICIO 1 (BRAZO DERECHO)",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=COLORES["hombro"]
        )
        self.lbl_vol_badge.pack(anchor="w")

        self.lbl_sesion_sub = ctk.CTkLabel(
            frame_vol_info,
            text="Sesión: No iniciada | Meta: 5 repeticiones",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COLORES["text_secondary"]
        )
        self.lbl_sesion_sub.pack(anchor="w")

        # Panel derecho de controles seriales y botones de acción
        frame_controles = ctk.CTkFrame(frame_header, fg_color="transparent")
        frame_controles.grid(row=0, column=1, padx=14, pady=10, sticky="e")

        self.combo_puertos = ctk.CTkComboBox(
            frame_controles,
            values=["Buscar..."],
            width=100,
            height=32,
            corner_radius=6,
            fg_color=COLORES["bg_card_secondary"]
        )
        self.combo_puertos.pack(side="left", padx=3)

        btn_refrescar_puertos = ctk.CTkButton(
            frame_controles,
            text="🔄",
            width=32,
            height=32,
            corner_radius=6,
            fg_color=COLORES["bg_card_secondary"],
            hover_color=COLORES["border"],
            command=self.actualizar_puertos_com
        )
        btn_refrescar_puertos.pack(side="left", padx=3)

        # Selector de Baudrate (Sincronizado a 230400 bps por defecto)
        self.combo_baudrate = ctk.CTkComboBox(
            frame_controles,
            values=BAUDRATES_DISPONIBLES,
            width=90,
            height=32,
            corner_radius=6,
            fg_color=COLORES["bg_card_secondary"]
        )
        self.combo_baudrate.set(str(SERIAL_DEFAULT_BAUDRATE))
        self.combo_baudrate.pack(side="left", padx=3)

        # Indicador de Variable Articular Fija (PITCH EXCLUSIVAMENTE)
        lbl_eje = ctk.CTkLabel(
            frame_controles,
            text="Variable: Pitch",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=COLORES["hombro"],
            fg_color=COLORES["bg_card_secondary"],
            corner_radius=6,
            padx=8,
            pady=4
        )
        lbl_eje.pack(side="left", padx=4)

        self.btn_conectar = ctk.CTkButton(
            frame_controles,
            text="Conectar COM",
            width=105,
            height=32,
            corner_radius=6,
            fg_color=COLORES["accent_blue"],
            hover_color="#1a56b8",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self._toggle_conexion
        )
        self.btn_conectar.pack(side="left", padx=5)

        # Botón de TARA (0°)
        self.btn_tara = ctk.CTkButton(
            frame_controles,
            text="⚖️ Tarar (0°)",
            width=95,
            height=32,
            corner_radius=6,
            fg_color="#00838f",
            hover_color="#006064",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self._on_tarar
        )
        self.btn_tara.pack(side="left", padx=6)

        # Botón Iniciar Captura (BLOQUEADO INICIALMENTE HASTA QUE SE TARE)
        self.btn_iniciar_captura = ctk.CTkButton(
            frame_controles,
            text="▶ Iniciar Captura",
            width=125,
            height=32,
            corner_radius=6,
            fg_color=COLORES["accent_primary"],
            hover_color=COLORES["accent_hover"],
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            state="disabled",  # REGLA ESTRICTA: Deshabilitado hasta tarar
            command=self._toggle_captura
        )
        self.btn_iniciar_captura.pack(side="left", padx=6)

        # -------------------------------------------------------------
        # 2. BANNER DE ESTADO Y SEGMENTACIÓN
        # -------------------------------------------------------------
        frame_progreso = ctk.CTkFrame(
            self,
            fg_color=COLORES["bg_card"],
            corner_radius=8,
            border_width=1,
            border_color=COLORES["border"],
            height=40
        )
        frame_progreso.grid(row=1, column=0, padx=16, pady=(0, 8), sticky="ew")
        frame_progreso.grid_columnconfigure(1, weight=1)

        self.lbl_estado_rep = ctk.CTkLabel(
            frame_progreso,
            text="ESTADO: REQUIERE TARA (0°)",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=COLORES["warning"]
        )
        self.lbl_estado_rep.grid(row=0, column=0, padx=14, pady=6, sticky="w")

        # Barra de progreso visual
        self.barra_progreso = ctk.CTkProgressBar(
            frame_progreso,
            height=12,
            corner_radius=6,
            progress_color=COLORES["accent_primary"],
            fg_color=COLORES["bg_card_secondary"]
        )
        self.barra_progreso.set(0.0)
        self.barra_progreso.grid(row=0, column=1, padx=14, pady=6, sticky="ew")

        self.lbl_conteo_reps = ctk.CTkLabel(
            frame_progreso,
            text="Repeticiones: 0 / 5",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=COLORES["text_primary"]
        )
        self.lbl_conteo_reps.grid(row=0, column=2, padx=14, pady=6, sticky="e")

        # -------------------------------------------------------------
        # 3. ÁREA PRINCIPAL: GRÁFICA FILTRADA (IZQ) Y DIALES (DER)
        # -------------------------------------------------------------
        frame_cuerpo = ctk.CTkFrame(self, fg_color="transparent")
        frame_cuerpo.grid(row=2, column=0, padx=16, pady=0, sticky="nsew")
        frame_cuerpo.grid_columnconfigure(0, weight=3)  # Gráfica
        frame_cuerpo.grid_columnconfigure(1, weight=1)  # Tarjetas

        # Contenedor de la gráfica única de datos filtrados
        frame_grafica = ctk.CTkFrame(
            frame_cuerpo,
            fg_color=COLORES["bg_card"],
            corner_radius=10,
            border_width=1,
            border_color=COLORES["border"]
        )
        frame_grafica.grid(row=0, column=0, padx=(0, 8), pady=0, sticky="nsew")
        frame_grafica.grid_columnconfigure(0, weight=1)
        frame_grafica.grid_rowconfigure(0, weight=1)

        self._crear_grafica_filtrada(frame_grafica)

        # Columna derecha: 3 tarjetas angulares con dial orbital
        frame_tarjetas = ctk.CTkFrame(frame_cuerpo, fg_color="transparent")
        frame_tarjetas.grid(row=0, column=1, padx=(8, 0), pady=0, sticky="nsew")
        frame_tarjetas.grid_columnconfigure(0, weight=1)

        self.tarjeta_hombro = TarjetaAngular(frame_tarjetas, "hombro", COLORES["hombro"], ETIQUETAS_SENSORES["hombro"])
        self.tarjeta_hombro.grid(row=0, column=0, pady=(0, 8), sticky="ew")

        self.tarjeta_codo = TarjetaAngular(frame_tarjetas, "codo", COLORES["codo"], ETIQUETAS_SENSORES["codo"])
        self.tarjeta_codo.grid(row=1, column=0, pady=(0, 8), sticky="ew")

        self.tarjeta_muneca = TarjetaAngular(frame_tarjetas, "muneca", COLORES["muneca"], ETIQUETAS_SENSORES["muneca"])
        self.tarjeta_muneca.grid(row=2, column=0, pady=(0, 8), sticky="ew")

        # Tarjeta de frecuencia / estado de conexión
        frame_stats = ctk.CTkFrame(
            frame_tarjetas,
            fg_color=COLORES["bg_card"],
            corner_radius=8,
            border_width=1,
            border_color=COLORES["border"]
        )
        frame_stats.grid(row=3, column=0, pady=(0, 0), sticky="ew")
        self.lbl_frecuencia = ctk.CTkLabel(
            frame_stats,
            text="Arduino: 0.0 Hz | recepción: 0.0 Hz | análisis: 0.0 Hz",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COLORES["text_secondary"]
        )
        self.lbl_frecuencia.pack(padx=10, pady=6)

        # -------------------------------------------------------------
        # 4. BARRA DE NAVEGACIÓN INFERIOR
        # -------------------------------------------------------------
        frame_nav = ctk.CTkFrame(
            self,
            fg_color=COLORES["bg_card"],
            corner_radius=8,
            border_width=1,
            border_color=COLORES["border"]
        )
        frame_nav.grid(row=3, column=0, padx=16, pady=10, sticky="ew")
        frame_nav.grid_columnconfigure(1, weight=1)

        btn_nuevo_vol = ctk.CTkButton(
            frame_nav,
            text="👤 Nuevo Voluntario (Inicio)",
            height=34,
            corner_radius=6,
            fg_color=COLORES["bg_card_secondary"],
            hover_color=COLORES["border"],
            font=ctk.CTkFont(family="Segoe UI", size=12),
            command=self._on_nuevo_voluntario
        )
        btn_nuevo_vol.pack(side="left", padx=10, pady=8)

        btn_historial = ctk.CTkButton(
            frame_nav,
            text="📋 Historial de Sesiones",
            height=34,
            corner_radius=6,
            fg_color=COLORES["bg_card_secondary"],
            hover_color=COLORES["border"],
            font=ctk.CTkFont(family="Segoe UI", size=12),
            command=lambda: self.app.mostrar_vista("historial")
        )
        btn_historial.pack(side="right", padx=10, pady=8)

        btn_3d = ctk.CTkButton(
            frame_nav,
            text="📈 Gráficas de Dispersión 3D",
            height=34,
            corner_radius=6,
            fg_color=COLORES["bg_card_secondary"],
            hover_color=COLORES["border"],
            font=ctk.CTkFont(family="Segoe UI", size=12),
            command=lambda: self.app.mostrar_vista("3d")
        )
        btn_3d.pack(side="right", padx=6, pady=8)

        self.actualizar_puertos_com()

    def _crear_grafica_filtrada(self, contenedor: ctk.CTkFrame):
        """Inicializa la figura de Matplotlib para la señal filtrada con estética Light Tech."""
        self.figura = Figure(figsize=(8, 4), dpi=100, facecolor=COLORES["bg_card"])
        self.ax = self.figura.add_subplot(111)
        self.ax.set_facecolor("#FFFFFF")

        # Curvas para los 3 canales articulares (PITCH)
        self.linea_hombro, = self.ax.plot([], [], color=COLORES["hombro"], linewidth=1.8, label="Hombro (MPU1 Pitch)")
        self.linea_codo, = self.ax.plot([], [], color=COLORES["codo"], linewidth=1.8, label="Codo (MPU2 Pitch)")
        self.linea_muneca, = self.ax.plot([], [], color=COLORES["muneca"], linewidth=1.8, label="Muñeca (MPU3 Pitch)")

        # Configuración estética de ejes
        self.ax.set_title("Señal Filtrada (Mediana + Kalman Adaptativo) en Tiempo Real", color=COLORES["text_primary"], fontsize=11, fontweight="bold", pad=8)
        self.ax.set_xlabel("Tiempo Relativo (s)", color=COLORES["text_secondary"], fontsize=9)
        self.ax.set_ylabel("Ángulo Articular Tarado (°)", color=COLORES["text_secondary"], fontsize=9)
        self.ax.tick_params(colors=COLORES["text_secondary"], labelsize=8)
        self.ax.grid(True, linestyle="--", alpha=0.5, color=COLORES["border"])
        self.ax.set_ylim(-30, 160)

        # Leyenda
        leg = self.ax.legend(facecolor=COLORES["bg_card_secondary"], edgecolor=COLORES["border"], fontsize=8)
        for text in leg.get_texts():
            text.set_color(COLORES["text_primary"])

        self.figura.tight_layout()
        self.canvas_plot = FigureCanvasTkAgg(self.figura, master=contenedor)
        self.canvas_plot.get_tk_widget().pack(fill="both", expand=True, padx=4, pady=4)

    def actualizar_puertos_com(self):
        """Refresca la lista de puertos COM disponibles."""
        puertos = self.app.serial.listar_puertos()
        if puertos:
            self.combo_puertos.configure(values=puertos)
            self.combo_puertos.set(puertos[0])
        else:
            self.combo_puertos.configure(values=["No detectado"])
            self.combo_puertos.set("No detectado")

    def _toggle_conexion(self):
        """Conecta o desconecta el puerto serial seleccionado con baudrate y eje configurados."""
        if self.app.serial.esta_conectado():
            self.app.serial.desconectar()
            self.btn_conectar.configure(text="Conectar COM", fg_color=COLORES["accent_blue"])
        else:
            puerto = self.combo_puertos.get()
            if not puerto or "No" in puerto or "Buscar" in puerto:
                return
            try:
                baud = int(self.combo_baudrate.get().strip())
            except ValueError:
                baud = SERIAL_DEFAULT_BAUDRATE

            # El protocolo de captura usa Pitch en los tres sensores.
            self.app.serial.eje_articular = EJE_ARTICULAR_DEFECTO

            ok = self.app.serial.conectar(puerto, baudrate=baud)
            if ok:
                self.btn_conectar.configure(text="Desconectar", fg_color=COLORES["danger"])

    def _on_eje_cambiado(self, eleccion: str):
        """Actualiza el eje articular procesado (Pitch o Roll) para los 3 MPUs."""
        eje = "pitch" if "Pitch" in eleccion else "roll"
        self.app.serial.eje_articular = eje

    def _on_tarar(self):
        """Ejecuta la tara física y habilita el botón de Iniciar Captura."""
        if not self.app.serial.esta_conectado() or self.app.serial.muestras_validas == 0:
            self.lbl_estado_rep.configure(
                text="ERROR: Conecta el puerto COM y espera recibir lecturas válidas antes de tarar.",
                text_color=COLORES["danger"]
            )
            return

        offsets = self.app.serial.aplicar_tara()
        self.tarado_realizado = True
        
        # Sincronizar offsets con el segmentador para persistencia en metadata y MongoDB
        self.segmentador.tara_offsets = dict(offsets)

        # Desbloquear botón de captura (REGLA ESTRICTA CUMPLIDA)
        self.btn_iniciar_captura.configure(state="normal")
        self.lbl_estado_rep.configure(
            text="ESTADO: TARADO A 0.0° - LISTO PARA CAPTURAR",
            text_color=COLORES["info"]
        )

        # Actualizar offsets en segmentador y widgets
        self.tarjeta_hombro.actualizar(0.0, offsets["hombro"])
        self.tarjeta_codo.actualizar(0.0, offsets["codo"])
        self.tarjeta_muneca.actualizar(0.0, offsets["muneca"])

    def _toggle_captura(self):
        """Inicia o detiene la segmentación de repeticiones."""
        if self.segmentador.estado in [
            EstadoSegmentador.ESPERANDO_MOVIMIENTO,
            EstadoSegmentador.EN_MOVIMIENTO,
            EstadoSegmentador.CONFIRMANDO_RETORNO
        ]:
            # Detener
            self.segmentador.detener_captura()
            self.btn_iniciar_captura.configure(text="▶ Iniciar Captura", fg_color=COLORES["accent_primary"])
            self.lbl_estado_rep.configure(text="ESTADO: CAPTURA PAUSADA", text_color=COLORES["warning"])
        else:
            # Asegurar sincronización de offsets antes de iniciar
            self.segmentador.tara_offsets = dict(self.app.serial.tara_offsets)
            self.segmentador.iniciar_captura()
            self.btn_iniciar_captura.configure(text="⏹ Detener Captura", fg_color=COLORES["danger"])
            self.lbl_estado_rep.configure(text="ESTADO: ESPERANDO MOVIMIENTO (DESPEGUE > 12°)", text_color=COLORES["hombro"])

    def cargar_contexto_sesion(
        self,
        sesion_info: Dict[str, Any],
        modo_recaptura: bool = False,
        rep_a_recapturar: Optional[int] = None
    ):
        """Recibe el contexto de voluntario y configura el segmentador."""
        self.sesion_info = sesion_info
        self.modo_recaptura = modo_recaptura
        self.rep_a_recapturar = rep_a_recapturar
        self.tarado_realizado = False

        vol_id = sesion_info.get("voluntario_id", "VOL-001")
        ejercicio = sesion_info.get("ejercicio", "Ejercicio 1")
        brazo = sesion_info.get("brazo", "Derecho")
        reps_obj = sesion_info.get("reps_objetivo", 5)
        sesion_id = sesion_info.get("sesion_id", "")

        # Reiniciar bloqueo de tara
        self.btn_iniciar_captura.configure(state="disabled")

        if modo_recaptura and rep_a_recapturar is not None:
            self.lbl_vol_badge.configure(
                text=f"MODO RECAPTURA: VOL {vol_id} | {ejercicio} | REP #{rep_a_recapturar}",
                text_color=COLORES["warning"]
            )
            self.lbl_sesion_sub.configure(text=f"Sesión: {sesion_id} | Sobreescribirá rep_{rep_a_recapturar}.npz")
            self.lbl_conteo_reps.configure(text=f"Recapturando Rep: #{rep_a_recapturar}")
        else:
            self.lbl_vol_badge.configure(
                text=f"VOLUNTARIO: {vol_id} | {ejercicio} ({brazo})",
                text_color=COLORES["hombro"]
            )
            self.lbl_sesion_sub.configure(text=f"Sesión: {sesion_id} | Meta: {reps_obj} repeticiones")
            self.lbl_conteo_reps.configure(text=f"Repeticiones: 0 / {reps_obj}")

        # Configurar segmentador (la sesión se creará en MongoDB SOLO al capturar datos reales)
        self.segmentador.configurar_sesion(
            voluntario_id=vol_id,
            sesion_id=sesion_id,
            ejercicio=ejercicio,
            brazo=brazo,
            reps_objetivo=reps_obj,
            tara_offsets=self.app.serial.tara_offsets,
            modo_recaptura=modo_recaptura,
            rep_a_recapturar=rep_a_recapturar
        )

    def _on_segmentador_estado_cambio(self, estado: str):
        """Actualiza el badge de estado en el hilo principal."""
        self.after(0, self._actualizar_badge_estado, estado)

    def _actualizar_badge_estado(self, estado: str):
        if estado == EstadoSegmentador.ESPERANDO_MOVIMIENTO:
            self.lbl_estado_rep.configure(text="ESTADO: EN POSICIÓN BASAL (ESPERANDO MOVIMIENTO)", text_color=COLORES["hombro"])
        elif estado == EstadoSegmentador.EN_MOVIMIENTO:
            self.lbl_estado_rep.configure(text="ESTADO: EN MOVIMIENTO ARTICULAR...", text_color=COLORES["codo"])
        elif estado == EstadoSegmentador.CONFIRMANDO_RETORNO:
            self.lbl_estado_rep.configure(text="ESTADO: RETORNO DETECTADO (ESTABILIZANDO)", text_color=COLORES["muneca"])
        elif estado == EstadoSegmentador.GUARDANDO:
            self.lbl_estado_rep.configure(text="ESTADO: EMPAQUETANDO NPZ Y METADATOS...", text_color=COLORES["info"])
        elif estado == EstadoSegmentador.COMPLETADO:
            self.lbl_estado_rep.configure(text="ESTADO: ¡SESIÓN COMPLETADA CON ÉXITO!", text_color=COLORES["codo"])
            self.btn_iniciar_captura.configure(text="▶ Iniciar Captura", fg_color=COLORES["accent_primary"])

    def _on_repeticion_guardada(self, num_rep: int, ruta_npz: Any, stats: Dict[str, Any]):
        """Notificación de repetición completada y guardada en disco y MongoDB."""
        self.after(0, self._actualizar_progreso_reps, num_rep, stats)

    def _actualizar_progreso_reps(self, num_rep: int, stats: Dict[str, Any]):
        reps_obj = self.sesion_info.get("reps_objetivo", 5)
        progreso = min(1.0, num_rep / reps_obj)
        self.barra_progreso.set(progreso)
        self.lbl_conteo_reps.configure(text=f"Repeticiones: {num_rep} / {reps_obj}")
        print(f"[ViewCapture] ¡Repetición {num_rep} guardada! Duración: {stats['duracion_s']}s")

    def _on_sesion_finalizada(self, metadata: Dict[str, Any]):
        """Callback al completar la totalidad de repeticiones."""
        self.after(0, lambda: self.lbl_estado_rep.configure(
            text=f"¡FINALIZADO! {self.sesion_info.get('reps_objetivo', 5)} repeticiones almacenadas en disco y MongoDB.",
            text_color=COLORES["codo"]
        ))

    def _on_nuevo_voluntario(self):
        """Detiene captura y redirige a la Ventana 1."""
        self.segmentador.detener_captura()
        self.app.mostrar_vista("login")

    def _iniciar_loop_interfaz(self):
        """Bucle de refresco a 30 FPS para actualizar gráfica y diales."""
        self._actualizar_interfaz_periodica()

    def _actualizar_interfaz_periodica(self):
        try:
            # La captura y segmentación corren en el hilo serial a tasa completa de hardware.
            # Este bucle a 33 ms (~30 FPS) se encarga únicamente de refrescar la visualización gráfica.
            if self.app.serial.esta_conectado():
                ultimo = self.app.serial.ultimo_frame

                # Actualizar diales y tarjetas numéricas
                ft = ultimo["filtrados_tarados"]
                offsets = self.app.serial.tara_offsets
                self.tarjeta_hombro.actualizar(ft[0], offsets["hombro"])
                self.tarjeta_codo.actualizar(ft[1], offsets["codo"])
                self.tarjeta_muneca.actualizar(ft[2], offsets["muneca"])

                # Frecuencia real medida y auditoría de pérdidas
                serial_stats = self.app.serial.obtener_metricas()
                segmenter_stats = self.segmentador.obtener_metricas()
                self.lbl_frecuencia.configure(
                    text=(
                        f"Arduino: {serial_stats['frecuencia_arduino_hz']:.1f} Hz | "
                        f"recepción: {serial_stats['frecuencia_recepcion_hz']:.1f} Hz | "
                        f"análisis: {serial_stats['frecuencia_procesamiento_hz']:.1f} Hz\n"
                        f"Tramas recibidas: {serial_stats['lineas_uart_recibidas']} | "
                        f"válidas: {serial_stats['muestras_validas']} | "
                        f"saltos seq.: {serial_stats['tramas_perdidas']} | "
                        f"I2C inválidas: {serial_stats['tramas_invalidas_i2c']} "
                        f"(fallos sensor: {serial_stats['errores_i2c_firmware']}) | "
                        f"cola descartadas: {serial_stats['lineas_descartadas_cola']} | "
                        f"cola pendiente: {serial_stats['cola_pendiente']}\n"
                        f"Segmentador recibidas/procesadas: "
                        f"{segmenter_stats['muestras_recibidas']}/"
                        f"{segmenter_stats['muestras_procesadas']}"
                    )
                )

                # Actualizar gráfica
                t, s1, s2, s3 = self.app.serial.obtener_ventana_grafica()
                if t:
                    self.linea_hombro.set_data(t, s1)
                    self.linea_codo.set_data(t, s2)
                    self.linea_muneca.set_data(t, s3)
                    
                    t_min = t[-1] - 8.0 if t[-1] > 8.0 else 0.0
                    t_max = max(t[-1] + 0.5, 8.5)
                    self.ax.set_xlim(t_min, t_max)
                    
                    # Rango automático Y
                    todos_angulos = s1 + s2 + s3
                    if todos_angulos:
                        y_min = min(min(todos_angulos) - 10, -20)
                        y_max = max(max(todos_angulos) + 15, 120)
                        self.ax.set_ylim(y_min, y_max)

                    self.canvas_plot.draw_idle()

        except Exception as e:
            pass

        # Programar siguiente frame (33 ms ~ 30 FPS)
        self.after(33, self._actualizar_interfaz_periodica)
