---
title: Wispr Proxyflow
description: Wispr Flow → Pro — local MITM helper documentation
navigation:
  title: Home
---

# Wispr Proxyflow

Wispr Flow → Pro — a single-file Python tool (mitmproxy addon + CLI) that
starts a local intercepting proxy and rewrites Wispr Flow's subscription API
response so the app shows the **Pro** plan.

Everything runs locally. Only the app's *displayed* state changes.

::card
#title
Get started
#description
Install, run and build the app in a few commands.
#link
/2.installation
::

## Repository layout

| Path | Purpose |
|------|---------|
| `wispr_pro.py` | The tool: addon + CLI (single file) |
| `build_app.py` | Build entrypoint → `dist/<name>.app` |
| `build_app.py --arch universal2` | arm64 + Intel fat binary |
| `assets/icon/` | App icon (`.icns`) |
| `tests/` | pytest suite (no mitmproxy needed) |
| `.github/workflows/` | CI + DMG release builds |

## Quick links

- [Installation](/2.installation)
- [Usage](/3.usage)
- [Build & package](/4.build)
- [Architecture](/5.architecture)
- [Troubleshooting](/6.troubleshooting)
