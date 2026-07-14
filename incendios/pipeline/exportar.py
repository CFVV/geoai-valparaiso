"""
Exportación del hexgrid final a GPKG + GeoJSON.

Nombre de salida corregido: hexGrid_250m_incendiosValpo_1985_{anio_fin}
(el hexágono real mide 250 m, no 200 m — ver docs/METODOLOGIA.md). La capa
base histórica (hexGrid_200m_incendiosValpo.gpkg) no se toca ni se renombra.
"""

from pathlib import Path

import geopandas as gpd


def exportar(hgrid: gpd.GeoDataFrame, cfg: dict, log) -> list[str]:
    anio_fin = cfg["anios"]["fin"]

    ruta_gpkg = Path(cfg["rutas"]["entrega_gpkg"].format(anio_fin=anio_fin))
    ruta_geojson = Path(cfg["rutas"]["entrega_geojson"].format(anio_fin=anio_fin))
    ruta_gpkg.parent.mkdir(parents=True, exist_ok=True)
    ruta_geojson.parent.mkdir(parents=True, exist_ok=True)

    hgrid.to_file(ruta_gpkg, driver="GPKG")
    hgrid.to_file(ruta_geojson, driver="GeoJSON")

    log.info(f"Exportado: {ruta_gpkg}")
    log.info(f"Exportado: {ruta_geojson}")

    return [str(ruta_gpkg), str(ruta_geojson)]
