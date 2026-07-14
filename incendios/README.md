# Pipeline de Recurrencia de Incendios — hexgrid MODIS 1985-2026

Reconstruye el hexgrid de recurrencia de incendios de la cuenca de
Valparaíso: capa base histórica de Miranda et al. (1985-2017) + MODIS
MCD64A1 (2018-presente).

## Uso

```bash
export GEE_PROJECT="tu-proyecto-gee"   # o edita gee.proyecto en config.yaml
python run_pipeline.py
```

Todos los parámetros (años, rutas, umbrales) se editan en `config.yaml`. No
hace falta tocar ningún script para correr con un año nuevo — solo cambiar
`anios.fin`.

### Flags

- `--skip-descarga`: no descarga TIFs MODIS nuevos, reusa los que ya están en
  disco (`rutas.modis_tifs`). Útil si ya se descargó todo el rango o si GEE
  no está disponible.

### Salida

- `outputs/hexGrid_250m_incendiosValpo_1985_{anio_fin}.gpkg` (+ `.geojson`)
- `outputs/logs/log_ejecucion_{anio_fin}.txt`

Si el log muestra cualquier `⚠️` o `❌`, revísalo antes de usar el resultado.

## Estructura

```
config.yaml              — único archivo a editar normalmente
run_pipeline.py           — punto de entrada
pipeline/
  descarga_modis.py       — descarga TIFs MODIS faltantes (BurnDate, mensual)
  construir_hexgrid.py    — lógica idempotente: base Miranda + incrementos MODIS
  exportar.py             — gpkg + geojson
  validaciones.py         — chequeos de integridad
  logger.py               — logger con ℹ️/⚠️/❌ (reusado del pipeline de campamentos)
tests/
  test_idempotencia.py    — verifica que dos corridas con el mismo anio_fin dan el mismo resultado
docs/
  METODOLOGIA.md          — fuentes, corrección de nombre 200m→250m, semántica de conteo
```

## Qué NO hace este pipeline

No toca `codes/hexGrid_200m_incendiosValpo.gpkg` (capa base, solo lectura) ni
`codes/fire_MODIS/` (caché parcial, ignorada — se repolygoniza desde los TIFs
en cada corrida). No incluye el análisis de severidad dNBR/Sentinel-2
(`codes/get_dNBR.ipynb`, `codes/S2_burntArea.ipynb`) — ese es un flujo aparte.
Ver `docs/METODOLOGIA.md` para el detalle completo.
