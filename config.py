"""
config.py - Configuración central de la suite biomecánica Cap_Data
Estilo visual: Light Tech Biomecánico
"""
from __future__ import annotations
import os
from pathlib import Path

# Directorios base
BASE_DIR = Path(__file__).resolve().parent
STORAGE_DIR = BASE_DIR / "storage"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

# MongoDB Configuration
MONGO_HOST = "localhost"
MONGO_PORT = 27017
MONGO_DB_NAME = "ROMDB"
MONGO_URI = f"mongodb://{MONGO_HOST}:{MONGO_PORT}/"

# Colecciones de MongoDB
COLL_VOLUNTARIOS = "voluntarios"
COLL_SESIONES = "sesiones"
COLL_REPETICIONES = "repeticiones"

# Configuración de Sensores y Canales (MPU1=Hombro, MPU2=Codo, MPU3=Muñeca)
VARIABLES_CLINICAS = ["hombro", "codo", "muneca"]
ETIQUETAS_SENSORES = {
    "hombro": "Hombro (MPU1)",
    "codo": "Codo (MPU2)",
    "muneca": "Muñeca (MPU3)"
}

# Paleta de Colores Cinemática (Light Tech Clean Theme)
COLORES = {
    "bg_main": "#F4F7FB",            # Grisáceo tecnológico ultra-limpio
    "bg_card": "#FFFFFF",            # Blanco puro
    "bg_card_secondary": "#F8FAFC",  # Pizarra clarísimo
    "border": "#E2E8F0",            # Borde sutil
    "border_focus": "#CBD5E1",
    "text_primary": "#0F172A",       # Pizarra profundo
    "text_secondary": "#475569",     # Pizarra medio
    "text_muted": "#94A3B8",         # Gris tenue
    
    # Canales articulares
    "hombro": "#0284C7",             # Azul Eléctrico (MPU1 - Hombro)
    "codo": "#10B981",               # Verde Esmeralda (MPU2 - Codo)
    "muneca": "#F59E0B",             # Ámbar Cálido (MPU3 - Muñeca)
    
    # Estados y acentos
    "accent_primary": "#059669",     # Verde esmeralda para Iniciar
    "accent_hover": "#047857",
    "accent_blue": "#0284C7",        # Azul acción
    "accent_blue_hover": "#0369A1",
    "accent_purple": "#7C3AED",
    "danger": "#EF4444",             # Rojo alerta
    "danger_hover": "#DC2626",
    "warning": "#F59E0B",            # Ámbar alerta
    "info": "#0284C7"
}

# Ejercicios clínicos oficiales
EJERCICIOS_DISPONIBLES = [
    "Flexo-Extension del codo",
    "Abduccion del hombro",
    "Flexion del hombro"
]

# Paleta para Ejercicios
COLORES_EJERCICIOS = {
    "Flexo-Extension del codo": "#0284C7", # Azul
    "Abduccion del hombro": "#10B981",     # Verde esmeralda
    "Flexion del hombro": "#F59E0B"        # Ámbar naranja
}

# Paleta distintiva para voluntarios (para comparaciones multiseries en 3D)
COLORES_VOLUNTARIOS = [
    "#0284C7", "#10B981", "#F59E0B", "#8B5CF6", "#EC4899",
    "#06B6D4", "#F97316", "#84CC16", "#6366F1", "#14B8A6"
]

# Nombres de cajones NPZ (Exactos según requerimiento)
CAJON_FILTRADOS_TARADOS = "filtrados_tarados"
CAJON_FILTRADOS_SIN_TARA = "filtrados_sin_tara"
CAJON_CRUDOS_TARADOS = "crudos_tarados"
CAJON_CRUDOS_SIN_TARA = "crudos_sin_tara"

LISTA_CAJONES_NPZ = [
    CAJON_FILTRADOS_TARADOS,
    CAJON_FILTRADOS_SIN_TARA,
    CAJON_CRUDOS_TARADOS,
    CAJON_CRUDOS_SIN_TARA
]

NOMBRES_LEGIBLES_CAJONES = {
    CAJON_FILTRADOS_TARADOS: "Datos con filtro y tarados (Default)",
    CAJON_FILTRADOS_SIN_TARA: "Datos con filtro sin tara",
    CAJON_CRUDOS_TARADOS: "Datos crudos y tarados",
    CAJON_CRUDOS_SIN_TARA: "Datos crudos y sin tarar"
}

# Parámetros del Filtro Kalman Adaptativo y Mediana
FILTRO_CONFIG = {
    "VENTANA_MED": 5,
    "Q_QUIETO": 0.05,
    "Q_MOVIMIENTO": 3.5,
    "R": 6.0,
    "UMBRAL_MOV": 4.0
}

# Parámetros del Segmentador Automático de Repeticiones
SEGMENTADOR_CONFIG = {
    "UMBRAL_INICIO_MOV": 12.0,            # Grados mínimos para considerar despegue
    "UMBRAL_RETORNO_REPOSO": 6.0,         # Grados máximos para considerar retorno a posición basal
    "TIEMPO_CONFIRMACION_REPOSO_S": 0.35, # Segundos en reposo para sellar la repetición
    "DURACION_MINIMA_REP_S": 0.8,         # Duración mínima de repetición
    "MAX_DURACION_REP_S": 15.0            # Límite superior por seguridad
}

# Baudrate inicial para abrir el puerto COM/serial virtual; no fija el muestreo Bluetooth
SERIAL_DEFAULT_BAUDRATE = 230400
BAUDRATES_DISPONIBLES = ["230400", "115200", "57600", "9600"]
SERIAL_TIMEOUT = 0.05
SERIAL_BUFFER_SIZE = 4096

# Eje articular: Se utiliza estrictamente PITCH para todos los sensores
EJE_ARTICULAR_DEFECTO = "pitch"

# Opciones por defecto de la interfaz
BRAZOS_DISPONIBLES = ["Derecho", "Izquierdo"]
REPS_OBJETIVO_DEFAULT = 5
