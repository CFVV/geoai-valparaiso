"""
Chequeos de integridad de datos de entrada, antes de correr inferencia.
Cada problema detectado se retorna como string legible (no técnico) para
que run_pipeline.py lo reporte con log.warn().

Chequeos implementados:
1. Mosaico S2 faltante o vacío por tile/año (ver problema histórico: tiles 20/27/38)
2. % de píxeles nulos/nubes fuera de rango esperable (>30% del tile — umbral
   documentado en el stub original; no está en config.yaml porque es un
   chequeo de sanidad de datos, no un umbral de modelo)
3. Modelo .pkl encontrado y con metadata["version"] == cfg["modelo"]["version_esperada"]
4. Consistencia de CRS entre mosaicos y polígono comunal de filtro
"""

from pathlib import Path

import geopandas as gpd
import joblib
import numpy as np
import rasterio

PCT_NULOS_MAX = 30  # % máximo de píxeles nulos/0 tolerado por tile antes de advertir


def _check_pct_nulos(ruta_s2: Path, tiles: list, anio: int) -> list:
    problemas = []
    for tile_id in tiles:
        ruta_tile = ruta_s2 / f"tile_{tile_id}.tif"
        if not ruta_tile.exists():
            continue  # ya reportado por el chequeo de archivo faltante
        try:
            with rasterio.open(ruta_tile) as src:
                arr = src.read(1).astype(np.float32)
                nodata = src.nodata
                if nodata is not None and not np.isnan(nodata):
                    nulos = (arr == nodata) | (arr == 0) | ~np.isfinite(arr)
                else:
                    nulos = (arr == 0) | ~np.isfinite(arr)
                pct = 100.0 * nulos.mean()
            if pct > PCT_NULOS_MAX:
                problemas.append(
                    f"Tile {tile_id} ({anio}): {pct:.0f}% de píxeles nulos/vacíos "
                    f"(umbral {PCT_NULOS_MAX}%). Revisar cobertura de nubes o exportación GEE."
                )
        except Exception as e:
            problemas.append(f"Tile {tile_id} ({anio}): no se pudo leer el TIF ({e}).")
    return problemas


def _check_modelo(cfg: dict) -> list:
    problemas = []
    ruta_modelo = Path(cfg["modelo"]["ruta"])
    if not ruta_modelo.exists():
        problemas.append(f"No se encontró el modelo en {ruta_modelo}.")
        return problemas
    try:
        bundle = joblib.load(str(ruta_modelo))
        metadata = bundle.get("metadata", {}) if isinstance(bundle, dict) else {}
        version = metadata.get("version")
        esperada = cfg["modelo"]["version_esperada"]
        if version != esperada:
            problemas.append(
                f"El modelo {ruta_modelo} tiene metadata['version']={version!r}, "
                f"se esperaba {esperada!r}. ¿Se cargó el modelo equivocado?"
            )
    except Exception as e:
        problemas.append(f"No se pudo leer/validar el modelo {ruta_modelo}: {e}")
    return problemas


def _check_crs(cfg: dict, ruta_s2: Path, tiles: list) -> list:
    problemas = []
    poligono = Path(cfg["filtro_espacial"]["poligono_comunal"])
    if not poligono.exists():
        problemas.append(f"No se encontró el polígono comunal de filtro marítimo en {poligono}.")
        return problemas

    try:
        comunas_crs = gpd.read_file(poligono).crs
    except Exception as e:
        problemas.append(f"No se pudo leer el CRS de {poligono}: {e}")
        return problemas

    for tile_id in tiles:
        ruta_tile = ruta_s2 / f"tile_{tile_id}.tif"
        if not ruta_tile.exists():
            continue
        try:
            with rasterio.open(ruta_tile) as src:
                tile_crs = src.crs
            if comunas_crs is not None and tile_crs is not None and comunas_crs.to_epsg() != tile_crs.to_epsg():
                problemas.append(
                    f"Tile {tile_id}: CRS del mosaico ({tile_crs}) no coincide con el del "
                    f"polígono comunal ({comunas_crs}). El filtro marítimo puede fallar silenciosamente."
                )
                break  # un solo aviso basta, no repetir por cada tile
        except Exception:
            continue
    return problemas


def verificar_mosaicos(cfg: dict, log) -> list[str]:
    """Retorna lista de strings — cada uno una advertencia a mostrar al usuario."""
    problemas = []

    ruta_s2 = Path(cfg["rutas"]["s2_mosaics"]) / str(cfg["anios"]["fin"])
    if not ruta_s2.exists():
        problemas.append(
            f"No se encontró la carpeta de mosaicos {ruta_s2}. "
            "¿Corriste la descarga o usaste --skip-descarga por error?"
        )
        return problemas

    for tile_id in cfg["tiles"]:
        ruta_tile = ruta_s2 / f"tile_{tile_id}.tif"
        if not ruta_tile.exists():
            problemas.append(f"Falta el mosaico del tile {tile_id} para el año {cfg['anios']['fin']}.")

    problemas += _check_pct_nulos(ruta_s2, cfg["tiles"], cfg["anios"]["fin"])
    problemas += _check_modelo(cfg)
    problemas += _check_crs(cfg, ruta_s2, cfg["tiles"])

    return problemas
