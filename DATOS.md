# Datos que no están en git tracking normal

Este repo versiona código, config y documentación. Los datos se dividen en
dos categorías según si se pueden regenerar o no,

## 1. NO reproducibles — requieren preservación permanente

Estos archivos **no se pueden recrear** corriendo el pipeline de nuevo (no
vienen de una descarga GEE ni de un re-entrenamiento trivial). Si se
pierden, se pierde el punto de partida del proyecto.

| Dato | Ruta | Tamaño | Estado | Por qué no es reproducible |
|---|---|---|---|---|
| Capa base Miranda (cicatrices de incendios 1985-2017) | `incendios/hexGrid_200m_incendiosValpo.gpkg` | 4.6 MB | ✅ **versionada en git** (chica, se sube tal cual) | Recopilación histórica original (Miranda et al.); no se descarga de MODIS/GEE ni se recalcula — es un insumo externo al pipeline, ver `incendios/docs/METODOLOGIA.md` |
| Modelo XGBoost en producción | `cambio_urbano/models/model_xgb_norm_v2.pkl` | 8.5 MB | ⚠️ gitignorado — ✅ **respaldado en Zenodo** (ver abajo) | Resultado de un entrenamiento con dataset y normalización específicos (nb35, `geoai-valpo/wip-experiments/`); recrearlo requiere reconstruir el dataset de entrenamiento completo, no solo correr un script |
| Modelos archivados (v1, v3) | `cambio_urbano/models/model_xgb_2018_v1.pkl`, `model_xgb_norm_v3_lulc.pkl` | 7.7 MB + 8.2 MB | ⚠️ gitignorados — mismo caso que v2, menor prioridad (no están en producción) | Idem — archivados solo como referencia histórica de la comparación v1/v2/v3 |

### Respaldo en Zenodo

El modelo XGBoost en producción (`model_xgb_norm_v2.pkl`) y la capa base
Miranda (`incendios/hexGrid_200m_incendiosValpo.gpkg` — ya versionada en
este repo, pero también respaldada acá como copia de seguridad adicional)
están depositados en Zenodo con DOI:

**DOI:** https://doi.org/10.5281/zenodo.21351448

**Cita:**
> Vera Villa, C. & Aguirre, P. (2026). GeoAI Valparaíso - Modelo XGBoost v2 y
> datos base para detección de cambio urbano e incendios [Dataset]. Zenodo.
> https://doi.org/10.5281/zenodo.21351448

**Instrucción de descarga**: bajar `model_xgb_norm_v2.pkl` desde
https://doi.org/10.5281/zenodo.21351448 y colocarlo en
`cambio_urbano/models/model_xgb_norm_v2.pkl` (crear la carpeta `models/` si
no existe). Sin este archivo, `cambio_urbano/run_pipeline.py` no puede
correr la etapa de inferencia.

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


## Compartido

| Dato | Ruta | Tamaño | Notas |
|---|---|---|---|
| AOI (5 comunas) | `comun/gdf_comunas.gpkg` | ~848 KB | ✅ versionado en git |

## Credenciales

Ninguno de los dos pipelines guarda credenciales en el repo. La
autenticación a Google Earth Engine se hace vía `earthengine authenticate`
en la máquina antes de correr `run_pipeline.py` (sin `--skip-descarga`).
