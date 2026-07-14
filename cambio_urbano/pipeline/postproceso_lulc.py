"""
Postprocesamiento LULC y generación de entregables finales.

Extracción de frac_built portada desde
wip-experiments/nb38_lulc_postprocesamiento.ipynb (BUILT_CLS = 7 = "Built
Area" en ESRI LULC 10m; `rasterio.mask.mask` del polígono del subtile sobre
el TIF LULC, frac_built = píxeles Built / píxeles válidos). Ese mecanismo de
extracción NO se modifica.

CAMBIO ACORDADO 2026-07-03 (ver docs/METODOLOGIA.md, validación ciega nb40):
las categorías confirmado_lulc (frac_built >= 0.40) y ambiguo_lulc
(0.02 <= frac_built < 0.40) del notebook original se FUSIONAN en una sola
etiqueta pública "Alerta de cambio" (frac_built >= umbrales.frac_built_alerta,
0.10 en config.yaml — nótese que este umbral único de corte, 0.10, es
distinto de los dos umbrales originales de nb38, 0.40/0.02: es el valor
acordado para la categoría fusionada, no una media de los anteriores). Lo que
antes era suprimido_lulc sigue excluido del entregable público.

Exportación KMZ: método de wip-experiments/recalibrar_v2.py /
nb36_aplicacion_modelo_v2.ipynb (`build_kml` / `hex_to_kml` + `zipfile`) —
es el que efectivamente generó los KMZ ya entregados en
outputs/ENTREGA_FINAL/ (a TECHO / Gobierno Regional), NO el `simplekml` usado
en nb38 (que nunca se usó para un entregable final). El KMZ original tenía 2
capas de color por confianza (verde=confirmado, amarillo=sin_confirmar); como
ahora hay una sola categoría pública, el KMZ resultante tiene una sola capa
"Alerta de cambio" (color ámbar) — cambio intencional de 2026-07, documentado
aquí porque reduce la cantidad de capas respecto al KMZ histórico.
"""

import zipfile
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.mask import mask as rio_mask
from shapely.geometry import mapping

BUILT_CLS = 7  # ESRI LULC 10m: 7 = Built Area
LULC_CRS = "EPSG:32719"

ALERTA_COLOR = "00a0ff"  # ámbar/naranjo (KML: BBGGRR), capa única "Alerta de cambio"
ALERTA_ALPHA = "cc"


def _frac_built_por_subtile(gdf_utm, lulc_dir: Path, year: int, log) -> np.ndarray:
    vals = []
    cache = {}
    for _, row in gdf_utm.iterrows():
        tid = int(row["tile_id"])
        tif_path = lulc_dir / str(year) / f"lulc_tile_{tid}_{year}.tif"
        if tid not in cache:
            cache[tid] = tif_path if tif_path.exists() else None
            if cache[tid] is None:
                log.warn(f"No se encontró TIF LULC para tile {tid} año {year} ({tif_path}).")

        if cache[tid] is None:
            vals.append(np.nan)
            continue

        try:
            with rasterio.open(cache[tid]) as src:
                out_arr, _ = rio_mask(src, [mapping(row.geometry)], crop=True, nodata=0)
            px = out_arr[0][out_arr[0] > 0]
            vals.append(int(np.sum(px == BUILT_CLS)) / len(px) if len(px) > 0 else np.nan)
        except Exception:
            vals.append(np.nan)

    return np.array(vals, dtype=float)


def clasificar(gdf_detecciones: gpd.GeoDataFrame, cfg: dict, log, lulc_anio_usado=None) -> gpd.GeoDataFrame:
    """
    Cruza gdf_detecciones con LULC (frac_built) y asigna:
    - "Alerta de cambio"  si frac_built_{anio} >= umbrales.frac_built_alerta
    - excluye el resto (no se agrega al gdf final, pero se puede loggear el conteo)
    """
    anio_fin = cfg["anios"]["fin"]
    if lulc_anio_usado is not None:
        year = lulc_anio_usado
    else:
        # run_pipeline.py pasa lulc_anio_usado=None con --skip-lulc (no se corrió la
        # descarga en esta invocación). Se replica la misma lógica de proxy que usa
        # pipeline.descarga_lulc_modis.descargar() para no asumir que anio_fin tiene
        # LULC en disco cuando puede que ni siquiera esté publicado por ESRI todavía.
        anios_disp = cfg["lulc"]["anios_disponibles"]
        year = anio_fin if anio_fin in anios_disp else max(anios_disp)
    thr = cfg["umbrales"]["frac_built_alerta"]

    gdf_utm = gdf_detecciones.to_crs(LULC_CRS) if gdf_detecciones.crs.to_epsg() != 32719 else gdf_detecciones

    lulc_dir = Path(cfg["rutas"]["lulc"])
    frac_built = _frac_built_por_subtile(gdf_utm, lulc_dir, year, log)

    gdf = gdf_detecciones.copy()
    gdf["frac_built"] = frac_built
    gdf["categoria"] = np.where(
        pd.notna(gdf["frac_built"]) & (gdf["frac_built"] >= thr),
        "Alerta de cambio", "excluido",
    )

    n_alerta = (gdf["categoria"] == "Alerta de cambio").sum()
    n_excluido = (gdf["categoria"] == "excluido").sum()
    log.info(f"Postprocesamiento LULC (año {year}, umbral frac_built >= {thr}): "
              f"{n_alerta} 'Alerta de cambio', {n_excluido} excluidos.")

    gdf_final = gdf[gdf["categoria"] == "Alerta de cambio"].drop(columns=["categoria"]).copy()

    if year != anio_fin:
        gdf_final["lulc_anio_proxy"] = (
            f"LULC {year} usado como proxy de {anio_fin} — dato no publicado aún por ESRI."
        )

    return gdf_final.reset_index(drop=True)


