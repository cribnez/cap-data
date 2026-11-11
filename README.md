# Cap_Data — Suite Modular de Captura Biomecánica y Persistencia en MongoDB (ROMDB)

Cap_Data adquiere por Bluetooth Serial (SPP bajo el identificador `"Goniometro"`) o USB las tramas transmitidas por el microcontrolador (ESP32/Arduino), las almacena en una cola FIFO acotada multihilo para desacoplar la ingestión UART del análisis, aplica filtrado digital dual (Mediana Móvil + Filtro de Kalman Adaptativo), calibra la postura basal mediante tara física ($0^\circ$), segmenta automáticamente repeticiones articulares por ciclo de movimiento y retorno a reposo, y almacena en disco 4 matrices de señal (`rep_X.npz`) más un archivo de auditoría forense (`rep_X.audit.json`) junto con la persistencia en **MongoDB (`ROMDB`)**.

La aplicación incluye un explorador cinemático articular 3D con selección multiserie independiente y tres esquemas de coloración dinámica, un historial clínico con eliminación completa de sesiones y métricas separadas de excursión pico a pico frente a desviación máxima.

---

## 1. Mapeo Físico y Protocolo de Transmisión

### Mapeo Anatómico de los Sensores
| Sensor MPU-6050 | Conexión Física (ESP32) | Articulación Biomecánica | Canal Articular en Python | Eje Articular |
| :--- | :--- | :--- | :--- | :--- |
| **MPU1 (Sensor 1)** | **Bus I²C 1 (SDA 15, SCL 16)** | **Hombro** | Canal 0 (`hombro`) | Pitch ($\arctan 2(A_z, A_y)$) |
| **MPU2 (Sensor 2)** | **Bus I²C 0 (SDA 4, SCL 5, AD0=3.3V)** | **Codo** | Canal 1 (`codo`) | Pitch ($\arctan 2(A_z, A_y)$) |
| **MPU3 (Sensor 3)** | **Bus I²C 0 (SDA 4, SCL 5, AD0=GND)** | **Muñeca** | Canal 2 (`muneca`) | Pitch ($\arctan 2(A_z, A_y)$) |

> [!NOTE]
> Orientación del sensor: Pines AD0 e INT orientados hacia el suelo. El movimiento de flexión en el plano sagital rota entre los ejes gravitatorios Y y Z, registrado con fidelidad directa por el ángulo de **Pitch**.

### Protocolo de Trama Serial (10 Campos CSV)
```
seq,ts_ms,valid_mask,i2c_errors,roll1,pitch1,roll2,pitch2,roll3,pitch3
```
- `seq`: Contador consecutivo de trama ($0$ a $4\,294\,967\,295$) para detectar pérdida de paquetes.
- `ts_ms`: Marca de tiempo en milisegundos desde el arranque de Arduino (`millis()`).
- `valid_mask`: Máscara de bits de validez de lectura I²C (`0x01`=Hombro/MPU1, `0x02`=Codo/MPU2, `0x04`=Muñeca/MPU3; `0x07`=Todos OK).
- `i2c_errors`: Contador acumulado de fallos en el bus I²C.
- `roll1, pitch1`: Lecturas de Hombro (MPU1 - Sensor 1).
- `roll2, pitch2`: Lecturas de Codo (MPU2 - Sensor 2).
- `roll3, pitch3`: Lecturas de Muñeca (MPU3 - Sensor 3).

---

## 2. Estructura del Software

```
Cap_Data/
├── main.py                     # Punto de entrada de la aplicación
├── config.py                   # Configuración central (MongoDB, paleta de colores, umbrales)
├── README.md                   # Documentación técnica completa
├── arduino/
│   └── arduino.ino             # Firmware ESP32/Arduino (Bluetooth SPP + 10 campos CSV)
├── core/                       # Núcleo de adquisición y procesamiento de señal
│   ├── __init__.py
│   ├── filters.py              # FiltroKalmanAdaptativo + Filtro de Mediana
│   ├── serial_reader.py        # Ingestor multihilo con cola FIFO y métricas triples de frecuencia
│   └── segmenter.py            # Máquina de estados para segmentación automática y auditoría
├── database/                   # Capa de almacenamiento y persistencia
│   ├── __init__.py
│   ├── mongo_manager.py        # Gestor de conexiones y CRUD con MongoDB (ROMDB)
│   └── storage_manager.py      # Gestor de directorios locales, NPZ, auditorías JSON y metadata
├── ui/                         # Interfaz gráfica moderna en CustomTkinter
│   ├── __init__.py
│   ├── app_window.py           # Ventana maestra y coordinador de navegación (SPA)
│   ├── view_login.py           # Ventana 1: Split-Card Hero con acceso directo a Historial y 3D
│   ├── view_capture.py         # Ventana 2: Captura en tiempo real, tara estricta y panel diagnóstico
│   ├── view_3d.py              # Ventana 3: Dispersión 3D multiserie y modos de coloración
│   └── view_history.py         # Ventana 4: Historial clínico, recaptura y borrado completo
└── storage/                    # Repositorio local de archivos .npz, .audit.json y metadata.json
    └── V_{voluntario_id}/
        └── {sesion_id}_{ejercicio}/
            ├── metadata.json
            ├── rep_1.npz
            ├── rep_1.audit.json
            └── ...
```

