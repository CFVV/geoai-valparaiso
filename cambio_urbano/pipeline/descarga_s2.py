"""
Descarga de mosaicos Sentinel-2 vía Google Earth Engine.

Lógica portada de wip-experiments/25_descarga_inferencia_2026.ipynb (sección 1):
mediana de imágenes COPERNICUS/S2_SR_HARMONIZED con CLOUDY_PIXEL_PERCENTAGE < 20,
6 bandas (B2, B3, B4, B8, B11, B12), 10 m, EPSG:32719.

NOTA — "máscara SCL": el docstring original de este módulo mencionaba una
máscara SCL (Scene Classification Layer) "ya validada". Se verificó contra
wip-experiments/25_descarga_inferencia_2026.ipynb y no existe tal máscara por
píxel en ese notebook ni en ningún otro pipeline de producción: el único
filtro de nubes usado para generar los mosaicos que alimentan el modelo v2 es
el filtro de escena CLOUDY_PIXEL_PERCENTAGE < 20 aplicado antes de la mediana.
Existe una máscara QA60 por píxel (gee_utils.maskS2clouds), pero pertenece a
un notebook exploratorio distinto (export-s2.ipynb) con otra composición de
bandas, y nunca se usó para generar los mosaicos de producción. Se portó la
lógica real (filtro de escena únicamente) en vez de inventar un enmascarado
por píxel que cambiaría el comportamiento respecto a lo ya validado.

Detección de mosaico incompleto (NUEVO — no existía en nb25, que hardcodeaba
"enero-marzo 2026" a mano): si cfg["anios"]["fin"] es el año en curso, se
consulta la colección S2 filtrada por el mismo criterio de nubosidad y se
determina el último mes calendario con al menos una escena disponible.
"""

import datetime
from pathlib import Path

import ee
import geemap
import geopandas as gpd
from shapely.geometry import mapping

BANDS = ["B2", "B3", "B4", "B8", "B11", "B12"]
CLOUD_MAX = 20  # % nubosidad máxima por escena (CLOUDY_PIXEL_PERCENTAGE) — igual a nb25
SCALE_M = 10
CRS_OUT = "EPSG:32719"

MESES_ES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio",
    7: "julio", 8: "agosto", 9: "septiembre", 10: "octubre", 11: "noviembre",
    12: "diciembre",
}


def _tile_to_ee_geom(row):
    geom = row.geometry.buffer(0)
    coords = mapping(geom)["coordinates"]
    if geom.geom_type == "Polygon":
        return ee.Geometry.Polygon(coords[0], proj=None, geodesic=False)
    polys = [p[0] for p in coords]
    return ee.Geometry.MultiPolygon(polys, proj=None, geodesic=False)


def _make_s2_mosaic(geom_ee, date_start, date_end, cloud_max):
    col = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(geom_ee)
        .filterDate(date_start, date_end)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", cloud_max))
    )
    n = col.size().getInfo()
    img = col.median().select(BANDS)
    return img, n


def _detectar_mosaico_incompleto(roi_ee, anio, cloud_max, hoy=None):
    """Si `anio` es el año en curso, retorna (incompleto, ultimo_mes_cubierto)."""
    hoy = hoy or datetime.date.today()
    if anio != hoy.year:
        return False, None

    col = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(roi_ee)
        .filterDate(f"{anio}-01-01", f"{anio + 1}-01-01")
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", cloud_max))
    )
    timestamps = col.aggregate_array("system:time_start").getInfo()
    if not timestamps:
        return True, None

    meses_con_datos = sorted({
        datetime.datetime.utcfromtimestamp(t / 1000).month for t in timestamps
    })
    ultimo_mes = max(meses_con_datos)
    incompleto = ultimo_mes < hoy.month
    return incompleto, (MESES_ES[ultimo_mes] if incompleto else None)


def descargar(cfg: dict, log) -> dict:
    """
    Descarga los mosaicos S2 de AMBOS años del período de comparación
    (anios.inicio y anios.fin) — delta_v2 = prob_fin - prob_inicio necesita
    los dos, no solo el año "fin". El chequeo de "ya existe, se salta" es
    por año Y por tile (una carpeta out_dir distinta por año).

    Retorna un dict con al menos:
        {
            "mosaico_incompleto": bool,          # solo evalúa anios.fin
            "ultimo_mes_cubierto": str | None,   # ej. "marzo" — solo si incompleto
            "tiles_descargados": list[(int, int)],  # (anio, tile_id)
            "tiles_fallidos": list[(int, int)],
        }
    """
    from comun.gee_utils import resolver_proyecto_gee

    ee.Initialize(project=resolver_proyecto_gee(cfg))

    anio_inicio = cfg["anios"]["inicio"]
    anio_fin = cfg["anios"]["fin"]
    anios = sorted({anio_inicio, anio_fin})
    tiles_cfg = set(cfg["tiles"])

    tiles_gdf = gpd.read_file(cfg["rutas"]["tiles_gpkg"]).to_crs("EPSG:4326")
    tiles_gdf = tiles_gdf[tiles_gdf["tile_id"].astype(int).isin(tiles_cfg)]

    roi_ee = ee.FeatureCollection(
        [ee.Feature(_tile_to_ee_geom(row)) for _, row in tiles_gdf.iterrows()]
    ).geometry()

    incompleto_fin, ultimo_mes_fin = False, None
    descargados, fallidos = [], []

    for anio in anios:
        s2_out = Path(cfg["rutas"]["s2_mosaics"]) / str(anio)
        s2_out.mkdir(parents=True, exist_ok=True)

        date_start = f"{anio}-01-01"
        date_end = f"{anio + 1}-01-01"

        incompleto, ultimo_mes = _detectar_mosaico_incompleto(roi_ee, anio, CLOUD_MAX)
        if incompleto:
            date_end = min(date_end, datetime.date.today().isoformat())
        if anio == anio_fin:
            incompleto_fin, ultimo_mes_fin = incompleto, ultimo_mes

        for i, (_, row) in enumerate(tiles_gdf.iterrows(), 1):
            tile_id = int(row["tile_id"])
            out_tif = s2_out / f"tile_{tile_id}.tif"

            if out_tif.exists():
                log.info(f"Descargando tile {i}/{len(tiles_gdf)} (id={tile_id}) año {anio}... ya existe, se salta.")
                descargados.append((anio, tile_id))
                continue

            log.info(f"Descargando tile {i}/{len(tiles_gdf)} (id={tile_id}) año {anio}...")
            try:
                geom_ee = _tile_to_ee_geom(row)
                img, n_imgs = _make_s2_mosaic(geom_ee, date_start, date_end, CLOUD_MAX)
                if n_imgs == 0:
                    log.warn(f"Tile {tile_id} ({anio}): sin escenas S2 en el período {date_start}..{date_end}.")
                    fallidos.append((anio, tile_id))
                    continue
                geemap.ee_export_image(
                    img,
                    filename=str(out_tif),
                    scale=SCALE_M,
                    region=geom_ee,
                    crs=CRS_OUT,
                    file_per_band=False,
                )
                descargados.append((anio, tile_id))
            except Exception:
                log.error(f"Tile {tile_id} ({anio}): falló la descarga S2.")
                fallidos.append((anio, tile_id))

    return {
        "mosaico_incompleto": incompleto_fin,
        "ultimo_mes_cubierto": ultimo_mes_fin,
        "tiles_descargados": descargados,
        "tiles_fallidos": fallidos,
    }
