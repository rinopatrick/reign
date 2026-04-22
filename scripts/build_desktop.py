#!/usr/bin/env python3
"""Build Reign as a standalone desktop executable using PyInstaller."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC = PROJECT_ROOT / "src"
STATIC = SRC / "reign" / "static"


def run(cmd: list[str]) -> None:
    print(" ", " ".join(cmd))
    subprocess.run(cmd, check=True)


def main() -> int:
    print("Building Reign desktop executable...")
    os.chdir(PROJECT_ROOT)

    # Ensure pyinstaller is available
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("PyInstaller not found. Install dev dependencies first:")
        print("  uv sync --dev")
        return 1

    # Clean old build artifacts
    for folder in ("dist", "build"):
        path = PROJECT_ROOT / folder
        if path.exists():
            shutil.rmtree(path)

    # Base PyInstaller command
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name",
        "Reign",
        "--onefile",
        "--windowed",
        "--add-data",
        f"{SRC}{os.pathsep}src",
        "--add-data",
        f"{STATIC}{os.pathsep}src/reign/static",
        "--hidden-import",
        "uvicorn.logging",
        "--hidden-import",
        "uvicorn.loops.auto",
        "--hidden-import",
        "uvicorn.protocols.http.auto",
        "--hidden-import",
        "uvicorn.protocols.websockets.auto",
        "--hidden-import",
        "sqlalchemy.ext.asyncio",
        "--hidden-import",
        "aiosqlite",
        "--hidden-import",
        "pydantic",
        "--hidden-import",
        "reportlab",
        "--hidden-import",
        "reportlab.pdfbase._fontdata",
        "--distpath",
        str(PROJECT_ROOT / "dist"),
        "--workpath",
        str(PROJECT_ROOT / "build"),
        str(SRC / "reign" / "desktop.py"),
    ]

    run(cmd)

    print("\nDone! Executable created at:")
    exe_name = "Reign.exe" if sys.platform == "win32" else "Reign"
    print(f"  {PROJECT_ROOT / 'dist' / exe_name}")
    print("\nNotes:")
    print("- Build on each target OS for best results (Windows .exe on Windows, macOS .app on macOS).")
    print("- Linux builds produce a single ELF binary.")
    print("- Data is stored in the OS user data folder, not inside the executable.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
