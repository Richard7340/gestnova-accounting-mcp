# gestnova-accounting-mcp

Multi-jurisdiction operational accounting engine exposed as an MCP server.

## Quick start

```bash
uv sync --extra dev
uv run pytest
uv run gestnova-accounting-mcp     # stdio MCP
uv run gestnova-accounting-http    # HTTP on :8014
```

## Status

- Plan 1 (in progress): Foundation + ES core (payroll/leave/time_tracking)
- Plans 2-5: see `docs/superpowers/plans/2026-05-15-multi-jurisdiction-INDEX.md` in `livekit-voice-platform`.
