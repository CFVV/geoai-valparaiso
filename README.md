# GeoAI Valparaíso

Repo unificado de los dos pipelines de detección geoespacial desarrollados para
la cuenca de Valparaíso: expansión de asentamientos informales y
recurrencia de incendios forestales.

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
├── docs/                # guía de traspaso general (pendiente)
├── DATOS.md             # dónde viven los datos que no están en git
├── requirements.txt
└── .gitignore
```

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
  `README.md` y `docs/METODOLOGIA.md` ya incluidos. **No tiene tests
  todavía** — la carpeta `tests/` quedó vacía (con `.gitkeep`), pendiente.
- **incendios/**: código completo y funcional, con 1 test de idempotencia
  (PASSED) y documentación (`README.md`, `docs/METODOLOGIA.md`) ya
  incluidos. Verificado con `--skip-descarga` → Nfires total 1985-2026 =
  7,830.
- Ambos pipelines comparten `comun/logger.py` (idéntico en ambos orígenes) y
  `comun/gdf_comunas.gpkg` (mismo AOI, verificado geométrica y
  atributivamente idéntico entre ambos orígenes).
- Este repo es **independiente** de `geoai-valpo/` y `MLxWildfires_valparaiso/`
  (los repos/carpetas de trabajo originales, que se dejaron intactos). No los
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
