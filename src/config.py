"""Runtime configuration — all values overridable via environment variables."""

import os
from pathlib import Path

# parents[1]: src/ -> repo root
_DEFAULT_DATA = Path(__file__).resolve().parents[1] / "data"

DATA_DIR      = Path(os.getenv("WINE_DSS_DATA_DIR", str(_DEFAULT_DATA)))
ONTOLOGY_PATH = Path(os.getenv("WINE_DSS_ONTOLOGY", str(DATA_DIR / "wine_dss.owl")))
DB_PATH       = Path(os.getenv("WINE_DSS_DB",       str(DATA_DIR / "wine_dss.db")))

MCP_HOST = os.getenv("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.getenv("MCP_PORT", "8000"))
