# AGENTS.md

macOS-only educational MITM helper for [Wispr Flow](https://wisprflow.ai).
Single-file mitmproxy addon + CLI rewrites the subscription JSON so the app
shows Pro; `build_app.py` produces a macOS `.app` (Apple Silicon).

## Layout

| Path | Role |
|------|------|
| `wispr_pro.py` | The whole tool: addon (rewrite logic), CLI (`start/stop/status/trust/selftest/restart`), CA trust, app relaunch. Single file, no package |
| `build_app.py` | Single build entrypoint: PyInstaller onefile → assembles `dist/<name>.app` (Info.plist, launcher, icon, ad-hoc codesign) |
| `assets/icon/` | `AppIcon.icns` used by the .app |
| `tests/test_wispr_pro.py` | pytest for rewrite logic — imports `wispr_pro` directly, **no mitmproxy needed** (top-level mitmproxy import is guarded) |
| `pyproject.toml` | Minimal: name `wispr-pro`, `[project.optional-dependencies] dev` (pytest, mitmproxy, pyinstaller), pytest `pythonpath=["."]` |
| `.github/workflows/ci.yml` | pytest + `wispr_pro.py selftest` on ubuntu (3.11/3.12) and macos-14 |
| `README.md` | Concise usage/build docs — the only docs |

Runtime state: `~/.wispr_pro/` (`config.toml`, `proxy.pid`, `mitmproxy/`
CA + data). Never commit `*.pem` / `*.key` / `*.p12`. `dist/`, `build/`,
`.venv/`, `*.spec` are gitignored.

## Commands

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
python3 wispr_pro.py selftest      # no proxy/macOS needed; CI uses this
python3 wispr_pro.py start --no-relaunch --port 8081   # foreground proxy
python3 build_app.py               # dist/Wispr Pro.app (arm64)
python3 build_app.py --arch universal2 --name "Wispr Pro"
```

## Architecture facts agents miss

- **Rewrite trigger:** body must contain the marker bytes (default
  `total_trial_days`) AND parse as a JSON **object** (`rewrite_body` in
  `wispr_pro.py`). Everything else passes through untouched.
- **Config vs API field:** toml `days_left` maps to rewrite key `daysLeft`
  (camelCase). `load_patch()` merges defaults → config.toml `[rewrite]` →
  CLI overrides. Addon calls `load_patch()` at request time (in-process).
- **CLI flags:** all customization flags live on the `start`/`restart`
  subparsers (via `_add_common`), so they come AFTER the subcommand:
  `start --plan FLOW_PRO_YEARLY --credits 500`. `--serve` is a hidden
  top-level flag (used by tests/CI and direct invocation).
- **Foreground only:** `start` runs mitmproxy in-process (DumpMaster +
  asyncio) and blocks. No child processes → the PyInstaller onefile temp
  dir can never be cleaned out from under the proxy (previous design had a
  re-exec daemon that crashed with `base_library.zip` FileNotFoundError).
  Background via `nohup ... &`; `stop`/`status` read `proxy.pid`.
- **stop does NOT killpg itself:** the foreground proxy shares the caller's
  process group; `cmd_stop` only killpg's when the groups differ.
- **App bundle:** `dist/<name>.app/Contents/MacOS/` contains the onefile
  binary `wispr-pro` and a shell launcher `wispr-pro-launcher` (double-click
  entry, redirects to `$WISPR_PRO_LOG` or `~/.wispr_pro/proxy.log`).
  Info.plist: `LSUIElement=true`, `CFBundleExecutable=wispr-pro-launcher`,
  `CFBundleIdentifier=com.local.wispr-pro`.
- **Plan values:** from the app's own enums — `FLOW_PRO_MONTHLY`,
  `FLOW_PRO_YEARLY`, `FLOW_BASIC`, student/team/business variants. Status
  enum: `active`, `trialing`, `canceled`, `none`, ...
- **Build:** `build_app.py` requires mitmproxy + PyInstaller in the current
  env (checks, then errors with install hint). `--arch universal2` passes
  `--target-arch universal2` to PyInstaller; `--clean` wipes old outputs.
  Ad-hoc codesign via `codesign --force --sign -`.

## Do not

- Assume Linux/Windows runtime paths or keychain trust.
- Commit `dist/`, `build/`, generated certs, or `*.spec`.
- Ship without the original Wispr Flow app — this project only proxies it.
- Re-introduce a background child/daemon for the proxy (see crash history).
- Add a second source file to the tool — single-file is a feature.
