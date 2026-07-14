#!/usr/bin/env python3
"""
Pipeline GeoAI Valparaíso — detección de expansión de asentamientos informales
=================================================================================

USO BÁSICO (uso normal, corrida completa de un año nuevo):

    python run_pipeline.py

FLAGS OPCIONALES (red de seguridad, no uso normal):

    --skip-descarga     No vuelve a descargar mosaicos S2 (usa lo que ya hay en disco).
                         Útil si el pipeline falló DESPUÉS de la descarga y no quieres
                         esperar de nuevo los ~15-40 min que toma bajar de GEE.

    --skip-lulc          No vuelve a descargar/procesar LULC (usa lo que ya hay en disco).

Todos los parámetros (años, tiles, umbrales, rutas) se editan en config.yaml.
NO es necesario tocar este archivo para correr el pipeline en un año nuevo.

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

# Los módulos reales de cada etapa viven en pipeline/. Se importan acá para que
# un error de import (ej. falta una librería) se reporte de forma clara arriba,
# antes de empezar a procesar nada.
try:
    from pipeline import descarga_s2
    from pipeline import descarga_lulc_modis
    from pipeline import inferencia
    from pipeline import deteccion
    from pipeline import postproceso_lulc
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
        description="Pipeline de detección de expansión de asentamientos informales — GeoAI Valparaíso"
    )
    parser.add_argument(
        "--skip-descarga", action="store_true",
        help="No descargar mosaicos S2 nuevos; usar los que ya están en disco.",
    )
    parser.add_argument(
        "--skip-lulc", action="store_true",
        help="No descargar/procesar LULC nuevo; usar el que ya está en disco.",
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
    saltar_lulc = args.skip_lulc or cfg["ejecucion"].get("saltar_lulc", False)

    log.info("=" * 70)
    log.info(f"PIPELINE GEOAI VALPARAÍSO — corrida para año {anio_fin}")
    log.info("=" * 70)

    t0 = time.time()

    # -------------------------------------------------------------------
    # PASO 1 — Descarga de mosaicos Sentinel-2
    # -------------------------------------------------------------------
    if saltar_descarga:
        log.info("[1/6] Descarga S2 — SALTADA (--skip-descarga). Usando mosaicos en disco.")
    else:
        log.info(f"[1/6] Descargando mosaicos Sentinel-2 para {len(cfg['tiles'])} tiles...")
        try:
            resultado_descarga = descarga_s2.descargar(cfg, log)
            if resultado_descarga.get("mosaico_incompleto"):
                log.warn(
                    f"El mosaico {anio_fin} está INCOMPLETO — "
                    f"solo cubre hasta {resultado_descarga['ultimo_mes_cubierto']}. "
                    "Los resultados de este año deben interpretarse con cautela."
                )
        except Exception:
            log.error("Falló la descarga de Sentinel-2 / autenticación GEE.")
            log.error(traceback.format_exc())
            log.resumen_final(exito=False)
            sys.exit(1)

    # -------------------------------------------------------------------
    # PASO 2 — Descarga de LULC + MODIS (incendio)
    # -------------------------------------------------------------------
    if saltar_lulc:
        log.info("[2/6] Descarga LULC/MODIS — SALTADA (--skip-lulc). Usando datos en disco.")
        lulc_anio_usado = None
    else:
        log.info("[2/6] Descargando/verificando LULC y área quemada MODIS...")
        try:
            resultado_lulc = descarga_lulc_modis.descargar(cfg, log)
            lulc_anio_usado = resultado_lulc["anio_lulc_usado"]
            if lulc_anio_usado != anio_fin:
                log.warn(
                    f"LULC {anio_fin} no está publicado todavía en ESRI. "
                    f"Se usa LULC {lulc_anio_usado} (el más reciente disponible) como proxy "
                    "para el postprocesamiento de confianza. Este año queda marcado en los "
                    "metadatos del entregable."
                )
        except Exception:
            log.error("Falló la descarga de LULC/MODIS.")
            log.error(traceback.format_exc())
            log.resumen_final(exito=False)
            sys.exit(1)

    # -------------------------------------------------------------------
    # PASO 3 — Validación de integridad de datos de entrada
    # -------------------------------------------------------------------
    log.info("[3/6] Verificando integridad de mosaicos descargados...")
    try:
        problemas = validaciones.verificar_mosaicos(cfg, log)
        if problemas:
            for p in problemas:
                log.warn(p)
    except Exception:
        log.error("Falló la verificación de integridad de mosaicos.")
        log.error(traceback.format_exc())
        log.resumen_final(exito=False)
        sys.exit(1)

    # -------------------------------------------------------------------
    # PASO 4 — Inferencia (XGBoost v2 + normalización P2-P98)
    # -------------------------------------------------------------------
    log.info("[4/6] Corriendo inferencia del modelo...")
    try:
        resultado_inferencia = inferencia.correr(cfg, log)
    except FileNotFoundError:
        log.error(f"No se encontró el modelo en {cfg['modelo']['ruta']}. Revisa la ruta en config.yaml.")
        log.resumen_final(exito=False)
        sys.exit(1)
    except Exception:
        log.error("Falló la inferencia del modelo.")
        log.error(traceback.format_exc())
        log.resumen_final(exito=False)
        sys.exit(1)

    # -------------------------------------------------------------------
    # PASO 5 — Detección de cambio + filtros (incendio, marítimo)
    # -------------------------------------------------------------------
    log.info("[5/6] Aplicando umbral de detección y filtros...")
    try:
        gdf_detecciones = deteccion.detectar(resultado_inferencia, cfg, log)
        if len(gdf_detecciones) == 0:
            log.warn(
                "0 detecciones en esta corrida. Esto puede ser correcto (sin cambio real) "
                "o señal de un error silencioso (ej. mosaico vacío). Revisar antes de publicar."
            )
    except Exception:
        log.error("Falló la etapa de detección.")
        log.error(traceback.format_exc())
        log.resumen_final(exito=False)
        sys.exit(1)

    # -------------------------------------------------------------------
    # PASO 6 — Postprocesamiento LULC + generación de entregables
    # -------------------------------------------------------------------
    log.info("[6/6] Generando categoría 'Alerta de cambio' y entregables finales...")
    try:
        gdf_final = postproceso_lulc.clasificar(gdf_detecciones, cfg, log, lulc_anio_usado=lulc_anio_usado)
        rutas_generadas = postproceso_lulc.exportar(gdf_final, cfg, log)
    except Exception:
        log.error("Falló el postprocesamiento / exportación de entregables.")
        log.error(traceback.format_exc())
        log.resumen_final(exito=False)
        sys.exit(1)

    # -------------------------------------------------------------------
    # Resumen final
    # -------------------------------------------------------------------
    duracion_min = (time.time() - t0) / 60
    log.info("-" * 70)
    log.info(f"✅ Pipeline completado en {duracion_min:.1f} min.")
    log.info(f"   Alertas de cambio generadas: {len(gdf_final)}")
    for r in rutas_generadas:
        log.info(f"   → {r}")
    log.resumen_final(exito=True)


if __name__ == "__main__":
    main()
