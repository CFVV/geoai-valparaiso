"""
Descarga de área quemada MODIS (MCD64A1, banda BurnDate) por mes.

Portado desde codes/1.MODIS_download_burntArea.ipynb (celda 5), con dos
correcciones sobre el original:

1. BUG DE RANGO DE MESES: el notebook original itera
   `for month in np.arange(1,12,1)` → genera meses 1..11 y SE SALTA DICIEMBRE.
   Acá se itera 1..12 inclusive, calculando la fecha de fin con manejo de
   rollover de año (diciembre → enero del año siguiente).

2. NOMBRE NORMALIZADO: el notebook original nombra el archivo con
   '%s-%s-01' % (year, month) sin cero a la izquierda, lo que en codes/MODIS/
   produjo duplicados como "MODIS_2025-1-01.tif" y "MODIS_2025-01-01.tif" para
   el mismo mes. Acá el nombre siempre es MODIS_{AAAA}-{MM:02d}-01.tif.
"""

from pathlib import Path


def _rango_fecha(year: int, month: int) -> tuple[str, str]:
    inicio = f"{year}-{month:02d}-01"
    if month == 12:
        fin = f"{year + 1}-01-01"
    else:
        fin = f"{year}-{month + 1:02d}-01"
    return inicio, fin


def descargar(cfg: dict, log) -> dict:
    """
    Descarga los TIFs MODIS faltantes para el rango [anios.modis_inicio, anios.fin].
    Si un TIF normalizado ya existe en disco, no se vuelve a descargar (skip individual).

    Retorna dict con:
        {
            "descargados": int,
            "saltados_ya_existian": int,
            "meses_sin_datos": [str, ...],  # meses dentro del rango sin imágenes en GEE
        }
    """
    import ee
    import geemap
    import geopandas as gpd

    from comun.gee_utils import resolver_proyecto_gee

    ee.Initialize(project=resolver_proyecto_gee(cfg))

    aoi = gpd.read_file(cfg["aoi"]["poligono"]).dissolve()
    fc = geemap.geopandas_to_ee(aoi)
    b = aoi.to_crs(4326).total_bounds
    roi = ee.Geometry.Rectangle([float(b[0]), float(b[1]), float(b[2]), float(b[3])])

    out_dir = Path(cfg["rutas"]["modis_tifs"])
    out_dir.mkdir(parents=True, exist_ok=True)

    anio_inicio = cfg["anios"]["modis_inicio"]
    anio_fin = cfg["anios"]["fin"]

    descargados = 0
    saltados = 0
    meses_sin_datos = []

    for year in range(anio_inicio, anio_fin + 1):
        for month in range(1, 13):
            inicio, fin = _rango_fecha(year, month)
            nombre = f"MODIS_{year}-{month:02d}-01.tif"
            out_path = out_dir / nombre

            if out_path.exists():
                saltados += 1
                continue

            dataset = (
                ee.ImageCollection(cfg["modis"]["coleccion"])
                .filterBounds(fc)
                .filterDate(inicio, fin)
            )
            ids = dataset.aggregate_array("system:id").getInfo()
            if len(ids) == 0:
                meses_sin_datos.append(f"{year}-{month:02d}")
                log.info(f"MODIS {year}-{month:02d}: sin imágenes disponibles en GEE todavía (mes futuro o no publicado). Se salta.")
                continue

            log.info(f"MODIS {year}-{month:02d}: descargando...")
            imagen = dataset.select(cfg["modis"]["banda"]).first()
            try:
                geemap.ee_export_image(
                    imagen, filename=str(out_path), scale=cfg["modis"]["scale"],
                    region=roi, file_per_band=False, crs="EPSG:4326",
                )
                descargados += 1
            except Exception:
                log.error(f"MODIS {year}-{month:02d}: falló la descarga.")
                raise

    return {
        "descargados": descargados,
        "saltados_ya_existian": saltados,
        "meses_sin_datos": meses_sin_datos,
    }
