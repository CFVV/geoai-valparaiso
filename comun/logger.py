"""
Logger simple pensado para un usuario no técnico: todo mensaje va a pantalla
Y a archivo, con símbolos claros (✅ ⚠️ ❌) para que sea fácil de escanear
sin tener que leer un traceback.
"""

import datetime
from pathlib import Path


class PipelineLogger:
    def __init__(self, ruta_log: str):
        self.ruta_log = Path(ruta_log)
        self.ruta_log.parent.mkdir(parents=True, exist_ok=True)
        self.advertencias = []
        self.errores = []
        self._f = open(self.ruta_log, "w", encoding="utf-8")

    def _timestamp(self) -> str:
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _escribir(self, prefijo: str, mensaje: str):
        linea = f"[{self._timestamp()}] {prefijo} {mensaje}"
        print(linea)
        self._f.write(linea + "\n")
        self._f.flush()

    def info(self, mensaje: str):
        self._escribir("ℹ️ ", mensaje)

    def warn(self, mensaje: str):
        self.advertencias.append(mensaje)
        self._escribir("⚠️ ", mensaje)

    def error(self, mensaje: str):
        self.errores.append(mensaje)
        self._escribir("❌", mensaje)

    def resumen_final(self, exito: bool):
        self._escribir("-" * 3, "-" * 60)
        if exito and not self.advertencias:
            self._escribir("✅", "Pipeline terminó sin advertencias.")
        elif exito and self.advertencias:
            self._escribir("⚠️ ", f"Pipeline terminó con {len(self.advertencias)} advertencia(s). Revisar antes de publicar.")
        else:
            self._escribir("❌", f"Pipeline terminó con ERROR. Revisar {self.ruta_log} para más detalle.")
        self._f.close()
