$ErrorActionPreference = "Stop"

uv sync --extra dev
.\\.venv\\Scripts\\python.exe -m pytest -q
