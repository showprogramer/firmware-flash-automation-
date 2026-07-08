$ErrorActionPreference = "Stop"

uv sync --extra dev --extra qt
.\\.venv\\Scripts\\python.exe -m pytest -q
