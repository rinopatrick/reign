@echo off
REM Reign Launcher for Windows
REM Double-click to run

cd /d "%~dp0"

echo Starting Reign...
echo Open http://localhost:8000 in your browser
echo Press Ctrl+C to stop
echo.

REM Try uv first, fallback to python -m reign
where uv >nul 2>nul
if %errorlevel% == 0 (
    uv run python -m reign
) else (
    python -m reign
)
