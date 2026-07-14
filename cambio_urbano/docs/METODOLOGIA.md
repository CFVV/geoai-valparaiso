# Metodología — Pipeline de Detección de Expansión de Asentamientos Informales
## Proyecto GeoAI Valparaíso

**Última actualización:** 2026-07-14
**Estado:** Pipeline funcional y validado; limitaciones conocidas documentadas
(ver secciones 7-8). Nombre del módulo: `cambio_urbano` (el pipeline detecta
cambio espectral compatible con construcción/urbanización, no campamentos
confirmados — ver sección 4).

---

## 1. Objetivo

Este pipeline complementa el cadastre en terreno de TECHO-Chile mediante un
sistema de alerta temprana satelital: detecta zonas con cambio espectral
compatible con construcción/urbanización reciente, para priorizar dónde
dirigir esfuerzo de validación en terreno — no reemplaza el cadastre, lo hace
más eficiente. Nota sobre el nombre: el módulo se llama `cambio_urbano` y no
"campamentos" a propósito, porque el pipeline no puede confirmar por sí solo
que un cambio detectado sea un campamento (podría ser obra formal u otra
construcción); esa determinación la hace la validación visual o el trabajo de
campo posterior. El cadastre de TECHO usado como ground-truth de validación,
en cambio, sí corresponde a campamentos reales.

---

## 2. Arquitectura del pipeline

```
Descarga S2 (GEE) → Inferencia (XGBoost v2) → Detección (umbral delta_v2)
                                                        ↓
                        Filtro incendio (MODIS) + Filtro marítimo (límite comunal)
                                                        ↓
                          Postprocesamiento LULC (ESRI 10m) → Alerta de cambio
                                                        ↓
                                    Entregables: GPKG + KMZ
```

### 2.1 Datos de entrada
- **Sentinel-2**: mosaicos de mediana por tile/año, 6 bandas (B2, B3, B4, B8,
  B11, B12), filtro de nube a nivel de escena (`CLOUDY_PIXEL_PERCENTAGE < 20`
  antes de la mediana). **No se aplica máscara de nube por píxel (SCL/QA60)**
  — se evaluó y no forma parte del pipeline de producción validado.
- **20 tiles prioritarios**, definidos por el equipo en fases anteriores del
  proyecto.
- **MODIS** (MCD64A1/MOD14A1) para filtro de artefactos por incendio.
- **LULC ESRI 10m Time Series** (GEE, `ESRI_Global-LULC_10m_TS`) para
  postprocesamiento — años disponibles: 2020, 2022, 2023, 2024.

### 2.2 Modelo
- `model_xgb_norm_v2.pkl` — XGBoost sobre bandas normalizadas por percentil
  (P2-P98) calculado por tile/año.
- **Por qué normalización por percentil:** mosaicos de años distintos pueden
  tener diferencias sistemáticas de iluminación/fenología no atribuibles a
  cambio real (ej. tile_52 2025 apareció sistemáticamente más "verde" que 2023,
  NDVI +0.10 a +0.25, por fenología — no por incendio). La normalización P2-P98
  redujo falsos positivos en ~76% manteniendo verdaderos positivos.

### 2.3 Umbral de detección
`delta_v2 > 0.070` sobre la salida del modelo — define "cambio reciente".

### 2.4 Filtros post-detección
- **Filtro de incendio**: recalculado en vivo contra MODIS fresco por
  corrida (no se reutiliza una columna estática de corridas anteriores, ya
  que esa columna no cubre tiles/años nuevos).
- **Filtro marítimo**: excluye subtiles cuyo centroide cae fuera de los
  límites comunales (evita falsos positivos en cuerpos de agua costeros).

### 2.5 Postprocesamiento LULC — categoría "Alerta de cambio"
Se cruza cada detección con la fracción de suelo clasificado "Built" por
LULC ESRI. **Cambio de diseño (2026-07):** las categorías originales
`confirmado_lulc` (≥40% Built) y `ambiguo_lulc` (10-40% Built) se
**fusionaron en una sola etiqueta pública "Alerta de cambio"**
(`frac_built ≥ 0.10`). La categoría `suprimido_lulc` (<10% Built) se sigue
excluyendo del entregable público, pero se retiene internamente para
auditoría.

