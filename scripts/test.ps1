$ErrorActionPreference = "Stop"

uv sync --extra dev
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
.\\.venv\\Scripts\\python.exe -m pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
.\\.venv\\Scripts\\python.exe scripts\\check_task_sync.py --pre-commit --strict
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& .\\scripts\\quality.ps1
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
