"""
Descarga/verificación de LULC (ESRI 10m) y área quemada MODIS.

MODIS: portado desde wip-experiments/22_modis_burnt_area.ipynb
(`build_annual_burnt_mask` — MODIS/061/MCD64A1, banda BurnDate, máscara
binaria por año, 500 m). Se descarga una máscara por cada año distinto del
período de comparación (anios.inicio y anios.fin): el filtro de incendio de
pipeline.deteccion se aplica sobre delta_v2 = prob_fin − prob_inicio, y un
incendio en cualquiera de los dos años puede producir una señal espuria de
cambio, así que ambos años quedan cubiertos.

LULC: portado desde wip-experiments/nb37_lulc_verificacion.ipynb /
nb38_lulc_postprocesamiento.ipynb (`get_lulc_image` — mosaico ESRI Global
LULC 10m Time Series por año, exportado por tile a 10 m / EPSG:32719). Solo
se descarga el año usado como proxy (`anio_lulc_usado`), no todo el rango
histórico: pipeline.postproceso_lulc solo necesita frac_built para un año
(a diferencia de nb38, que comparaba 2020 vs 2023 para delta_built).

Lógica de proxy LULC (acordada 2026-07-03, ya presente en el stub original):
si cfg["anios"]["fin"] no está en cfg["lulc"]["anios_disponibles"], se usa el
año disponible más reciente como proxy.
"""

from pathlib import Path

import ee
import geemap
import geopandas as gpd

BURNT_SCALE_M = 500
LULC_SCALE_M = 10
LULC_CRS_OUT = "EPSG:32719"
ROI_PAD_DEG = 0.02  # buffer en grados para no perder píxeles MODIS en el borde


def get_lulc_image(year, lulc_collection):
    """Mosaico LULC para el año dado (ESRI LULC TS indexa por '{tile}_{year}')."""
    col = ee.ImageCollection(lulc_collection)
    return col.filter(ee.Filter.stringContains("system:index", f"_{year}")).mosaic().rename("lulc")


def _build_annual_burnt_mask(year, roi):
    col = (
        ee.ImageCollection("MODIS/061/MCD64A1")
        .filterBounds(roi)
        .filterDate(f"{year}-01-01", f"{year + 1}-01-01")
        .select("BurnDate")
    )
    burnt = col.map(lambda img: img.gt(0)).max()
    return burnt.rename("burnt").unmask(0).clip(roi)


def _descargar_modis(cfg, tiles_gdf_4326, log) -> bool:
    anios = sorted({cfg["anios"]["inicio"], cfg["anios"]["fin"]})
    out_dir = Path(cfg["rutas"]["burnt_area"])
    out_dir.mkdir(parents=True, exist_ok=True)

    b = tiles_gdf_4326.total_bounds
    roi = ee.Geometry.Rectangle(
        [b[0] - ROI_PAD_DEG, b[1] - ROI_PAD_DEG, b[2] + ROI_PAD_DEG, b[3] + ROI_PAD_DEG]
    )

    ok = True
    for year in anios:
        out_path = out_dir / f"burnt_{year}.tif"
        if out_path.exists():
            log.info(f"MODIS área quemada {year}: ya existe, se salta.")
            continue
        log.info(f"MODIS área quemada {year}: descargando...")
        try:
            mask = _build_annual_burnt_mask(year, roi)
            geemap.ee_export_image(
                mask, filename=str(out_path), scale=BURNT_SCALE_M, region=roi,
                crs="EPSG:4326", file_per_band=False,
            )
        except Exception:
            log.error(f"MODIS área quemada {year}: falló la descarga.")
            ok = False
    return ok


def _descargar_lulc(cfg, tiles_gdf_4326, anio_lulc_usado, log):
    lulc_collection = cfg["lulc"]["gee_collection"]
    year_dir = Path(cfg["rutas"]["lulc"]) / str(anio_lulc_usado)
    year_dir.mkdir(parents=True, exist_ok=True)

    for _, row in tiles_gdf_4326.iterrows():
        tile_id = int(row["tile_id"])
        out_path = year_dir / f"lulc_tile_{tile_id}_{anio_lulc_usado}.tif"
        if out_path.exists():
            log.info(f"LULC tile {tile_id} ({anio_lulc_usado}): ya existe, se salta.")
            continue
        log.info(f"LULC tile {tile_id} ({anio_lulc_usado}): descargando...")
        minx, miny, maxx, maxy = row.geometry.bounds
        tile_ee = ee.Geometry.BBox(float(minx), float(miny), float(maxx), float(maxy))
        img = get_lulc_image(anio_lulc_usado, lulc_collection).clip(tile_ee)
        try:
            geemap.ee_export_image(
                img, filename=str(out_path), scale=LULC_SCALE_M, region=tile_ee,
                crs=LULC_CRS_OUT, file_per_band=False,
            )
        except Exception:
            log.error(f"LULC tile {tile_id} ({anio_lulc_usado}): falló la descarga.")


def descargar(cfg: dict, log) -> dict:
    """
    Retorna un dict con al menos:
        {
            "anio_lulc_usado": int,   # año real usado (puede ser distinto a anios.fin)
            "modis_ok": bool,
        }
    """
    anio_fin = cfg["anios"]["fin"]
    anios_disp = cfg["lulc"]["anios_disponibles"]

    if anio_fin in anios_disp:
        anio_lulc_usado = anio_fin
    else:
        anio_lulc_usado = max(anios_disp)

    from comun.gee_utils import resolver_proyecto_gee

    ee.Initialize(project=resolver_proyecto_gee(cfg))

    tiles_gdf_4326 = gpd.read_file(cfg["rutas"]["tiles_gpkg"]).to_crs("EPSG:4326")
    tiles_gdf_4326 = tiles_gdf_4326[tiles_gdf_4326["tile_id"].astype(int).isin(set(cfg["tiles"]))]

    modis_ok = _descargar_modis(cfg, tiles_gdf_4326, log)
    _descargar_lulc(cfg, tiles_gdf_4326, anio_lulc_usado, log)

    return {
        "anio_lulc_usado": anio_lulc_usado,
        "modis_ok": modis_ok,
    }
