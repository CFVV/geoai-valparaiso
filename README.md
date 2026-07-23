# GeoAI Valparaíso

Repo unificado de los dos pipelines de detección geoespacial desarrollados para
la cuenca de Valparaíso: **expansión de asentamientos informales y
recurrencia de incendios forestales.**

El resultado de este proyecto es parte de la **plataforma SIRVAL**. La cual comprende un sistema computacional de acceso público orientado a distintos niveles de usuario, especialmente tomadores de decisión, con el objetivo de dar soporte a análisis preliminares de riesgo en el territorio de las comunas del Gran Valparaíso. Para ello integra datos georreferenciados de exposición y expansión urbana (formal e informal) con registros históricos y modelamiento de amenazas naturales como terremotos, tsunamis, incendios forestales y remociones en masa, generados a partir del análisis automatizado de cartografía histórica, imágenes satelitales y aerofotogrametría por dron, en constante actualización. 

**SIRVAL** permite el monitoreo continuo del riesgo territorial y de esta manera dar soporte tanto a la planificación territorial como la gestión del riesgo y la emergencia en el Gran Valparaíso.
[Plataforma SIRVAL](https://experience.arcgis.com/experience/771e1d79452f40a8ace331fdcb841dad/page/P%C3%A1gina)

## Estructura

```
geoai-valparaiso/
├── comun/               # código compartido por ambos pipelines
│   ├── logger.py        # logger simple (pantalla + archivo)
│   └── gdf_comunas.gpkg # AOI compartido (5 comunas: Valparaíso, Concón, Viña,
│                        #   Quilpué, Villa Alemana)
├── cambio_urbano/       # detección de expansión de asentamientos informales
│   ├── README.md         # guía rápida de uso
│   ├── config.yaml      # único archivo a editar para correr un año nuevo
│   ├── run_pipeline.py
│   ├── pipeline/
│   ├── models/          # modelo XGBoost entrenado (gitignored, ver DATOS.md)
│   ├── s2_mosaics/       # mosaicos Sentinel-2 (gitignored, ver DATOS.md)
│   ├── lulc_io/          # LULC ESRI 10m (gitignored, ver DATOS.md)
│   ├── outputs/          # resultados + caché de inferencia (gitignored)
│   ├── tests/            # vacío — validación extra futura
│   └── docs/METODOLOGIA.md
├── incendios/           # recurrencia de incendios (hexgrid MODIS 1985-2026)
│   ├── config.yaml
│   ├── run_pipeline.py
│   ├── pipeline/
│   ├── MODIS/            # TIFs MCD64A1 descargados (gitignored, ver DATOS.md)
│   ├── hexGrid_200m_incendiosValpo.gpkg  # capa base Miranda 1985-2017 — NO reproducible, versionada en git (ver DATOS.md)
│   ├── outputs/
│   ├── tests/
│   ├── docs/
│   └── README.md
├── docs/                # guía de traspaso 
├── DATOS.md             # dónde viven los datos que no están en git
├── requirements.txt     # instalación vía pip (Mac/Linux)
├── environment.yml      # instalación vía conda (recomendada en Windows)
└── .gitignore
```

## Instalación

**Mac/Linux:**
```bash
pip install -r requirements.txt
```

**Windows:** el stack geoespacial (`geopandas`/`rasterio`/`fiona`/`pyproj`, que
dependen de GDAL) suele fallar al compilar vía pip. Se recomienda conda:
```bash
conda env create -f environment.yml
conda activate sirval
```
`environment.yml` fija `python=3.10` (Anaconda instala 3.13 por defecto, que
puede dar problemas con el stack geoespacial) y trae el stack geoespacial
precompilado desde `conda-forge`, evitando la compilación de GDAL.

En Mac/Linux también se puede usar `environment.yml` si se prefiere conda a
pip — funciona igual en las tres plataformas.

**Importante en cualquier plataforma con conda**: hay que activar el entorno
(`conda activate sirval`) en **cada terminal nueva** antes de correr los
pipelines — no queda activado permanentemente.

## Cómo correr cada pipeline

Cada pipeline se corre parado en su propia carpeta:

```bash
cd cambio_urbano/
python run_pipeline.py --skip-descarga --skip-lulc   # usa datos ya en disco
python run_pipeline.py                               # corrida completa (descarga GEE)

cd ../incendios/
python run_pipeline.py --skip-descarga
python run_pipeline.py
```

Todos los parámetros (años, tiles, umbrales, rutas) se editan en el
`config.yaml` de cada pipeline — no hace falta tocar código para correr un
año nuevo.

## Estado del proyecto (2026-07-14, migración al repo unificado)

- **cambio_urbano/**: código completo y funcional, verificado con
  `--skip-descarga --skip-lulc` → 222 "Alerta de cambio" generadas.
  `README.md` y `docs/METODOLOGIA.md` ya incluidos. No se incluyen  tests,
   la carpeta `tests/` quedó vacía (con `.gitkeep`), pendiente.
- **incendios/**: código completo y funcional, con 1 test de idempotencia
  (PASSED) y documentación (`README.md`, `docs/METODOLOGIA.md`) ya
  incluidos. Verificado con `--skip-descarga` → Nfires total 1985-2026 =
  7,834 (corregido desde 7,830 — ver `docs/METODOLOGIA.md`, sección
  "Nota sobre el Nfires de referencia").
- Ambos pipelines comparten `comun/logger.py` (idéntico en ambos orígenes) y
  `comun/gdf_comunas.gpkg` (mismo AOI, verificado geométrica y
  atributivamente idéntico entre ambos orígenes).
- Este repo es **independiente** de los códugos de desarrollo y trabajo originales. No los
  referencia ni depende de ellos.
- El modelo `.pkl` de cambio_urbano y la capa Miranda están respaldados en
  Zenodo (DOI [10.5281/zenodo.21351448](https://doi.org/10.5281/zenodo.21351448))
  — ver `DATOS.md` para el detalle completo de qué descargar y dónde colocarlo.

## Metodología

- `cambio_urbano/`: ver [`cambio_urbano/docs/METODOLOGIA.md`](cambio_urbano/docs/METODOLOGIA.md).
- `incendios/`: ver [`incendios/docs/METODOLOGIA.md`](incendios/docs/METODOLOGIA.md).

## Cómo citar

Si usas el modelo o los datos base de este proyecto, cita el dataset de
Zenodo:

> Vera Villa, C. & Aguirre, P. (2026). GeoAI Valparaíso - Modelo XGBoost v2 y
> datos base para detección de cambio urbano e incendios [Dataset]. Zenodo.
> https://doi.org/10.5281/zenodo.21351448

### Fuentes de datos y atribución
Capa histórica de recurrencia de incendios (1985–2017)
El pipeline de incendios se construye a partir de una capa base histórica de cicatrices de incendios que no fue generada por este proyecto, sino que deriva de la Base de Datos de Cicatrices de Incendios de Chile (Landscape Fire Scars Database) de Miranda et al. La capa fue obtenida desde el portal Datos para Resiliencia (ITREND). Cualquier uso de los resultados de incendios de este proyecto debe citar las siguientes fuentes originales:

#### Artículo metodológico:

> Miranda, A., Mentler, R., Moletto-Lobos, Í., Alfaro, G., Aliaga, L., Balbontín, D., Barraza, M., Baumbach, S., Calderón, P., Cárdenas, F., Castillo, I., Contreras, G., de la Barra, F., Galleguillos, M., González, M. E.,
>  Hormazábal, C., Lara, A., Mancilla, I., Muñoz, F., Oyarce, C., Pantoja, F., Ramírez, R., & Urrutia, V. (2022). The Landscape Fire Scars Database: mapping historical burned area and fire severity in Chile. Earth System Science
> Data, 14(8), 3599–3613. https://doi.org/10.5194/essd-14-3599-2022

#### Conjunto de datos original:

> Miranda, A., Mentler, R., Moletto-Lobos, I., et al. (2022). Fire Scars: remotely sensed historical burned area and fire severity in Chile between 1984–2018 [Data set]. PANGAEA. https://doi.org/10.1594/PANGAEA.941127

#### Fuente de descarga utilizada en este proyecto (Datos para Resiliencia / ITREND):

> Miranda, A., Mentler, R., Moletto-Lobos, Í., et al. (2024). Cicatrices de incendios — Resumen (V3) [Data set]. Datos para Resiliencia (ITREND). https://doi.org/10.71578/XAZAKP

### Otras fuentes de datos utilizadas
- Sentinel-2 (Copernicus / ESA), vía Google Earth Engine.
- MODIS MCD64A1 (NASA LP DAAC), producto de área quemada, vía Google Earth Engine.
- ESRI 10m Land Cover Time Series, vía Google Earth Engine.
- Catastro de campamentos de TECHO-Chile (usado como referencia de validación para el pipeline de cambio urbano).


