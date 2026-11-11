#include <Wire.h>
#include <math.h> 

// =======================================================
// CONFIGURACIÓN DE CONECTIVIDAD: BLUETOOTH / USB SERIAL
// =======================================================
// Si la placa seleccionada en el IDE de Arduino soporta Bluetooth Classic
// (como el ESP32 estándar / ESP32 Dev Module con Bluedroid activo),
// se habilita la transmisión inalámbrica con nombre "Goniometro".
// Si la placa es ESP32-S2, ESP32-S3, ESP32-C3 o se compila sin Bluetooth,
// se desactiva limpiamente sin dar error y transmite por cable USB (Serial).
#if defined(CONFIG_BT_ENABLED) && defined(CONFIG_BLUEDROID_ENABLED)
  #define TIENE_BLUETOOTH 1
  #include "BluetoothSerial.h"
  BluetoothSerial SerialBT;
#else
  #define TIENE_BLUETOOTH 0
#endif

// =======================================================
// CONFIGURACIÓN DE PINES I2C (ESP32)
// =======================================================
// Bus I2C 1 (Sensor 1: Hombro)
#define SDA_1 15
#define SCL_1 16

// Bus I2C 0 (Sensor 2: Codo, Sensor 3: Muñeca)
#define SDA_0 4
#define SCL_0 5

// Mapeo físico oficial: MPU1 = Hombro, MPU2 = Codo, MPU3 = Muñeca
const int MPU_1_ADDR = 0x68; // Hombro (AD0 a GND en Bus 1: Pines 15 y 16)
const int MPU_2_ADDR = 0x69; // Codo (AD0 a 3.3V en Bus 0: Pines 4 y 5)
const int MPU_3_ADDR = 0x68; // Muñeca (AD0 a GND en Bus 0: Pines 4 y 5)

float roll1, pitch1, roll2, pitch2, roll3, pitch3;
unsigned long contadorSecuencia = 0;
unsigned long contadorErroresI2C = 0;

// =======================================================
// INICIALIZACIÓN OPTIMIZADA DEL SENSOR MPU6050
// =======================================================
void iniciarSensor(TwoWire &puertoI2C, int direccion) {
  puertoI2C.beginTransmission(direccion);
  puertoI2C.write(0x6B); // Registro PWR_MGMT_1
  puertoI2C.write(0x00); // Despertar sensor
  puertoI2C.endTransmission();

  // Activar Filtro Pasa Bajas Digital (DLPF nivel 3 para reducir ruido)
  puertoI2C.beginTransmission(direccion);
  puertoI2C.write(0x1A);
  puertoI2C.write(0x03); 
  puertoI2C.endTransmission();
}

// =======================================================
// LECTURA VECTORIZADA CON ORIENTACIÓN VERTICAL CORREGIDA
// =======================================================
// Sensor vertical apoyado sobre pines AD0/INT (Eje Y apuntando verticalmente al techo,
// Eje X lateral horizontal, Eje Z perpendicular al frente).
bool obtenerAngulos(TwoWire &puertoI2C, int direccion, float &roll, float &pitch) {
  puertoI2C.beginTransmission(direccion);
  puertoI2C.write(0x3B); 
  if (puertoI2C.endTransmission(false) != 0) {
    return false;
  }
  
  if (puertoI2C.requestFrom(direccion, 6, true) != 6) {
    return false;
  }

  int16_t AcX = puertoI2C.read() << 8 | puertoI2C.read();
  int16_t AcY = puertoI2C.read() << 8 | puertoI2C.read();
  int16_t AcZ = puertoI2C.read() << 8 | puertoI2C.read();

  float ax_g = AcX / 16384.0;
  float ay_g = AcY / 16384.0;
  float az_g = AcZ / 16384.0;

  // FÓRMULAS CORREGIDAS PARA SENSOR VERTICAL (Gravedad en Eje Y en reposo)
  // 1. Inclinación Frontal (Flexión/Extensión Articular -> Pitch)
  pitch = atan2(az_g, ay_g) * (180.0 / PI);

  // 2. Inclinación Lateral (Alabeo / Abducción -> Roll)
  roll = atan2(-ax_g, sqrt(az_g * az_g + ay_g * ay_g)) * (180.0 / PI);

  return true;
}

