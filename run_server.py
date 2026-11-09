from __future__ import annotations

import uvicorn


def main() -> None:
    """Run only the SARSim FastAPI backend."""
    print("SARSim API: http://127.0.0.1:8000")
    print("SARSim API documentation: http://127.0.0.1:8000/docs")
    print("This command does not start the browser application; use ./run.sh for that.")
    uvicorn.run(
        "src.api.server:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
    )


if __name__ == "__main__":
    main()