def _hex_to_kml(h, alpha="ff"):
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"{alpha}{b}{g}{r}"


def _geom_to_coords(geom):
    polys = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)
    return [" ".join(f"{x},{y},0" for x, y in p.exterior.coords) for p in polys]


def _build_kml(gdf_layer, name, color_hex, alpha):
    kml_color = _hex_to_kml(color_hex, alpha)
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<kml xmlns="http://www.opengis.net/kml/2.2">',
        "<Document>",
        f"  <name>{name}</name>",
        '  <Style id="poly_style">',
        "    <LineStyle><color>ff000000</color><width>0.5</width></LineStyle>",
        f"    <PolyStyle><color>{kml_color}</color></PolyStyle>",
        "  </Style>",
    ]
    for _, row in gdf_layer.iterrows():
        sid = row.get("subtile_id", "")
        dv2 = row.get("delta_v2", float("nan"))
        fb = row.get("frac_built", float("nan"))
        dv2_s = f"{dv2:.4f}" if pd.notna(dv2) else "N/A"
        fb_s = f"{fb:.4f}" if pd.notna(fb) else "N/A"
        desc = (
            "<![CDATA["
            f"<b>ID:</b> {sid}<br/>"
            f'<b>Tile:</b> {row.get("tile_id", "")}<br/>'
            f'<b>Comuna:</b> {row.get("comuna", "")}<br/>'
            f"<b>delta_v2:</b> {dv2_s}<br/>"
            f"<b>frac_built:</b> {fb_s}"
            "]]>"
        )
        for ring_coords in _geom_to_coords(row.geometry):
            lines += [
                "  <Placemark>",
                f"    <name>{sid}</name>",
                f"    <description>{desc}</description>",
                "    <styleUrl>#poly_style</styleUrl>",
                "    <Polygon><outerBoundaryIs><LinearRing>",
                f"      <coordinates>{ring_coords}</coordinates>",
                "    </LinearRing></outerBoundaryIs></Polygon>",
                "  </Placemark>",
            ]
    lines += ["</Document>", "</kml>"]
    return "\n".join(lines)


def exportar(gdf_final: gpd.GeoDataFrame, cfg: dict, log) -> list[str]:
    """
    Exporta GPKG y KMZ a las rutas definidas en cfg["rutas"].
    Retorna la lista de rutas generadas (para el resumen final en pantalla).
    """
    anio_fin = cfg["anios"]["fin"]
    rutas_generadas = []

    out_gpkg = Path(cfg["rutas"]["entrega_gpkg"].format(anio_fin=anio_fin))
    out_gpkg.parent.mkdir(parents=True, exist_ok=True)
    gdf_final.to_file(str(out_gpkg), driver="GPKG")
    log.info(f"GPKG exportado: {out_gpkg}")
    rutas_generadas.append(str(out_gpkg))

    out_kmz = Path(cfg["rutas"]["entrega_kmz"].format(anio_fin=anio_fin))
    out_kmz.parent.mkdir(parents=True, exist_ok=True)
    gdf_wgs = gdf_final.to_crs("EPSG:4326") if gdf_final.crs.to_epsg() != 4326 else gdf_final
    with zipfile.ZipFile(str(out_kmz), "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "alerta_de_cambio.kml",
            _build_kml(gdf_wgs, "Alerta de cambio", ALERTA_COLOR, ALERTA_ALPHA),
        )
    log.info(f"KMZ exportado: {out_kmz}")
    rutas_generadas.append(str(out_kmz))

    return rutas_generadas
