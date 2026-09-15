# Datos que no están en git tracking normal

Este repo versiona código, config y documentación. Los datos se dividen en
dos categorías según si se pueden regenerar o no,

## 1. NO reproducibles - requieren preservación permanente

Estos archivos **no se pueden recrear** corriendo el pipeline de nuevo (no
vienen de una descarga GEE ni de un re-entrenamiento trivial). Si se
pierden, se pierde el punto de partida del proyecto.

| Dato | Ruta | Tamaño | Estado | Por qué no es reproducible |
|---|---|---|---|---|
| Capa base Miranda (cicatrices de incendios 1985-2017) | `incendios/hexGrid_200m_incendiosValpo.gpkg` | 4.6 MB | ✅ **versionada en git**  | Recopilación histórica original (Miranda et al.); no se descarga de MODIS/GEE ni se recalcula — es un insumo externo al pipeline, ver `incendios/docs/METODOLOGIA.md` |
| Modelo XGBoost en producción | `cambio_urbano/models/model_xgb_norm_v2.pkl` | 8.5 MB | ⚠️ gitignorado — ✅ **respaldado en Zenodo** (ver abajo) | Resultado de un entrenamiento con dataset y normalización específicos; recrearlo requiere reconstruir el dataset de entrenamiento completo, no solo correr un script |
| Modelos archivados (v1, v3) | `cambio_urbano/models/model_xgb_2018_v1.pkl`, `model_xgb_norm_v3_lulc.pkl` | 7.7 MB + 8.2 MB | ⚠️ gitignorados — mismo caso que v2, menor prioridad (no están en producción) | archivados solo como referencia histórica de la comparación v1/v2/v3 |
| Tiles prioritarios (geometrías) | `cambio_urbano/data/tiles_priority.gpkg` | 308 KB | ✅ **versionada en git** | Generado en desarrollo, no por el pipeline; sin él `run_pipeline.py` no puede funcionar (necesita las geometrías de los 20 tiles) |
| Grilla de subtiles 250m | `cambio_urbano/data/subtiles_250m_change_classification.gpkg` | 2.9 MB | ✅ **versionada en git** | Grilla estática de subtiles (solo se usan `subtile_id`/`tile_id`/`geometry`); no se recalcula en cada corrida |
| Checkpoint fine-tuned de RoofNet (`best_clip_model_balanced.pth`) | `experiments/phase2-drone-vulnerability/roofnet-eval/scripts/roofnet_finetuned.pth` (symlink local) | 1.7 GB | ⚠️ gitignorado — **NO redistribuible, sin respaldo en Zenodo** (ver nota abajo) | Checkpoint de terceros (no entrenado por este proyecto); publicado por el equipo RoofNet (`Climate-Energy-and-Risk-Analytics-Lab/RoofNet` v1.0) únicamente vía un dataset de Kaggle (`kaggle.com/datasets/doubleblindreview/xbd-roof-images`) bajo licencia **xBD CC-BY-NC-SA (no comercial)** y cuenta double-blind-review; no se puede regenerar ni redistribuir desde este repo |
| Metadata de referencia RoofNet (`roofnet_metadata.csv`) | `experiments/phase2-drone-vulnerability/roofnet-eval/scripts/roofnet_metadata.csv` | 14 MB | ⚠️ gitignorado — dato de terceros | Metadata del dataset RoofNet (49.663 filas, ciudad/material/coordenadas), vendorizado dentro de los clones `roofnet/`/`roofnet_new/` (tampoco versionados, ver `roofnet-eval/FINDINGS.md` §12); no generado por este proyecto |

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

### Por qué el checkpoint de RoofNet NO tiene el mismo tratamiento

A diferencia del modelo XGBoost (propiedad de este proyecto, por eso se
puede respaldar libremente en Zenodo), el checkpoint fine-tuned de RoofNet
(`best_clip_model_balanced.pth`) es de un tercero y está licenciado
**xBD CC-BY-NC-SA (no comercial)**, distribuido solo vía un dataset de
Kaggle bajo cuenta double-blind-review. Redistribuirlo — incluso como
respaldo en Zenodo, incluso vía Git LFS — probablemente viola esos
términos, además de que este repo es público. Se mantiene **solo local**
(ver tabla arriba y `experiments/phase2-drone-vulnerability/roofnet-eval/FINDINGS.md`
§1/§1a). Quien quiera reproducir la evaluación con el checkpoint real debe
obtenerlo directamente desde Kaggle con su propia cuenta y aceptar los
términos xBD.

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
| AOI | `comun/gdf_comunas.gpkg` | ~848 KB | ✅ versionado en git |

## Credenciales

Ninguno de los dos pipelines guarda credenciales en el repo. La
autenticación a Google Earth Engine se hace vía `earthengine authenticate`
en la máquina antes de correr `run_pipeline.py` (sin `--skip-descarga`).
