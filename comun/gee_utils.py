"""
Resolución del proyecto de Google Earth Engine, compartida por ambos pipelines.

Antes de este módulo, cada script de descarga leía cfg["gee"]["proyecto"]
directamente, ignorando la variable de entorno GEE_PROJECT documentada en
README.md/METODOLOGIA.md de ambos pipelines. Esto rompía la reproducibilidad
en cualquier máquina que no tuviera el placeholder de config.yaml editado a
mano (ver docs/METODOLOGIA.md de cambio_urbano, sección de instalación).
"""

import os


def resolver_proyecto_gee(cfg: dict) -> str:
    """Prioriza la variable de entorno GEE_PROJECT; si no está seteada, usa
    gee.proyecto de config.yaml como fallback."""
    return os.environ.get("GEE_PROJECT", cfg["gee"]["proyecto"])
