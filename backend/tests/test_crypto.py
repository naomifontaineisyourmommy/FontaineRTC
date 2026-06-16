"""Round-trip + tamper tests for the shared transport crypto."""

import base64

import pytest

from fontaine.core import crypto


KEY = "a" * 64  # 32 bytes hex


def test_roundtrip():
    pt = b'{"action":"list","ts":1700000000}'
    blob = crypto.encrypt(KEY, pt)
    assert crypto.decrypt(KEY, blob) == pt


def test_nonce_randomized():
    pt = b"same plaintext"
    assert crypto.encrypt(KEY, pt) != crypto.encrypt(KEY, pt)


def test_tamper_detected():
    blob = crypto.encrypt(KEY, b"hello")
    raw = bytearray(base64.urlsafe_b64decode(blob + "=="))
    raw[-1] ^= 0x01  # flip a ciphertext bit
    tampered = base64.urlsafe_b64encode(bytes(raw)).decode()
    with pytest.raises(ValueError):
        crypto.decrypt(KEY, tampered)


def test_wrong_key_fails():
    blob = crypto.encrypt(KEY, b"hello")
    with pytest.raises(ValueError):
        crypto.decrypt("b" * 64, blob)


def test_short_payload():
    with pytest.raises(ValueError):
        crypto.decrypt(KEY, base64.urlsafe_b64encode(b"short").decode())


def test_api_key_helpers():
    k = crypto.new_api_key()
    assert crypto.valid_api_key(k)
    assert not crypto.valid_api_key("xyz")
    assert not crypto.valid_api_key("z" * 64)
