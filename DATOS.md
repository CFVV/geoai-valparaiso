# Datos que NO están en git tracking normal

Este repo versiona código, config y documentación. Los datos se dividen en
dos categorías según si se pueden regenerar o no — esa distinción importa
más que el tamaño a la hora de decidir dónde deben vivir.

## 1. NO reproducibles — requieren preservación permanente

Estos archivos **no se pueden recrear** corriendo el pipeline de nuevo (no
vienen de una descarga GEE ni de un re-entrenamiento trivial). Si se
pierden, se pierde el punto de partida del proyecto.

| Dato | Ruta | Tamaño | Estado | Por qué no es reproducible |
|---|---|---|---|---|
| Capa base Miranda (cicatrices de incendios 1985-2017) | `incendios/hexGrid_200m_incendiosValpo.gpkg` | 4.6 MB | ✅ **versionada en git** (chica, se sube tal cual) | Recopilación histórica original (Miranda et al.); no se descarga de MODIS/GEE ni se recalcula — es un insumo externo al pipeline, ver `incendios/docs/METODOLOGIA.md` |
| Modelo XGBoost en producción | `cambio_urbano/models/model_xgb_norm_v2.pkl` | 8.5 MB | ⚠️ **gitignorado — [PENDIENTE: subir a Zenodo/DOI]** | Resultado de un entrenamiento con dataset y normalización específicos (nb35, `geoai-valpo/wip-experiments/`); recrearlo requiere reconstruir el dataset de entrenamiento completo, no solo correr un script |
| Modelos archivados (v1, v3) | `cambio_urbano/models/model_xgb_2018_v1.pkl`, `model_xgb_norm_v3_lulc.pkl` | 7.7 MB + 8.2 MB | ⚠️ gitignorados — mismo caso que v2, menor prioridad (no están en producción) | Idem — archivados solo como referencia histórica de la comparación v1/v2/v3 |

**Acción pendiente**: subir los `.pkl` (23 MB total) a un repositorio con DOI
(Zenodo u otro) para que quien herede el proyecto (Randy) pueda obtenerlos
sin re-entrenar. Hasta que eso se resuelva, viven localmente en
`cambio_urbano/models/` en esta máquina.

## 2. Reproducibles — se regeneran o re-descargan, no se distribuyen

Estos archivos SÍ se pueden recrear corriendo el pipeline (con o sin
`--skip-descarga`). No tiene sentido preservarlos como dato permanente ni
subirlos a ningún repositorio de datos — están gitignorados y punto.

| Dato | Ruta esperada | Tamaño | Cómo se regenera |
|---|---|---|---|
| Mosaicos Sentinel-2 | `cambio_urbano/s2_mosaics/{año}/tile_{id}.tif` | ~377 MB | `pipeline/descarga_s2.py` (GEE) |
| LULC ESRI 10m | `cambio_urbano/lulc_io/{año}/lulc_tile_{id}_{año}.tif` | ~0.6 MB | `pipeline/descarga_lulc_modis.py` (GEE) |
| Caché de inferencia + entregables | `cambio_urbano/outputs/` | ~46 MB | corrida del propio pipeline |
| TIFs MODIS MCD64A1 (BurnDate) | `incendios/MODIS/MODIS_{AAAA}-{M}-01.tif` (+ `.gpkg` de polígonos por mes) | ~11.4 MB (110+110 archivos, 2017-2026) | `pipeline/descarga_modis.py` (GEE) |
| Resultados + logs | `incendios/outputs/` | ~11 MB | corrida del propio pipeline |

[PENDIENTE: definir ubicación de descarga] para quien clone el repo sin
acceso a esta máquina — hoy estos archivos solo existen localmente,
copiados desde `geoai-valpo/` y `MLxWildfires_valparaiso/` el 2026-07-14.
No requieren almacenamiento permanente porque `--skip-descarga` es solo un
atajo de conveniencia, no una dependencia real: sin ellos, el pipeline
corre igual descargando de GEE desde cero.

## Compartido

| Dato | Ruta | Tamaño | Notas |
|---|---|---|---|
| AOI (5 comunas) | `comun/gdf_comunas.gpkg` | ~848 KB | ✅ versionado en git (chico, base para ambos pipelines) |

## Credenciales

Ninguno de los dos pipelines guarda credenciales en el repo. La
autenticación a Google Earth Engine se hace vía `earthengine authenticate`
en la máquina antes de correr `run_pipeline.py` (sin `--skip-descarga`).
