"""
Construcción idempotente del hexgrid de recurrencia de incendios.

Portado desde codes/2.MODIS_makeMap.ipynb. Reproduce la lógica REAL que generó
los entregables existentes (hexGrid_..._1985_2025/2026.gpkg) — es decir, la
celda 3 del notebook (`for gid in match.grid_id: ... Nfires = val+1`), NO la
celda 7 (`match.at[i,'Nfires']=1`), que corre después del export y es código
abandonado sin efecto en el entregable final.

SEMÁNTICA DE CONTEO (verificada empíricamente contra los archivos de entrega
reales, no solo leída del código — ver docs/METODOLOGIA.md):
cada intersección entre un hexágono y un polígono de área quemada de un mes
suma +1 a Nfires de ese hexágono. Como MODIS BurnDate codifica el día juliano
de quema por píxel, un mes con quemas en días distintos puede producir varios
polígonos disjuntos (uno por valor de día contiguo) que se solapan con el
mismo hexágono — en ese caso ese hexágono puede sumar más de +1 en un mismo
mes. Esto NO es un bug: es el comportamiento real del pipeline original,
verificado reproduciendo exactamente los totales de los entregables ya
publicados (base=4562, 1985-2025=7796, 1985-2026=7834 — corregido desde
7830, ver docs/METODOLOGIA.md sección "Nota sobre el Nfires de referencia").

IDEMPOTENCIA: esta función siempre parte de una copia fresca de la capa base
de Miranda (nunca la muta) y reconstruye el acumulado completo leyendo los
TIFs en disco desde cero en cada corrida. No hay estado incremental persistido
entre corridas, así que correr esta función dos veces con el mismo año_fin
sobre los mismos TIFs produce exactamente el mismo resultado.

Reemplaza `os.system('gdal_polygonize.py ...')` del notebook original por
`rasterio.features.shapes` (sin dependencia de binario GDAL externo). Ambos
implementan el mismo algoritmo de agrupar píxeles contiguos de igual valor,
y se verificó que producen sumas de Nfires idénticas.
"""

import re
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
import rasterio.features
from shapely.geometry import shape

NOMBRE_TIF_RE = re.compile(r"MODIS_(\d{4})-(\d{2})-01\.tif$")
# Exige mes con 2 dígitos (convención normalizada, ver docs/METODOLOGIA.md). Un
# archivo viejo sin cero a la izquierda (ej. MODIS_2018-1-01.tif) sería otro
# nombre de archivo para el MISMO mes que uno ya normalizado — si el regex
# aceptara ambos, _tifs_en_rango() los trataría como dos meses distintos y
# construir() sumaría ese mes dos veces a Nfires (double counting silencioso).


def _tifs_en_rango(carpeta_tifs: Path, anio_inicio: int, anio_fin: int) -> list[Path]:
    candidatos = []
    for f in sorted(carpeta_tifs.glob("MODIS_*.tif")):
        m = NOMBRE_TIF_RE.search(f.name)
        if not m:
            continue
        year = int(m.group(1))
        if anio_inicio <= year <= anio_fin:
            candidatos.append((year, int(m.group(2)), f))
    candidatos.sort(key=lambda t: (t[0], t[1]))
    return [f for _, _, f in candidatos]


def _polygonizar_quemado(tif_path: Path, dn_min: int):
    """Polígonos (en el CRS del TIF) de píxeles con DN > dn_min. None si no hay quema ese mes."""
    with rasterio.open(tif_path) as src:
        arr = src.read(1)
        mascara = arr > dn_min
        if not mascara.any():
            return None
        geoms = [
            shape(geom)
            for geom, _val in rasterio.features.shapes(arr, mask=mascara, transform=src.transform)
        ]
        return gpd.GeoDataFrame({"geometry": geoms}, crs=src.crs)


def construir(cfg: dict, log) -> gpd.GeoDataFrame:
    """
    Reconstruye el hexgrid completo (1985..anio_fin) desde cero:
      1. Lee la capa base de Miranda (Nfires 1985-2017) — solo lectura.
      2. Para cada mes de modis_inicio..anio_fin con TIF en disco, polygoniza
         los píxeles quemados (DN > dn_min) y suma +1 a Nfires por cada
         hexágono que intersecte cada polígono quemado de ese mes.
      3. Retorna el GeoDataFrame resultante (no escribe archivos — eso lo
         hace pipeline/exportar.py).
    """
    ruta_base = Path(cfg["hexgrid"]["base_miranda"])
    if not ruta_base.exists():
        raise FileNotFoundError(f"No se encontró la capa base de Miranda en {ruta_base}")

    base = gpd.read_file(ruta_base)
    if "Nfires" not in base.columns:
        raise ValueError(f"La capa base {ruta_base} no tiene columna 'Nfires'.")

    crs_trabajo = "EPSG:32719"
    hgrid = base.to_crs(crs_trabajo).copy()

    carpeta_tifs = Path(cfg["rutas"]["modis_tifs"])
    anio_inicio = cfg["anios"]["modis_inicio"]
    anio_fin = cfg["anios"]["fin"]
    dn_min = cfg["umbrales"]["dn_min"]

    tifs = _tifs_en_rango(carpeta_tifs, anio_inicio, anio_fin)
    if not tifs:
        log.warn(f"No se encontraron TIFs MODIS en {carpeta_tifs} para el rango {anio_inicio}-{anio_fin}.")

    meses_procesados = 0
    meses_con_quema = 0

    for tif_path in tifs:
        m = NOMBRE_TIF_RE.search(tif_path.name)
        year, month = int(m.group(1)), int(m.group(2))

        farea = _polygonizar_quemado(tif_path, dn_min)
        meses_procesados += 1
        if farea is None:
            continue
        meses_con_quema += 1

        farea = farea.to_crs(crs_trabajo)
        match = hgrid.overlay(farea)
        if len(match) == 0:
            continue

        conteos = match["grid_id"].value_counts()
        hgrid["Nfires"] = hgrid["Nfires"] + hgrid["grid_id"].map(conteos).fillna(0).astype(int)
        log.info(f"MODIS {year}-{month:02d}: {len(farea)} polígono(s) quemado(s), {len(match)} intersección(es) con hexágonos.")

    log.info(f"Meses procesados: {meses_procesados} ({meses_con_quema} con quema detectada).")

    return hgrid.to_crs(base.crs)