**Justificación de la fusión** (ver sección 5, Validación): en la validación
ciega de 40 casos, `confirmado_lulc` y `ambiguo_lulc` no se distinguieron de
forma confiable en revisión visual humana (tasas de confirmación como
`cambio_construccion`: 20-27% vs 20-33% respectivamente) — mantener la
distinción alta/media daba una falsa sensación de jerarquía de confianza que
los datos no respaldan. `suprimido_lulc` sí validó correctamente: 0% de
confirmación como construcción en ambos evaluadores.

### 2.6 Manejo de años sin LULC publicado (proxy)
Si el año de análisis no tiene LULC publicado en GEE (situación esperable
para el año en curso), el pipeline usa automáticamente el año LULC disponible
más reciente como proxy, y lo documenta explícitamente:
- En el log de ejecución (advertencia)
- En los metadatos del GPKG/KMZ entregado (columna `lulc_anio_proxy`)

### 2.7 Mosaicos de año incompleto
Si el año de análisis es el año en curso, el mosaico Sentinel-2 puede estar
incompleto (cobertura parcial del año). El pipeline detecta e informa
explícitamente hasta qué mes hay cobertura real, tanto en el log como en los
metadatos del entregable — para que quien reciba el resultado sepa que no es
un año completo.

---

## 3. Métricas de validación establecidas

| Métrica | Valor | Contexto |
|---|---|---|
| Eficiencia (subset alta confianza vs. búsqueda no dirigida) | ~9× | Sobre 110 campamentos ground-truth |
| Recall (buffer 25m) | 14.5% | Sobre 110 campamentos ground-truth, cadastre TECHO 2025 |
| Reducción de falsos positivos (v1→v2) | ~76% | Por normalización P2-P98 |
| Precisión "alta confianza" (raw) | ~12% | Ver interpretación en sección 4 |
| Precisión "ambigua" (raw) | ~4% | Ver interpretación en sección 4 |

---

## 4. Cómo interpretar la precisión (nota importante para lectores no técnicos)

La precisión "cruda" del pipeline es estructuralmente baja (~12% incluso en
el subset de mayor confianza). **Esto es esperado y aceptable dado el diseño
del sistema**: el objetivo no es reemplazar la validación en terreno, sino
**priorizar dónde TECHO/Gobierno Regional dirigen ese esfuerzo limitado**. Un
sistema que reduce el área de búsqueda ~9× sigue siendo enormemente útil
aunque la mayoría de sus alertas individuales terminen siendo falsos
positivos en terreno — el valor está en la eficiencia de priorización, no en
la exactitud caso por caso.

---

## 5. Validación ciega (nb40 / nb42)

### 5.1 Protocolo
40 casos seleccionados con muestreo estratificado (SEED=42: 15
`confirmado_lulc`, 15 `ambiguo_lulc`, 10 `suprimido_lulc`), IDs anonimizados
y reordenados con un seed distinto (SEED_ID=99) para blinding. Tres
evaluadores puntuaron independientemente sin acceso a la categoría real del
pipeline: Camila, Paula, y un tercer evaluador (Nacho).

### 5.2 Exclusión de un evaluador
El tercer evaluador (Nacho) mostró concordancia débil con los otros dos
(kappa Nacho-Paula = 0.166, kappa Nacho-Cami = 0.303 — vs. Paula-Cami =
0.560). Se excluyó de las conclusiones cuantitativas de la validación,
manteniéndolo solo como referencia. *(Pendiente: entender la causa de esa
discrepancia — ver sección 8.)*

### 5.3 Resultado
- Acuerdo Paula-Cami: 72.5% (29/40), kappa = 0.560 (moderado)
- 11 casos en desacuerdo, revisados individualmente
- Cruce contra `categoria_real` del pipeline: ver sección 2.5 y notebook
  `nb42_reporte_validacion_ciega.ipynb`

### 5.4 Documento de reporte
El notebook `wip-experiments/nb42_reporte_validacion_ciega.ipynb` recalcula
esta validación de forma reproducible (no hardcodea números salvo las
métricas históricas ya cerradas) y exporta un resumen de 2 páginas en PDF.

---

## 6. Uso del pipeline de producción

Ver `README` del módulo (`cambio_urbano/`) para
instrucciones operativas. En resumen:

