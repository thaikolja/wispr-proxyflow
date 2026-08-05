# Wispr Proxyflow

Single-file Python tool (mitmproxy addon + CLI) that starts a local
intercepting proxy and rewrites Wispr Flow's subscription API response so
the app shows the **Pro** plan (`plan: FLOW_PRO_MONTHLY`, `status: active`).
Everything runs locally; nothing is sent to Wispr's servers on your behalf. macOS only. Requires the original [Wispr Flow](https://wisprflow.ai) app.

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"          # dev deps: pytest, mitmproxy, pyinstaller

python3 wispr_pro.py start       # proxy + relaunch Wispr Flow → Pro
python3 wispr_pro.py status      # proxy / app state
python3 wispr_pro.py stop        # stop proxy + quit Wispr Flow
```

First run creates a CA under `~/.wispr_pro/`. If the app can't connect,
trust it once: `python3 wispr_pro.py trust` (asks for your password).

Run in the background:

```bash
nohup python3 wispr_pro.py start >/tmp/wispr-pro.log 2>&1 &
```

## Build the macOS app (Apple Silicon)

One entrypoint, everything bundled (Python + mitmproxy):

```bash
python3 build_app.py                        # dist/Wispr Pro.app (arm64)
python3 build_app.py --arch universal2      # arm64 + Intel fat binary
python3 build_app.py --name "Wispr Pro"
```

Double-click `dist/Wispr Pro.app` to start the proxy in the background
(logs: `~/.wispr_pro/proxy.log`), or use its CLI directly:

```bash
"dist/Wispr Pro.app/Contents/MacOS/wispr-pro" start --no-relaunch
```

## Commands

| Command | What it does |
|---------|--------------|
| `wispr_pro.py start` | Start proxy (foreground) + relaunch Wispr Flow |
| `wispr_pro.py stop` | Stop proxy + quit Wispr Flow |
| `wispr_pro.py status` | Show proxy / port / app state |
| `wispr_pro.py trust` | Trust the proxy CA in the System keychain (sudo) |
| `wispr_pro.py selftest` | Verify the rewrite on a captured payload |
| `wispr_pro.py restart` | Stop, then start again |

## Customization flags

```bash
python3 wispr_pro.py start \
  --plan FLOW_PRO_YEARLY \      # plan: FLOW_PRO_MONTHLY (default), FLOW_PRO_YEARLY, ...
  --status active \             # status: active (default), trialing, ...
  --trial-days 30 \             # total_trial_days + daysLeft
  --trial-ends-at 1893456000 \  # unix timestamp
  --credits 99999 \             # credits
  --no-subscribed \             # --subscribed / --no-subscribed (is_subscribed)
  --days-left 30 \              # daysLeft only
  --marker total_trial_days \   # JSON key that triggers the rewrite
  --host 127.0.0.1 --port 8080 \# proxy bind address
  --ca-dir ~/.wispr_pro \       # state dir (config, CA, pid)
  --app "/Applications/Wispr Flow.app" \
  --no-relaunch                 # don't relaunch Wispr Flow
```

Persistent values live in `~/.wispr_pro/config.toml` (created on first
`start`); flags override them.

## How it works

1. A local mitmproxy rewrites responses to
   `/api/v1/payment/subscription` — if the body contains the marker key
   (`total_trial_days`) it is patched (plan/status/credits/…).
2. Wispr Flow is relaunched with `--proxy-server=http://127.0.0.1:8080
   --ignore-certificate-errors` so its traffic goes through the proxy.
3. Log lines look like:
   `[PRO] rewrote /api/v1/payment/subscription?...: {...FLOW_BASIC...} -> {...FLOW_PRO_MONTHLY...}`

Only the app's *displayed* state changes. Unrelated responses, non-JSON
payloads and other hosts are passed through untouched.

## Project layout

```
wispr_pro.py          # the tool: addon + CLI (single file)
build_app.py          # build entrypoint → dist/<name>.app
assets/icon/          # app icon (.icns)
tests/                # pytest (rewrite logic, no mitmproxy needed)
pyproject.toml        # dev deps + pytest config
.github/workflows/    # CI: pytest + CLI smoke
```

## Development

```bash
pip install -e ".[dev]"
pytest -q
python3 wispr_pro.py selftest
```

State dir `~/.wispr_pro/` (config.toml, proxy.pid, mitmproxy/ CA) is never
committed. `dist/`, `build/`, `.venv/` are gitignored.

## Notes

- Educational project — it does not modify the Wispr Flow app itself and
  does not claim to. MIT licensed.
