"""
storage_manager.py - Gestor de almacenamiento en disco para metadatos JSON y archivos NPZ
"""
from __future__ import annotations
import json
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from Cap_Data.config import (
    STORAGE_DIR,
    CAJON_FILTRADOS_TARADOS,
    CAJON_FILTRADOS_SIN_TARA,
    CAJON_CRUDOS_TARADOS,
    CAJON_CRUDOS_SIN_TARA
)


class StorageManager:
    """Administrador de estructura de carpetas, metadata.json y compresión NPZ de 4 cajones."""

    @staticmethod
    def limpiar_nombre(texto: str) -> str:
        """Sanitiza nombres de carpetas y archivos reemplazando caracteres inválidos."""
        caracteres_invalidos = '<>:"/\\|?* '
        resultado = texto.strip()
        for c in caracteres_invalidos:
            resultado = resultado.replace(c, "_")
        return resultado

    @classmethod
    def obtener_carpeta_sesion(cls, voluntario_id: str, sesion_id: str, ejercicio: str) -> Path:
        """Devuelve (y crea) la ruta de almacenamiento de una sesión clínica."""
        v_folder = cls.limpiar_nombre(voluntario_id.upper())
        s_folder = f"{cls.limpiar_nombre(sesion_id)}_{cls.limpiar_nombre(ejercicio)}"
        
        ruta_completa = STORAGE_DIR / f"V_{v_folder}" / s_folder
        ruta_completa.mkdir(parents=True, exist_ok=True)
        return ruta_completa

    @classmethod
    def guardar_metadata(cls, voluntario_id: str, sesion_id: str, ejercicio: str, metadata: Dict[str, Any]) -> Path:
        """Guarda o actualiza el archivo metadata.json en el directorio de la sesión."""
        carpeta = cls.obtener_carpeta_sesion(voluntario_id, sesion_id, ejercicio)
        ruta_json = carpeta / "metadata.json"
        
        with open(ruta_json, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=4, ensure_ascii=False)
            
        return ruta_json

    @classmethod
    def leer_metadata(cls, ruta_carpeta_o_json: Path) -> Optional[Dict[str, Any]]:
        """Lee el contenido de un archivo metadata.json."""
        ruta_json = ruta_carpeta_o_json if ruta_carpeta_o_json.name == "metadata.json" else ruta_carpeta_o_json / "metadata.json"
        if not ruta_json.exists():
            return None
        try:
            with open(ruta_json, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[StorageManager] Error al leer metadata en {ruta_json}: {e}")
            return None

    @classmethod
    def guardar_repeticion_npz(
        cls,
        voluntario_id: str,
        sesion_id: str,
        ejercicio: str,
        num_rep: int,
        filtrados_tarados: np.ndarray,
        filtrados_sin_tara: np.ndarray,
        crudos_tarados: np.ndarray,
        crudos_sin_tara: np.ndarray,
        auditoria: Optional[Dict[str, Any]] = None
    ) -> Tuple[Path, Dict[str, Any]]:
        """
        Guarda una repetición en un archivo .npz con exactamente los 4 cajones independientes:
        - filtrados_tarados
        - filtrados_sin_tara
        - crudos_tarados
        - crudos_sin_tara
        
        Calcula excursión de señal, desviación máxima y duración.
        """
        carpeta = cls.obtener_carpeta_sesion(voluntario_id, sesion_id, ejercicio)
        nombre_archivo = f"rep_{num_rep}.npz"
        ruta_npz = carpeta / nombre_archivo

        # Asegurar tipo flotante y continuidad en memoria
        ft = np.ascontiguousarray(filtrados_tarados, dtype=np.float32)
        fst = np.ascontiguousarray(filtrados_sin_tara, dtype=np.float32)
        ct = np.ascontiguousarray(crudos_tarados, dtype=np.float32)
        cst = np.ascontiguousarray(crudos_sin_tara, dtype=np.float32)

        # Guardar comprimido
        np.savez_compressed(
            str(ruta_npz),
            **{
                CAJON_FILTRADOS_TARADOS: ft,
                CAJON_FILTRADOS_SIN_TARA: fst,
                CAJON_CRUDOS_TARADOS: ct,
                CAJON_CRUDOS_SIN_TARA: cst
            }
        )

        ruta_auditoria = ruta_npz.with_name(f"{ruta_npz.stem}.audit.json")
        if auditoria is not None:
            with open(ruta_auditoria, "w", encoding="utf-8") as archivo_auditoria:
                json.dump(auditoria, archivo_auditoria, indent=2, ensure_ascii=False)
        elif ruta_auditoria.exists():
            ruta_auditoria.unlink()

        # Cálculo de estadísticas de excursión y desviación de la señal:
        duracion = float(ft[-1, 0] - ft[0, 0]) if len(ft) > 1 else 0.0

        # 1. Excursión total de la señal pico a pico (PTP: max(x) - min(x))
        excursion_total = {
            "hombro": float(np.ptp(ft[:, 1])) if len(ft) > 0 else 0.0,
            "codo": float(np.ptp(ft[:, 2])) if len(ft) > 0 else 0.0,
            "muneca": float(np.ptp(ft[:, 3])) if len(ft) > 0 else 0.0
        }

        # 2. Máxima desviación absoluta respecto a la tara basal: max(|x|)
        desviacion_maxima_abs = {
            "hombro": float(np.max(np.abs(ft[:, 1]))) if len(ft) > 0 else 0.0,
            "codo": float(np.max(np.abs(ft[:, 2]))) if len(ft) > 0 else 0.0,
            "muneca": float(np.max(np.abs(ft[:, 3]))) if len(ft) > 0 else 0.0
        }

        stats = {
            "duracion_s": round(duracion, 2),
            "muestras_totales": int(len(ft)),
            "excursion_total": excursion_total,
            "desviacion_maxima_abs": desviacion_maxima_abs,
            "rom_max": desviacion_maxima_abs,
            "auditoria": auditoria or {}
        }

        return ruta_npz, stats

    @classmethod
    def cargar_repeticion_npz(cls, ruta_npz: Path | str) -> Optional[Dict[str, np.ndarray]]:
        """Carga y valida los 4 arrays de un archivo de repetición."""
        ruta = Path(ruta_npz)
        if not ruta.exists():
            print(f"[StorageManager] Archivo NPZ no encontrado: {ruta}")
            return None
        try:
            with np.load(str(ruta)) as data:
                return {
                    CAJON_FILTRADOS_TARADOS: data[CAJON_FILTRADOS_TARADOS],
                    CAJON_FILTRADOS_SIN_TARA: data[CAJON_FILTRADOS_SIN_TARA],
                    CAJON_CRUDOS_TARADOS: data[CAJON_CRUDOS_TARADOS],
                    CAJON_CRUDOS_SIN_TARA: data[CAJON_CRUDOS_SIN_TARA]
                }
        except Exception as e:
            print(f"[StorageManager] Error al cargar NPZ en {ruta}: {e}")
            return None

    @classmethod
    def eliminar_archivo_repeticion(cls, ruta_npz: Path | str) -> bool:
        """Elimina físicamente un archivo de repetición o lo renombra a .bak."""
        ruta = Path(ruta_npz)
        if not ruta.exists():
            return False
        try:
            bak_path = ruta.with_suffix(".npz.bak")
            if bak_path.exists():
                bak_path.unlink()
            ruta.rename(bak_path)
            return True
        except Exception as e:
            print(f"[StorageManager] Error al eliminar/respaldar {ruta}: {e}")
            return False

    @classmethod
    def eliminar_carpeta_sesion(cls, voluntario_id: str, sesion_id: str, ejercicio: str) -> bool:
        """Elimina físicamente la carpeta de la sesión completa en disco."""
        v_folder = cls.limpiar_nombre(voluntario_id.upper())
        s_folder = f"{cls.limpiar_nombre(sesion_id)}_{cls.limpiar_nombre(ejercicio)}"
        ruta_completa = STORAGE_DIR / f"V_{v_folder}" / s_folder
        if not ruta_completa.exists():
            return False
        try:
            shutil.rmtree(ruta_completa)
            print(f"[StorageManager] Carpeta eliminada: {ruta_completa}")
            # Si la carpeta del voluntario queda vacía, limpiarla también
            carpeta_voluntario = ruta_completa.parent
            if carpeta_voluntario.exists() and not any(carpeta_voluntario.iterdir()):
                carpeta_voluntario.rmdir()
            return True
        except Exception as e:
            print(f"[StorageManager] Error al eliminar carpeta de sesión {ruta_completa}: {e}")
            return False

    @classmethod
    def listar_sesiones_locales(cls) -> List[Dict[str, Any]]:
        """Recupera la lista de todas las carpetas de sesiones con metadata válida."""
        sesiones = []
        if not STORAGE_DIR.exists():
            return sesiones

        for p in STORAGE_DIR.glob("V_*/*"):
            if p.is_dir():
                meta = cls.leer_metadata(p)
                if meta:
                    sesiones.append(meta)
        return sesiones

    # Alias de compatibilidad
    listar_sesiones_en_disco = listar_sesiones_locales
