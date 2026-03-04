# PMOVES-Agent-Zero Codex Home

Use this file as the Codex-first entrypoint for Agent Zero operations.

## Start Here

1. Install PMOVES root Codex config:
   - `make -C ../pmoves codex-config`
2. Review PMOVES operator docs:
   - `../pmoves/docs/AGENTS/CODEX_OPERATOR_HOME.md`
   - `../pmoves/docs/AGENTS/CODEX_PERSONA_STYLE_PLAYBOOK.md`
3. Validate runtime:
   - `curl http://localhost:8080/healthz`
   - `curl http://localhost:8080/mcp/commands`

## Style-aware MCP operations

- `form.get` with optional `style`
- `form.switch` with optional `style`
- `style.list`
- `form.styled`

## Notes

- Keep this guide aligned with PMOVES root runbooks when MCP commands change.
