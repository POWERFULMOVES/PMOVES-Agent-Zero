# Branching Strategy

This document outlines the branching strategy for PMOVES-Agent-Zero, particularly for managing multiple hardened editions while ensuring feature parity across variants.

## Overview

PMOVES-Agent-Zero maintains multiple **hardened edition variants** that share common features but have variant-specific customizations. The branching strategy ensures:

1. **Features flow to all variants** - No variant is left behind
2. **Variant customizations are preserved** - Custom configurations are not overwritten
3. **Clear merge paths** - Developers know which branch to target for PRs

## Branch Structure

```
                    ┌─────────────────────────────────────────┐
                    │         Shared Ancestor (upstream)       │
                    │         agent0ai:main                    │
                    └─────────────────┬───────────────────────┘
                                      │
                    ┌─────────────────┴───────────────────────┐
                    │                                         │
    ┌───────────────▼──────────────┐    ┌────────────────────▼─────────────┐
    │  PMOVES.AI-Edition-Hardened  │    │  PMOVES.AI-Edition-Hardened-DoX  │
    │  (Primary Hardened Edition)  │    │  (DoX Integration Variant)       │
    │  - Default hardened config   │    │  - PMOVES-DoX specific settings  │
    │  - Standard agent profiles   │    │  - pmoves_custom agent profile   │
    │  - Baseline security         │    │  - Configurable env vars         │
    └───────────────┬──────────────┘    └───────────────┬───────────────────┘
                    │                                  │
                    │         Feature Development       │
                    │                 │                 │
                    └─────────────────┼─────────────────┘
                                      │
                    ┌─────────────────▼──────────────────┐
                    │  feat/* (Feature Branches)         │
                    │  - Created from hardened main      │
                    │  - Merged back to hardened main    │
                    │  - Cascaded to variants            │
                    └────────────────────────────────────┘
```

## Branch Descriptions

| Branch | Purpose | Created From | Target for PRs |
|--------|---------|--------------|----------------|
| `main` | Upstream (agent0ai) | - | Never target directly |
| `PMOVES.AI-Edition-Hardened` | **Primary hardened edition** | main | **DEFAULT target for all features** |
| `PMOVES.AI-Edition-Hardened-DoX` | DoX integration variant | main | Only for DoX-specific changes |
| `feat/*` | Feature development branches | PMOVES.AI-Edition-Hardened | Merge back to hardened main |

## Variant Differences

### PMOVES.AI-Edition-Hardened (Primary)
- Standard hardened security configuration
- Default agent profiles (agent0, developer, researcher, etc.)
- Base settings and model provider configuration

### PMOVES.AI-Edition-Hardened-DoX
All of the above, plus:
- `agents/pmoves_custom/` - Custom agent profile for PMOVES-DoX
- `python/helpers/settings.py` - Environment variable overrides:
  - `MCP_SERVER_TOKEN` - Token override via environment
  - `MCP_SERVER_ENABLED` - Enable/disable MCP server via environment
- `docker/run/fs/exe/run_A0.sh` - Configurable port and MCP settings

## Merge Workflow

### For New Features (All Variants)

```bash
# 1. Create feature branch from primary hardened
git checkout PMOVES.AI-Edition-Hardened
git pull origin PMOVES.AI-Edition-Hardened
git checkout -b feat/your-feature-name

# 2. Develop and test your feature
# ... make changes, commit, test ...

# 3. Push and create PR to PMOVES.AI-Edition-Hardened
git push origin feat/your-feature-name
# Create PR: feat/your-feature-name → PMOVES.AI-Edition-Hardened

# 4. After PR is merged, the maintainer cascades to variants
# (See "Cascading Features to Variants" below)
```

### For Variant-Specific Changes Only

If your change ONLY applies to a specific variant (e.g., DoX-specific configuration):

```bash
# 1. Create feature branch from that variant
git checkout PMOVES.AI-Edition-Hardened-DoX
git pull origin PMOVES.AI-Edition-Hardened-DoX
git checkout -b feat/dox-specific-change

# 2. Make variant-specific changes only
# ... edit files in agents/pmoves_custom/, etc ...

# 3. Push and create PR to that variant
git push origin feat/dox-specific-change
# Create PR: feat/dox-specific-change → PMOVES.AI-Edition-Hardened-DoX
```

