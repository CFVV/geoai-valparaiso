"""
Inferencia con model_xgb_norm_v2.pkl.

Portado desde wip-experiments/nb36_aplicacion_modelo_v2.ipynb (funciones
`load_bands` / `compute_indices` / `bands_to_prob_v2` / `infer_tile_v2`), NO
desde wip-experiments/recalibrar_v2.py: ese script no normaliza ni corre el
modelo — solo relee TIFs de probabilidad ya generados por una corrida
anterior de nb36. La normalización P2-P98 por tile/año se mantiene
exactamente igual a nb36:

    for bname, arr in bands.items():
        lo, hi = np.percentile(arr[~np.isnan(arr)], [2, 98])
        norm[bname] = np.clip((arr - lo) / (hi - lo), 0, 1)

NOTA (portado tal cual, sin modificar): en `bands_to_prob_v2`, la feature
'year_mosaic' del modelo se fija a un valor constante 2023 sin importar el
año realmente inferido. Esto viene así del notebook fuente (nb36, celda de
FASE 1) y no se altera aquí — cambiarlo sería reescribir lógica de inferencia
ya validada.
"""

from pathlib import Path

import joblib
import numpy as np
import rasterio

BAND_MAP = {"B2": 1, "B3": 2, "B4": 3, "B8": 4, "B11": 5, "B12": 6}
P_LOW, P_HIGH = 2, 98


def load_bands(tif_path):
    with rasterio.open(tif_path) as src:
        bands = {}
        for name, idx in BAND_MAP.items():
            arr = src.read(idx).astype(np.float32)
            arr[arr == 0] = np.nan
            bands[name] = arr
        return bands, src.profile.copy(), src.transform, (src.height, src.width)


def compute_indices(b):
    def ds(a, c):
        d = a + c
        out = np.zeros_like(a, dtype=np.float32)
        m = d != 0
        out[m] = (a[m] - c[m]) / d[m]
        return out

    return {
        "NDVI": ds(b["B8"], b["B4"]), "NDWI": ds(b["B3"], b["B8"]),
        "NDBI": ds(b["B11"], b["B8"]), "NDMI": ds(b["B8"], b["B11"]),
        "NBR": ds(b["B8"], b["B12"]),
    }


def bands_to_prob_v2(bands_dict, model, feat_names):
    idx = compute_indices(bands_dict)
    lookup = {
        **{k.upper(): v for k, v in bands_dict.items()},
        **{k.upper(): v for k, v in idx.items()},
    }
    H, W = next(iter(bands_dict.values())).shape
    X = np.zeros((H * W, len(feat_names)), dtype=np.float32)
    for j, fname in enumerate(feat_names):
        if fname == "year_mosaic":
            X[:, j] = 2023
            continue
        base = fname.split("_")[0].upper()
        arr = lookup.get(base)
        if arr is None:
            raise ValueError(f"Feature {fname} (base={base}) no disponible")
        X[:, j] = arr.ravel()
    bad = ~np.isfinite(X)
    if bad.any():
        med = np.nanmedian(np.where(np.isfinite(X), X, np.nan), axis=0)
        r, c = np.where(bad)
        X[r, c] = med[c]
    return np.clip(model.predict_proba(X)[:, 1], 0, 1).reshape(H, W).astype(np.float32)


def infer_tile_v2(tif_path, model, feat_names):
    bands, prof, tf, shp = load_bands(tif_path)
    norm = {}
    for bname, arr in bands.items():
        valid = arr[np.isfinite(arr)].ravel()
        lo, hi = np.percentile(valid, [P_LOW, P_HIGH])
        rng = hi - lo if hi > lo else 1.0
        norm[bname] = np.where(
            np.isfinite(arr), np.clip((arr - lo) / rng, 0.0, 1.0), np.nan
        ).astype(np.float32)
    prob = bands_to_prob_v2(norm, model, feat_names)
    return prob, tf, shp, prof


def correr(cfg: dict, log):
    """
    Retorna dict {tile_id: {anio: {"prob": array, "transform": Affine,
    "shape": (H, W)}}} — consumido por pipeline.deteccion.detectar().
    """
    bundle = joblib.load(cfg["modelo"]["ruta"])
    model = bundle["model"]
    feat_names = bundle["metadata"]["feature_names"]

    anios = [cfg["anios"]["inicio"], cfg["anios"]["fin"]]
    s2_dir = Path(cfg["rutas"]["s2_mosaics"])
    out_dir = Path(cfg["rutas"]["inferencia"])

    resultado = {}
    for tile_id in cfg["tiles"]:
        resultado[tile_id] = {}
        for year in anios:
            tif_src = s2_dir / str(year) / f"tile_{tile_id}.tif"
            if not tif_src.exists():
                log.warn(f"Inferencia tile {tile_id} {year}: mosaico S2 no encontrado, se salta.")
                continue

            out_tif = out_dir / str(year) / f"prob_tile_{tile_id}_{year}.tif"
            if out_tif.exists():
                log.info(f"Inferencia tile {tile_id} {year}: ya existe, se reutiliza.")
                with rasterio.open(out_tif) as src:
                    prob = src.read(1).astype(np.float32)
                    tf = src.transform
                    shp = (src.height, src.width)
            else:
                log.info(f"Inferencia tile {tile_id} {year}: corriendo modelo...")
                prob, tf, shp, prof = infer_tile_v2(str(tif_src), model, feat_names)
                out_tif.parent.mkdir(parents=True, exist_ok=True)
                prof_out = prof.copy()
                prof_out.update(dtype="float32", count=1, nodata=np.nan)
                with rasterio.open(str(out_tif), "w", **prof_out) as dst:
                    dst.write(prob, 1)

            resultado[tile_id][year] = {"prob": prob, "transform": tf, "shape": shp}

    return resultado
