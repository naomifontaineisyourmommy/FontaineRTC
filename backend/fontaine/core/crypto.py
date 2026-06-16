"""Shared transport crypto for FontaineRTC.

Hash-CTR stream cipher + HMAC-SHA256, pure stdlib (no dependencies).
Ported 1:1 from OlcRTC-VPS / OlcRTC-AdminVPS so the node<->admin protocol
stays wire-compatible with existing deployments during migration.

Wire format (base64url):  nonce(16) | HMAC-SHA256(32) | ciphertext
Key: 64-char HEX string (the per-node ``api_key``).
"""

import base64
import hashlib
import hmac as _hmac
import secrets

__all__ = ["keystream", "encrypt", "decrypt", "new_api_key", "valid_api_key"]


def keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    buf, ctr = bytearray(), 0
    while len(buf) < length:
        buf += hashlib.sha256(key + nonce + ctr.to_bytes(8, "big")).digest()
        ctr += 1
    return bytes(buf[:length])


def encrypt(api_key_hex: str, plaintext: bytes) -> str:
    """Encrypt bytes -> base64url string (nonce|mac|ciphertext)."""
    key = bytes.fromhex(api_key_hex)
    nonce = secrets.token_bytes(16)
    ct = bytes(a ^ b for a, b in zip(plaintext, keystream(key, nonce, len(plaintext))))
    mac = _hmac.new(key, nonce + ct, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(nonce + mac + ct).decode()


def decrypt(api_key_hex: str, b64data: str) -> bytes:
    """Decrypt base64url string -> bytes. Raises ValueError on auth failure."""
    key = bytes.fromhex(api_key_hex)
    raw = base64.urlsafe_b64decode(b64data + "==")
    if len(raw) < 48:
        raise ValueError("payload too short")
    nonce, mac, ct = raw[:16], raw[16:48], raw[48:]
    expected = _hmac.new(key, nonce + ct, hashlib.sha256).digest()
    if not secrets.compare_digest(mac, expected):
        raise ValueError("mac mismatch")
    return bytes(a ^ b for a, b in zip(ct, keystream(key, nonce, len(ct))))


def new_api_key() -> str:
    """Generate a fresh 64-char HEX API key."""
    return secrets.token_hex(32)


def valid_api_key(k: str) -> bool:
    if not isinstance(k, str) or len(k) != 64:
        return False
    try:
        bytes.fromhex(k)
    except ValueError:
        return False
    return True
