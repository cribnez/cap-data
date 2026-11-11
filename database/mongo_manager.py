"""
mongo_manager.py - Gestor de persistencia en MongoDB (ROMDB)
"""
from __future__ import annotations
import datetime
from typing import Any, Dict, List, Optional
import pymongo
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

from Cap_Data.config import (
    MONGO_URI,
    MONGO_DB_NAME,
    COLL_VOLUNTARIOS,
    COLL_SESIONES,
    COLL_REPETICIONES
)


class MongoManager:
    """Administrador singleton de conexiones y operaciones CRUD con MongoDB."""
    
    _instance: Optional[MongoManager] = None
    
    def __new__(cls) -> MongoManager:
        if cls._instance is None:
            cls._instance = super(MongoManager, cls).__new__(cls)
            cls._instance._inicializado = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_inicializado", False):
            return
        self.client: Optional[pymongo.MongoClient] = None
        self.db: Optional[pymongo.database.Database] = None
        self._conectado: bool = False
        self._inicializado = True
        self.conectar()

    def conectar(self) -> bool:
        """Establece conexión con el servidor MongoDB en localhost:27017."""
        try:
            self.client = pymongo.MongoClient(
                MONGO_URI,
                serverSelectionTimeoutMS=2000,
                connectTimeoutMS=2000
            )
            # Forzar ping al servidor para validar conexión real
            self.client.admin.command('ping')
            self.db = self.client[MONGO_DB_NAME]
            self._crear_indices()
            self._conectado = True
            print(f"[MongoManager] Conectado exitosamente a MongoDB: '{MONGO_DB_NAME}'")
            return True
        except (ConnectionFailure, ServerSelectionTimeoutError, Exception) as e:
            self._conectado = False
            print(f"[MongoManager] Advertencia: No se pudo conectar a MongoDB ({e}).")
            return False

    def esta_conectado(self) -> bool:
        """Verifica si la conexión a MongoDB se encuentra activa."""
        if not self._conectado or self.client is None:
            return self.conectar()
        try:
            self.client.admin.command('ping')
            return True
        except Exception:
            self._conectado = False
            return False

    def _crear_indices(self):
        """Genera índices necesarios para consultas rápidas."""
        try:
            if self.db is not None:
                self.db[COLL_VOLUNTARIOS].create_index("voluntario_id", unique=True)
                self.db[COLL_SESIONES].create_index("sesion_id", unique=True)
                self.db[COLL_SESIONES].create_index("voluntario_id")
                self.db[COLL_REPETICIONES].create_index([("sesion_id", 1), ("num_rep", 1)], unique=True)
                self.db[COLL_REPETICIONES].create_index("voluntario_id")
                self.db[COLL_REPETICIONES].create_index("ejercicio")
        except Exception as e:
            print(f"[MongoManager] Error al crear índices: {e}")

    # ==========================================
    # GESTIÓN DE VOLUNTARIOS
    # ==========================================
    def registrar_o_actualizar_voluntario(self, voluntario_id: str, brazo_evaluado: str = "Derecho") -> bool:
        """Registra un nuevo voluntario o actualiza la fecha de su última actividad."""
        if not self.esta_conectado():
            return False
        try:
            now = datetime.datetime.now()
            col = self.db[COLL_VOLUNTARIOS]
            col.update_one(
                {"voluntario_id": voluntario_id.strip().upper()},
                {
                    "$setOnInsert": {
                        "voluntario_id": voluntario_id.strip().upper(),
                        "fecha_registro": now,
                        "brazo_defecto": brazo_evaluado
                    },
                    "$set": {"ultima_actividad": now},
                    "$inc": {"total_sesiones": 1}
                },
                upsert=True
            )
            return True
        except Exception as e:
            print(f"[MongoManager] Error al registrar voluntario: {e}")
            return False

    def obtener_voluntarios_ids(self) -> List[str]:
        """Devuelve la lista de IDs de voluntarios registrados para autocompletado."""
        if not self.esta_conectado():
            return []
        try:
            cursor = self.db[COLL_VOLUNTARIOS].find({}, {"voluntario_id": 1}).sort("voluntario_id", 1)
            return [doc["voluntario_id"] for doc in cursor if "voluntario_id" in doc]
        except Exception as e:
            print(f"[MongoManager] Error al obtener voluntarios: {e}")
            return []

    # ==========================================
    # GESTIÓN DE SESIONES
    # ==========================================
    def crear_sesion(self, datos_sesion: Dict[str, Any]) -> bool:
        """Inserta el documento maestro de una nueva sesión clínica."""
        if not self.esta_conectado():
            return False
        try:
            doc = {
                "sesion_id": datos_sesion["sesion_id"],
                "voluntario_id": datos_sesion["voluntario_id"].strip().upper(),
                "ejercicio": datos_sesion["ejercicio"],
                "brazo": datos_sesion["brazo"],
                "reps_objetivo": int(datos_sesion.get("reps_objetivo", 5)),
                "reps_completadas": int(datos_sesion.get("reps_completadas", 0)),
                "fecha_hora": datos_sesion.get("fecha_hora", datetime.datetime.now().isoformat()),
                "timestamp": datetime.datetime.now(),
                "tara_offsets": datos_sesion.get("tara_offsets", {"hombro": 0.0, "codo": 0.0, "muneca": 0.0}),
                "storage_path": str(datos_sesion.get("storage_path", "")),
                "estado": datos_sesion.get("estado", "INICIADA"),
                "frecuencia_muestreo_hz": float(datos_sesion.get("frecuencia_muestreo_hz", 0.0)),
                "datos_tecnicos": datos_sesion.get("datos_tecnicos", {})
            }
            self.db[COLL_SESIONES].insert_one(doc)
            return True
        except Exception as e:
            print(f"[MongoManager] Error al crear sesión: {e}")
            return False

    def actualizar_sesion(self, sesion_id: str, actualizaciones: Dict[str, Any]) -> bool:
        """Actualiza campos de una sesión existente."""
        if not self.esta_conectado():
            return False
        try:
            actualizaciones["timestamp_modificacion"] = datetime.datetime.now()
            self.db[COLL_SESIONES].update_one(
                {"sesion_id": sesion_id},
                {"$set": actualizaciones}
            )
            return True
        except Exception as e:
            print(f"[MongoManager] Error al actualizar sesión {sesion_id}: {e}")
            return False

    def obtener_sesion(self, sesion_id: str) -> Optional[Dict[str, Any]]:
        """Obtiene una sesión por su identificador único."""
        if not self.esta_conectado():
            return None
        try:
            doc = self.db[COLL_SESIONES].find_one({"sesion_id": sesion_id})
            if doc and "_id" in doc:
                doc["_id"] = str(doc["_id"])
            return doc
        except Exception as e:
            print(f"[MongoManager] Error al obtener sesión: {e}")
            return None

    def obtener_todas_sesiones(self, filtro: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Recupera la lista de sesiones ordenadas descendentemente por fecha."""
        if not self.esta_conectado():
            return []
        try:
            query = filtro or {}
            cursor = self.db[COLL_SESIONES].find(query).sort("timestamp", -1)
            sesiones = []
            for doc in cursor:
                doc["_id"] = str(doc["_id"])
                sesiones.append(doc)
            return sesiones
        except Exception as e:
            print(f"[MongoManager] Error al listar sesiones: {e}")
            return []

    # ==========================================
    # GESTIÓN DE REPETICIONES
    # ==========================================
    def registrar_repeticion(self, datos_rep: Dict[str, Any]) -> bool:
        """Registra o actualiza los metadatos y estadísticas de una repetición."""
        if not self.esta_conectado():
            return False
        try:
            filtro = {
                "sesion_id": datos_rep["sesion_id"],
                "num_rep": int(datos_rep["num_rep"])
            }
            doc = {
                "sesion_id": datos_rep["sesion_id"],
                "voluntario_id": datos_rep["voluntario_id"].strip().upper(),
                "ejercicio": datos_rep["ejercicio"],
                "num_rep": int(datos_rep["num_rep"]),
                "archivo_npz": str(datos_rep.get("archivo_npz", "")),
                "duracion_s": float(datos_rep.get("duracion_s", 0.0)),
                "muestras_totales": int(datos_rep.get("muestras_totales", 0)),
                "excursion_total": datos_rep.get("excursion_total", {"hombro": 0.0, "codo": 0.0, "muneca": 0.0}),
                "desviacion_maxima_abs": datos_rep.get("desviacion_maxima_abs", {"hombro": 0.0, "codo": 0.0, "muneca": 0.0}),
                "rom_max": datos_rep.get("rom_max", {"hombro": 0.0, "codo": 0.0, "muneca": 0.0}),
                "timestamp": datetime.datetime.now(),
                "estado": datos_rep.get("estado", "VALIDA")
            }
            self.db[COLL_REPETICIONES].update_one(filtro, {"$set": doc}, upsert=True)
            
            # Incrementar contador de repeticiones en la sesión si está en estado VALIDA
            reps_validas = self.db[COLL_REPETICIONES].count_documents({
                "sesion_id": datos_rep["sesion_id"],
                "estado": {"$ne": "ELIMINADA"}
            })
            self.actualizar_sesion(datos_rep["sesion_id"], {"reps_completadas": reps_validas})
            return True
        except Exception as e:
            print(f"[MongoManager] Error al registrar repetición: {e}")
            return False

    def obtener_repeticiones_sesion(self, sesion_id: str) -> List[Dict[str, Any]]:
        """Recupera todas las repeticiones pertenecientes a una sesión."""
        if not self.esta_conectado():
            return []
        try:
            cursor = self.db[COLL_REPETICIONES].find(
                {"sesion_id": sesion_id, "estado": {"$ne": "ELIMINADA"}}
            ).sort("num_rep", 1)
            reps = []
            for doc in cursor:
                doc["_id"] = str(doc["_id"])
                reps.append(doc)
            return reps
        except Exception as e:
            print(f"[MongoManager] Error al obtener repeticiones: {e}")
            return []

    def eliminar_repeticion(self, sesion_id: str, num_rep: int) -> bool:
        """Marca una repetición como ELIMINADA y ajusta el conteo de la sesión."""
        if not self.esta_conectado():
            return False
        try:
            self.db[COLL_REPETICIONES].update_one(
                {"sesion_id": sesion_id, "num_rep": num_rep},
                {"$set": {"estado": "ELIMINADA", "timestamp_eliminada": datetime.datetime.now()}}
            )
            reps_validas = self.db[COLL_REPETICIONES].count_documents({
                "sesion_id": sesion_id,
                "estado": {"$ne": "ELIMINADA"}
            })
            self.actualizar_sesion(sesion_id, {"reps_completadas": reps_validas})
            return True
        except Exception as e:
            print(f"[MongoManager] Error al eliminar repetición: {e}")
            return False

    def recapturar_repeticion(self, sesion_id: str, num_rep: int, nuevo_npz_path: str, stats_rep: Dict[str, Any]) -> bool:
        """Actualiza los datos de una repetición recapturada."""
        if not self.esta_conectado():
            return False
        try:
            update_data = {
                "archivo_npz": nuevo_npz_path,
                "duracion_s": float(stats_rep.get("duracion_s", 0.0)),
                "muestras_totales": int(stats_rep.get("muestras_totales", 0)),
                "excursion_total": stats_rep.get("excursion_total", {"hombro": 0.0, "codo": 0.0, "muneca": 0.0}),
                "desviacion_maxima_abs": stats_rep.get("desviacion_maxima_abs", {"hombro": 0.0, "codo": 0.0, "muneca": 0.0}),
                "rom_max": stats_rep.get("rom_max", {"hombro": 0.0, "codo": 0.0, "muneca": 0.0}),
                "timestamp_recaptura": datetime.datetime.now(),
                "estado": "RECAPTURADA"
            }
            self.db[COLL_REPETICIONES].update_one(
                {"sesion_id": sesion_id, "num_rep": num_rep},
                {"$set": update_data},
                upsert=True
            )
            reps_validas = self.db[COLL_REPETICIONES].count_documents({
                "sesion_id": sesion_id,
                "estado": {"$ne": "ELIMINADA"}
            })
            self.actualizar_sesion(sesion_id, {"reps_completadas": reps_validas})
            return True
        except Exception as e:
            print(f"[MongoManager] Error al recapturar repetición: {e}")
            return False

    def eliminar_sesion_completa(self, sesion_id: str) -> bool:
        """Elimina por completo la sesión y todas sus repeticiones de MongoDB."""
        if not self.esta_conectado():
            return False
        try:
            self.db[COLL_REPETICIONES].delete_many({"sesion_id": sesion_id})
            self.db[COLL_SESIONES].delete_one({"sesion_id": sesion_id})
            print(f"[MongoManager] Sesión {sesion_id} y sus repeticiones eliminadas de MongoDB.")
            return True
        except Exception as e:
            print(f"[MongoManager] Error al eliminar sesión completa {sesion_id}: {e}")
            return False

    def obtener_todas_repeticiones_validas(self) -> List[Dict[str, Any]]:
        """Recupera todas las repeticiones no eliminadas de la base de datos (para gráficas 3D)."""
        if not self.esta_conectado():
            return []
        try:
            cursor = self.db[COLL_REPETICIONES].find({"estado": {"$ne": "ELIMINADA"}}).sort("timestamp", -1)
            reps = []
            for doc in cursor:
                doc["_id"] = str(doc["_id"])
                reps.append(doc)
            return reps
        except Exception as e:
            print(f"[MongoManager] Error al recuperar repeticiones globales: {e}")
            return []
