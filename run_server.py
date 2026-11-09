from __future__ import annotations

import uvicorn


def main() -> None:
    """Run the SARSim FastAPI development server."""
    uvicorn.run(
        "src.api.server:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
    )


if __name__ == "__main__":
    main()
