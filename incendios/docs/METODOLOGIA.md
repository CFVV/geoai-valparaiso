# Metodología — Recurrencia de Incendios (hexgrid MODIS 1985-2026)

## Fuentes

1. **Miranda et al. (1985-2017)** — cicatrices de incendios históricas
   (`data/FireScars_Miranda/Fire Scars Summary...`), agregadas a una grilla
   hexagonal mediante un `sjoin` + conteo (`FireID` por hexágono). Este
   proceso se corrió UNA VEZ (ver `codes/fireScars.ipynb`, celdas 0-19) y
   produjo el archivo `hexGrid_200m_incendiosValpo.gpkg`. **Este pipeline
   nunca recalcula esta capa** — es el punto de partida estático, de solo
   lectura.

2. **MODIS MCD64A1 (2018-presente)** — banda `BurnDate` (día juliano de quema
   por píxel, 500 m), descargada mes a mes vía Google Earth Engine
   (`codes/1.MODIS_download_burntArea.ipynb`). El pipeline nuevo (módulo
   `pipeline/descarga_modis.py`) reproduce esta descarga con dos correcciones
   (ver sección "Correcciones respecto al código original").

## Corrección de nombre: "200m" → "250m"

El archivo histórico `hexGrid_200m_incendiosValpo.gpkg` tiene un nombre que
no corresponde al tamaño real del hexágono. Verificado dos veces:

- **Geométricamente**: reproyectando la capa a EPSG:32719, el área de un
  hexágono completo (no recortado por el borde del AOI) es constante =
  162,379.76 m², que corresponde exactamente a `(3√3/2)·s²` con `s = 250 m`
  (lado del hexágono regular).
- **En el código fuente**: `codes/fireScars.ipynb`, celda 15, llama
  `create_hexa_grid(..., cellsize_m=size, ...)` con `size = 250`.

**Decisión**: no se renombra el archivo histórico (es un archivo ya
publicado/referenciado). El pipeline nuevo:
- **LEE** la capa base desde su nombre existente `hexGrid_200m_incendiosValpo.gpkg`.
- **ESCRIBE** la salida nueva con el nombre corregido
  `hexGrid_250m_incendiosValpo_1985_{anio_fin}.gpkg` (+ `.geojson`).

## Semántica de conteo de `Nfires`

Cada mes (desde 2018) con píxeles MODIS `BurnDate > 0` se polygoniza (agrupando
píxeles contiguos del mismo valor de día juliano — mismo algoritmo que
`gdal_polygonize.py`, reemplazado acá por `rasterio.features.shapes` para no
depender del binario GDAL externo). Por cada polígono quemado de ese mes, se
hace overlay contra el hexgrid y se suma **+1 a `Nfires`** por cada hexágono
que intersecte ese polígono.

Importante: esto significa que, si en un mismo mes hay quemas en varios días
distintos que generan varios polígonos disjuntos superpuestos sobre el mismo
hexágono, ese hexágono puede sumar **más de +1 en ese mes** (una vez por cada
polígono que lo toca, no una vez por mes). Esto no es una simplificación
nuestra: es el comportamiento real del código original
(`codes/2.MODIS_makeMap.ipynb`, celda 3 — `for gid in match.grid_id: ...
Nfires = val+1`, donde `match` viene de un `overlay`, no de un `sjoin`
deduplicado). Se verificó reproduciendo exactamente los totales de los
entregables ya publicados:

| Corte | Nfires total (suma) |
|---|---|
| Base Miranda (1985-2017) | 4,562 |
| 1985-2025 | 7,796 |
| 1985-2026 (parcial, ene-feb) | 7,830 (histórico — corregido a 7,834, ver nota abajo) |

La celda 7 del mismo notebook (`match.at[i,'Nfires']=1`) corre **después**
del export (celda 6) y no tiene efecto en ningún entregable — es código
abandonado, no se porta.

### Nota sobre el Nfires de referencia: 7,834 (no 7,830)

