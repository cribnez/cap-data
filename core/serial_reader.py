"""
serial_reader.py - Ingestor serial multihilo a alta frecuencia con filtrado y tara
"""
from __future__ import annotations
import math
import queue
import threading
import time
from collections import deque
from typing import Any, Callable, Dict, List, Optional, Tuple
import serial
import serial.tools.list_ports

from Cap_Data.config import (
    SERIAL_DEFAULT_BAUDRATE,
    SERIAL_TIMEOUT,
    SERIAL_BUFFER_SIZE,
    VARIABLES_CLINICAS,
    EJE_ARTICULAR_DEFECTO
)
from Cap_Data.core.filters import crear_filtros_variables


class SerialReader:
    """Adquiere tramas seriales y las procesa en un hilo separado."""

    def __init__(self, callback_muestra: Optional[Callable[[Dict[str, Any]], None]] = None):
        self.callback_muestra = callback_muestra
        self.puerto: Optional[str] = None
        self.baudrate: int = SERIAL_DEFAULT_BAUDRATE
        self.eje_articular: str = EJE_ARTICULAR_DEFECTO  # "pitch" (defecto) o "roll"
        self.serial_conn: Optional[serial.Serial] = None
        
        self._hilo_lectura: Optional[threading.Thread] = None
        self._hilo_procesamiento: Optional[threading.Thread] = None
        self._cola_procesamiento: Optional[queue.Queue] = None
        self._max_cola_procesamiento = 10000
        self._corriendo: bool = False
        self._lock = threading.Lock()
        
        # Filtros para datos con tara y sin tara
        self.filtros_tarados = crear_filtros_variables()
        self.filtros_sin_tara = crear_filtros_variables()
        
        # Offsets de calibración / Tara
        self.tara_offsets: Dict[str, float] = {var: 0.0 for var in VARIABLES_CLINICAS}
        self.tarado_completado: bool = False
        
        # Último paquete estructurado
        self.ultimo_frame: Dict[str, Any] = {
            "tiempo": 0.0,
            "crudos_sin_tara": [0.0, 0.0, 0.0],
            "crudos_tarados": [0.0, 0.0, 0.0],
            "filtrados_sin_tara": [0.0, 0.0, 0.0],
            "filtrados_tarados": [0.0, 0.0, 0.0],
            "roll_crudo": [0.0, 0.0, 0.0],
            "pitch_crudo": [0.0, 0.0, 0.0]
        }
        
        # Tasas y contadores de adquisición, análisis y auditoría.
        self.frecuencia_hz: float = 0.0
        self.frecuencia_arduino_hz: float = 0.0
        self.frecuencia_recepcion_hz: float = 0.0
        self.frecuencia_procesamiento_hz: float = 0.0
        self.lineas_uart_recibidas: int = 0
        self.lineas_malformadas: int = 0
        self.lineas_descartadas_cola: int = 0
        self.total_tramas_recibidas: int = 0
        self.muestras_validas: int = 0
        self.tramas_invalidas_i2c: int = 0
        self.tramas_perdidas: int = 0
        self.errores_i2c_firmware: int = 0
        self.muestras_entregadas_analisis: int = 0
        self.errores_callback: int = 0
        self.ultimo_seq: Optional[int] = None
        self._ultimo_ts_hw_ms: Optional[int] = None
        self._t0_hw_ms: Optional[int] = None
        self._seq_ventana_hw = 0
        self._ms_ventana_hw = 0
        self._tasa_rx_inicio = time.perf_counter()
        self._tasa_rx_conteo = 0
        self._tasa_proc_inicio = time.perf_counter()
        self._tasa_proc_conteo = 0
        
        # Búfer de histórico para la gráfica en tiempo real (ventana deslizante)
        self.buffer_historial = deque(maxlen=600)
        self.t0: Optional[float] = None

    @staticmethod
    def listar_puertos() -> List[str]:
        """Obtiene la lista de puertos COM seriales disponibles en el sistema."""
        puertos = serial.tools.list_ports.comports()
        return [p.device for p in sorted(puertos)]

    def esta_conectado(self) -> bool:
        """Indica si el puerto serial está abierto y transmitiendo."""
        return self._corriendo and self.serial_conn is not None and self.serial_conn.is_open

    def conectar(self, puerto: str, baudrate: int = SERIAL_DEFAULT_BAUDRATE) -> bool:
        """Abre el puerto serial virtual e inicia los hilos de lectura y análisis."""
        if self.esta_conectado():
            self.desconectar()

        if self._hilo_procesamiento and self._hilo_procesamiento.is_alive():
            self._hilo_procesamiento.join(timeout=2.0)
            if self._hilo_procesamiento.is_alive():
                print("[SerialReader] El análisis anterior sigue ocupado; no se abre otra conexión.")
                return False

        try:
            self.serial_conn = serial.Serial(
                port=puerto,
                baudrate=baudrate,
                timeout=SERIAL_TIMEOUT
            )
            # Vaciar buffers de hardware iniciales
            self.serial_conn.reset_input_buffer()
            self.serial_conn.reset_output_buffer()
            
            self.puerto = puerto
            self.baudrate = baudrate
            self._corriendo = True
            self.t0 = time.perf_counter()
            ahora = time.perf_counter()
            self._cola_procesamiento = queue.Queue(maxsize=self._max_cola_procesamiento)
            self.frecuencia_hz = 0.0
            self.frecuencia_arduino_hz = 0.0
            self.frecuencia_recepcion_hz = 0.0
            self.frecuencia_procesamiento_hz = 0.0
            self.lineas_uart_recibidas = 0
            self.lineas_malformadas = 0
            self.lineas_descartadas_cola = 0
            self.total_tramas_recibidas = 0
            self.muestras_validas = 0
            self.tramas_invalidas_i2c = 0
            self.tramas_perdidas = 0
            self.errores_i2c_firmware = 0
            self.muestras_entregadas_analisis = 0
            self.errores_callback = 0
            self.ultimo_seq = None
            self._ultimo_ts_hw_ms = None
            self._t0_hw_ms = None
            self._seq_ventana_hw = 0
            self._ms_ventana_hw = 0
            self._tasa_rx_inicio = ahora
            self._tasa_rx_conteo = 0
            self._tasa_proc_inicio = ahora
            self._tasa_proc_conteo = 0
            self.buffer_historial.clear()
            
            self._hilo_procesamiento = threading.Thread(
                target=self._loop_procesamiento,
                daemon=True
            )
            self._hilo_procesamiento.start()
            self._hilo_lectura = threading.Thread(target=self._loop_lectura, daemon=True)
            self._hilo_lectura.start()
            print(f"[SerialReader] Conectado exitosamente al puerto {puerto} @ {baudrate} baud.")
            return True
        except Exception as e:
            print(f"[SerialReader] Error al conectar al puerto {puerto}: {e}")
            self.serial_conn = None
            self._corriendo = False
            return False

    def desconectar(self):
        """Detiene la lectura serial y deja al hilo de análisis vaciar su cola pendiente."""
        self._corriendo = False
        if self._hilo_lectura and self._hilo_lectura.is_alive():
            self._hilo_lectura.join(timeout=1.0)
            
        if self.serial_conn and self.serial_conn.is_open:
            try:
                self.serial_conn.close()
            except Exception:
                pass
        self.serial_conn = None
        if self._hilo_procesamiento and self._hilo_procesamiento.is_alive():
            self._hilo_procesamiento.join(timeout=3.0)
            if self._hilo_procesamiento.is_alive():
                print("[SerialReader] El hilo de análisis continúa vaciando la cola pendiente.")
        print("[SerialReader] Puerto serial desconectado.")

    def aplicar_tara(self) -> Dict[str, float]:
        """
        Fija los ángulos actuales crudos como el nuevo offset (0° virtual).
        Reinicia los filtros para eliminar transitorios y marca 'tarado_completado = True'.
        """
        with self._lock:
            # Tomar los últimos valores crudos estables
            c_raw = self.ultimo_frame["crudos_sin_tara"]
            self.tara_offsets = {
                "hombro": float(c_raw[0]),
                "codo": float(c_raw[1]),
                "muneca": float(c_raw[2])
            }
            # Reiniciar filtros para que converjan rápidamente al nuevo 0°
            for f in self.filtros_tarados.values():
                f.reset()
            self.tarado_completado = True
            print(f"[SerialReader] Tara aplicada: {self.tara_offsets}")
            return dict(self.tara_offsets)

    def restablecer_tara(self):
        """Limpia los offsets basales regresando a la medición absoluta."""
        with self._lock:
            self.tara_offsets = {var: 0.0 for var in VARIABLES_CLINICAS}
            self.tarado_completado = False

    def _loop_lectura(self):
        """Lee bytes y encola líneas sin ejecutar filtros ni análisis en este hilo."""
        buffer_bytes = bytearray()

        try:
            while self._corriendo and self.serial_conn and self.serial_conn.is_open:
                bytes_espera = max(self.serial_conn.in_waiting, 1)
                chunk = self.serial_conn.read(min(bytes_espera, SERIAL_BUFFER_SIZE))
                if not chunk:
                    continue

                buffer_bytes.extend(chunk)
                while b'\n' in buffer_bytes:
                    linea, buffer_bytes = buffer_bytes.split(b'\n', 1)
                    linea_str = linea.decode('utf-8', errors='ignore').strip()
                    if not linea_str:
                        continue

                    ahora = time.perf_counter()
                    with self._lock:
                        self.lineas_uart_recibidas += 1
                        self._tasa_rx_conteo += 1
                        dt_rx = ahora - self._tasa_rx_inicio
                        if dt_rx >= 0.5:
                            self.frecuencia_recepcion_hz = self._tasa_rx_conteo / dt_rx
                            self.frecuencia_hz = self.frecuencia_recepcion_hz
                            self._tasa_rx_conteo = 0
                            self._tasa_rx_inicio = ahora

                    cola = self._cola_procesamiento
                    if cola is None:
                        continue
                    try:
                        cola.put_nowait(linea_str)
                    except queue.Full:
                        with self._lock:
                            self.lineas_descartadas_cola += 1
        except serial.SerialException:
            print("[SerialReader] Excepción de hardware en puerto serial.")
        except Exception as e:
            print(f"[SerialReader] Error de lectura serial: {e}")
        finally:
            self._corriendo = False

    def _loop_procesamiento(self):
        """Consume la cola FIFO y procesa cada línea fuera del hilo serial."""
        cola = self._cola_procesamiento
        if cola is None:
            return

        while self._corriendo or not cola.empty():
            try:
                linea = cola.get(timeout=0.05)
            except queue.Empty:
                continue
            try:
                self._procesar_linea(linea)
            except Exception as error:
                print(f"[SerialReader] Error procesando una trama: {error}")
            finally:
                cola.task_done()

    @staticmethod
    def _delta_uint32(actual: int, anterior: int) -> int:
        return (actual - anterior) & 0xFFFFFFFF

    def _registrar_tiempo_fuente(self, seq_num: int, ts_hw_ms: int) -> float:
        """Actualiza pérdidas y tasa del firmware usando secuencia y millis()."""
        with self._lock:
            if self._t0_hw_ms is None:
                self._t0_hw_ms = ts_hw_ms

            if self.ultimo_seq is not None and self._ultimo_ts_hw_ms is not None:
                delta_seq = self._delta_uint32(seq_num, self.ultimo_seq)
                delta_ms = self._delta_uint32(ts_hw_ms, self._ultimo_ts_hw_ms)

                if 0 < delta_seq < 0x80000000:
                    self.tramas_perdidas += max(0, delta_seq - 1)
                    if 0 < delta_ms < 0x80000000:
                        self._seq_ventana_hw += delta_seq
                        self._ms_ventana_hw += delta_ms
                        if self._ms_ventana_hw >= 500:
                            self.frecuencia_arduino_hz = (
                                self._seq_ventana_hw * 1000.0 / self._ms_ventana_hw
                            )
                            self._seq_ventana_hw = 0
                            self._ms_ventana_hw = 0
                else:
                    self._t0_hw_ms = ts_hw_ms
                    self._seq_ventana_hw = 0
                    self._ms_ventana_hw = 0

            self.ultimo_seq = seq_num
            self._ultimo_ts_hw_ms = ts_hw_ms
            tiempo_relativo = (
                self._delta_uint32(ts_hw_ms, self._t0_hw_ms) / 1000.0
                if self._t0_hw_ms is not None
                else 0.0
            )
            return tiempo_relativo

    def _actualizar_tasa_procesamiento(self, ahora: float):
        with self._lock:
            self._tasa_proc_conteo += 1
            dt = ahora - self._tasa_proc_inicio
            if dt >= 0.5:
                self.frecuencia_procesamiento_hz = self._tasa_proc_conteo / dt
                self._tasa_proc_conteo = 0
                self._tasa_proc_inicio = ahora

    def _procesar_linea(self, linea: str):
        """
        Parsea líneas seriales soportando:
        1. Formato de diez campos con auditoría I2C y de secuencia.
        2. Formatos legados de ocho, seis o tres campos.
        Aplica mapeo al eje articular activo (Pitch por defecto), tara y filtrado dual.
        """
        partes = [p.strip() for p in linea.split(',')]
        seq_num: Optional[int] = None
        ts_hw: Optional[int] = None
        mascara_validez = 0x07
        errores_i2c_hw: Optional[int] = None
        formato_mpu_actual = False

        if len(partes) >= 10:
            try:
                seq_num = int(partes[0])
                ts_hw = int(partes[1])
                mascara_validez = int(partes[2])
                errores_i2c_hw = int(partes[3])
                r1, p1 = float(partes[4]), float(partes[5])
                r2, p2 = float(partes[6]), float(partes[7])
                r3, p3 = float(partes[8]), float(partes[9])
                formato_mpu_actual = True
            except ValueError:
                with self._lock:
                    self.lineas_malformadas += 1
                return
        elif len(partes) >= 8:
            try:
                seq_num = int(partes[0])
                ts_hw = int(partes[1])
                r1, p1 = float(partes[2]), float(partes[3])
                r2, p2 = float(partes[4]), float(partes[5])
                r3, p3 = float(partes[6]), float(partes[7])
            except ValueError:
                with self._lock:
                    self.lineas_malformadas += 1
                return
        elif len(partes) >= 6:
            try:
                r1, p1 = float(partes[0]), float(partes[1])
                r2, p2 = float(partes[2]), float(partes[3])
                r3, p3 = float(partes[4]), float(partes[5])
            except ValueError:
                with self._lock:
                    self.lineas_malformadas += 1
                return
        elif len(partes) >= 3:
            try:
                s1_raw, s2_raw, s3_raw = (float(partes[0]), float(partes[1]), float(partes[2]))
            except ValueError:
                with self._lock:
                    self.lineas_malformadas += 1
                return
            rolls = [0.0, 0.0, 0.0]
            pitches = [s1_raw, s2_raw, s3_raw]
        else:
            with self._lock:
                self.lineas_malformadas += 1
            return

        if len(partes) >= 6:
            # Mapeo físico oficial:
            # Sensor 1 (Pines 15 y 16) = Hombro (r1, p1) -> Canal 0 [Hombro]
            # Sensor 2 (Pines 4 y 5)   = Codo (r2, p2)   -> Canal 1 [Codo]
            # Sensor 3 (Pines 4 y 5)   = Muñeca (r3, p3) -> Canal 2 [Muñeca]
            rolls = [r1, r2, r3]
            pitches = [p1, p2, p3]
            if self.eje_articular.lower() == "pitch":
                s1_raw, s2_raw, s3_raw = pitches
            else:
                s1_raw, s2_raw, s3_raw = rolls

        tiempo_fuente = None
        if seq_num is not None and ts_hw is not None:
            tiempo_fuente = self._registrar_tiempo_fuente(seq_num, ts_hw)

        with self._lock:
            self.total_tramas_recibidas += 1
            if errores_i2c_hw is not None:
                self.errores_i2c_firmware = errores_i2c_hw
            if mascara_validez != 0x07:
                self.tramas_invalidas_i2c += 1
                return

        if not all(math.isfinite(value) for value in (s1_raw, s2_raw, s3_raw)):
            with self._lock:
                self.lineas_malformadas += 1
            return

        with self._lock:
            self.muestras_validas += 1

        t_ahora = time.perf_counter()
        t_host_rel = t_ahora - self.t0 if self.t0 else 0.0
        t_rel = tiempo_fuente if tiempo_fuente is not None else t_host_rel

        with self._lock:
            cst = [s1_raw, s2_raw, s3_raw]
            ct = [
                s1_raw - self.tara_offsets["hombro"],
                s2_raw - self.tara_offsets["codo"],
                s3_raw - self.tara_offsets["muneca"]
            ]

            fst = []
            ft = []
            for nombre, valor, valor_tarado in zip(VARIABLES_CLINICAS, cst, ct):
                filtrado_sin_tara = self.filtros_sin_tara[nombre].actualizar(valor)
                filtrado_tarado = self.filtros_tarados[nombre].actualizar(valor_tarado)
                fst.append(valor if filtrado_sin_tara is None else filtrado_sin_tara)
                ft.append(valor_tarado if filtrado_tarado is None else filtrado_tarado)

            frame = {
                "tiempo": t_rel,
                "tiempo_host": t_host_rel,
                "seq": seq_num,
                "ts_hw_ms": ts_hw,
                "mascara_validez": mascara_validez,
                "tramas_perdidas": self.tramas_perdidas,
                "total_tramas": self.total_tramas_recibidas,
                "lineas_uart_recibidas": self.lineas_uart_recibidas,
                "lineas_malformadas": self.lineas_malformadas,
                "lineas_descartadas_cola": self.lineas_descartadas_cola,
                "cola_pendiente": self._cola_procesamiento.qsize() if self._cola_procesamiento else 0,
                "muestras_entregadas_analisis": self.muestras_entregadas_analisis,
                "errores_callback": self.errores_callback,
                "muestras_validas": self.muestras_validas,
                "tramas_invalidas_i2c": self.tramas_invalidas_i2c,
                "errores_i2c_firmware": self.errores_i2c_firmware,
                "frecuencia_arduino_hz": self.frecuencia_arduino_hz,
                "frecuencia_recepcion_hz": self.frecuencia_recepcion_hz,
                "frecuencia_procesamiento_hz": self.frecuencia_procesamiento_hz,
                "crudos_sin_tara": cst,
                "crudos_tarados": ct,
                "filtrados_sin_tara": fst,
                "filtrados_tarados": ft,
                "roll_crudo": rolls,
                "pitch_crudo": pitches
            }
            self.ultimo_frame = frame
            self.buffer_historial.append((t_rel, ft[0], ft[1], ft[2]))

        if self.callback_muestra:
            with self._lock:
                self.muestras_entregadas_analisis += 1
                frame["muestras_entregadas_analisis"] = self.muestras_entregadas_analisis
                frame["errores_callback"] = self.errores_callback
            try:
                self.callback_muestra(frame)
            except Exception:
                with self._lock:
                    self.errores_callback += 1
                    frame["errores_callback"] = self.errores_callback
            finally:
                self._actualizar_tasa_procesamiento(time.perf_counter())
                frame["frecuencia_procesamiento_hz"] = self.frecuencia_procesamiento_hz

    def obtener_metricas(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "frecuencia_arduino_hz": self.frecuencia_arduino_hz,
                "frecuencia_recepcion_hz": self.frecuencia_recepcion_hz,
                "frecuencia_procesamiento_hz": self.frecuencia_procesamiento_hz,
                "lineas_uart_recibidas": self.lineas_uart_recibidas,
                "lineas_malformadas": self.lineas_malformadas,
                "lineas_descartadas_cola": self.lineas_descartadas_cola,
                "total_tramas_recibidas": self.total_tramas_recibidas,
                "muestras_validas": self.muestras_validas,
                "tramas_invalidas_i2c": self.tramas_invalidas_i2c,
                "tramas_perdidas": self.tramas_perdidas,
                "errores_i2c_firmware": self.errores_i2c_firmware,
                "muestras_entregadas_analisis": self.muestras_entregadas_analisis,
                "errores_callback": self.errores_callback,
                "cola_pendiente": self._cola_procesamiento.qsize() if self._cola_procesamiento else 0
            }

    def obtener_instantanea_angular(self) -> Tuple[float, float, float]:
        """Devuelve los últimos ángulos filtrados y tarados (Hombro, Codo, Muñeca)."""
        with self._lock:
            ft = self.ultimo_frame["filtrados_tarados"]
            return ft[0], ft[1], ft[2]

    def obtener_ventana_grafica(self) -> Tuple[List[float], List[float], List[float], List[float]]:
        """Devuelve listas de tiempo, hombro, codo y muñeca para el plot en tiempo real."""
        with self._lock:
            if not self.buffer_historial:
                return [], [], [], []
            datos = list(self.buffer_historial)
            t = [d[0] for d in datos]
            s1 = [d[1] for d in datos]
            s2 = [d[2] for d in datos]
            s3 = [d[3] for d in datos]
            return t, s1, s2, s3