## Cascading Features to Variants

After a feature is merged to `PMOVES.AI-Edition-Hardened`, cascade it to other variants:

```bash
# 1. Ensure hardened main is up to date
git checkout PMOVES.AI-Edition-Hardened
git pull origin PMOVES.AI-Edition-Hardened

# 2. Checkout the variant branch
git checkout PMOVES.AI-Edition-Hardened-DoX
git pull origin PMOVES.AI-Edition-Hardened-DoX

# 3. Merge hardened main into the variant
git merge PMOVES.AI-Edition-Hardened

# 4. Resolve any conflicts (preserve variant-specific changes)
# ... resolve conflicts if any ...

# 5. Push the variant
git push origin PMOVES.AI-Edition-Hardened-DoX
```

### Conflict Resolution Guidelines

When cascading features to variants, **always preserve variant-specific customizations**:

| File Pattern | Conflict Strategy |
|--------------|-------------------|
| `agents/pmoves_custom/**` | **Keep variant** - Do not overwrite DoX-specific agent |
| `python/helpers/settings.py` | **Keep variant** - Preserve env var overrides |
| `docker/run/fs/exe/run_A0.sh` | **Keep variant** - Preserve DoX-specific script |
| `python/api/**` | **Accept merged** - New APIs should be available to all |
| `python/helpers/**` | **Accept merged** - New helpers should be available to all |
| `requirements.txt` | **Accept merged** - Dependencies should be synchronized |
| `tests/**` | **Accept merged** - Tests should be available to all |

## Safe File Categories

### Files Safe to Merge Across All Variants
These files should always be synchronized:
- `python/api/*` - New API endpoints
- `python/helpers/*` - Helper modules (except variant-specific settings)
- `tests/*` - Test suites
- `requirements.txt` - Python dependencies
- `run_ui.py` - Main entry point
- New feature files (anything not in variant-specific directories)

### Files That Should Diverge Between Variants
These files may legitimately differ:
- `agents/pmoves_custom/**` - DoX-specific agent profiles
- `python/helpers/settings.py` - Environment variable configuration
- `docker/run/fs/exe/run_A0.sh` - Docker run scripts
- `.env` files - Environment configuration

## Quick Reference

| Task | Command |
|------|---------|
| Start new feature | `git checkout PMOVES.AI-Edition-Hardened && git checkout -b feat/your-name` |
| Target PR for features | `PMOVES.AI-Edition-Hardened` |
| Cascade to DoX variant | `git checkout PMOVES.AI-Edition-Hardened-DoX && git merge PMOVES.AI-Edition-Hardened` |
| Check variant differences | `git diff PMOVES.AI-Edition-Hardened...PMOVES.AI-Edition-Hardened-DoX` |
| Find merge base | `git merge-base PMOVES.AI-Edition-Hardened PMOVES.AI-Edition-Hardened-DoX` |

## Example: Persona Integration Feature

The persona integration feature (feat/personas-first-architecture) demonstrates this workflow:

1. Feature branch created from `PMOVES.AI-Edition-Hardened`
2. Developed and tested on feature branch
3. Merged to `PMOVES.AI-Edition-Hardened` (commit `0eef070`)
4. Cascaded to `PMOVES.AI-Edition-Hardened-DoX` (preserving DoX-specific settings)

Files added (available to all variants):
- `python/api/persona_agent_create.py` - Persona API endpoints
- `python/helpers/persona_integration.py` - Persona integration logic
- `tests/test_persona_integration.py` - Test suite

Files preserved in DoX variant:
- `agents/pmoves_custom/prompts/agent.system.main.md` - DoX-specific prompt
- `python/helpers/settings.py` - DoX env var configuration
- `docker/run/fs/exe/run_A0.sh` - DoX docker script

## Questions?

- See [contribution.md](contribution.md) for general contribution guidelines
- See [development.md](development.md) for development setup
- See [architecture.md](architecture.md) for system architecture details
