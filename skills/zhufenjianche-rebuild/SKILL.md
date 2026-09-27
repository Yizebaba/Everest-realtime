---
name: zhufenjianche-rebuild
description: Safely rebuild, operate, audit, and deploy the Zhufenjianche monitoring system without exposing credentials or changing production notification behavior unintentionally.
---

# Zhufenjianche Rebuild Skill

## Use When

Use this skill for work on the `Zhufenjianche` environmental monitoring project, including rebuilds, source changes, evidence pages, notification behavior, Docker deployment, audits, and server migration.

## Project Boundary

There are two separate local projects:

```text
D:\Zhufenjianche
  Environmental monitoring and notification system.

D:\FacetWatch-Realtime
  Glacier-motion candidate and marker monitoring project.
```

Do not delete or move root PowerShell scripts from `D:\Zhufenjianche` until FacetWatch has been separately audited. HyP3, Earthdata, ASF, JupyterHub, glacier-candidate, and Windy-plugin scripts can belong to FacetWatch operations.

## Required Reading

Before modifying behavior, read:

```text
docs/REBUILD_HANDOFF_20260925.md
docs/CHANGE_CONTROL.md
docs/LEGACY_CODE.md
config/sources.json
config/runtime.json
compose.yaml
```

## Change Rules

1. Inspect relevant source, config, caller, test, and runtime state before editing.
2. Keep one focused behavior change per batch.
3. Do not delete unknown files, scripts, tests, data, evidence, or configuration.
4. Do not change Docker entrypoints, source URLs, notification rules, or SQLite schemas outside the requested scope.
5. Use `apply_patch` for code/config/document edits.
6. Do not commit, push, or publish to GitHub unless explicitly requested.
7. Do not send test notifications unless explicitly requested.
8. Do not expose, print, copy, or document live tokens, secrets, passwords, recipient identifiers, or private URLs.

## Secrets

The runtime notification secret is mounted at:

```text
/run/secrets/notify_config
```

Local secret files may exist but must never be included in documentation, source control, logs, or prompts. Rotate credentials before server migration.

## Runtime Model

```text
worker.py
  -> normal `monitor.py run --notify changed --send` loop
  -> persistent `monitor.py fast` child

monitor.py
  -> collector
  -> decision / deduplication
  -> screenshot evidence
  -> SQLite state
  -> GitHub image + Pages publication
  -> WeChat or optional Server Chan delivery
```

Persistent monitoring state is in:

```text
data-docker/monitor.sqlite3
```

Never clear it without an explicit migration decision. It contains baselines, event keys, frame signatures, and notice state.

## Evidence Rule

Use original source pixels or an in-place Chinese translation of the source page. Do not redraw API/JSON text as an image card.

If a translated screenshot fails, preserve the original screenshot fallback unless the user explicitly requests a stricter source-specific policy.

## Notification Rule

Normal changes must have:

```text
valid acquisition
AND allowed event/visual trigger
AND local evidence card
AND deduplication approval
AND configured destination
```

GitHub Pages can lag after a successful Contents API write. Delivery waits for an HTTP 200 evidence page before sending the WeChat link.

## Earthquake Rule

Keep all configured fast earthquake sources. Use normalized real events, not whole-page text. Cross-source identity is the UTC occurrence minute. A parser-version migration must silently seed baselines and event keys before any source is allowed to notify.

## Windy Rule

Windy sends only at a risk activation edge or a qualifying temperature drop. Sustained active conditions do not repeatedly send the 16-image bundle.

## LangGraph And MCP Boundary

```text
vendor/langgraph
  Upstream LangGraph source reference.

vendor/mcp-servers
  Official MCP reference server source.

skills/agenthouse
  Upstream community SKILL.md package.
```

The worker is orchestrated by LangGraph. Every production cycle must be invoked through registered MCP gateway tools, not arbitrary shell commands. The gateway may expose only reviewed fixed tools for fast polling, normal cycles, state inspection, evidence handling, publishing, and delivery. Do not add arbitrary shell, broad filesystem, unrestricted database, or token-export tools.

## Verification

Use the smallest relevant check first:

```powershell
docker run --rm -v "${PWD}:/app" -w /app --entrypoint python everest-realtime:local -m pytest <relevant tests>
docker run --rm -v "${PWD}:/app" -w /app --entrypoint python everest-realtime:local -m py_compile <changed modules>
docker compose build
docker compose up -d --force-recreate
docker logs --tail 100 zhufenjianche-monitor-1
```

Do not treat a test as passed if it attempted a real provider request when the test intended to be offline.

## Rebuild

For a clean project, follow `docs/REBUILD_HANDOFF_20260925.md`. Copy active runtime code/config, create fresh rotated secrets, and decide whether `data-docker/monitor.sqlite3` is migrated or a fresh baseline is required.
