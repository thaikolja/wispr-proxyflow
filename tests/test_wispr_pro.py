"""Unit tests for wispr_pro.py (rewrite logic, no mitmproxy needed)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import wispr_pro as wp


def _payload(**overrides: object) -> bytes:
    """Build a sample subscription JSON payload as bytes."""
    base = {
        "status": "expired",
        "total_trial_days": 7,
        "trial_ends_at": 1700000000,
        "credits": 0,
        "is_subscribed": False,
        "extra_field": "keep-me",
    }
    base.update(overrides)
    return json.dumps(base).encode()


def test_rewrites_subscription_fields() -> None:
    """The patch replaces every configured field and keeps the rest."""
    patch = wp.load_patch(overrides={"plan": "FLOW_PRO_MONTHLY"})
    body, original = wp.rewrite_body(_payload(), patch)
    data = json.loads(body)
    for key, value in patch.items():
        assert data[key] == value
    assert data["extra_field"] == "keep-me"
    assert original["plan"] is None


def test_no_marker_left_alone() -> None:
    """Bodies without the marker key are passed through unchanged."""
    body = json.dumps({"hello": "world"}).encode()
    assert wp.rewrite_body(body) is None


def test_invalid_json_left_alone() -> None:
    """Invalid JSON is never rewritten."""
    assert wp.rewrite_body(b'{"total_trial_days": not-valid') is None


def test_list_payload_left_alone() -> None:
    """Non-object payloads are never rewritten."""
    body = json.dumps([{"total_trial_days": 7}]).encode()
    assert wp.rewrite_body(body) is None


def test_marker_parameter() -> None:
    """A custom marker triggers the rewrite only when present."""
    body = json.dumps({"plan": "FLOW_BASIC", "daysLeft": 3}).encode()
    assert wp.rewrite_body(body, marker="daysLeft") is not None
    assert wp.rewrite_body(body, marker="total_trial_days") is None


def test_config_days_left_maps_to_daysLeft(tmp_path: Path) -> None:
    """Toml key days_left maps to the API field daysLeft."""
    cfg = tmp_path / "config.toml"
    cfg.write_text("[rewrite]\ndays_left = 90\n", encoding="utf-8")
    patch = wp.load_patch(config_path=cfg)
    assert patch["daysLeft"] == 90


def test_cli_overrides_win_over_config(tmp_path: Path) -> None:
    """CLI overrides beat the config file; unset keys fall through."""
    cfg = tmp_path / "config.toml"
    cfg.write_text('[rewrite]\nplan = "FLOW_BASIC"\ncredits = 10\n', encoding="utf-8")
    patch = wp.load_patch(config_path=cfg, overrides={"plan": "FLOW_PRO_YEARLY", "daysLeft": 400})
    assert patch["plan"] == "FLOW_PRO_YEARLY"
    assert patch["credits"] == 10
    assert patch["daysLeft"] == 400


def test_missing_config_uses_defaults(tmp_path: Path) -> None:
    """A missing config file falls back to the built-in defaults."""
    patch = wp.load_patch(config_path=tmp_path / "nope.toml")
    assert patch["plan"] == "FLOW_PRO_MONTHLY"
    assert patch["status"] == "active"


def test_rewrite_keeps_other_fields() -> None:
    """Fields outside the patch survive the rewrite untouched."""
    body = _payload(is_student=False, team_domain_status="exists")
    data = json.loads(wp.rewrite_body(body, wp.load_patch())[0])
    assert data["is_student"] is False
    assert data["team_domain_status"] == "exists"


if __name__ == "__main__":
    pytest.main([__file__])
