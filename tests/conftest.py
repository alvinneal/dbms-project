import uuid

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import AppUser
from app.security import hash_password, limiter

PASSWORD = "Correct-horse-9"


@pytest.fixture(autouse=True)
def fresh_rate_limits():
    limiter.reset()
    yield


def make_admin(email: str | None = None, password: str = PASSWORD) -> str:
    """A staff account straight in the database (there is no public way to become staff)."""
    email = email or f"admin-{uuid.uuid4().hex[:8]}@staff.example"
    with SessionLocal() as db:
        db.add(AppUser(email=email, password_hash=hash_password(password), role="admin"))
        db.commit()
    return email


def login(client: TestClient, email: str, password: str = PASSWORD) -> str:
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def anon():
    return TestClient(app)


@pytest.fixture
def admin():
    """A client logged in as a new staff member."""
    c = TestClient(app)
    c.headers.update(bearer(login(c, make_admin())))
    return c
