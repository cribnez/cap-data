"""
filters.py - Filtro de Suavizado con Mediana Móvil y Kalman Adaptativo
"""
from __future__ import annotations
from collections import deque
from typing import Dict, Optional
import numpy as np

from Cap_Data.config import FILTRO_CONFIG, VARIABLES_CLINICAS


class FiltroKalmanAdaptativo:
    """
    Filtro secuencial de dos etapas:
    1. Mediana móvil para eliminación de outliers / picos espurios.
    2. Filtro de Kalman con covarianza de proceso adaptable (Q_MOV vs Q_QUIETO).
    """
    VENTANA_MED = FILTRO_CONFIG["VENTANA_MED"]
    Q_QUIETO = FILTRO_CONFIG["Q_QUIETO"]
    Q_MOVIMIENTO = FILTRO_CONFIG["Q_MOVIMIENTO"]
    R = FILTRO_CONFIG["R"]
    UMBRAL_MOV = FILTRO_CONFIG["UMBRAL_MOV"]

    def __init__(self):
        self._buf = deque(maxlen=self.VENTANA_MED)
        self._x: Optional[float] = None
        self._p: float = 1.0

    def actualizar(self, medicion: Optional[float]) -> Optional[float]:
        """Procesa una nueva medición angular y devuelve el valor óptimo estimado."""
        # Rechazar datos nulos (None), Not a Number (NaN) o infinitos
        if medicion is None or not np.isfinite(medicion):
            return self._x

        self._buf.append(medicion)
        med = float(np.median(self._buf))

        if self._x is None or not np.isfinite(self._x):
            # Primer valor válido detectado
            self._x = med
            self._p = 1.0
            return self._x

        # Ajustar la covarianza del proceso (Q) según la tasa de cambio angular
        q = self.Q_MOVIMIENTO if abs(med - self._x) > self.UMBRAL_MOV else self.Q_QUIETO
        self._p = self._p + q
        k = self._p / (self._p + self.R)
        self._x = self._x + k * (med - self._x)
        self._p = (1.0 - k) * self._p
       
        return self._x

    def reset(self):
        """Reinicia por completo el filtro y buffer."""
        self._buf.clear()
        self._x = None
        self._p = 1.0

    def reset_buffer_mediana(self):
        """Limpia el buffer de mediana preservando el último estado estimado."""
        self._buf.clear()
        self._p = 1.0


def crear_filtros_variables() -> Dict[str, FiltroKalmanAdaptativo]:
    """Crea un diccionario con un filtro independiente para cada articulación."""
    return {var: FiltroKalmanAdaptativo() for var in VARIABLES_CLINICAS}
