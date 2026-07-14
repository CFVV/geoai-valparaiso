#!/usr/bin/env python3
"""
Pipeline de Recurrencia de Incendios — hexgrid MODIS 1985-2026
=================================================================================

USO BÁSICO (corrida completa hasta el año configurado en config.yaml):

    python run_pipeline.py

FLAGS OPCIONALES (red de seguridad, no uso normal):

    --skip-descarga     No vuelve a descargar TIFs MODIS nuevos (usa los que ya
                         están en disco en rutas.modis_tifs). Útil si ya se
                         descargó todo el rango y solo se quiere reconstruir
                         el hexgrid, o si GEE no está disponible.

Todos los parámetros (años, rutas, umbrales) se editan en config.yaml.
NO es necesario tocar este archivo para correr el pipeline con un año nuevo.

Al terminar, revisa el resumen que se imprime en pantalla y el log en
outputs/logs/. Si aparece cualquier "⚠️" o "❌", léelo antes de usar los
resultados — indica algo que requiere revisión manual.
"""

import argparse
import sys
import time
import traceback
from pathlib import Path

import yaml

# comun/ vive en la raíz del repo unificado, un nivel arriba de este pipeline.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from pipeline import descarga_modis
    from pipeline import construir_hexgrid
    from pipeline import exportar
    from pipeline import validaciones
    from comun.logger import PipelineLogger
except ImportError as e:
    print(f"❌ ERROR: falta un módulo o librería del pipeline: {e}")
    print("   Revisa que el entorno esté instalado correctamente (ver docs/METODOLOGIA.md).")
    sys.exit(1)


def cargar_config(ruta_config: str = "config.yaml") -> dict:
    ruta = Path(ruta_config)
    if not ruta.exists():
        print(f"❌ ERROR: no se encontró {ruta_config}. Este archivo es obligatorio.")
        sys.exit(1)
    with open(ruta, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main():
    parser = argparse.ArgumentParser(
        description="Pipeline de recurrencia de incendios (hexgrid MODIS 1985-2026) — cuenca de Valparaíso"
    )
    parser.add_argument(
        "--skip-descarga", action="store_true",
        help="No descargar TIFs MODIS nuevos; usar los que ya están en disco.",
    )
    parser.add_argument(
        "--config", default="config.yaml",
        help="Ruta al archivo de configuración (default: config.yaml)",
    )
    args = parser.parse_args()

    cfg = cargar_config(args.config)
    anio_fin = cfg["anios"]["fin"]
    log = PipelineLogger(cfg["rutas"]["log"].format(anio_fin=anio_fin))

    saltar_descarga = args.skip_descarga or cfg["ejecucion"].get("saltar_descarga", False)

    log.info("=" * 70)
    log.info(f"PIPELINE RECURRENCIA DE INCENDIOS — corrida 1985-{anio_fin}")
    log.info("=" * 70)

    t0 = time.time()

    # -------------------------------------------------------------------
    # PASO 1 — Validar capa base de Miranda (nunca se recalcula)
    # -------------------------------------------------------------------
    log.info("[1/4] Verificando capa base de Miranda (1985-2017)...")
    try:
        validaciones.verificar_capa_base(cfg)
    except (FileNotFoundError, ValueError) as e:
        log.error(str(e))
        log.resumen_final(exito=False)
        sys.exit(1)
    except Exception:
        log.error("Falló la verificación de la capa base de Miranda.")
        log.error(traceback.format_exc())
        log.resumen_final(exito=False)
        sys.exit(1)

    # -------------------------------------------------------------------
    # PASO 2 — Descarga de TIFs MODIS (BurnDate)
    # -------------------------------------------------------------------
    if saltar_descarga:
        log.info("[2/4] Descarga MODIS — SALTADA (--skip-descarga). Usando TIFs en disco.")
    else:
        log.info(f"[2/4] Descargando TIFs MODIS {cfg['anios']['modis_inicio']}-{anio_fin}...")
        try:
            resultado_descarga = descarga_modis.descargar(cfg, log)
            log.info(
                f"Descarga: {resultado_descarga['descargados']} nuevo(s), "
                f"{resultado_descarga['saltados_ya_existian']} ya existían."
            )
            if resultado_descarga["meses_sin_datos"]:
                log.warn(
                    f"{len(resultado_descarga['meses_sin_datos'])} mes(es) sin imágenes "
                    f"publicadas todavía en GEE: {', '.join(resultado_descarga['meses_sin_datos'])}."
                )
        except Exception:
            log.error("Falló la descarga de TIFs MODIS / autenticación GEE.")
            log.error(traceback.format_exc())
            log.resumen_final(exito=False)
            sys.exit(1)

    # -------------------------------------------------------------------
    # PASO 3 — Verificar disponibilidad de TIFs para el rango pedido
    # -------------------------------------------------------------------
    log.info("[3/4] Verificando disponibilidad de TIFs MODIS para el rango solicitado...")
    try:
        problemas = validaciones.verificar_tifs_disponibles(cfg, log)
        for p in problemas:
            log.warn(p)
    except Exception:
        log.error("Falló la verificación de TIFs disponibles.")
        log.error(traceback.format_exc())
        log.resumen_final(exito=False)
        sys.exit(1)

    # -------------------------------------------------------------------
    # PASO 4 — Construcción idempotente del hexgrid + exportación
    # -------------------------------------------------------------------
    log.info("[4/4] Construyendo hexgrid de recurrencia (base Miranda + MODIS)...")
    try:
        import geopandas as gpd
        nfires_base_total = int(gpd.read_file(cfg["hexgrid"]["base_miranda"])["Nfires"].sum())

        hgrid_final = construir_hexgrid.construir(cfg, log)

        problemas_resultado = validaciones.verificar_resultado(hgrid_final, nfires_base_total)
        hay_error_resultado = any("VACÍO" in p or "MENOR" in p for p in problemas_resultado)
        for p in problemas_resultado:
            if hay_error_resultado:
                log.error(p)
            else:
                log.warn(p)
        if hay_error_resultado:
            log.resumen_final(exito=False)
            sys.exit(1)

        rutas_generadas = exportar.exportar(hgrid_final, cfg, log)
    except Exception:
        log.error("Falló la construcción/exportación del hexgrid.")
        log.error(traceback.format_exc())
        log.resumen_final(exito=False)
        sys.exit(1)

    # -------------------------------------------------------------------
    # Resumen final
    # -------------------------------------------------------------------
    duracion_min = (time.time() - t0) / 60
    nfires_total = int(hgrid_final["Nfires"].sum())
    log.info("-" * 70)
    log.info(f"✅ Pipeline completado en {duracion_min:.1f} min.")
    log.info(f"   Nfires base (1985-2017): {nfires_base_total}")
    log.info(f"   Nfires total (1985-{anio_fin}): {nfires_total}")
    log.info(f"   Hexágonos: {len(hgrid_final)}")
    for r in rutas_generadas:
        log.info(f"   → {r}")
    log.resumen_final(exito=True)


if __name__ == "__main__":
    main()
