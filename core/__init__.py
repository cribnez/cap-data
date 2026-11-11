"""
Paquete core de adquisición, filtrado y segmentación cinemática
"""
from Cap_Data.core.filters import FiltroKalmanAdaptativo, crear_filtros_variables
from Cap_Data.core.serial_reader import SerialReader
from Cap_Data.core.segmenter import RepetitionSegmenter

__all__ = ["FiltroKalmanAdaptativo", "crear_filtros_variables", "SerialReader", "RepetitionSegmenter"]
