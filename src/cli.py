from __future__ import annotations

import uvicorn


def main() -> None:
    """Start the SARSim API and integrated browser workspace."""
    print("SARSim Studio: http://127.0.0.1:8000")
    print("API documentation: http://127.0.0.1:8000/docs")
    uvicorn.run("src.api.server:app", host="127.0.0.1", port=8000, reload=False)