void setup() {
  Serial.begin(230400); // Comunicación serial USB (Sincronizado con Python Cap_Data a 230400 bps)
  
  // Espera de enumeración USB CDC para placas ESP32-S3 (máximo 1.5s)
  unsigned long tInicioSerial = millis();
  while (!Serial && (millis() - tInicioSerial < 1500));
  delay(200);

  Serial.println("[ESP32-S3] Iniciando Goniometro 3x MPU-6050...");

#if TIENE_BLUETOOTH
  SerialBT.begin("Goniometro"); // Nombre Bluetooth Classic SPP visible
  Serial.println("[ESP32] Bluetooth Serial iniciado con exito: 'Goniometro'");
#else
  Serial.println("[ESP32] Modo USB Serial activo (Para usar Bluetooth, selecciona placa 'ESP32 Dev Module' en Arduino IDE)");
#endif

  pinMode(SDA_0, INPUT_PULLUP);
  pinMode(SCL_0, INPUT_PULLUP);
  pinMode(SDA_1, INPUT_PULLUP);
  pinMode(SCL_1, INPUT_PULLUP);

  // Modo rápido I2C (400 kHz)
  Wire.begin(SDA_0, SCL_0, 400000);   
  Wire1.begin(SDA_1, SCL_1, 400000);  

  iniciarSensor(Wire1, MPU_1_ADDR); // Hombro (Sensor 1 en Bus 1: Pines 15 y 16)
  iniciarSensor(Wire, MPU_2_ADDR);  // Codo (Sensor 2 en Bus 0: Pines 4 y 5)
  iniciarSensor(Wire, MPU_3_ADDR);  // Muñeca (Sensor 3 en Bus 0: Pines 4 y 5)

  Serial.println("[ESP32] Sensores I2C iniciados. Transmitiendo...");
}

void loop() {
  contadorSecuencia++;
  unsigned long timestampHardwareMs = millis();
  uint8_t mascaraValidez = 0;

  // 1. Lectura Sensor 1 (Hombro - Bus 1) -> Bit 0 (0x01)
  if (obtenerAngulos(Wire1, MPU_1_ADDR, roll1, pitch1)) {
    mascaraValidez |= 0x01;
  } else {
    contadorErroresI2C++;
  }

  // 2. Lectura Sensor 2 (Codo - Bus 0) -> Bit 1 (0x02)
  if (obtenerAngulos(Wire, MPU_2_ADDR, roll2, pitch2)) {
    mascaraValidez |= 0x02;
  } else {
    contadorErroresI2C++;
  }

  // 3. Lectura Sensor 3 (Muñeca - Bus 0) -> Bit 2 (0x04)
  if (obtenerAngulos(Wire, MPU_3_ADDR, roll3, pitch3)) {
    mascaraValidez |= 0x04;
  } else {
    contadorErroresI2C++;
  }

  // Trama oficial de 10 campos a ~100 Hz:
  // seq,timestamp_ms,valid_mask,i2c_errors_total,roll1,pitch1,roll2,pitch2,roll3,pitch3
  // Mapeo: MPU1=Hombro, MPU2=Codo, MPU3=Muñeca
  String trama = String(contadorSecuencia) + "," +
                 String(timestampHardwareMs) + "," +
                 String(mascaraValidez) + "," +
                 String(contadorErroresI2C) + "," +
                 String(roll1, 2) + "," + String(pitch1, 2) + "," +
                 String(roll2, 2) + "," + String(pitch2, 2) + "," +
                 String(roll3, 2) + "," + String(pitch3, 2);

  // Transmisión inalámbrica por Bluetooth Serial (si la placa lo soporta)
#if TIENE_BLUETOOTH
  SerialBT.println(trama);
#endif

  // Transmisión directa por USB Serial (funciona siempre en cualquier placa)
  Serial.println(trama);

  // Muestreo controlado a ~100 Hz (10 ms)
  delay(10); 
}
