# Cambio Urbano — Guía rápida

Detección de zonas con cambio espectral compatible con construcción o
urbanización reciente, a partir de imágenes satelitales. Sirve para priorizar
dónde dirigir validación en terreno (ej. cadastre de campamentos de TECHO),
no para confirmar campamentos por sí solo. Para el detalle metodológico
completo, ver `docs/METODOLOGIA.md`. Esta guía es solo para correr el
pipeline.

---

## Antes de la primera vez

1. Tener Python instalado y las librerías del proyecto (`pip install -r requirements.txt`, si existe ese archivo — si no, pedir a Claude Code que lo genere).
2. Autenticarse en Google Earth Engine una vez en la máquina:
   ```
   earthengine authenticate
   ```
3. Definir tu proyecto de Google Earth Engine como variable de entorno
   (reemplaza `tu-proyecto-gee` por el tuyo):
   ```
   Linux/Mac:   export GEE_PROJECT="tu-proyecto-gee"
   Windows:     set GEE_PROJECT=tu-proyecto-gee
   ```
   Cada persona usa su propio proyecto GEE — el repo no viene amarrado a
   ninguna cuenta en particular. (Alternativa: escribir el nombre en
   `gee.proyecto` dentro de `config.yaml`, pero la variable de entorno es
   más limpia y no queda guardada en el repo.)
4. No es necesario tocar ningún archivo `.py`. Solo `config.yaml`.

---

## Uso normal (una vez al año)

**Paso 1 — Editar `config.yaml`:**
Cambiar `anios.fin` al año que se quiere analizar. Ejemplo, para analizar 2027:

```yaml
anios:
  inicio: 2023
  fin: 2027
```

**Paso 2 — Correr:**
```
python run_pipeline.py
```

Eso es todo. El pipeline descarga las imágenes, corre el modelo, filtra, y
genera los archivos finales. Tarda entre 15 y 45 minutos aproximadamente
(la mayor parte es la descarga de imágenes satelitales).

**Paso 3 — Revisar el resultado:**
Al terminar, en pantalla aparece un resumen como:

```
✅ Pipeline completado en 22.4 min.
   Alertas de cambio generadas: 222
   → outputs/entrega/deteccion_2027.gpkg
   → outputs/entrega/deteccion_2027.kmz
```

Esos dos archivos (`.gpkg` y `.kmz`) son el entregable. El `.kmz` se puede
abrir directo en Google Earth; el `.gpkg` en QGIS.

---

## ¿Qué significan los símbolos en pantalla?

| Símbolo | Significado |
|---|---|
| ℹ️ | Información normal, no requiere acción |
| ⚠️ | Advertencia — el pipeline siguió corriendo, pero conviene leer el mensaje antes de usar el resultado (ej. "año incompleto", "LULC usó proxy") |
| ❌ | Error — el pipeline se detuvo. Leer el mensaje, dice exactamente qué falló |

Todos los mensajes también quedan guardados en
`outputs/logs/log_ejecucion_{año}.txt`.

---

## Si algo falla a mitad de camino

No hay que empezar de nuevo desde cero. Según en qué paso falló:

- Si ya se descargaron las imágenes Sentinel-2 (paso 1 del log) pero falló
  después:
  ```
  python run_pipeline.py --skip-descarga
  ```

- Si además ya se descargó LULC/MODIS (paso 2) y falló más adelante:
  ```
  python run_pipeline.py --skip-descarga --skip-lulc
  ```

Esto evita esperar de nuevo la parte más lenta (la descarga).

---

## Advertencias esperables (no son errores)

- **"El mosaico está incompleto — solo cubre hasta [mes]"**: normal si se
  está corriendo para el año en curso antes de que termine. El resultado
  sigue siendo válido, pero parcial para ese año.

- **"LULC [año] no está publicado — se usa LULC [año anterior] como proxy"**:
  normal cuando ESRI todavía no publica el LULC del año más reciente. Queda
  documentado en los metadatos del entregable.

---

## Preguntas frecuentes

**¿Puedo correrlo para más de un año a la vez?**
No en esta versión — `config.yaml` define un solo `anios.fin` por corrida.
Para varios años, correr el pipeline varias veces cambiando ese valor.

**¿Puedo cambiar qué tiles se analizan?**
Sí, en la lista `tiles:` de `config.yaml`. No se recomienda hacerlo sin
consultar con el equipo técnico, ya que los 20 tiles actuales fueron
definidos como prioritarios en fases anteriores del proyecto.

**¿Dónde reviso los detalles de por qué el pipeline funciona así (umbrales,
modelo, validación)?**
En `docs/METODOLOGIA.md`.

**Algo no está en esta guía / el pipeline hace algo raro.**
Anotar el mensaje exacto que aparece en pantalla (o revisar el log en
`outputs/logs/`) y llevarlo a la siguiente sesión de desarrollo con
Claude Code.
