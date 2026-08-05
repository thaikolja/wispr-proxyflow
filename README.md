# Wispr Proxyflow

![Version](https://img.shields.io/github/v/release/thaikolja/wispr-proxyflow?label=version) ![Platform](https://img.shields.io/badge/platform-macOS-black) ![Python](https://img.shields.io/badge/python-3.11%2B-blue) ![License](https://img.shields.io/github/license/thaikolja/wispr-proxyflow) ![CI](https://img.shields.io/github/actions/workflow/status/thaikolja/wispr-proxyflow/ci.yml)

**Wispr Proxyflow** is a small, single-file tool for macOS. It starts a local proxy and rewrites Wispr Flow's subscription response, so the app shows the **Pro** plan. Everything runs on your Mac. Nothing is sent to Wispr's servers on your behalf. You still need the original [Wispr Flow](https://wisprflow.ai) app as base app.

> [!IMPORTANT]
>
> Read more in the [official documentation](https://thaikolja.github.io/wispr-proxyflow/).

## Quick Start

1. Go to [Releases](https://github.com/thaikolja/wispr-proxyflow/releases) and download the newest `.dmg`.
2. Open the `.dmg` and drag `Wispr Proxyflow.app` to your `/Applications` folder.
3. Double-click the app. It starts the proxy and relaunches Wispr Flow — the plan shows **Pro**.

> First time opening a downloaded app? Right-click it → **Open** (macOS blocks unsigned downloads otherwise).

4. To stop the proxy: open Terminal and run:

```bash
"/Applications/Wispr Proxyflow.app/Contents/MacOS/wispr-pro" stop
```

## Start with Git

Clone the repository and run it straight from the source:

```bash
git clone https://github.com/thaikolja/wispr-proxyflow.git
cd wispr-proxyflow

# Install virtual environment, source into it, and install
python3 -m venv .venv && source .venv/bin/activate

# Install via live mode
pip install -e ".[dev]"

# Run your commands
python3 wispr_pro.py start       # start proxy + relaunch Wispr Flow → Pro
python3 wispr_pro.py status      # check proxy / app state
python3 wispr_pro.py stop        # stop proxy + quit Wispr Flow
```

The first run creates a CA under `~/.wispr_pro/`. If the app cannot connect, trust the CA once:

```bash
python3 wispr_pro.py trust      # asks for your password
```

Run the proxy in the background:

```bash
nohup python3 wispr_pro.py start >/tmp/wispr-pro.log 2>&1 &
```

## Build the macOS App

One command builds a ready-to-use `.app` for Apple Silicon (Python and mitmproxy are bundled inside):

```bash
python3 build_app.py                          # dist/Wispr Proxyflow.app (arm64)
python3 build_app.py --arch universal2        # arm64 + Intel
python3 build_app.py --name "Wispr Proxyflow" # custom name
```

A ready-made `.dmg` with the `.app` inside is built and published automatically for every release (see the [GitHub Releases](https://github.com/thaikolja/wispr-proxyflow/releases) page).

## Commands

| Command | What It Does |
|---------|--------------|
| `wispr_pro.py start` | Start proxy (foreground) + relaunch Wispr Flow |
| `wispr_pro.py stop` | Stop proxy + quit Wispr Flow |
| `wispr_pro.py status` | Show proxy / port / app state |
| `wispr_pro.py trust` | Trust the proxy CA in the System keychain (sudo) |
| `wispr_pro.py selftest` | Verify the rewrite on a captured payload |
| `wispr_pro.py restart` | Stop, then start again |

## Customization Flags

Flags come after the command:

```bash
python3 wispr_pro.py start \
  --plan FLOW_PRO_YEARLY \      # plan: FLOW_PRO_MONTHLY (default), FLOW_PRO_YEARLY, ...
  --status active \             # status: active (default), trialing, ...
  --trial-days 30 \             # total_trial_days + daysLeft
  --trial-ends-at 1893456000 \  # unix timestamp
  --credits 99999 \             # credits
  --no-subscribed \             # --subscribed / --no-subscribed
  --days-left 30 \              # daysLeft only
  --marker total_trial_days \   # JSON key that triggers the rewrite
  --host 127.0.0.1 --port 8080 \# proxy address
  --ca-dir ~/.wispr_pro \       # state folder (config, CA, pid)
  --app "/Applications/Wispr Flow.app" \
  --no-relaunch                 # do not relaunch Wispr Flow
```

Run `python3 wispr_pro.py start --help` for the full list.

For permanent settings, edit `~/.wispr_pro/config.toml` (created on first start). Flags always win over the config file.

## Project Layout

```
wispr_pro.py          # the tool: addon + CLI (single file)
build_app.py          # build entrypoint → dist/<name>.app
assets/icon/          # app icon (.icns)
docs/                 # Nuxt documentation site
tests/                # pytest suite (no mitmproxy needed)
.github/workflows/    # CI + DMG release builds
```

## Development

```bash
# Install the app in live mode
pip install -e ".[dev]"

# Run Pytest
pytest -q

# Run Ruff to check the code style
ruff check . && ruff format --check .

# MyPy linter
mypy wispr_pro.py build_app.py

# Test the app in live mode
python3 wispr_pro.py selftest
```

The state folder `~/.wispr_pro/` (config, CA, pid) is never committed. `dist/`, `build/`, `.venv/` are gitignored. See [CHANGELOG.md](CHANGELOG.md) for release history.

## Contributors

* Kolja Nolte (kolja.nolte@gmail.com)

## License

MIT — see [LICENSE](LICENSE).
