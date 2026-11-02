"""Desktop entry point — bundles server + browser into one experience."""

import logging
import multiprocessing
import os
import sys
import time
import webbrowser
from pathlib import Path

logger = logging.getLogger("reign.desktop")


def get_data_dir() -> Path:
    """Return a platform-specific directory for user data."""
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path.home() / ".local" / "share"
    data_dir = base / "Reign"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def _is_port_open(host: str, port: int) -> bool:
    import socket  # noqa: PLC0415  # lazy: startup probe only

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((host, port)) == 0


def resolve_port(host: str, port: int) -> int:
    """Return a free port: requested one, or an ephemeral port if occupied."""
    import socket  # noqa: PLC0415  # lazy: startup probe only

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if _is_port_open(host, port):
            s.bind((host, 0))
            return s.getsockname()[1]
    return port


def wait_for_server(host: str, port: int, tries: int = 30, delay: float = 0.2) -> bool:
    """Wait until the server accepts connections. True on success."""
    for _ in range(tries):
        time.sleep(delay)
        if _is_port_open(host, port):
            return True
    return False


def _run_server(host: str, port: int) -> None:
    """Server worker (runs in a child process)."""
    import uvicorn  # noqa: PLC0415  # lazy: child process only

    uvicorn.run(
        "reign.api.app:app",
        host=host,
        port=port,
        reload=False,
        log_level="warning",
    )


def _spawn_server(host: str, port: int):
    """Spawn the server child process (separated for testability)."""
    ctx = multiprocessing.get_context("spawn")
    proc = ctx.Process(target=_run_server, args=(host, port), daemon=True)
    proc.start()
    return proc


def main() -> None:
    """Run Reign as a desktop app."""
    data_dir = get_data_dir()
    db_path = data_dir / "reign.db"
    backups_dir = data_dir / "backups"
    backups_dir.mkdir(exist_ok=True)

    # Point app to user data directory (both cases; pydantic-settings is case-insensitive,
    # backups_dir is read via REIGN_BACKUPS_DIR fallback in api/routes/backup.py).
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"
    os.environ["REIGN_BACKUPS_DIR"] = str(backups_dir)

    host = "127.0.0.1"
    port = 8000

    port = resolve_port(host, port)

    url = f"http://{host}:{port}"

    proc = _spawn_server(host, port)

    # Wait for server to accept connections
    if not wait_for_server(host, port):
        logger.error("Server failed to start.")
        proc.terminate()
        sys.exit(1)

    logger.info("Opening Reign at %s", url)
    webbrowser.open(url)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down Reign...")
        proc.terminate()
        proc.join(timeout=3)
        sys.exit(0)


if __name__ == "__main__":
    main()