---

## 3. Puesta en Marcha

### Requisitos Previos:
- Python 3.8 o superior.
- Servicio de MongoDB activo en `localhost:27017` (Base de datos: `ROMDB`).
- Dependencias instaladas:
  ```bash
  pip install pyserial customtkinter matplotlib numpy pymongo
  ```

### Ejecución:
Desde el directorio del proyecto:
```bash
python Cap_Data/main.py
```

---

## 4. Descripción de las 4 Vistas

### Ventana 1: Inicio de Sesión y Registro (`view_login.py`)
- **Diseño Split-Card Hero**: Panel visual izquierdo con especificaciones del protocolo e ilustración tecnológica; panel derecho espacioso con formulario ergonómico sin barras de desplazamiento innecesarias.
- **Validación Limpia**: No crea sesiones vacías en MongoDB ni en disco hasta que el voluntario registre efectivamente su primera repetición válida.
- **Navegación Inmediata**: Botones directos para inspeccionar el `Historial Clínico` o el `Explorador 3D` sin requerir iniciar una nueva sesión de captura.

### Ventana 2: Captura y Segmentación (`view_capture.py`)
- **Desacoplamiento Total de Frecuencia**: El hilo de lectura serial ingresa tramas a una cola FIFO (`maxsize=10000`). El hilo de procesamiento consume el 100% de las muestras y alimenta al segmentador. La interfaz gráfica se refresca a 30 FPS (`33 ms`) sin bloquear ni perder muestras de hardware.
- **Panel Diagnóstico de Tasa y Calidad**: Muestra simultáneamente:
  - Frecuencia de envío Arduino (`millis()`)
  - Frecuencia de recepción UART en el host
  - Frecuencia de procesamiento de señales
  - Conteo de tramas recibidas, válidas, saltos de secuencia (`packet loss`) y fallos I²C.
- **Regla Estricta de Tara**: "Iniciar Captura" permanece inhabilitado hasta que se ejecute la tara física en postura basal ($0^\circ$).
- **Segmentación Temporal**:
  1. *Reposo*: Espera superación del umbral articular ($>12^\circ$).
  2. *En Movimiento*: Acumula datos y rastrea picos de flexión.
  3. *Retorno a Reposo*: Al descender a $<6^\circ$ durante $350\text{ ms}$, valida la repetición y descuenta el tiempo de confirmación estática para una duración biomecánica exacta.

### Ventana 3: Explorador Cinemático 3D (`view_3d.py`)
- **Ejes Espaciales Articulares**:
  - $X$: Hombro (MPU3 Pitch)
  - $Y$: Codo (MPU2 Pitch)
  - $Z$: Muñeca (MPU1 Pitch)
- **Selección Multiserie Libre e Ilimitada**: Permite seleccionar mediante casillas de verificación cualquier repetición de cualquier voluntario y cualquier sesión, permitiendo comparaciones directas (ej. Repetición 1 de Voluntario A contra Repetición 1 de Voluntario B).
- **Modos de Coloración Dinámica**:
  - *Por Repetición*: Colores contrastantes individuales para cada ciclo de movimiento.
  - *Por Ejercicio*: Paleta coordinada por tipo de movimiento.
  - *Por Voluntario*: Permite aislar y contrastar visualmente el patrón motor entre diferentes sujetos.

### Ventana 4: Historial Clínico y Gestión de Datos (`view_history.py`)
- **Métricas Biomecánicas Estrictas**:
  - **Excursión pico a pico (PTP)**: $\max(x) - \min(x)$, recorrido completo de la señal durante la repetición.
  - **Desviación máxima absoluta**: $\max(|x|)$, desplazamiento pico respecto al cero tarado.
  - Formato seguro con indicador `"N/D"` para registros históricos que carezcan de cálculo PTP.
- **Eliminación Completa de Sesión**: Opción con confirmación de seguridad para purgar sesiones erróneas o de calibración tanto de MongoDB (`ROMDB`) como de los directorios de almacenamiento en disco.
- **Recaptura Asistida**: Permite sustituir una repetición puntual sin alterar el resto de la sesión.
