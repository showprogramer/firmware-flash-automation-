$ErrorActionPreference = "Stop"

uv run ruff check src scripts
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
uv run ruff format --check src scripts
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
uv run mypy
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
