"""Shared signing helper: Appendix A vector, canonicalisation, wrong salt, salt loading."""
import hashlib
import hmac
import json

import pytest

from app.core import config
from app.core.config import ConfigError, load_settings
from app.core.signing import canonical, request_hash, sign_record

VECTOR = "972a8b558690b19121cc5bea84978f85e8eb15a3735018db36616bab1d7ec501"


def test_official_vector_with_injected_demo_salt():
    sig = sign_record("evt-1", {"team_id": "t1", "event_type": "goal"}, salt="demo-salt")
    assert sig == VECTOR
    assert len(sig) == 64 and sig == sig.lower()


def test_canonical_form_sorted_compact_unicode_literal():
    assert canonical({"b": 1, "a": {"z": [3, 1], "y": None}}) == '{"a":{"y":null,"z":[3,1]},"b":1}'
    assert canonical({"name": "Zoë ✓"}) == '{"name":"Zoë ✓"}'          # not \u-escaped
    assert canonical({"t": True, "f": False, "n": 5}) == '{"f":false,"n":5,"t":true}'


def test_key_order_and_nesting_do_not_change_signature():
    a = sign_record("id-1", {"x": {"b": 1, "a": 2}, "arr": [{"q": 1, "p": 2}]}, salt="s")
    b = sign_record("id-1", {"arr": [{"p": 2, "q": 1}], "x": {"a": 2, "b": 1}}, salt="s")
    assert a == b


def test_array_order_is_significant():
    assert sign_record("i", {"a": [1, 2]}, salt="s") != sign_record("i", {"a": [2, 1]}, salt="s")


def test_wrong_salt_and_wrong_id_change_signature():
    base = sign_record("evt-1", {"k": 1}, salt="demo-salt")
    assert sign_record("evt-1", {"k": 1}, salt="other") != base
    assert sign_record("evt-2", {"k": 1}, salt="demo-salt") != base


def test_matches_reference_implementation_for_unicode_payload():
    payload = {"reason": "الغاء الهدف", "n": 3}
    msg = ("cmp-1|" + json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)).encode()
    expected = hmac.new(b"demo-salt", msg, hashlib.sha256).hexdigest()
    assert sign_record("cmp-1", payload, salt="demo-salt") == expected


def test_nan_is_rejected():
    with pytest.raises(ValueError):
        canonical({"x": float("nan")})


def test_salt_is_required_and_not_in_repr():
    with pytest.raises(ConfigError):
        load_settings({})
    with pytest.raises(ConfigError):
        load_settings({"DAY1_SALT": ""})
    s = load_settings({"DAY1_SALT": "TOP-SECRET-VALUE"})
    assert "TOP-SECRET-VALUE" not in repr(s)
    assert s.day1_salt == "TOP-SECRET-VALUE"          # never trimmed/decoded


def test_get_settings_reads_environment_once():
    config.set_settings(None)
    first = config.get_settings()
    assert config.get_settings() is first


def test_request_hash_is_order_independent():
    assert request_hash({"a": 1, "b": 2}) == request_hash({"b": 2, "a": 1})
