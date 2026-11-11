"""
segmenter.py - Máquina de estados para segmentación automática de repeticiones biomecánicas
"""
from __future__ import annotations
import time
from collections import deque
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
import numpy as np

from Cap_Data.config import (
    SEGMENTADOR_CONFIG,
    CAJON_FILTRADOS_TARADOS,
    CAJON_FILTRADOS_SIN_TARA,
    CAJON_CRUDOS_TARADOS,
    CAJON_CRUDOS_SIN_TARA
)
from Cap_Data.database.mongo_manager import MongoManager
from Cap_Data.database.storage_manager import StorageManager


class EstadoSegmentador:
    INACTIVO = "INACTIVO"
    ESPERANDO_TARA = "ESPERANDO_TARA"
    LISTO = "LISTO"
    ESPERANDO_MOVIMIENTO = "ESPERANDO_MOVIMIENTO"
    EN_MOVIMIENTO = "EN_MOVIMIENTO"
    CONFIRMANDO_RETORNO = "CONFIRMANDO_RETORNO"
    GUARDANDO = "GUARDANDO"
    COMPLETADO = "COMPLETADO"


class RepetitionSegmenter:
    """
    Detector automático de ciclos de repetición biomecánica basado en retorno al reposo tarado (0°).
    Exporta de manera autónoma los 4 cajones a archivos .npz y sincroniza con MongoDB.
    """

    def __init__(
        self,
        mongo_mgr: MongoManager,
        on_estado_cambio: Optional[Callable[[str], None]] = None,
        on_rep_guardada: Optional[Callable[[int, Path, Dict[str, Any]], None]] = None,
        on_sesion_fin: Optional[Callable[[Dict[str, Any]], None]] = None
    ):
        self.mongo = mongo_mgr
        self.on_estado_cambio = on_estado_cambio
        self.on_rep_guardada = on_rep_guardada
        self.on_sesion_fin = on_sesion_fin

        self.estado = EstadoSegmentador.INACTIVO
        self.modo_recaptura: bool = False
        self.rep_a_recapturar: Optional[int] = None

        # Contexto de la sesión activa
        self.voluntario_id: str = ""
        self.sesion_id: str = ""
        self.ejercicio: str = ""
        self.brazo: str = "Derecho"
        self.reps_objetivo: int = 5
        self.reps_completadas: int = 0
        self.tara_offsets: Dict[str, float] = {}

        # Buffers temporales
        self._buffer_preroll = deque(maxlen=25)
        self._buffer_rep_actual: List[Dict[str, Any]] = []
        
        # Variables de tiempo y seguimiento de pico
        self._t_inicio_retorno: float = 0.0
        self._t_despegue: float = 0.0
        self._t_retorno: float = 0.0
        self._indice_retorno: Optional[int] = None
        self._pico_maximo: float = 0.0
        self.muestras_recibidas_total: int = 0
        self.muestras_procesadas_total: int = 0
        self.muestras_fuera_captura_total: int = 0
        self._ultima_muestra: Optional[Dict[str, Any]] = None
        self._timestamp_inicio_ms: Optional[int] = None
        self._timestamp_fin_ms: Optional[int] = None

        # Umbrales
        self.umbral_inicio = SEGMENTADOR_CONFIG["UMBRAL_INICIO_MOV"]
        self.umbral_reposo = SEGMENTADOR_CONFIG["UMBRAL_RETORNO_REPOSO"]
        self.tiempo_confirmacion = SEGMENTADOR_CONFIG["TIEMPO_CONFIRMACION_REPOSO_S"]
        self.duracion_minima = SEGMENTADOR_CONFIG["DURACION_MINIMA_REP_S"]

    def obtener_metricas(self) -> Dict[str, int]:
        return {
            "muestras_recibidas": self.muestras_recibidas_total,
            "muestras_procesadas": self.muestras_procesadas_total,
            "muestras_fuera_captura": self.muestras_fuera_captura_total
        }

    def _cambiar_estado(self, nuevo_estado: str):
        """Actualiza el estado interno y notifica a la interfaz gráfica."""
        self.estado = nuevo_estado
        if self.on_estado_cambio:
            try:
                self.on_estado_cambio(nuevo_estado)
            except Exception:
                pass

    def configurar_sesion(
        self,
        voluntario_id: str,
        sesion_id: str,
        ejercicio: str,
        brazo: str,
        reps_objetivo: int,
        tara_offsets: Dict[str, float],
        modo_recaptura: bool = False,
        rep_a_recapturar: Optional[int] = None,
        reps_iniciales: int = 0
    ):
        """Inicializa los parámetros de la sesión antes de comenzar la adquisición."""
        self.voluntario_id = voluntario_id
        self.sesion_id = sesion_id
        self.ejercicio = ejercicio
        self.brazo = brazo
        self.reps_objetivo = reps_objetivo
        self.reps_completadas = reps_iniciales
        self.tara_offsets = dict(tara_offsets)
        self.modo_recaptura = modo_recaptura
        self.rep_a_recapturar = rep_a_recapturar
        self.sesion_registrada_en_mongo: bool = False
        self.muestras_recibidas_total = 0
        self.muestras_procesadas_total = 0
        self.muestras_fuera_captura_total = 0
        self._ultima_muestra = None
        self._timestamp_inicio_ms = None
        self._timestamp_fin_ms = None
        
        self._buffer_rep_actual.clear()
        self._buffer_preroll.clear()
        self._pico_maximo = 0.0
        self._indice_retorno = None
        self._cambiar_estado(EstadoSegmentador.LISTO)

    def iniciar_captura(self):
        """Activa la búsqueda de repeticiones."""
        self._buffer_rep_actual.clear()
        self._buffer_preroll.clear()
        self._pico_maximo = 0.0
        self._indice_retorno = None
        self._cambiar_estado(EstadoSegmentador.ESPERANDO_MOVIMIENTO)

    def detener_captura(self):
        """Cancela o finaliza la captura de repeticiones."""
        self._buffer_rep_actual.clear()
        self._indice_retorno = None
        self._cambiar_estado(EstadoSegmentador.INACTIVO)

    def procesar_muestra(self, frame: Dict[str, Any]):
        """
        Recibe cada muestra válida del hilo de análisis y actualiza los contadores.
        Las decisiones temporales usan la marca de la muestra cuando está disponible.
        """
        self.muestras_recibidas_total += 1
        self._ultima_muestra = frame
        timestamp_ms = frame.get("ts_hw_ms")
        if timestamp_ms is not None:
            timestamp_ms = int(timestamp_ms)
            if self._timestamp_inicio_ms is None:
                self._timestamp_inicio_ms = timestamp_ms
            self._timestamp_fin_ms = timestamp_ms

        if self.estado not in [
            EstadoSegmentador.ESPERANDO_MOVIMIENTO,
            EstadoSegmentador.EN_MOVIMIENTO,
            EstadoSegmentador.CONFIRMANDO_RETORNO
        ]:
            self.muestras_fuera_captura_total += 1
            return

        self.muestras_procesadas_total += 1
        ft = frame["filtrados_tarados"]
        # Calcular excursión máxima del complejo articular
        amplitud_actual = max(abs(ft[0]), abs(ft[1]), abs(ft[2]))
        tiempo_muestra = frame.get("tiempo")
        t_ahora = float(tiempo_muestra) if tiempo_muestra is not None else time.perf_counter()

        # ==========================================
        # ESTADO 1: ESPERANDO MOVIMIENTO
        # ==========================================
        if self.estado == EstadoSegmentador.ESPERANDO_MOVIMIENTO:
            self._buffer_preroll.append(frame)
            if amplitud_actual > self.umbral_inicio:
                # Se detecta despegue cinemático
                self._buffer_rep_actual.clear()
                
                # Identificar en el preroll el momento en que comenzó a elevarse el ángulo (> 3.0°)
                muestras_despegue = []
                umbral_fino = max(2.5, self.umbral_reposo / 2.0)
                despegue_encontrado = False
                for f_prev in self._buffer_preroll:
                    ft_prev = f_prev["filtrados_tarados"]
                    amp_prev = max(abs(ft_prev[0]), abs(ft_prev[1]), abs(ft_prev[2]))
                    if amp_prev >= umbral_fino:
                        despegue_encontrado = True
                    if despegue_encontrado:
                        muestras_despegue.append(f_prev)

                if muestras_despegue:
                    self._buffer_rep_actual.extend(muestras_despegue)
                else:
                    self._buffer_rep_actual.append(frame)

                self._pico_maximo = amplitud_actual
                self._indice_retorno = None
                self._t_despegue = self._buffer_rep_actual[0]["tiempo"]
                self._cambiar_estado(EstadoSegmentador.EN_MOVIMIENTO)

        # ==========================================
        # ESTADO 2: EN MOVIMIENTO (EXCURSIÓN ARTICULAR)
        # ==========================================
        elif self.estado == EstadoSegmentador.EN_MOVIMIENTO:
            self._buffer_rep_actual.append(frame)
            if amplitud_actual > self._pico_maximo:
                self._pico_maximo = amplitud_actual

            # Verificar si ha retornado hacia la posición de reposo tarado (0°)
            if amplitud_actual < self.umbral_reposo:
                self._t_inicio_retorno = t_ahora
                self._t_retorno = frame["tiempo"]
                # Congelar el índice exacto de fin de movimiento (descartando la confirmación de espera)
                self._indice_retorno = len(self._buffer_rep_actual)
                self._cambiar_estado(EstadoSegmentador.CONFIRMANDO_RETORNO)

        # ==========================================
        # ESTADO 3: CONFIRMANDO RETORNO AL REPOSO BASAL
        # ==========================================
        elif self.estado == EstadoSegmentador.CONFIRMANDO_RETORNO:
            self._buffer_rep_actual.append(frame)

            # Si el ángulo vuelve a subir súbitamente, fue una oscilación intermedia o rebote
            if amplitud_actual > self.umbral_reposo:
                self._indice_retorno = None
                self._cambiar_estado(EstadoSegmentador.EN_MOVIMIENTO)
            else:
                # Comprobar si se ha mantenido en reposo el tiempo de confirmación necesario
                if (t_ahora - self._t_inicio_retorno) >= self.tiempo_confirmacion:
                    self._finalizar_y_guardar_repeticion()

    def _crear_auditoria_repeticion(self, muestras: List[Dict[str, Any]]) -> Dict[str, Any]:
        secuencias = [int(item["seq"]) for item in muestras if item.get("seq") is not None]
        marcas_ms = [int(item["ts_hw_ms"]) for item in muestras if item.get("ts_hw_ms") is not None]
        tiempos_host = [float(item["tiempo_host"]) for item in muestras if item.get("tiempo_host") is not None]
        saltos_secuencia = 0
        for anterior, actual in zip(secuencias, secuencias[1:]):
            delta = (actual - anterior) & 0xFFFFFFFF
            if 0 < delta < 0x80000000:
                saltos_secuencia += max(0, delta - 1)

        ultima = self._ultima_muestra or (muestras[-1] if muestras else {})
        return {
            "base_tiempo": "millis_arduino" if marcas_ms else "reloj_monotono_host",
            "muestras_incluidas": len(muestras),
            "secuencia_inicio": secuencias[0] if secuencias else None,
            "secuencia_fin": secuencias[-1] if secuencias else None,
            "saltos_secuencia_en_repeticion": saltos_secuencia,
            "timestamp_arduino_inicio_ms": marcas_ms[0] if marcas_ms else None,
            "timestamp_arduino_fin_ms": marcas_ms[-1] if marcas_ms else None,
            "tiempo_host_inicio_s": tiempos_host[0] if tiempos_host else None,
            "tiempo_host_fin_s": tiempos_host[-1] if tiempos_host else None,
            "muestras_segmentador_recibidas_total": self.muestras_recibidas_total,
            "muestras_segmentador_procesadas_total": self.muestras_procesadas_total,
            "muestras_fuera_captura_total": self.muestras_fuera_captura_total,
            "lineas_uart_recibidas_total": ultima.get("lineas_uart_recibidas"),
            "lineas_malformadas_total": ultima.get("lineas_malformadas"),
            "lineas_descartadas_cola_total": ultima.get("lineas_descartadas_cola"),
            "cola_pendiente": ultima.get("cola_pendiente"),
            "muestras_entregadas_analisis_total": ultima.get("muestras_entregadas_analisis"),
            "errores_callback_total": ultima.get("errores_callback"),
            "tramas_validas_total": ultima.get("muestras_validas"),
            "tramas_invalidas_i2c_total": ultima.get("tramas_invalidas_i2c"),
            "tramas_perdidas_secuencia_total": ultima.get("tramas_perdidas"),
            "errores_i2c_firmware_total": ultima.get("errores_i2c_firmware"),
            "frecuencia_arduino_hz": ultima.get("frecuencia_arduino_hz"),
            "frecuencia_recepcion_hz": ultima.get("frecuencia_recepcion_hz"),
            "frecuencia_procesamiento_hz": ultima.get("frecuencia_procesamiento_hz")
        }

    def _finalizar_y_guardar_repeticion(self):
        """Empaqueta los datos en los 4 cajones requeridos, guarda el .npz y registra en BD."""
        self._cambiar_estado(EstadoSegmentador.GUARDANDO)

        # Recortar estrictamente al movimiento activo (descartando los 350 ms de reposo posterior)
        if self._indice_retorno is not None and self._indice_retorno > 0:
            muestras_activas = self._buffer_rep_actual[:self._indice_retorno]
        else:
            muestras_activas = self._buffer_rep_actual

        if not muestras_activas:
            self._buffer_rep_actual.clear()
            self._cambiar_estado(EstadoSegmentador.ESPERANDO_MOVIMIENTO)
            return

        # Calcular duración biomecánica exacta entre despegue y retorno
        t_inicio = muestras_activas[0]["tiempo"]
        t_fin = muestras_activas[-1]["tiempo"]
        duracion = max(0.0, float(t_fin - t_inicio))

        # Validar si cumple la duración mínima
        if duracion < self.duracion_minima or self._pico_maximo < self.umbral_inicio:
            # Falso positivo / temblor menor, descartar y seguir
            self._buffer_rep_actual.clear()
            self._pico_maximo = 0.0
            self._indice_retorno = None
            self._cambiar_estado(EstadoSegmentador.ESPERANDO_MOVIMIENTO)
            return

        # Número de repetición a asignar
        if self.modo_recaptura and self.rep_a_recapturar is not None:
            num_rep = self.rep_a_recapturar
        else:
            num_rep = self.reps_completadas + 1

        # Construir las 4 matrices independientes de tamaño (N, 4): [t_rel, hombro, codo, muneca]
        n_muestras = len(muestras_activas)
        ft_mat = np.zeros((n_muestras, 4), dtype=np.float32)
        fst_mat = np.zeros((n_muestras, 4), dtype=np.float32)
        ct_mat = np.zeros((n_muestras, 4), dtype=np.float32)
        cst_mat = np.zeros((n_muestras, 4), dtype=np.float32)

        for i, item in enumerate(muestras_activas):
            t_rel = float(item["tiempo"] - t_inicio)
            ft_mat[i] = [t_rel, item["filtrados_tarados"][0], item["filtrados_tarados"][1], item["filtrados_tarados"][2]]
            fst_mat[i] = [t_rel, item["filtrados_sin_tara"][0], item["filtrados_sin_tara"][1], item["filtrados_sin_tara"][2]]
            ct_mat[i] = [t_rel, item["crudos_tarados"][0], item["crudos_tarados"][1], item["crudos_tarados"][2]]
            cst_mat[i] = [t_rel, item["crudos_sin_tara"][0], item["crudos_sin_tara"][1], item["crudos_sin_tara"][2]]

        auditoria = self._crear_auditoria_repeticion(muestras_activas)

        # Guardar las señales y la auditoría temporal de la repetición.
        ruta_npz, stats = StorageManager.guardar_repeticion_npz(
            voluntario_id=self.voluntario_id,
            sesion_id=self.sesion_id,
            ejercicio=self.ejercicio,
            num_rep=num_rep,
            filtrados_tarados=ft_mat,
            filtrados_sin_tara=fst_mat,
            crudos_tarados=ct_mat,
            crudos_sin_tara=cst_mat,
            auditoria=auditoria
        )

        # Registro en MongoDB
        if not self.modo_recaptura and not self.sesion_registrada_en_mongo:
            # Crear documento de sesión en MongoDB ÚNICAMENTE al capturar la primera repetición real
            sesion_doc = {
                "sesion_id": self.sesion_id,
                "voluntario_id": self.voluntario_id,
                "ejercicio": self.ejercicio,
                "brazo": self.brazo,
                "reps_objetivo": self.reps_objetivo,
                "reps_completadas": 0,
                "tara_offsets": self.tara_offsets,
                "estado": "EN_PROCESO"
            }
            self.mongo.crear_sesion(sesion_doc)
            self.mongo.registrar_o_actualizar_voluntario(self.voluntario_id, self.brazo)
            self.sesion_registrada_en_mongo = True

        datos_rep_mongo = {
            "sesion_id": self.sesion_id,
            "voluntario_id": self.voluntario_id,
            "ejercicio": self.ejercicio,
            "num_rep": num_rep,
            "archivo_npz": str(ruta_npz),
            "duracion_s": stats["duracion_s"],
            "muestras_totales": stats["muestras_totales"],
            "excursion_total": stats.get("excursion_total", {}),
            "desviacion_maxima_abs": stats.get("desviacion_maxima_abs", {}),
            "auditoria": stats.get("auditoria", {}),
            "rom_max": stats["rom_max"],
            "estado": "RECAPTURADA" if self.modo_recaptura else "VALIDA"
        }

        if self.modo_recaptura:
            self.mongo.recapturar_repeticion(self.sesion_id, num_rep, str(ruta_npz), stats)
        else:
            self.mongo.registrar_repeticion(datos_rep_mongo)
            self.reps_completadas += 1

        # Notificar a la UI
        if self.on_rep_guardada:
            try:
                self.on_rep_guardada(num_rep, ruta_npz, stats)
            except Exception:
                pass

        # Limpiar buffer de repetición
        self._buffer_rep_actual.clear()
        self._pico_maximo = 0.0

        # Evaluar condición de fin
        if self.modo_recaptura:
            self._finalizar_sesion_completa()
        elif self.reps_completadas >= self.reps_objetivo:
            self._finalizar_sesion_completa()
        else:
            # Continuar esperando la siguiente repetición
            self._cambiar_estado(EstadoSegmentador.ESPERANDO_MOVIMIENTO)

    def _finalizar_sesion_completa(self):
        """Cierra la sesión y genera el archivo metadata.json."""
        self._cambiar_estado(EstadoSegmentador.COMPLETADO)

        # Guardar metadata.json completo en la carpeta
        metadata = {
            "voluntario_id": self.voluntario_id,
            "ejercicio": self.ejercicio,
            "sesion_id": self.sesion_id,
            "brazo": self.brazo,
            "reps_objetivo": self.reps_objetivo,
            "reps_completadas": self.reps_completadas,
            "tara_offsets": self.tara_offsets,
            "auditoria_adquisicion": {
                "muestras_segmentador_recibidas": self.muestras_recibidas_total,
                "muestras_segmentador_procesadas": self.muestras_procesadas_total,
                "muestras_fuera_captura": self.muestras_fuera_captura_total,
                "timestamp_arduino_inicio_ms": self._timestamp_inicio_ms,
                "timestamp_arduino_fin_ms": self._timestamp_fin_ms,
                "lineas_uart_recibidas": (self._ultima_muestra or {}).get("lineas_uart_recibidas"),
                "lineas_malformadas": (self._ultima_muestra or {}).get("lineas_malformadas"),
                "lineas_descartadas_cola": (self._ultima_muestra or {}).get("lineas_descartadas_cola"),
                "muestras_entregadas_analisis": (self._ultima_muestra or {}).get("muestras_entregadas_analisis"),
                "tramas_validas": (self._ultima_muestra or {}).get("muestras_validas"),
                "tramas_invalidas_i2c": (self._ultima_muestra or {}).get("tramas_invalidas_i2c"),
                "tramas_perdidas_secuencia": (self._ultima_muestra or {}).get("tramas_perdidas"),
                "errores_i2c_firmware": (self._ultima_muestra or {}).get("errores_i2c_firmware")
            },
            "estado": "COMPLETA",
            "cajones_npz": [
                CAJON_FILTRADOS_TARADOS,
                CAJON_FILTRADOS_SIN_TARA,
                CAJON_CRUDOS_TARADOS,
                CAJON_CRUDOS_SIN_TARA
            ]
        }
        StorageManager.guardar_metadata(self.voluntario_id, self.sesion_id, self.ejercicio, metadata)

        # Actualizar sesión en MongoDB
        self.mongo.actualizar_sesion(self.sesion_id, {
            "estado": "COMPLETA",
            "reps_completadas": self.reps_completadas
        })

        if self.on_sesion_fin:
            try:
                self.on_sesion_fin(metadata)
            except Exception:
                pass
