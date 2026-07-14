"""
Aplica el umbral delta_v2 y los filtros de incendio/marítimo sobre la
salida de inferencia.

Clasificación ("v4 adaptada") y umbral portados desde
wip-experiments/nb36_aplicacion_modelo_v2.ipynb (`assign_tipo_v2_cal`,
`DELTA_V2_THR = 0.070`, recalibrado 2026-05-13 para reproducir ~757 CRs de
v1). Filtro marítimo portado desde la misma notebook (FASE 4: centroide del
subtile dentro de un polígono de `comun/gdf_comunas.gpkg`, sjoin
`predicate="within"`).

Filtro de incendio — DIFERENTE del notebook fuente por necesidad: en nb36,
`es_artefacto_incendio` se hereda de una columna estática ya calculada en
`outputs/subtiles_250m_change_classification.gpkg` (de una corrida histórica
única). Esa columna no existe para años/tiles nuevos, así que aquí se
recalcula en cada corrida a partir de las máscaras MODIS descargadas por
pipeline.descarga_lulc_modis, comparando `frac_burnt >= umbrales.frac_burnt_incendio`
(mismo umbral y misma fuente de datos — MODIS MCD64A1 — que ya estaba en uso,
solo que evaluado en vivo en vez de leído de un archivo estático). El umbral
delta_v2 y la lógica de clasificación en sí NO se tocan.
"""

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.mask import mask as rio_mask
from rasterio.windows import from_bounds as win_from_bounds
from shapely.geometry import mapping


def _read_patch(prob_arr, tf, shp, bounds):
    H, W = shp
    win = win_from_bounds(*bounds, transform=tf)
    r0 = max(0, int(np.floor(win.row_off)))
    r1 = min(H, int(np.ceil(win.row_off + win.height)))
    c0 = max(0, int(np.floor(win.col_off)))
    c1 = min(W, int(np.ceil(win.col_off + win.width)))
    if r1 <= r0 or c1 <= c0:
        return None
    return prob_arr[r0:r1, c0:c1].astype(float)


def _frac_burnt_por_subtile(gdf, cfg, log):
    burnt_dir = Path(cfg["rutas"]["burnt_area"])
    anios = sorted({cfg["anios"]["inicio"], cfg["anios"]["fin"]})
    gdf_wgs = gdf.to_crs("EPSG:4326")

    fracs = pd.DataFrame(index=gdf.index)
    for yr in anios:
        tif_path = burnt_dir / f"burnt_{yr}.tif"
        if not tif_path.exists():
            log.warn(f"No se encontró máscara MODIS de área quemada para {yr} ({tif_path}).")
            fracs[yr] = np.nan
            continue
        vals = []
        with rasterio.open(tif_path) as src:
            for geom in gdf_wgs.geometry:
                try:
                    arr, _ = rio_mask(src, [mapping(geom)], crop=True, nodata=255, all_touched=True)
                    v = arr[0]
                    valid = v[v != 255]
                    vals.append(float((valid > 0).mean()) if valid.size else np.nan)
                except Exception:
                    vals.append(np.nan)
        fracs[yr] = vals

    return fracs.max(axis=1, skipna=True).fillna(0.0).values


def detectar(resultado_inferencia, cfg: dict, log) -> gpd.GeoDataFrame:
    """
    Retorna GeoDataFrame de subtiles con cambio detectado (delta_v2 > umbral),
    ya excluidos los marítimos y los marcados como posible_incendio.
    Columnas mínimas esperadas: subtile_id, tile_id, delta_v2, geometry,
    es_artefacto_incendio.
    """
    anio_inicio = cfg["anios"]["inicio"]
    anio_fin = cfg["anios"]["fin"]
    delta_thr = cfg["umbrales"]["delta_v2_deteccion"]

    sub_gdf = gpd.read_file(cfg["rutas"]["subtiles_gpkg"])[["subtile_id", "tile_id", "geometry"]]
    sub_gdf["tile_id"] = sub_gdf["tile_id"].astype(int)
    sub_gdf = sub_gdf[sub_gdf["tile_id"].isin(set(cfg["tiles"]))]

    records = []
    for _, row in sub_gdf.iterrows():
        tid = int(row["tile_id"])
        bounds = row.geometry.bounds
        rec = {"subtile_id": row["subtile_id"], "tile_id": tid, "geometry": row.geometry}

        probs_tile = resultado_inferencia.get(tid, {})
        patches = {}
        for yr in (anio_inicio, anio_fin):
            d = probs_tile.get(yr)
            if d is None:
                rec[f"prob_{yr}"] = np.nan
                continue
            patch = _read_patch(d["prob"], d["transform"], d["shape"], bounds)
            if patch is not None:
                v = patch[np.isfinite(patch)].ravel()
                rec[f"prob_{yr}"] = float(v.mean()) if len(v) > 0 else np.nan
                patches[yr] = patch
            else:
                rec[f"prob_{yr}"] = np.nan

        if anio_inicio in patches and anio_fin in patches:
            delta = patches[anio_fin] - patches[anio_inicio]
            m = np.isfinite(delta)
            rec["delta_v2"] = float(np.nanmean(delta)) if m.sum() > 0 else np.nan
        else:
            rec["delta_v2"] = np.nan

        records.append(rec)

    gdf = gpd.GeoDataFrame(pd.DataFrame(records), geometry="geometry", crs=sub_gdf.crs)

    gdf["cambio_tipo"] = np.where(
        gdf["delta_v2"].notna() & (gdf["delta_v2"] > delta_thr),
        "cambio_reciente", "sin_cambio",
    )

    gdf["frac_burnt"] = _frac_burnt_por_subtile(gdf, cfg, log)
    gdf["es_artefacto_incendio"] = gdf["frac_burnt"] >= cfg["umbrales"]["frac_burnt_incendio"]

    cr = gdf[(gdf["cambio_tipo"] == "cambio_reciente") & (~gdf["es_artefacto_incendio"])].copy()
    log.info(f"Subtiles cambio_reciente (delta_v2 > {delta_thr}) antes de filtro marítimo: {len(cr)}")

    comunas = gpd.read_file(cfg["filtro_espacial"]["poligono_comunal"])[["NOM_COMUNA", "geometry"]].to_crs(gdf.crs)
    cents = cr[["subtile_id", "geometry"]].copy()
    cents["geometry"] = cr.geometry.centroid
    within = gpd.sjoin(cents, comunas, how="inner", predicate="within")
    within = within[~within.index.duplicated(keep="first")][["subtile_id", "NOM_COMUNA"]].rename(
        columns={"NOM_COMUNA": "comuna"}
    )

    cr = cr[cr["subtile_id"].isin(within["subtile_id"])].merge(within, on="subtile_id", how="left")
    log.info(f"Subtiles cambio_reciente después de filtro marítimo: {len(cr)}")

    return cr.reset_index(drop=True)
