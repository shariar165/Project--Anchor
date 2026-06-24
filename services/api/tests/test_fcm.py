"""
Regression tests for FCM message construction (services/fcm.py).

Focus: the webpush deep-link must never break message encoding. The firebase-admin
encoder rejects a non-https WebpushFCMOptions.link with ValueError, which previously
caused EVERY web push (test push + real alert fan-out) to fail with delivered=0.
These tests run the built message through the real encoder without needing a live
Firebase project.
"""
import json

import pytest
from firebase_admin import _messaging_encoder

from app.services import fcm


def _encode(msg):
    """Run a firebase-admin Message through the production encoder (raises on bad fields)."""
    return json.dumps(msg, cls=_messaging_encoder.MessageEncoder)


def test_relative_deep_link_encodes_without_frontend_url():
    """No FRONTEND_URL configured (test env default) → fcm_options omitted → no ValueError."""
    msg = fcm._message("tok", "Title", "Body", {"deep_link": "/?alert=abc"}, 3600)
    _encode(msg)  # must not raise


def test_default_deep_link_encodes():
    """Test-push payload (no deep_link → '/') must also encode cleanly."""
    msg = fcm._message("tok", "Title", "Body", {"category": "test"}, 3600)
    _encode(msg)


def test_no_fcm_options_when_frontend_unset(monkeypatch):
    monkeypatch.setattr(
        "app.config.get_settings",
        lambda: type("S", (), {"frontend_url": ""})(),
    )
    cfg = fcm._webpush_config("t", "b", {"deep_link": "/?alert=abc"})
    assert cfg.fcm_options is None


def test_https_frontend_sets_absolute_link(monkeypatch):
    monkeypatch.setattr(
        "app.config.get_settings",
        lambda: type("S", (), {"frontend_url": "https://app.example"})(),
    )
    cfg = fcm._webpush_config("t", "b", {"deep_link": "/?alert=abc"})
    assert cfg.fcm_options.link == "https://app.example/?alert=abc"
    # And the full message still encodes with the absolute https link.
    msg = fcm._message("tok", "t", "b", {"deep_link": "/?alert=abc"}, 3600)
    _encode(msg)


def test_non_https_frontend_is_ignored(monkeypatch):
    """A plain-http FRONTEND_URL must NOT be used as a link (encoder requires https)."""
    monkeypatch.setattr(
        "app.config.get_settings",
        lambda: type("S", (), {"frontend_url": "http://localhost:8080"})(),
    )
    cfg = fcm._webpush_config("t", "b", {"deep_link": "/?alert=abc"})
    assert cfg.fcm_options is None
    _encode(fcm._message("tok", "t", "b", {"deep_link": "/?alert=abc"}, 3600))
