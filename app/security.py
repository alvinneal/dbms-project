# Password hashing, login tokens and rate limiting. Nothing here touches the database.
import base64
import hashlib
import hmac
import secrets
import threading
import time
from collections import defaultdict, deque

import jwt

from .config import settings

# ---------- passwords: scrypt from the standard library (memory-hard, salted) ----------

_N, _R, _P = 2 ** 14, 8, 1


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=32)
    return f"scrypt${_N}${_R}${_P}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, n, r, p, salt, digest = stored.split("$")
        expected = base64.b64decode(digest)
        actual = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt),
                                n=int(n), r=int(r), p=int(p), dklen=len(expected))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)  # constant time


# verified against when the email is unknown, so "no such user" takes as long as "wrong password"
DUMMY_HASH = hash_password(secrets.token_urlsafe(12))


# ---------- login tokens (JWT, HS256) ----------

ALGORITHM = "HS256"


def create_token(user_id: int, token_version: int) -> str:
    now = int(time.time())
    claims = {"sub": str(user_id), "tv": token_version, "iat": now,
              "exp": now + settings.access_token_minutes * 60}
    return jwt.encode(claims, settings.secret_key, algorithm=ALGORITHM)


def read_token(token: str) -> dict | None:
    """The claims of a valid, unexpired token, else None. The algorithm is pinned, never taken from the token."""
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM],
                          options={"require": ["exp", "sub", "tv"]})
    except jwt.PyJWTError:
        return None


# ---------- rate limiting: sliding window per key, in memory ----------
# shortcut: state lives in this process, so with several workers each has its own
# counters; move to Redis (or the reverse proxy) if you scale out.

class RateLimiter:
    def __init__(self):
        self.hits: dict[str, deque] = defaultdict(deque)
        self.lock = threading.Lock()

    def check(self, key: str, limit: int, window: float = 60.0) -> float:
        """Record a hit. Returns 0 if allowed, else the seconds until the client may retry."""
        now = time.monotonic()
        with self.lock:
            q = self.hits[key]
            while q and q[0] <= now - window:
                q.popleft()
            if len(q) >= limit:
                return max(q[0] + window - now, 1.0)
            q.append(now)
            if len(self.hits) > 10_000:  # forget idle clients so the table cannot grow without bound
                for k in [k for k, v in self.hits.items() if not v or v[-1] <= now - window]:
                    del self.hits[k]
            return 0.0

    def reset(self):
        with self.lock:
            self.hits.clear()


limiter = RateLimiter()
