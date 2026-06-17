"""Stateless session tokens survive restarts (same secret) but not key changes."""

from fontaine.core import security


def test_session_survives_restart():
    security.set_session_secret("k" * 64)
    tok = security.new_session()
    assert security.valid_session(tok)
    # simulate a service restart: the same api_key is loaded again
    security.set_session_secret("k" * 64)
    assert security.valid_session(tok)


def test_session_rejects_other_secret_and_garbage():
    security.set_session_secret("k" * 64)
    tok = security.new_session()
    security.set_session_secret("x" * 64)
    assert not security.valid_session(tok)
    assert not security.valid_session("garbage")
    assert not security.valid_session("")


def test_password_hash_roundtrip():
    h = security.hash_password("secret")
    assert security.is_hashed(h)
    assert security.verify_password("secret", h)
    assert not security.verify_password("wrong", h)
