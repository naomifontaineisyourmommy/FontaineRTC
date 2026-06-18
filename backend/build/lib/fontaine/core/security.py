"""Panel auth primitives shared by both roles.

- Password hashing: PBKDF2-HMAC-SHA256, 200_000 iterations (as in OlcRTC-AdminVPS).
- In-memory login rate limiting: max 5 failures / 5 minutes per IP.
- Stateless signed session tokens (survive restarts; no server-side storage).
"""

import hashlib
import hmac
import secrets
import time

_PBKDF2_ITER = 200_000
_ALGO = "pbkdf2_sha256"

# --- rate limit state ---
_LOGIN_WINDOW = 300          # seconds
_LOGIN_MAX_FAILS = 5
_fails: dict[str, list[float]] = {}

# --- sessions (stateless: token = "issued.nonce.hmac") ---
_SESSION_MAX_AGE = 30 * 24 * 3600   # 30 days
_session_secret: bytes = b""


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

def set_session_secret(secret: str) -> None:
    """Set the HMAC key for signing session tokens (the panel's api_key).
    Stable across restarts, so issued tokens stay valid after update/restart."""
    global _session_secret
    _session_secret = (secret or "").encode()


def _sign(msg: str) -> str:
    return hmac.new(_session_secret, msg.encode(), hashlib.sha256).hexdigest()[:32]


def new_session() -> str:
    issued = int(time.time())
    nonce = secrets.token_hex(8)
    msg = f"{issued}.{nonce}"
    return f"{msg}.{_sign(msg)}"


def valid_session(token: str) -> bool:
    if not _session_secret or not token:
        return False
    try:
        issued_s, nonce, sig = token.split(".")
        issued = int(issued_s)
    except (ValueError, AttributeError):
        return False
    if time.time() - issued > _SESSION_MAX_AGE:
        return False
    return secrets.compare_digest(sig, _sign(f"{issued}.{nonce}"))
