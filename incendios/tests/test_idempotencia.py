"""
Test de idempotencia: correr construir_hexgrid.construir() dos veces con el
mismo config (mismo anio_fin, mismos TIFs en disco) debe producir EXACTAMENTE
el mismo Nfires por hexágono. Esto es lo que garantiza que "correr de nuevo"
nunca corrompe el acumulado — no hay estado incremental persistido, cada
corrida reconstruye desde la capa base + TIFs en disco.

Corre con: python -m pytest tests/test_idempotencia.py -v
"""

import sys
from pathlib import Path

import pandas as pd
import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import construir_hexgrid


class _LoggerMudo:
    def info(self, msg):
        pass

    def warn(self, msg):
        pass

    def error(self, msg):
        pass


def _cargar_cfg():
    ruta_config = Path(__file__).resolve().parent.parent / "config.yaml"
    with open(ruta_config, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_idempotencia_mismo_anio_fin_produce_mismo_resultado():
    cfg = _cargar_cfg()
    log = _LoggerMudo()

    hgrid_1 = construir_hexgrid.construir(cfg, log)
    hgrid_2 = construir_hexgrid.construir(cfg, log)

    assert len(hgrid_1) == len(hgrid_2)

    s1 = hgrid_1.set_index("grid_id")["Nfires"].sort_index()
    s2 = hgrid_2.set_index("grid_id")["Nfires"].sort_index()
    pd.testing.assert_series_equal(s1, s2, check_names=False)

    assert int(hgrid_1["Nfires"].sum()) == int(hgrid_2["Nfires"].sum())


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
