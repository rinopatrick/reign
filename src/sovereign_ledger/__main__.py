"""Entry point for python -m sovereign_ledger."""

import uvicorn

from sovereign_ledger.config import settings
from sovereign_ledger.logging import setup_logging


def main() -> None:
    """Run the FastAPI application."""
    setup_logging(settings.log_level)
    uvicorn.run(
        "sovereign_ledger.api.app:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )


if __name__ == "__main__":
    main()
