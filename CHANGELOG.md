# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-08-06

### Added

- Single-file tool `wispr_pro.py`: mitmproxy addon + CLI.
  - Commands: `start`, `stop`, `status`, `trust`, `selftest`, `restart`.
  - Customization flags: `--plan`, `--status`, `--trial-days`,
    `--trial-ends-at`, `--credits`, `--subscribed/--no-subscribed`,
    `--days-left`, `--marker`, `--host`, `--port`, `--ca-dir`, `--app`,
    `--no-relaunch`.
  - Persistent config via `~/.wispr_pro/config.toml`; flags override it.
- `build_app.py`: single entrypoint that produces a macOS `.app` bundle
  (arm64 by default, `--arch universal2` for arm64 + Intel).
- GitHub Actions:
  - `ci.yml`: pytest + `selftest` smoke on Python 3.11/3.12 (Linux) and
    macOS.
  - `build-app-dmg.yml`: builds the `.app`, packages it into a `.dmg` and
    attaches it to a GitHub Release on `v*` tag pushes.
- Nuxt documentation site under `docs/` (Nuxt 3 + `@nuxt/content`).
- `tests/`: pytest suite for the rewrite logic (no mitmproxy needed).
- Linting: `ruff` (lint + format) and `mypy` configured in `pyproject.toml`.

### Fixed

- Proxy crashes on other machines caused by the PyInstaller onefile temp
  directory being cleaned up (previous daemon re-exec design). The proxy
  now runs fully in-process in the foreground.

### Notes

- Educational project. The tool rewrites the subscription API response
  locally so Wispr Flow *displays* the Pro plan; it does not modify the
  Wispr Flow app itself.
