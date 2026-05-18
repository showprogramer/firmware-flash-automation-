# Migration Notes

This file records repository moves and compatibility-sensitive migrations that future agents should know before editing. Add an entry when paths, public entry points, config/runtime locations, database/cache schemas, or documentation homes change. Do not add entries for ordinary bug fixes with no migration impact.

## 2026-05-18: Documentation Directory Consolidation

Reason: keep user-facing docs, changelog, migration notes, and code-review records under one documentation root.

Path changes:
- `README.md` -> `docs/README.md`
- `CHANGELOG.md` -> `docs/CHANGELOG.md`
- `specs/code-review/` -> `docs/code-review/`
- New migration log: `docs/migration note.md`

Agent impact:
- Update `docs/CHANGELOG.md` after user verification, not the removed root `CHANGELOG.md`.
- Write code-review records under `docs/code-review/`.
- Use this file for future path/API/config/runtime/schema migrations that are not obvious from local code.

Verification:
- Documentation-only migration note; code tests are not required for this file itself.
