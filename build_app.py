#!/usr/bin/env python3
"""Build the macOS Wispr Pro .app (Apple Silicon) from wispr_pro.py.

Single entrypoint: produces dist/<name>.app containing the onefile proxy
binary, a double-click launcher (starts the proxy in the background), the
app icon and an Info.plist (LSUIElement, no dock icon).

Usage:
    python3 build_app.py                     # dist/Wispr Pro.app (arm64)
    python3 build_app.py --arch universal2   # arm64 + x86_64 fat binary
    python3 build_app.py --name "Wispr Pro"

Requires: Python 3.11+, mitmproxy, PyInstaller in the current environment:
    python3 -m pip install mitmproxy pyinstaller
"""

from __future__ import annotations

import argparse
import importlib.util
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCRIPT = ROOT / "wispr_pro.py"
DEFAULT_ICON = ROOT / "assets" / "icon" / "AppIcon.icns"

VERSION = "1.0.0"
BUNDLE_ID = "com.local.wispr-pro"
BINARY_NAME = "wispr-pro"
LAUNCHER_NAME = "wispr-pro-launcher"


def _check_deps() -> None:
    """Fail with an install hint if build dependencies are missing."""
    missing = [pkg for pkg in ("mitmproxy", "PyInstaller") if not _importable(pkg)]
    if missing:
        raise SystemExit(
            f"[error] missing build dependencies: {', '.join(missing)}\n"
            f"Install them with: {sys.executable} -m pip install mitmproxy pyinstaller",
        )


def _importable(pkg: str) -> bool:
    """Return True if the package can be imported in this environment."""
    return importlib.util.find_spec(pkg) is not None


def _run(cmd: list[str]) -> None:
    """Run a command in the project root, failing the build on error."""
    print(f"[build] $ {' '.join(cmd)}")
    subprocess.run(cmd, check=True, cwd=ROOT)


def _build_binary(arch: str, clean: bool) -> Path:
    """Build the PyInstaller onefile binary and return its path."""
    out = ROOT / "dist" / BINARY_NAME
    if clean:
        shutil.rmtree(out, ignore_errors=True)
    args = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--onefile",
        "--name",
        BINARY_NAME,
        "--clean",
        "--noupx",
        "--collect-all",
        "mitmproxy",
    ]
    if arch == "universal2":
        args += ["--target-arch", "universal2"]
    args.append(str(SCRIPT))
    _run(args)
    return out


def _write_info_plist(app: Path, name: str) -> None:
    """Write the app bundle Info.plist (background agent, no dock icon)."""
    info = {
        "CFBundleName": name,
        "CFBundleDisplayName": name,
        "CFBundleExecutable": LAUNCHER_NAME,
        "CFBundleIdentifier": BUNDLE_ID,
        "CFBundleIconFile": "AppIcon",
        "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": VERSION,
        "CFBundleVersion": VERSION,
        "LSMinimumSystemVersion": "12.0",
        "LSUIElement": True,
        "NSHighResolutionCapable": True,
        "NSAppleEventsUsageDescription": (
            "Needed to quit and relaunch Wispr Flow through the local proxy."
        ),
    }
    with (app / "Contents" / "Info.plist").open("wb") as fh:
        plistlib.dump(info, fh)


def _write_launcher(app: Path) -> None:
    """Write the double-click launcher that starts the proxy in the background."""
    script = f"""#!/bin/sh
# Double-click entry: start the Wispr Pro proxy in the background.
# Logs go to ${{WISPR_PRO_LOG:-~/.wispr_pro/proxy.log}}.
DIR="$(cd "$(dirname "$0")" && pwd)"
LOG="${{WISPR_PRO_LOG:-$HOME/.wispr_pro/proxy.log}}"
mkdir -p "$(dirname "$LOG")"
exec "$DIR/{BINARY_NAME}" start >>"$LOG" 2>&1
"""
    path = app / "Contents" / "MacOS" / LAUNCHER_NAME
    path.write_text(script, encoding="utf-8")
    path.chmod(0o755)


def _assemble_app(binary: Path, name: str, icon: Path | None) -> Path:
    """Assemble the .app bundle around the binary, then ad-hoc codesign it."""
    app = ROOT / "dist" / f"{name}.app"
    shutil.rmtree(app, ignore_errors=True)
    contents = app / "Contents"
    (contents / "MacOS").mkdir(parents=True)
    (contents / "Resources").mkdir(parents=True)
    shutil.copy2(binary, contents / "MacOS" / BINARY_NAME)
    (contents / "MacOS" / BINARY_NAME).chmod(0o755)
    _write_launcher(app)
    _write_info_plist(app, name)
    if icon is not None and icon.is_file():
        shutil.copy2(icon, contents / "Resources" / "AppIcon.icns")
    _run(["codesign", "--force", "--sign", "-", str(app)])
    return app


def main() -> int:
    """Parse build options and produce dist/<name>.app."""
    parser = argparse.ArgumentParser(
        description="Build the Wispr Pro .app for macOS (Apple Silicon).",
    )
    parser.add_argument("--name", default="Wispr Pro", help="app name (default: Wispr Pro)")
    parser.add_argument(
        "--arch",
        choices=("arm64", "universal2"),
        default="arm64",
        help="target architecture (default: arm64; universal2 = arm64 + x86_64)",
    )
    parser.add_argument("--icon", default=None, help=f"icon .icns (default: {DEFAULT_ICON})")
    parser.add_argument("--clean", action="store_true", help="remove previous build outputs first")
    args = parser.parse_args()

    _check_deps()
    if not SCRIPT.is_file():
        raise SystemExit(f"[error] {SCRIPT} not found")
    icon = Path(args.icon).expanduser() if args.icon else DEFAULT_ICON

    print(f"[build] wispr_pro.py -> dist/{args.name}.app ({args.arch})")
    binary = _build_binary(args.arch, args.clean)
    app = _assemble_app(binary, args.name, icon)

    size = sum(p.stat().st_size for p in app.rglob("*")) / 1_000_000
    print(f"[done] {app} ({size:.0f} MB)")
    print("       double-click to start the proxy, or use the CLI:")
    print(f"       {app / 'Contents' / 'MacOS' / BINARY_NAME} start|stop|status|trust|selftest")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
