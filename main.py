"""
Punto de entrada del agente ZocoTickets.
Ejecutar: python main.py
"""
import os
from pathlib import Path


def _cargar_dotenv():
    """Carga variables desde .env sin sobreescribir las ya definidas en el entorno."""
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        return
    for linea in env_path.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, _, valor = linea.partition("=")
        clave = clave.strip()
        valor = valor.strip().strip('"').strip("'")
        if clave and not os.environ.get(clave):
            os.environ[clave] = valor


_cargar_dotenv()

from agente import main  # noqa: E402

if __name__ == "__main__":
    main()