```bash
python run_pipeline.py                      # corrida normal, año nuevo
python run_pipeline.py --skip-descarga      # reutiliza mosaicos S2 en disco
python run_pipeline.py --skip-lulc          # reutiliza LULC/MODIS en disco
```

Todos los parámetros (años, tiles, umbrales, proyecto GEE) se editan en
`config.yaml` — no requiere tocar código.

### 6.1 Proyecto GEE
El proyecto de Google Earth Engine no está hardcodeado en el repo, para que
no quede amarrado a la cuenta de una sola persona. Cada usuario define el
suyo mediante la variable de entorno `GEE_PROJECT` (ver README, paso 3).
El pipeline resuelve el proyecto en este orden: (1) variable de entorno
`GEE_PROJECT`, (2) `gee.proyecto` en `config.yaml` si se prefiere fijarlo
ahí. Si ninguno está definido, el pipeline se detiene con un mensaje claro
antes de intentar conectarse a GEE.

**Pendiente no bloqueante**: evaluar crear un proyecto GCP dedicado al
proyecto GeoAI Valparaíso para entrega institucional (requiere setup de
facturación/roles, fuera del alcance del pipeline en sí).

---

## 7. Limitaciones conocidas

- Precisión estructuralmente baja (ver sección 4) — no debe interpretarse
  como sistema de detección exacta, sino de priorización.
- Recall relativamente bajo (14.5% @ 25m) — el pipeline no captura todos los
  campamentos nuevos; complementa, no reemplaza, el cadastre de campo.
- Cobertura LULC limitada a los años publicados por ESRI (2020, 2022, 2023,
  2024 al momento de escribir esto); años posteriores usan proxy (ver 2.6).
- **Falsos positivos por cuerpos de agua interiores y cicatrices de incendio
  (limitación conocida, bajo revisión):** en la validación ciega, cuatro
  casos (V03, V32, V36, V37) recibieron notas de una evaluadora señalando
  posibles artefactos por incendio o cambio en cuerpos de agua (ej. embalses
  o lagunas que suben/bajan de nivel entre años). El pipeline tiene filtro de
  incendio (MODIS), pero **no tiene un filtro dedicado para cuerpos de agua
  interiores** — el filtro marítimo actual solo excluye por límite comunal, no
  masas de agua dentro del territorio. Un cambio espectral por variación de
  nivel de agua puede confundirse con cambio de construcción. No se ha
  cuantificado aún la magnitud de este efecto; queda como revisión abierta
  (ver sección 8). Mitigación provisional: los casos sobre o adyacentes a
  cuerpos de agua conocidos deben revisarse con criterio en la validación
  visual antes de priorizar terreno.

---

## 8. Pendientes

1. **Cuantificar el efecto de cuerpos de agua interiores** (ver sección 7).
   Los casos V03, V32, V36, V37 motivaron documentar esta limitación; queda
   pendiente medir cuántas alertas caen sobre o cerca de masas de agua
   conocidas, y evaluar si amerita un filtro dedicado (ej. excluir por
   intersección con capa hidrográfica de la DGA/IDE Chile) o basta con la
   revisión visual como mitigación.
2. Entender causa de la baja concordancia del tercer evaluador (Nacho) —
   ¿calibración de criterio, contexto insuficiente, u otro factor?
3. Confirmar si vale la pena crear un proyecto GCP dedicado (sección 6.1).
4. [Espacio para hallazgos adicionales de futuras iteraciones]

---

## 9. Referencias internas

- `CLAUDE.md` — contexto completo de sesiones de desarrollo (Claude Code)
- `wip-experiments/nb36_aplicacion_modelo_v2.ipynb` — inferencia
- `wip-experiments/nb38_lulc_postprocesamiento.ipynb` — lógica LULC original
  (3 categorías; ver sección 2.5 para el cambio a 2)
- `wip-experiments/nb40_metricas_finales.ipynb` — métricas finales y muestra
  de validación ciega (F-1/F-2/F-2b)
- `wip-experiments/nb42_reporte_validacion_ciega.ipynb` — reporte
  reproducible de validación
- `wip-experiments/outputs/validacion_muestra/categoria_mapping.csv` — mapeo
  interno de la validación ciega (no compartir durante sesiones de scoring)