El valor 7,830 (1985-2026, parcial ene-feb) fue el primer total reproducido
con el pipeline nuevo, pero estaba **subcontado en 1 píxel MODIS / 4
hexágonos**. Causa: el script exploratorio original
(`codes/1.MODIS_download_burntArea.ipynb`) descargaba cada TIF mensual con un
ROI (`ee.Geometry.Rectangle`) que nunca quedó documentado ni atado al AOI
oficial — cubría de más hacia el oeste/sur pero **no llegaba a cubrir el
borde este del AOI actual** (`comun/gdf_comunas.gpkg` disuelto), por una
franja de ~870 m.

`pipeline/descarga_modis.py` (el módulo de producción) calcula el ROI
directamente desde `aoi.to_crs(4326).total_bounds`, así que cubre el AOI
completo. Al re-descargar el histórico con este pipeline se detectó que el
mes **2019-07** tenía en esa franja este un píxel `BurnDate` legítimo
(DN=188, día juliano 188 = 7 de julio de 2019) que el ROI viejo nunca pidió a
GEE. Ese píxel intersecta 4 hexágonos que antes daban `Nfires=0` y ahora dan
`Nfires=1`. Se verificó que es un caso aislado: de 45 meses re-descargados
con ambos ROI (viejo y nuevo) para comparar, solo 2019-07 tiene esta
diferencia; los otros 44 son pixel-idénticos en la zona de solape.

**El valor de referencia correcto y reproducible con el pipeline actual es
Nfires = 7,834** (1985-2026, parcial ene-feb). El archivo `MODIS/` en disco
quedó normalizado: todos los TIFs usan el ROI completo (calculado desde el
AOI actual), sin remanentes del ROI viejo.

Nota aparte: el corte 1985-2025 (7,796) no se recalculó — si se necesita ese
entregable a futuro, debería re-verificarse por el mismo motivo (2019 cae
dentro de ese rango).

## Correcciones respecto al código original

1. **Bug de rango de meses** (`codes/1.MODIS_download_burntArea.ipynb`, celda 5):
   el original itera `for month in np.arange(1,12,1)`, que genera meses 1..11
   y se salta diciembre. El pipeline nuevo itera 1..12 inclusive, con manejo
   correcto de rollover de año (diciembre → enero del año siguiente) para
   calcular la fecha de fin del filtro GEE.
2. **Nombre de archivo no normalizado**: el original nombra
   `MODIS_%s-%s-01.tif % (year, month)` sin cero a la izquierda, lo que
   produjo duplicados en `codes/MODIS/` (ej. `MODIS_2025-1-01.tif` y
   `MODIS_2025-01-01.tif` para el mismo mes). El pipeline nuevo siempre nombra
   `MODIS_{AAAA}-{MM:02d}-01.tif`.
3. **`fire_MODIS/` no se reutiliza como caché**: en `codes/`, esa carpeta es
   una polygonización parcial/desactualizada (la celda que la genera solo
   procesaba `MODIS/*2024*.tif` en su último estado). El pipeline nuevo
   repolygoniza todos los TIFs del rango solicitado desde cero en cada
   corrida, directamente desde `rutas.modis_tifs`.
4. **`gdal_polygonize.py` vía `os.system`** → reemplazado por
   `rasterio.features.shapes` (sin dependencia de binario GDAL externo).
   Verificado que produce sumas de `Nfires` idénticas al original.

## Idempotencia

`pipeline/construir_hexgrid.py` no mantiene estado incremental: cada corrida
parte de una copia fresca de la capa base de Miranda y reconstruye el
acumulado completo leyendo los TIFs en disco desde cero. Correr el pipeline
dos veces con el mismo `anios.fin` sobre los mismos TIFs produce exactamente
el mismo resultado — verificado en `tests/test_idempotencia.py`.

## Flujos que NO alimentan este pipeline

`codes/get_dNBR.ipynb`, `codes/S2_burntArea.ipynb`,
`codes/burned_area_functions.py` y las funciones de severidad de
`codes/S2_functions.py` (`get_nbr`, `compute_dnbr`, etc.) implementan un
análisis de **severidad** de incendios con Sentinel-2/dNBR, un flujo
completamente aparte. No se referencian ni se importan desde este pipeline.
