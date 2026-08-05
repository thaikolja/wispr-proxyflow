#!/usr/bin/env python3

"""Wispr Flow -> Pro — local MITM helper (single file, macOS).

Starts a local intercepting proxy that rewrites Wispr Flow's subscription
API response so the app shows the Pro plan (plan: FLOW_PRO_MONTHLY,
status: active). Requires the original Wispr Flow app to be installed.

Usage:
    python3 wispr_pro.py start --plan FLOW_PRO_YEARLY --credits 500
    python3 wispr_pro.py start --no-relaunch --port 8081
    python3 wispr_pro.py status | stop | trust | selftest
    nohup python3 wispr_pro.py start >/tmp/wispr-pro.log 2>&1 &   # background

State lives in ~/.wispr_pro/ (override with --ca-dir): config.toml,
proxy.pid, mitmproxy/ (CA + data). Requires Python 3.11+ and mitmproxy.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import socket
import subprocess
import sys
import time
from copy import deepcopy
from pathlib import Path

APP_NAME = "Wispr Flow"
DEFAULT_APP_BUNDLE = Path("/Applications/Wispr Flow.app")
PGREP_PATTERN = r"Wispr Flow\.app/Contents/MacOS/Wispr Flow"

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8080
DEFAULT_CA_DIR = Path.home() / ".wispr_pro"

DEFAULT_REWRITE = {
    "status": "active",
    "plan": "FLOW_PRO_MONTHLY",
    "total_trial_days": 365,
    "trial_ends_at": 1893456000,
    "credits": 99999,
    "is_subscribed": True,
    "daysLeft": 365,
}

DEFAULT_MARKER = "total_trial_days"
PLANS = (
    "FLOW_BASIC",
    "FLOW_PRO_MONTHLY",
    "FLOW_PRO_YEARLY",
    "FLOW_STUDENT_MONTHLY",
    "FLOW_STUDENT_YEARLY",
    "FLOW_TEAM_MONTHLY",
    "FLOW_TEAM_YEARLY",
    "FLOW_BUSINESS_MONTHLY",
    "FLOW_BUSINESS_YEARLY",
)

# Mutable runtime state (set by cmd_start; read by the addon in-process).
CA_DIR: Path = DEFAULT_CA_DIR
APP_BUNDLE: Path = DEFAULT_APP_BUNDLE
MARKER: str = DEFAULT_MARKER
_OVERRIDES: dict = {}

log = logging.getLogger("wispr_pro")


# ---------------------------------------------------------------------------
# paths + config
# ---------------------------------------------------------------------------
def conf_dir() -> Path:
    """Path to the mitmproxy config and CA directory."""
    return CA_DIR / "mitmproxy"


def config_file() -> Path:
    """Path to the persistent config.toml."""
    return CA_DIR / "config.toml"


def pid_file() -> Path:
    """Path to the proxy PID file."""
    return CA_DIR / "proxy.pid"


def ca_cert() -> Path:
    """Path to the mitmproxy CA certificate."""
    return conf_dir() / "mitmproxy-ca-cert.pem"


DEFAULT_CONFIG_TOML = f"""\
# Wispr Pro bypass config (default: ~/.wispr_pro/config.toml)
[rewrite]
status = "active"
plan = "FLOW_PRO_MONTHLY"
total_trial_days = 365
trial_ends_at = 1893456000
credits = 99999
is_subscribed = true
days_left = 365
marker = "{DEFAULT_MARKER}"
"""


def write_config() -> None:
    """Create the default config.toml if missing."""
    CA_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = config_file()
    if not path.is_file():
        path.write_text(DEFAULT_CONFIG_TOML, encoding="utf-8")
        print(f"[setup] wrote {path}")


def load_patch(config_path: Path | None = None, overrides: dict | None = None) -> dict:
    """Defaults <- config.toml [rewrite] <- CLI overrides (days_left -> daysLeft)."""
    patch = deepcopy(DEFAULT_REWRITE)
    try:
        import tomllib
    except ImportError:
        return patch
    path = config_path or config_file()
    if path.is_file():
        try:
            with path.open("rb") as fh:
                data = tomllib.load(fh)
        except (tomllib.TOMLDecodeError, OSError):
            data = {}
        rw = data.get("rewrite") or {}
        for key in ("status", "plan"):
            if key in rw:
                patch[key] = str(rw[key])
        for key in ("total_trial_days", "trial_ends_at", "credits", "days_left"):
            if key in rw:
                patch["daysLeft" if key == "days_left" else key] = int(rw[key])
        if "is_subscribed" in rw:
            patch["is_subscribed"] = bool(rw["is_subscribed"])
    if overrides:
        patch.update(overrides)
    return patch


def rewrite_body(
    body: bytes,
    patch: dict | None = None,
    marker: str = DEFAULT_MARKER,
) -> tuple[bytes, dict] | None:
    """Return (rewritten body, original values) if this is a subscription payload."""
    if marker.encode() not in body:
        return None
    if patch is None:
        patch = load_patch()
    try:
        data = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(data, dict) or marker not in data:
        return None
    original = {k: data.get(k) for k in patch}
    data.update(patch)
    return json.dumps(data, separators=(",", ":")).encode(), original


# ---------------------------------------------------------------------------
# mitmproxy addon (defined only when mitmproxy is importable)
# ---------------------------------------------------------------------------
try:
    from mitmproxy import http
except ImportError:
    http = None  # type: ignore[assignment]


class WisprProAddon:
    """Rewrite Wispr Flow subscription responses to the configured profile."""

    def response(self, flow: http.HTTPFlow) -> None:
        """Patch subscription responses that carry the marker key."""
        if http is None or flow.response is None or flow.response.content is None:
            return
        patch = load_patch()
        result = rewrite_body(flow.response.content, patch, MARKER)
        if result is None:
            return
        body, original = result
        flow.response.content = body
        flow.response.headers.pop("Content-Encoding", None)
        flow.response.headers["Content-Length"] = str(len(body))
        path = flow.request.path if flow.request else "?"
        print(
            f"[PRO] rewrote {path}: {json.dumps(original)} -> {json.dumps(patch)}",
            flush=True,
        )


addons = [WisprProAddon()] if http is not None else []


# ---------------------------------------------------------------------------
# process helpers
# ---------------------------------------------------------------------------
def port_open(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> bool:
    """Return True if the proxy port accepts connections."""
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


def daemon_pid() -> int | None:
    """Return the live proxy PID from the pid file, or None."""
    path = pid_file()
    if not path.is_file():
        return None
    try:
        pid = int(path.read_text().strip())
    except ValueError:
        return None
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, PermissionError):
        return None
    return pid


def write_pid() -> None:
    """Write the current process PID to the pid file."""
    CA_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    pid_file().write_text(str(os.getpid()))


def remove_pid() -> None:
    """Remove the pid file if present."""
    pid_file().unlink(missing_ok=True)


def app_running() -> bool:
    """Return True if the Wispr Flow app process is running."""
    return subprocess.run(["pgrep", "-f", PGREP_PATTERN], capture_output=True).returncode == 0


def quit_app() -> None:
    """Quit Wispr Flow gracefully, force-kill as a fallback."""
    subprocess.run(["osascript", "-e", f'quit app "{APP_NAME}"'], capture_output=True)
    for _ in range(int(3.0 / 0.5)):
        if not app_running():
            return
        time.sleep(0.5)
    subprocess.run(["pkill", "-f", PGREP_PATTERN], capture_output=True)
    time.sleep(1)


def relaunch_app(host: str, port: int) -> None:
    """Relaunch Wispr Flow through the local proxy."""
    if not APP_BUNDLE.is_dir():
        raise SystemExit(f"[error] app not found at {APP_BUNDLE}")
    quit_app()
    subprocess.run(
        [
            "open",
            "-na",
            str(APP_BUNDLE),
            "--args",
            f"--proxy-server=http://{host}:{port}",
            "--ignore-certificate-errors",
        ],
        check=False,
    )
    print(f"[app] relaunched {APP_BUNDLE} through {host}:{port}")


def trust_hint() -> None:
    """Print a hint when the proxy CA is not trusted yet."""
    if not ca_cert().is_file():
        print(
            "[trust] CA not generated yet - run `start` once, then `trust` "
            "if the app fails to connect",
        )
        return
    for cn in ("Wispr Bypass CA", "mitmproxy"):
        if (
            subprocess.run(
                ["security", "find-certificate", "-c", cn, "-a", "-Z"],
                capture_output=True,
            ).returncode
            == 0
        ):
            print("[trust] CA already trusted in keychain")
            return
    print(f"[trust] CA not trusted yet - run: python3 {sys.argv[0]} trust")


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------
def cmd_start(args: argparse.Namespace) -> int:
    """Start the proxy in-process and relaunch Wispr Flow."""
    global CA_DIR, APP_BUNDLE, MARKER, _OVERRIDES
    host = args.host or DEFAULT_HOST
    port = args.port or DEFAULT_PORT
    if args.ca_dir:
        CA_DIR = Path(args.ca_dir).expanduser()
    if args.app:
        APP_BUNDLE = Path(args.app).expanduser()
    if args.marker:
        MARKER = args.marker

    overrides: dict = {}
    if args.status is not None:
        overrides["status"] = args.status
    if args.plan is not None:
        overrides["plan"] = args.plan
    if args.trial_days is not None:
        overrides["total_trial_days"] = args.trial_days
        if args.days_left is None:
            overrides["daysLeft"] = args.trial_days
    if args.trial_ends_at is not None:
        overrides["trial_ends_at"] = args.trial_ends_at
    if args.credits is not None:
        overrides["credits"] = args.credits
    if args.subscribed is not None:
        overrides["is_subscribed"] = args.subscribed
    if args.days_left is not None:
        overrides["daysLeft"] = args.days_left
    _OVERRIDES = overrides

    write_config()
    if port_open(host, port):
        raise SystemExit(
            f"[error] port {host}:{port} already in use - is a proxy already running? "
            f"(check `python3 {Path(sys.argv[0]).name} status`)",
        )
    write_pid()
    trust_hint()
    if not args.no_relaunch:
        relaunch_app(host, port)
    print(
        f"[start] serving on {host}:{port} - Ctrl+C to stop, "
        f"or `python3 {Path(sys.argv[0]).name} stop` from another terminal",
    )
    try:
        return cmd_serve(host, port)
    finally:
        remove_pid()


def cmd_serve(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> int:
    """Serve the proxy in-process (foreground)."""
    try:
        import asyncio

        from mitmproxy.options import Options
        from mitmproxy.tools.dump import DumpMaster
    except ImportError as exc:
        raise SystemExit(f"[error] mitmproxy missing in this environment: {exc}") from exc

    async def _amain() -> None:
        options = Options()
        master = DumpMaster(options, loop=asyncio.get_running_loop())
        options.update(
            listen_host=host,
            listen_port=port,
            confdir=str(conf_dir()),
            ssl_insecure=True,
            termlog_verbosity="error",
        )
        master.addons.add(WisprProAddon())
        print(f"[serve] listening on {host}:{port} (confdir {conf_dir()})", flush=True)
        await master.run()

    asyncio.run(_amain())
    return 0


def cmd_stop(_args: argparse.Namespace) -> int:
    """Stop the running proxy and quit Wispr Flow."""
    pid = daemon_pid()
    if pid:
        os.kill(pid, 15)
        try:
            if os.getpgid(pid) != os.getpgrp():
                os.killpg(os.getpgid(pid), 15)
        except (ProcessLookupError, PermissionError):
            pass
        for _ in range(20):
            if not port_open():
                break
            time.sleep(0.5)
        print(f"[proxy] stopped (pid {pid})")
    else:
        print("[proxy] not running")
    remove_pid()
    if app_running():
        quit_app()
        print("[app] quit")
    return 0


def cmd_status(_args: argparse.Namespace) -> int:
    """Print proxy, port and app state."""
    pid = daemon_pid()
    up = pid is not None and port_open()
    print(f"proxy:   {f'up (pid {pid})' if up else 'down'}")
    print(f"port:    {DEFAULT_HOST}:{DEFAULT_PORT} {'open' if port_open() else 'closed'}")
    print(f"app:     {'running' if app_running() else 'not running'}")
    print(f"config:  {config_file()}")
    print(f"ca-dir:  {CA_DIR}")
    return 0


def cmd_trust(_args: argparse.Namespace) -> int:
    """Trust the proxy CA in the System keychain (requires sudo)."""
    if not ca_cert().is_file():
        raise SystemExit("[error] no CA yet - run `start` once first")
    rc = subprocess.run(
        [
            "sudo",
            "security",
            "add-trusted-cert",
            "-d",
            "-r",
            "trustRoot",
            "-k",
            "/Library/Keychains/System.keychain",
            str(ca_cert()),
        ],
    ).returncode
    print("[trust] done" if rc == 0 else "[error] trust failed")
    return rc


def cmd_selftest(_args: argparse.Namespace) -> int:
    """Verify the rewrite logic on a captured payload."""
    payload = {
        "credits": 2,
        "is_student": False,
        "total_trial_days": 31,
        "status": "none",
        "plan": "FLOW_BASIC",
        "is_subscribed": False,
        "renews_at": 0,
    }
    patch = load_patch()
    result = rewrite_body(json.dumps(payload).encode(), patch)
    if result is None:
        raise SystemExit("[error] rewrite did not trigger - marker not found")
    _, original = result
    print(f"[selftest] patch:   {json.dumps(patch)}")
    print(f"[selftest] rewrote: {json.dumps(original)}")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _add_common(p: argparse.ArgumentParser) -> None:
    """Register shared proxy and rewrite flags on the given parser."""
    g = p.add_argument_group("proxy")
    g.add_argument("--host", default=None, help=f"proxy bind host (default {DEFAULT_HOST})")
    g.add_argument("--port", type=int, default=None, help=f"proxy port (default {DEFAULT_PORT})")
    g.add_argument("--ca-dir", metavar="DIR", help=f"state dir (default {DEFAULT_CA_DIR})")
    g.add_argument(
        "--app",
        metavar="PATH",
        help=f"Wispr Flow app bundle (default {DEFAULT_APP_BUNDLE})",
    )
    g.add_argument("--no-relaunch", action="store_true", help="do not relaunch Wispr Flow")
    g = p.add_argument_group("rewrite")
    g.add_argument(
        "--marker",
        metavar="KEY",
        help=f"JSON key that triggers rewrite (default {DEFAULT_MARKER})",
    )
    g.add_argument("--status", metavar="VALUE", help="forced status (active, trialing, ...)")
    g.add_argument("--plan", metavar="PLAN", help=f"forced plan, one of: {', '.join(PLANS)}")
    g.add_argument("--trial-days", type=int, metavar="N", help="forced total_trial_days + daysLeft")
    g.add_argument(
        "--trial-ends-at",
        type=int,
        metavar="UNIX",
        help="forced trial_ends_at timestamp",
    )
    g.add_argument("--credits", type=int, metavar="N", help="forced credits")
    g.add_argument(
        "--subscribed",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="forced is_subscribed (--subscribed / --no-subscribed)",
    )
    g.add_argument("--days-left", type=int, metavar="N", help="forced daysLeft")


def main() -> int:
    """Parse CLI arguments and dispatch to the matching command."""
    parser = argparse.ArgumentParser(
        prog="wispr_pro.py",
        description="Wispr Flow -> Pro: local MITM that rewrites the subscription response.",
    )
    parser.add_argument("--serve", action="store_true", help=argparse.SUPPRESS, dest="serve_flag")
    parser.add_argument("--host", default=DEFAULT_HOST, help=argparse.SUPPRESS)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=argparse.SUPPRESS)

    sub = parser.add_subparsers(dest="command")
    start = sub.add_parser("start", help="start proxy (foreground) + relaunch Wispr Flow")
    _add_common(start)
    start.set_defaults(func=cmd_start)
    restart = sub.add_parser("restart", help="stop then start")
    _add_common(restart)
    restart.set_defaults(func=None)
    sub.add_parser("stop", help="stop proxy + quit Wispr Flow").set_defaults(func=cmd_stop)
    sub.add_parser("status", help="show proxy / app state").set_defaults(func=cmd_status)
    sub.add_parser("trust", help="trust proxy CA in System keychain (sudo)").set_defaults(
        func=cmd_trust,
    )
    sub.add_parser("selftest", help="verify the rewrite on a captured payload").set_defaults(
        func=cmd_selftest,
    )

    args = parser.parse_args()
    if args.serve_flag:
        return cmd_serve(args.host, args.port)
    if args.command is None:
        parser.print_help()
        return 2
    if args.command == "restart":
        cmd_stop(args)
        return cmd_start(args)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
