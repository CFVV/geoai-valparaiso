# Cómo correr los pipelines → Paso a paso

Guía rápida para ejecutar cualquiera de los dos pipelines (cambio urbano o incendios) desde tu computador.

---

# PARTE A — Instalación (solo la primera vez)

> Si el computador ya tiene todo instalado y funcionando, salta a la Parte B.

## A.1 — Instalar Anaconda

Descarga e instala Anaconda desde [https://www.anaconda.com/download](https://www.anaconda.com/download) (instalador normal, "Siguiente" a todo).

> **Importante en Windows:** después de instalar, usa siempre **"Anaconda Prompt"** (búscalo en el menú Inicio), **no** CMD ni PowerShell. Solo Anaconda Prompt reconoce los comandos `conda` y `python`. Sabrás que estás en la terminal correcta porque la línea empieza con `(base)`.

## A.2 — Instalar Git

Descarga e instala Git:

- Windows: [https://git-scm.com/download/win](https://git-scm.com/download/win)  
- Mac: viene incluido, o `brew install git`

Después de instalar, **cierra y vuelve a abrir la terminal** (si no, no reconoce el comando `git`).

> **Alternativa sin Git:** puedes descargar el proyecto como ZIP desde [https://github.com/CFVV/geoai-valparaiso](https://github.com/CFVV/geoai-valparaiso) → botón verde "Code" → "Download ZIP". Funciona igual, pero después no podrás actualizar con `git pull`.

## A.3 — Descargar el proyecto

git clone https://github.com/CFVV/geoai-valparaiso.git

cd geoai-valparaiso

## A.4 — Crear el entorno e instalar las librerías

**En Windows (recomendado, desde Anaconda Prompt):**

conda env create \-f environment.yml

conda activate sirval

**En Mac/Linux:**

pip install \-r requirements.txt

> **Por qué conda en Windows:** las librerías geoespaciales (geopandas, rasterio) necesitan componentes que `pip` no siempre logra instalar en Windows. Conda los resuelve automáticamente.  
>   
> **Recuerda:** cada vez que abras una terminal nueva para trabajar en este proyecto, primero corre `conda activate sirval`. Si la línea dice `(base)` en vez de `(sirval)`, estás en el entorno equivocado.

## A.5 — Configurar Google Earth Engine

1. Pide acceso al proyecto `sirval-geoai` a quien administre el proyecto (te agregan con tu propia cuenta de Google; no necesitas crear nada).  
2. Entra una vez a [https://code.earthengine.google.com](https://code.earthengine.google.com) con tu cuenta y acepta los términos.  
3. En la terminal, autentícate:  
     
   earthengine authenticate  
     
   Se abre el navegador para iniciar sesión. Solo se hace una vez por computador.

## A.6 — Descargar el modelo entrenado (solo para cambio urbano)

El modelo no viene en el repositorio (es un archivo pesado). Descárgalo desde Zenodo: [https://doi.org/10.5281/zenodo.21351448](https://doi.org/10.5281/zenodo.21351448)

Guárdalo en: `cambio_urbano/models/model_xgb_norm_v2.pkl`

> Sin este archivo, el pipeline de cambio urbano falla en el paso 4\. El pipeline de incendios NO lo necesita.

---

# PARTE B — Correr un pipeline

## B.1 — Abrir la terminal correcta y activar el entorno

**Windows:** abre **Anaconda Prompt** (menú Inicio → escribe "anaconda").

conda activate sirval

cd ruta\\hacia\\geoai-valparaiso

La línea debe empezar con `(sirval)`.

## B.2 — Indicar el proyecto de Google Earth Engine

Windows (Anaconda Prompt / CMD):   set GEE\_PROJECT=sirval-geoai

Windows (PowerShell):              $env:GEE\_PROJECT="sirval-geoai"

Mac/Linux:                         export GEE\_PROJECT="sirval-geoai"

> Hay que repetirlo **cada vez que abres una terminal nueva**.

## B.3 — Entrar a la carpeta del pipeline

**Cambio urbano:**

cd cambio\_urbano

**Incendios:**

cd incendios

## B.4 — (Opcional) Revisar el año a analizar

Abre `config.yaml` con cualquier editor y revisa `anios.fin` (el año más reciente que se va a analizar). Si solo quieres probar que funciona, déjalo tal como está.

Es el único archivo que se edita.

## B.5 — Correr

### Opción A — Corrida completa (primera vez, o año nuevo)

Descarga las imágenes desde Google Earth Engine. Tarda entre 15 y 45 minutos.

python run\_pipeline.py

> **No cierres la terminal ni dejes que el computador se suspenda** mientras descarga. Si se interrumpe, la descarga se corta.

### Opción B — Prueba rápida (si ya descargaste antes)

Usa las imágenes que ya están en disco. Tarda segundos.

**Cambio urbano:**

python run\_pipeline.py \--skip-descarga \--skip-lulc

**Incendios:**

python run\_pipeline.py \--skip-descarga

## B.6 — Leer el resultado

Al terminar aparece un resumen con **✅** y la cantidad de resultados. Los archivos finales quedan en la carpeta `outputs/`:

- **Cambio urbano:** `.gpkg` (se abre en QGIS) y `.kmz` (Google Earth)  
- **Incendios:** `.gpkg` y `.geojson`

---

## 

## ¿Cómo sé si salió bien?

Números esperados sobre los datos actuales:

| Pipeline | Resultado esperado |
| :---- | :---- |
| cambio urbano | **222** "Alerta de cambio" |
| incendios | **Nfires total 7.834** |

Si ves esos números y un ✅, funcionó.

> Si tu número es distinto y no cambiaste el año en `config.yaml`, algo no está bien — revisa las advertencias del log antes de usar el resultado.

Es normal que aparezcan algunas advertencias (⚠️): aviso de sistemas de coordenadas, meses faltantes del año en curso, o uso de LULC como proxy. Esas **no son errores**.

---

# Solucionario de errores frecuentes

Cuando algo falla, el pipeline se detiene y muestra **❌** con un mensaje. Busca tu caso abajo. Siempre **copia el mensaje de error completo** — es lo más útil para pedir ayuda.

### 1\. "conda" o "python" no se reconoce como comando (Windows)

**Qué pasó:** estás en CMD o PowerShell, no en Anaconda Prompt.

**Solución:** cierra esa ventana. Menú Inicio → busca **"Anaconda Prompt"** → ábrelo. La línea debe empezar con `(base)` o `(sirval)`.

### 2\. "git" no se reconoce como comando (Windows)

**Qué pasó:** instalaste Git pero la terminal estaba abierta desde antes.

**Solución:** cierra y vuelve a abrir la terminal. Si sigue sin funcionar, usa "Git Bash" (viene con Git) o descarga el repositorio como ZIP.

### 3\. "ModuleNotFoundError" / "No module named ..."

**Qué pasó:** no activaste el entorno, o las librerías no están instaladas.

**Solución:** corre `conda activate sirval` (la línea debe decir `(sirval)`). Si persiste, reinstala con `conda env create -f environment.yml`.

### 4\. "No se definió el proyecto de Google Earth Engine"

**Qué pasó:** olvidaste el paso B.2 en esta terminal.

**Solución:** define `GEE_PROJECT` (ver B.2). Hay que hacerlo en cada terminal nueva.

### 5\. "Project 'xxx' not found or deleted"

**Qué pasó:** el proyecto indicado no existe o tu cuenta no tiene acceso.

**Solución:** verifica que sea `sirval-geoai` y que te hayan dado acceso a ese proyecto con tu cuenta de Google. Si no, pídelo a quien administre el proyecto.

### 6\. Error de autenticación / "credentials" (Earth Engine)

**Qué pasó:** tu sesión caducó o nunca se configuró.

**Solución:** corre `earthengine authenticate`.

### 7\. "No se encontró el modelo" / falta el archivo `.pkl`

**Qué pasó:** no descargaste el modelo entrenado (paso A.6).

**Solución:** bájalo de [https://doi.org/10.5281/zenodo.21351448](https://doi.org/10.5281/zenodo.21351448) y ponlo en `cambio_urbano/models/model_xgb_norm_v2.pkl`.

### 8\. "No such file or directory" con un archivo `.gpkg`

**Qué pasó:** falta un archivo de datos que el pipeline necesita.

**Solución:** verifica que descargaste el repositorio completo. Si el archivo falta, pídelo a quien administre el proyecto.

### 9\. La descarga se cortó a la mitad

**Qué pasó:** se cerró la terminal, se durmió el equipo, o se cayó internet.

**Solución:** vuelve a correr `python run_pipeline.py`. Lo que ya se descargó se conserva y solo baja lo que falta.

### 10\. El resultado dice "0 detecciones" o el mapa sale vacío

**Qué pasó:** puede ser correcto (sin cambio real) **o** señal de que faltan imágenes de alguno de los dos años que se comparan.

**Solución:** revisa el log: si dice "mosaico S2 no encontrado" para algún año, faltan imágenes. Corre sin `--skip-descarga` para completarlas. **Ante la duda, no publiques ese resultado.**

### 11\. El número de resultados no coincide con el esperado

**Qué pasó:** puede ser normal si cambiaste el año en `config.yaml`.

**Solución:** si no cambiaste el año y el número difiere, revisa las advertencias del log y consúltalo antes de usar el resultado.

### 12\. Advertencias ⚠️ durante la corrida

**Qué pasó:** normalmente nada grave; el pipeline sigue corriendo.

Las más comunes y esperables:

- Aviso de sistemas de coordenadas (CRS/EPSG) → el pipeline lo maneja solo.  
- "Mosaico incompleto" / "faltan N meses" → normal si es el año en curso.  
- "LULC usó proxy" → normal cuando el uso de suelo del año más reciente aún no se publica.

Si es una de estas, el resultado es válido. Anótalo al entregar (por ejemplo, que el año es parcial).

### Si tu error no está en esta lista

1. Copia el mensaje de error **completo** (o guarda el log de `outputs/logs/`).  
2. Anota qué estabas haciendo y qué pusiste en `config.yaml`.  
3. Llévalo a alguien que pueda ayudarte técnicamente. El mensaje exacto es la información más valiosa — no lo resumas, cópialo tal cual.

