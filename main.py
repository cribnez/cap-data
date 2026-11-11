"""
main.py - Punto de entrada principal para la suite biomecánica Cap_Data
"""
import os
import sys
from pathlib import Path

# Añadir directorio raíz al PYTHONPATH
directorio_raiz = Path(__file__).resolve().parent.parent
if str(directorio_raiz) not in sys.path:
    sys.path.insert(0, str(directorio_raiz))

from Cap_Data.ui.app_window import AppWindow


def main():
    print("=" * 65)
    print("   INICIANDO SUITE BIOMECÁNICA CAP_DATA CON MONGODB (ROMDB)")
    print("=" * 65)
    app = AppWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
