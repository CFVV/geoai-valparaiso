"""
Chequeos de integridad antes y después de construir el hexgrid.

Chequeos implementados:
1. La capa base de Miranda existe y tiene columna 'Nfires' poblada (sin nulos).
2. Hay TIFs MODIS para el rango [modis_inicio, anio_fin] — avisa qué meses faltan.
3. Si anio_fin es el año en curso, avisa que puede estar incompleto y hasta
   qué mes hay datos en disco (igual que el manejo de mosaico incompleto del
   pipeline de campamentos).
4. El resultado final no queda vacío y Nfires_total >= Nfires_base (nunca
   puede bajar, porque solo se suma).
"""

import datetime
import re
from pathlib import Path

import geopandas as gpd

NOMBRE_TIF_RE = re.compile(r"MODIS_(\d{4})-(\d{1,2})-01\.tif$")


def verificar_capa_base(cfg: dict) -> None:
    """Lanza excepción si la capa base no existe o no tiene Nfires poblado."""
    ruta_base = Path(cfg["hexgrid"]["base_miranda"])
    if not ruta_base.exists():
        raise FileNotFoundError(
            f"No se encontró la capa base de Miranda en {ruta_base}. "
            "Este archivo es el punto de partida estático y no se genera "
            "con este pipeline — sin él no se puede continuar."
        )

    gdf = gpd.read_file(ruta_base)
    if "Nfires" not in gdf.columns:
        raise ValueError(f"La capa base {ruta_base} no tiene columna 'Nfires'.")
    if gdf["Nfires"].isna().any():
        raise ValueError(f"La capa base {ruta_base} tiene valores nulos en 'Nfires'.")
    if len(gdf) == 0:
        raise ValueError(f"La capa base {ruta_base} está vacía.")


def verificar_tifs_disponibles(cfg: dict, log) -> list[str]:
    """Retorna lista de strings (advertencias) sobre meses faltantes en el rango pedido."""
    problemas = []
    carpeta_tifs = Path(cfg["rutas"]["modis_tifs"])
    anio_inicio = cfg["anios"]["modis_inicio"]
    anio_fin = cfg["anios"]["fin"]

    if not carpeta_tifs.exists():
        problemas.append(f"No existe la carpeta de TIFs MODIS {carpeta_tifs}.")
        return problemas

    meses_presentes = set()
    for f in carpeta_tifs.glob("MODIS_*.tif"):
        m = NOMBRE_TIF_RE.search(f.name)
        if m:
            meses_presentes.add((int(m.group(1)), int(m.group(2))))

    hoy = datetime.date.today()
    faltantes = []
    for year in range(anio_inicio, anio_fin + 1):
        ultimo_mes = 12
        if year == hoy.year:
            ultimo_mes = hoy.month  # no esperar meses futuros del año en curso
        for month in range(1, ultimo_mes + 1):
            if (year, month) not in meses_presentes:
                faltantes.append(f"{year}-{month:02d}")

    if faltantes:
        problemas.append(
            f"Faltan {len(faltantes)} mes(es) de TIFs MODIS en el rango solicitado: "
            f"{', '.join(faltantes[:12])}{' ...' if len(faltantes) > 12 else ''}. "
            "Corre sin --skip-descarga para completarlos."
        )

    if anio_fin == hoy.year:
        meses_del_anio = sorted(mo for (yr, mo) in meses_presentes if yr == anio_fin)
        ultimo_disponible = max(meses_del_anio) if meses_del_anio else None
        if ultimo_disponible and ultimo_disponible < 12:
            problemas.append(
                f"El año {anio_fin} está en curso: solo hay datos MODIS hasta el mes "
                f"{ultimo_disponible:02d}. El conteo de Nfires de {anio_fin} quedará "
                "incompleto hasta que termine el año."
            )

    return problemas


def verificar_resultado(hgrid: gpd.GeoDataFrame, nfires_base_total: int) -> list[str]:
    """Retorna lista de strings (advertencias/errores) sobre el resultado final."""
    problemas = []
    if len(hgrid) == 0:
        problemas.append("El hexgrid resultante está VACÍO.")
        return problemas

    total_final = int(hgrid["Nfires"].sum())
    if total_final < nfires_base_total:
        problemas.append(
            f"Nfires_total ({total_final}) es MENOR que Nfires_base ({nfires_base_total}). "
            "Esto no debería pasar nunca (solo se suma sobre la base) — revisar la lógica."
        )
    return problemas
