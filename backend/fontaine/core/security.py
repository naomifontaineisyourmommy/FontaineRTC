"""Panel auth primitives shared by both roles.

- Password hashing: PBKDF2-HMAC-SHA256, 200_000 iterations (as in OlcRTC-AdminVPS).
- In-memory login rate limiting: max 5 failures / 5 minutes per IP.
- In-memory session tokens.
"""

import hashlib
import secrets
import time

_PBKDF2_ITER = 200_000
_ALGO = "pbkdf2_sha256"

# --- rate limit state ---
_LOGIN_WINDOW = 300          # seconds
_LOGIN_MAX_FAILS = 5
_fails: dict[str, list[float]] = {}

# --- sessions ---
_sessions: dict[str, float] = {}   # token -> created_at


def hash_password(pw: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), _PBKDF2_ITER)
    return f"{_ALGO}${_PBKDF2_ITER}${salt}${dk.hex()}"


def verify_password(pw: str, stored: str) -> bool:
    try:
        algo, iters, salt, digest = stored.split("$")
        if algo != _ALGO:
            return False
        dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), int(iters))
        return secrets.compare_digest(dk.hex(), digest)
    except (ValueError, AttributeError):
        return False


def is_hashed(stored: str) -> bool:
    return isinstance(stored, str) and stored.startswith(_ALGO + "$")


# --- rate limiting ---

def login_blocked(ip: str) -> bool:
    now = time.time()
    hits = [t for t in _fails.get(ip, []) if now - t < _LOGIN_WINDOW]
    _fails[ip] = hits
    return len(hits) >= _LOGIN_MAX_FAILS


def login_record_fail(ip: str) -> None:
    _fails.setdefault(ip, []).append(time.time())


def login_reset(ip: str) -> None:
    _fails.pop(ip, None)


# --- sessions ---

def new_session() -> str:
    token = secrets.token_urlsafe(32)
    _sessions[token] = time.time()
    return token


def valid_session(token: str) -> bool:
    return token in _sessions


def drop_session(token: str) -> None:
    _sessions.pop(token, None)
