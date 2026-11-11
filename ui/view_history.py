"""
view_history.py - Ventana 4: Historial de Sesiones, Auditoría y Recaptura de Repeticiones
"""
from __future__ import annotations
import os
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional
import customtkinter as ctk

from Cap_Data.config import COLORES
from Cap_Data.database.storage_manager import StorageManager

if TYPE_CHECKING:
    from Cap_Data.ui.app_window import AppWindow


class ViewHistory(ctk.CTkFrame):
    """Vista de consulta de sesiones clínicas en MongoDB, auditoría de repeticiones y recaptura directa."""

    def __init__(self, parent: ctk.CTkFrame, app: AppWindow):
        super().__init__(parent, fg_color=COLORES["bg_main"])
        self.app = app
        self.sesion_seleccionada: Optional[Dict[str, Any]] = None
        self.repeticion_seleccionada: Optional[Dict[str, Any]] = None
        
        self.sesiones_cache: List[Dict[str, Any]] = []
        self.repeticiones_cache: List[Dict[str, Any]] = []

        self._construir_ui()

    def _construir_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # -------------------------------------------------------------
        # 1. ENCABEZADO Y FILTROS
        # -------------------------------------------------------------
        frame_header = ctk.CTkFrame(
            self,
            fg_color=COLORES["bg_card"],
            corner_radius=10,
            border_width=1,
            border_color=COLORES["border"]
        )
        frame_header.grid(row=0, column=0, padx=16, pady=(12, 8), sticky="ew")
        frame_header.grid_columnconfigure(0, weight=1)

        frame_titulos = ctk.CTkFrame(frame_header, fg_color="transparent")
        frame_titulos.grid(row=0, column=0, padx=14, pady=10, sticky="w")

        lbl_tit = ctk.CTkLabel(
            frame_titulos,
            text="Historial Clínico y Gestión de Repeticiones",
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color=COLORES["text_primary"]
        )
        lbl_tit.pack(anchor="w")

        lbl_desc = ctk.CTkLabel(
            frame_titulos,
            text="Persistencia sincronizada en MongoDB (ROMDB) y almacenamiento local NPZ.",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COLORES["text_secondary"]
        )
        lbl_desc.pack(anchor="w")

        # Filtro de búsqueda y recarga
        frame_filtros = ctk.CTkFrame(frame_header, fg_color="transparent")
        frame_filtros.grid(row=0, column=1, padx=14, pady=10, sticky="e")

        self.entry_buscar = ctk.CTkEntry(
            frame_filtros,
            placeholder_text="Buscar voluntario o ejercicio...",
            width=220,
            height=32,
            corner_radius=6,
            fg_color=COLORES["bg_card_secondary"]
        )
        self.entry_buscar.pack(side="left", padx=4)

        btn_buscar = ctk.CTkButton(
            frame_filtros,
            text="Buscar",
            width=70,
            height=32,
            corner_radius=6,
            fg_color=COLORES["accent_blue"],
            hover_color="#1a56b8",
            command=self.filtrar_sesiones
        )
        btn_buscar.pack(side="left", padx=4)

        btn_refrescar = ctk.CTkButton(
            frame_filtros,
            text="🔄 Actualizar",
            width=90,
            height=32,
            corner_radius=6,
            fg_color=COLORES["bg_card_secondary"],
            hover_color=COLORES["border"],
            command=self.cargar_sesiones
        )
        btn_refrescar.pack(side="left", padx=4)

        # -------------------------------------------------------------
        # 2. CUERPO: LISTADO DE SESIONES (IZQ) Y DETALLE DE REPETICIONES (DER)
        # -------------------------------------------------------------
        frame_cuerpo = ctk.CTkFrame(self, fg_color="transparent")
        frame_cuerpo.grid(row=1, column=0, padx=16, pady=0, sticky="nsew")
        frame_cuerpo.grid_columnconfigure(0, weight=3)  # Tabla de sesiones
        frame_cuerpo.grid_columnconfigure(1, weight=2)  # Detalle repeticiones
        frame_cuerpo.grid_rowconfigure(0, weight=1)

        # Panel izquierdo: Lista con scroll de sesiones
        self.panel_sesiones = ctk.CTkScrollableFrame(
            frame_cuerpo,
            fg_color=COLORES["bg_card"],
            corner_radius=10,
            border_width=1,
            border_color=COLORES["border"]
        )
        self.panel_sesiones.grid(row=0, column=0, padx=(0, 8), pady=0, sticky="nsew")

        # Panel derecho: Detalle de repeticiones y botones de acción
        self.panel_detalle = ctk.CTkFrame(
            frame_cuerpo,
            fg_color=COLORES["bg_card"],
            corner_radius=10,
            border_width=1,
            border_color=COLORES["border"]
        )
        self.panel_detalle.grid(row=0, column=1, padx=(8, 0), pady=0, sticky="nsew")
        self.panel_detalle.grid_columnconfigure(0, weight=1)
        self.panel_detalle.grid_rowconfigure(1, weight=1)

        self._construir_panel_detalle()

        # -------------------------------------------------------------
        # 3. BARRA DE NAVEGACIÓN INFERIOR
        # -------------------------------------------------------------
        frame_nav = ctk.CTkFrame(
            self,
            fg_color=COLORES["bg_card"],
            corner_radius=8,
            border_width=1,
            border_color=COLORES["border"]
        )
        frame_nav.grid(row=2, column=0, padx=16, pady=10, sticky="ew")

        btn_inicio = ctk.CTkButton(
            frame_nav,
            text="🏠 Inicio de Sesión",
            height=34,
            corner_radius=6,
            fg_color=COLORES["bg_card_secondary"],
            hover_color=COLORES["border"],
            font=ctk.CTkFont(family="Segoe UI", size=12),
            command=lambda: self.app.mostrar_vista("login")
        )
        btn_inicio.pack(side="left", padx=10, pady=8)

        btn_graficas_3d = ctk.CTkButton(
            frame_nav,
            text="📈 Gráficas de Dispersión 3D",
            height=34,
            corner_radius=6,
            fg_color=COLORES["bg_card_secondary"],
            hover_color=COLORES["border"],
            font=ctk.CTkFont(family="Segoe UI", size=12),
            command=lambda: self.app.mostrar_vista("3d")
        )
        btn_graficas_3d.pack(side="right", padx=10, pady=8)

    def _construir_panel_detalle(self):
        """Inicializa los controles del visor de repeticiones en la columna derecha."""
        # Cabecera de detalle
        self.lbl_detalle_tit = ctk.CTkLabel(
            self.panel_detalle,
            text="Detalle de Repeticiones",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color=COLORES["hombro"]
        )
        self.lbl_detalle_tit.grid(row=0, column=0, padx=14, pady=(12, 4), sticky="w")

        # Scroll de repeticiones de la sesión seleccionada
        self.scroll_reps = ctk.CTkScrollableFrame(
            self.panel_detalle,
            fg_color=COLORES["bg_card_secondary"],
            corner_radius=8
        )
        self.scroll_reps.grid(row=1, column=0, padx=12, pady=6, sticky="nsew")

        # Contenedor de botones de acción por repetición
        frame_acciones = ctk.CTkFrame(self.panel_detalle, fg_color="transparent")
        frame_acciones.grid(row=2, column=0, padx=12, pady=(6, 12), sticky="ew")
        frame_acciones.grid_columnconfigure(0, weight=1)
        frame_acciones.grid_columnconfigure(1, weight=1)

        # Botón RECAPTURAR (REQUERIDO)
        self.btn_recapturar = ctk.CTkButton(
            frame_acciones,
            text="🔄 Recapturar Rep",
            height=36,
            corner_radius=6,
            fg_color=COLORES["accent_primary"],
            hover_color=COLORES["accent_hover"],
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            state="disabled",
            command=self._on_recapturar_repeticion
        )
        self.btn_recapturar.grid(row=0, column=0, padx=(0, 4), pady=(0, 6), sticky="ew")

        # Botón ELIMINAR (REQUERIDO)
        self.btn_eliminar = ctk.CTkButton(
            frame_acciones,
            text="🗑️ Eliminar Rep",
            height=36,
            corner_radius=6,
            fg_color=COLORES["danger"],
            hover_color=COLORES["danger_hover"],
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            state="disabled",
            command=self._on_eliminar_repeticion
        )
        self.btn_eliminar.grid(row=0, column=1, padx=(4, 0), pady=(0, 6), sticky="ew")

        # Botón Eliminar Sesión Completa (Elimina en MongoDB y en storage/)
        self.btn_eliminar_sesion = ctk.CTkButton(
            frame_acciones,
            text="🗑️ Eliminar Sesión Completa",
            height=34,
            corner_radius=6,
            fg_color=COLORES["danger"],
            hover_color=COLORES["danger_hover"],
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            state="disabled",
            command=lambda: self._on_eliminar_sesion_completa(self.sesion_seleccionada)
        )
        self.btn_eliminar_sesion.grid(row=1, column=0, columnspan=2, pady=(0, 6), sticky="ew")

        # Botón Abrir Carpeta Local en Explorer
        btn_carpeta = ctk.CTkButton(
            frame_acciones,
            text="📁 Abrir Carpeta Local",
            height=30,
            corner_radius=6,
            fg_color=COLORES["bg_card_secondary"],
            hover_color=COLORES["border"],
            border_width=1,
            border_color=COLORES["border"],
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COLORES["text_primary"],
            command=self._on_abrir_carpeta_local
        )
        btn_carpeta.grid(row=2, column=0, columnspan=2, pady=(0, 0), sticky="ew")

    def cargar_sesiones(self):
        """Obtiene las sesiones desde MongoDB (o fallback de disco) y las lista."""
        sesiones = self.app.mongo.obtener_todas_sesiones()
        
        # Fallback a disco si la BD está vacía
        if not sesiones:
            sesiones = StorageManager.listar_sesiones_locales()

        self.sesiones_cache = sesiones
        self.renderizar_lista_sesiones(sesiones)

    def filtrar_sesiones(self):
        """Filtra las sesiones en memoria según el texto de búsqueda."""
        query = self.entry_buscar.get().strip().lower()
        if not query:
            self.renderizar_lista_sesiones(self.sesiones_cache)
            return

        filtradas = [
            s for s in self.sesiones_cache
            if query in s.get("voluntario_id", "").lower() or
               query in s.get("ejercicio", "").lower() or
               query in s.get("sesion_id", "").lower()
        ]
        self.renderizar_lista_sesiones(filtradas)

    def renderizar_lista_sesiones(self, sesiones: List[Dict[str, Any]]):
        """Genera visualmente las tarjetas de sesión en el scroll panel."""
        for widget in self.panel_sesiones.winfo_children():
            widget.destroy()

        if not sesiones:
            lbl_vacio = ctk.CTkLabel(
                self.panel_sesiones,
                text="No hay sesiones clínicas registradas.",
                font=ctk.CTkFont(family="Segoe UI", size=13),
                text_color=COLORES["text_secondary"]
            )
            lbl_vacio.pack(padx=20, pady=40)
            return

        for sesion in sesiones:
            card = ctk.CTkFrame(
                self.panel_sesiones,
                fg_color=COLORES["bg_card_secondary"],
                corner_radius=8,
                border_width=1,
                border_color=COLORES["border"]
            )
            card.pack(fill="x", padx=4, pady=4)
            card.grid_columnconfigure(0, weight=1)

            # Información principal
            vol_id = sesion.get("voluntario_id", "DESCONOCIDO")
            ej = sesion.get("ejercicio", "Ejercicio 1")
            brazo = sesion.get("brazo", "Derecho")
            reps_comp = sesion.get("reps_completadas", 0)
            reps_obj = sesion.get("reps_objetivo", 5)
            fecha = sesion.get("fecha_hora", "")[:19].replace("T", " ")

            lbl_encabezado = ctk.CTkLabel(
                card,
                text=f"{vol_id} — {ej} ({brazo})",
                font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
                text_color=COLORES["text_primary"]
            )
            lbl_encabezado.grid(row=0, column=0, padx=12, pady=(8, 2), sticky="w")

            lbl_meta = ctk.CTkLabel(
                card,
                text=f"Sesión: {sesion.get('sesion_id')} | Fecha: {fecha} | Reps: {reps_comp}/{reps_obj}",
                font=ctk.CTkFont(family="Segoe UI", size=11),
                text_color=COLORES["text_secondary"]
            )
            lbl_meta.grid(row=1, column=0, padx=12, pady=(0, 8), sticky="w")

            # Panel de botones de la tarjeta de sesión
            frame_card_btns = ctk.CTkFrame(card, fg_color="transparent")
            frame_card_btns.grid(row=0, column=1, rowspan=2, padx=10, pady=6)

            btn_sel = ctk.CTkButton(
                frame_card_btns,
                text="Ver Detalles",
                width=85,
                height=26,
                corner_radius=6,
                fg_color=COLORES["accent_blue"],
                hover_color=COLORES["accent_blue_hover"],
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                command=lambda s=sesion: self._seleccionar_sesion(s)
            )
            btn_sel.pack(side="top", pady=2)

            btn_del = ctk.CTkButton(
                frame_card_btns,
                text="🗑️ Borrar",
                width=85,
                height=24,
                corner_radius=6,
                fg_color=COLORES["bg_card"],
                hover_color=COLORES["danger"],
                border_width=1,
                border_color=COLORES["border"],
                font=ctk.CTkFont(family="Segoe UI", size=10),
                text_color=COLORES["danger"],
                command=lambda s=sesion: self._on_eliminar_sesion_completa(s)
            )
            btn_del.pack(side="top", pady=2)

    def _seleccionar_sesion(self, sesion: Dict[str, Any]):
        """Carga las repeticiones de la sesión en el panel de detalle."""
        self.sesion_seleccionada = sesion
        self.repeticion_seleccionada = None
        self.btn_recapturar.configure(state="disabled")
        self.btn_eliminar.configure(state="disabled")
        self.btn_eliminar_sesion.configure(state="normal")

        sesion_id = sesion.get("sesion_id", "")
        self.lbl_detalle_tit.configure(text=f"Reps de Sesión: {sesion_id}")

        # Buscar repeticiones en MongoDB
        reps = self.app.mongo.obtener_repeticiones_sesion(sesion_id)

        # Fallback de lectura directa de archivos si MongoDB no las tenía indexadas
        if not reps:
            reps = []
            carpeta = StorageManager.obtener_carpeta_sesion(
                sesion.get("voluntario_id", ""),
                sesion_id,
                sesion.get("ejercicio", "")
            )
            archivos_npz = sorted(list(carpeta.glob("rep_*.npz")))
            for p in archivos_npz:
                try:
                    num = int(p.stem.replace("rep_", ""))
                    reps.append({
                        "sesion_id": sesion_id,
                        "voluntario_id": sesion.get("voluntario_id"),
                        "ejercicio": sesion.get("ejercicio"),
                        "num_rep": num,
                        "archivo_npz": str(p),
                        "duracion_s": 0.0,
                        "estado": "VALIDA"
                    })
                except Exception:
                    pass

        self.repeticiones_cache = reps
        self._renderizar_lista_repeticiones(reps)

    def _renderizar_lista_repeticiones(self, repeticiones: List[Dict[str, Any]]):
        """Dibuja cada repetición en el panel secundario."""
        for widget in self.scroll_reps.winfo_children():
            widget.destroy()

        if not repeticiones:
            lbl = ctk.CTkLabel(
                self.scroll_reps,
                text="No hay repeticiones válidas para esta sesión.",
                font=ctk.CTkFont(family="Segoe UI", size=11),
                text_color=COLORES["text_secondary"]
            )
            lbl.pack(padx=10, pady=20)
            return

        for r in repeticiones:
            num = r.get("num_rep", 1)
            dur = r.get("duracion_s", 0.0)
            exc = r.get("excursion_total", {})
            desviacion = r.get("desviacion_maxima_abs", r.get("rom_max", {}))

            h_exc = exc.get("hombro")
            c_exc = exc.get("codo")
            m_exc = exc.get("muneca")
            h_desv = desviacion.get("hombro")
            c_desv = desviacion.get("codo")
            m_desv = desviacion.get("muneca")

            def formato_metrica(valor):
                return f"{valor:.1f}°" if valor is not None else "N/D"

            card_rep = ctk.CTkFrame(
                self.scroll_reps,
                fg_color=COLORES["bg_card"],
                corner_radius=6,
                border_width=1,
                border_color=COLORES["border"]
            )
            card_rep.pack(fill="x", padx=2, pady=3)
            card_rep.grid_columnconfigure(0, weight=1)

            lbl_num = ctk.CTkLabel(
                card_rep,
                text=f"Repetición #{num} | {dur}s",
                font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                text_color=COLORES["codo"]
            )
            lbl_num.grid(row=0, column=0, padx=8, pady=(4, 0), sticky="w")

            lbl_stats = ctk.CTkLabel(
                card_rep,
                text=(
                    f"Excursión PTP -> H: {formato_metrica(h_exc)} | "
                    f"C: {formato_metrica(c_exc)} | M: {formato_metrica(m_exc)}\n"
                    f"Desv. Máxima  -> H: {formato_metrica(h_desv)} | "
                    f"C: {formato_metrica(c_desv)} | M: {formato_metrica(m_desv)}"
                ),
                font=ctk.CTkFont(family="Segoe UI", size=9),
                text_color=COLORES["text_secondary"],
                justify="left"
            )
            lbl_stats.grid(row=1, column=0, padx=8, pady=(0, 4), sticky="w")

            btn_elegir = ctk.CTkButton(
                card_rep,
                text="Seleccionar",
                width=75,
                height=24,
                corner_radius=4,
                font=ctk.CTkFont(family="Segoe UI", size=10),
                fg_color=COLORES["bg_card_secondary"],
                hover_color=COLORES["border"],
                command=lambda rep=r: self._seleccionar_repeticion(rep)
            )
            btn_elegir.grid(row=0, column=1, rowspan=2, padx=8, pady=4)

    def _seleccionar_repeticion(self, rep: Dict[str, Any]):
        """Habilita los botones de acción para la repetición elegida."""
        self.repeticion_seleccionada = rep
        self.btn_recapturar.configure(state="normal", text=f"🔄 Recapturar Rep #{rep.get('num_rep')}")
        self.btn_eliminar.configure(state="normal", text=f"🗑️ Eliminar Rep #{rep.get('num_rep')}")

    def _on_recapturar_repeticion(self):
        """
        Navega a la Ventana de Captura en MODO RECAPTURA para la repetición seleccionada.
        Permite al voluntario realizar de nuevo el movimiento y sobreescribe rep_X.npz.
        """
        if not self.sesion_seleccionada or not self.repeticion_seleccionada:
            return

        num_rep = self.repeticion_seleccionada.get("num_rep", 1)

        # Transfiere el contexto de la sesión completa a la vista de captura
        self.app.mostrar_vista(
            "captura",
            sesion_info=self.sesion_seleccionada,
            modo_recaptura=True,
            rep_a_recapturar=num_rep
        )

    def _on_eliminar_repeticion(self):
        """Elimina la repetición de MongoDB y respalda el archivo en disco."""
        if not self.sesion_seleccionada or not self.repeticion_seleccionada:
            return

        sesion_id = self.sesion_seleccionada.get("sesion_id", "")
        num_rep = self.repeticion_seleccionada.get("num_rep", 1)
        ruta_npz = self.repeticion_seleccionada.get("archivo_npz", "")

        # 1. Eliminar en MongoDB
        self.app.mongo.eliminar_repeticion(sesion_id, num_rep)

        # 2. Respaldar / Renombrar archivo a .bak en disco
        if ruta_npz:
            StorageManager.eliminar_archivo_repeticion(ruta_npz)

        # 3. Refrescar lista de repeticiones
        self._seleccionar_sesion(self.sesion_seleccionada)
        self.cargar_sesiones()

    def _on_eliminar_sesion_completa(self, sesion: Optional[Dict[str, Any]] = None):
        """Elimina la sesión por completo de MongoDB y del almacenamiento físico en disco."""
        target = sesion or self.sesion_seleccionada
        if not target:
            return

        sesion_id = target.get("sesion_id", "")
        vol_id = target.get("voluntario_id", "")
        ej = target.get("ejercicio", "")

        # 1. Eliminar de MongoDB (sesión y repeticiones asociadas)
        self.app.mongo.eliminar_sesion_completa(sesion_id)

        # 2. Eliminar carpeta física en storage/
        StorageManager.eliminar_carpeta_sesion(vol_id, sesion_id, ej)

        # 3. Limpiar estado si era la sesión actualmente seleccionada
        if self.sesion_seleccionada and self.sesion_seleccionada.get("sesion_id") == sesion_id:
            self.sesion_seleccionada = None
            self.repeticion_seleccionada = None
            self.lbl_detalle_tit.configure(text="Detalle de Repeticiones")
            self._renderizar_lista_repeticiones([])
            self.btn_recapturar.configure(state="disabled")
            self.btn_eliminar.configure(state="disabled")
            self.btn_eliminar_sesion.configure(state="disabled")

        # 4. Refrescar listado
        self.cargar_sesiones()

    def _on_abrir_carpeta_local(self):
        """Abre la carpeta de la sesión en el explorador de Windows."""
        if not self.sesion_seleccionada:
            carpeta = StorageManager.STORAGE_DIR
        else:
            carpeta = StorageManager.obtener_carpeta_sesion(
                self.sesion_seleccionada.get("voluntario_id", ""),
                self.sesion_seleccionada.get("sesion_id", ""),
                self.sesion_seleccionada.get("ejercicio", "")
            )

        if os.name == "nt":
            os.startfile(str(carpeta))
        else:
            subprocess.Popen(["xdg-open", str(carpeta)])
