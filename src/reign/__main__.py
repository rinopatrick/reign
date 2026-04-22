"""Entry point for python -m reign."""

import uvicorn

from reign.config import settings
from reign.logging import setup_logging


def main() -> None:
    """Run the FastAPI application."""
    setup_logging(settings.log_level)
    uvicorn.run(
        "reign.api.app:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )


if __name__ == "__main__":
    main()
