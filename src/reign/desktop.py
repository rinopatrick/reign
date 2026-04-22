"""Desktop entry point — bundles server + browser into one experience."""

import os
import sys
import time
import webbrowser
from pathlib import Path


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


def _run_server(host: str, port: int) -> None:
    """Server worker (runs in a child process)."""
    import uvicorn

    uvicorn.run(
        "reign.api.app:app",
        host=host,
        port=port,
        reload=False,
        log_level="warning",
    )


def main() -> None:
    """Run Reign as a desktop app."""
    data_dir = get_data_dir()
    db_path = data_dir / "reign.db"
    backups_dir = data_dir / "backups"
    backups_dir.mkdir(exist_ok=True)

    # Point app to user data directory
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"
    os.environ["REIGN_BACKUPS_DIR"] = str(backups_dir)

    import socket

    host = "127.0.0.1"
    port = 8000

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex((host, port)) == 0:
            s.bind((host, 0))
            port = s.getsockname()[1]

    url = f"http://{host}:{port}"

    import multiprocessing

    ctx = multiprocessing.get_context("spawn")
    proc = ctx.Process(target=_run_server, args=(host, port), daemon=True)
    proc.start()

    # Wait for server to accept connections
    for _ in range(30):
        time.sleep(0.2)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex((host, port)) == 0:
                break
    else:
        print("Server failed to start.", file=sys.stderr)
        proc.terminate()
        sys.exit(1)

    print(f"Opening Reign at {url}")
    webbrowser.open(url)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down Reign...")
        proc.terminate()
        proc.join(timeout=3)
        sys.exit(0)


if __name__ == "__main__":
    main()
