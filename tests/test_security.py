# Login, roles, ownership and abuse protection against a real database.
import uuid
from datetime import datetime, timedelta

import jwt
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.security import create_token
from tests.conftest import PASSWORD, bearer, login, make_admin


def uid():
    return uuid.uuid4().hex[:8]


def register(client, email=None, password=PASSWORD):
    email = email or f"cust-{uid()}@example.com"
    r = client.post("/auth/register", json={"name": "Test Customer", "email": email, "phone": "+91 90000 11111",
                                            "id_proof": f"PASS-{uid().upper()}", "password": password})
    assert r.status_code == 201, r.text
    body = r.json()
    return email, TestClient(app, headers=bearer(body["access_token"])), body["user"]


def fleet(admin):
    """Minimal fleet: returns (aircraft, origin, dest)."""
    u = uid().upper()
    op = admin.post("/operators", json={"name": "Op", "license_no": f"L{u}", "email": f"{u}@op.in",
                                        "phone": "1234567", "city": "Pune", "service_interval_hrs": 500}).json()
    t = admin.post("/aircraft-types", json={"model": "J", "category": "Jet", "seats": 6, "range_nm": 2000,
                                            "cruise_speed_kts": 400, "hourly_rate": "100000"}).json()
    a = admin.post("/locations", json={"name": "A", "city": "A", "code": f"A{u}", "loc_type": "Airport",
                                       "latitude": "19.0896", "longitude": "72.8656"}).json()
    b = admin.post("/locations", json={"name": "B", "city": "B", "code": f"B{u}", "loc_type": "Airport",
                                       "latitude": "28.5562", "longitude": "77.1000"}).json()
    ac = admin.post("/aircraft", json={"registration_no": f"VT-{u}", "operator_id": op["operator_id"],
                                       "type_id": t["type_id"]}).json()
    admin.post("/pilots", json={"operator_id": op["operator_id"], "name": "P", "license_no": f"P{u}",
                                "category_rating": "Jet"})
    return ac, a, b


def test_health_reports_login_table(anon):
    assert anon.get("/health").json() == {"status": "ok"}


# ---------- who may call what ----------

def test_logged_out_requests_are_refused(anon):
    for method, url in [("get", "/bookings"), ("get", "/customers"), ("get", "/stats"), ("get", "/aircraft"),
                        ("post", "/bookings"), ("post", "/operators"), ("get", "/search"), ("get", "/auth/me"),
                        ("post", "/maintenance/check"), ("delete", "/pilots/1")]:
        r = getattr(anon, method)(url)
        assert r.status_code == 401, (method, url, r.status_code)
        assert r.headers["www-authenticate"] == "Bearer"
    assert anon.get("/locations").status_code == 200  # public on purpose
    assert anon.get("/meta").status_code == 200


def test_customers_cannot_use_staff_endpoints(anon):
    _, cust, _ = register(anon)
    for method, url in [("get", "/customers"), ("get", "/operators"), ("get", "/pilots"), ("get", "/aircraft"),
                        ("get", "/stats"), ("post", "/maintenance/check"), ("post", "/locations"),
                        ("post", "/aircraft-types"), ("delete", "/locations/1"), ("post", "/bookings/1/complete"),
                        ("post", "/aircraft/1/service")]:
        assert getattr(cust, method)(url).status_code == 403, (method, url)
    assert cust.get("/aircraft-types").status_code == 200  # the catalogue is readable


def test_register_cannot_create_staff_or_duplicates(anon):
    email, _, user = register(anon)
    assert user["role"] == "customer" and user["customer"]["email"] == email
    dup = anon.post("/auth/register", json={"name": "Again", "email": email.upper(), "phone": "1234567",
                                            "id_proof": "PASS-DUP1", "password": PASSWORD})
    assert dup.status_code == 409


# ---------- ownership: one customer must not reach another's data ----------

def test_customers_only_see_their_own_bookings(anon, admin):
    ac, a, b = fleet(admin)
    _, alice, alice_user = register(anon)
    _, bob, bob_user = register(anon)
    dep = (datetime.now() + timedelta(days=20)).replace(microsecond=0).isoformat()
    book = {"aircraft_id": ac["aircraft_id"], "origin_id": a["location_id"], "dest_id": b["location_id"],
            "departure_time": dep, "passengers": 2}

    r = alice.post("/bookings", json=book)  # no customer_id: it is her own
    assert r.status_code == 201, r.text
    mine = r.json()
    assert mine["customer_id"] == alice_user["customer"]["customer_id"]

    # she cannot book on someone else's behalf
    assert alice.post("/bookings", json={**book, "customer_id": bob_user["customer"]["customer_id"]}).status_code == 403
    # staff must say who it is for
    assert admin.post("/bookings", json=book).status_code == 422

    bid = mine["booking_id"]
    assert [x["booking_id"] for x in alice.get("/bookings").json()] == [bid]
    assert bob.get("/bookings").json() == []
    assert bob.get("/bookings", params={"customer_id": alice_user["customer"]["customer_id"]}).status_code == 403
    for method, url, body in [("get", f"/bookings/{bid}", None), ("post", f"/bookings/{bid}/cancel", None),
                              ("get", f"/bookings/{bid}/payments", None),
                              ("post", f"/bookings/{bid}/payments", {"amount": "10", "method": "UPI"})]:
        r = bob.request(method, url, json=body)
        assert r.status_code == 404, (url, r.status_code)  # not 403: she is not told it exists
    assert alice.post(f"/bookings/{bid}/payments", json={"amount": "10", "method": "UPI"}).status_code == 201
    assert admin.get(f"/bookings/{bid}").status_code == 200  # staff see everything
    assert alice.post(f"/bookings/{bid}/cancel").json()["status"] == "Cancelled"


# ---------- tokens ----------

def test_bad_tokens_are_rejected(anon):
    assert anon.get("/auth/me", headers=bearer("garbage")).status_code == 401
    assert anon.get("/auth/me", headers={"Authorization": "Basic abc"}).status_code == 401

    email, cust, user = register(anon)
    ok = create_token(user["user_id"], 0)
    assert anon.get("/auth/me", headers=bearer(ok)).status_code == 200
    # signed with another key
    forged = jwt.encode({"sub": str(user["user_id"]), "tv": 0, "exp": 9999999999}, "x" * 40, algorithm="HS256")
    assert anon.get("/auth/me", headers=bearer(forged)).status_code == 401
    # "alg: none" trick
    unsigned = jwt.encode({"sub": str(user["user_id"]), "tv": 0, "exp": 9999999999}, None, algorithm="none")
    assert anon.get("/auth/me", headers=bearer(unsigned)).status_code == 401
    # expired
    expired = jwt.encode({"sub": str(user["user_id"]), "tv": 0, "exp": 1}, settings.secret_key, algorithm="HS256")
    assert anon.get("/auth/me", headers=bearer(expired)).status_code == 401
    # a token for a user that does not exist
    assert anon.get("/auth/me", headers=bearer(create_token(99999999, 0))).status_code == 401


def test_changing_password_signs_out_old_tokens(anon):
    email, cust, _ = register(anon)
    assert cust.post("/auth/change-password", json={"current_password": "wrong-password-1",
                                                    "new_password": "Another-pass-77"}).status_code == 403
    r = cust.post("/auth/change-password", json={"current_password": PASSWORD, "new_password": "Another-pass-77"})
    assert r.status_code == 200
    assert cust.get("/auth/me").status_code == 401  # the old token is dead
    assert anon.get("/auth/me", headers=bearer(r.json()["access_token"])).status_code == 200
    assert anon.post("/auth/login", json={"email": email, "password": PASSWORD}).status_code == 401
    assert anon.post("/auth/login", json={"email": email, "password": "Another-pass-77"}).status_code == 200


def test_login_forms_and_me(anon):
    email, _, _ = register(anon)
    r = anon.post("/auth/token", data={"username": email, "password": PASSWORD})  # what /docs "Authorize" sends
    assert r.status_code == 200 and r.json()["token_type"] == "bearer" and r.json()["expires_in"] > 0
    me = anon.get("/auth/me", headers=bearer(r.json()["access_token"])).json()
    assert me["email"] == email and "password_hash" not in me and "password" not in str(me)
    upd = anon.patch("/auth/me", json={"phone": "+91 99999 00000"}, headers=bearer(r.json()["access_token"])).json()
    assert upd["customer"]["phone"] == "+91 99999 00000"
    assert anon.patch("/auth/me", json={"role": "admin"}, headers=bearer(r.json()["access_token"])).status_code == 422


# ---------- brute force ----------

def test_wrong_passwords_lock_the_account(anon):
    email, _, _ = register(anon)
    for _ in range(settings.max_failed_logins):
        r = anon.post("/auth/login", json={"email": email, "password": "wrong-password-1"})
        assert r.status_code == 401
        anon.app.state  # (limits are reset per test, so the lockout - not the IP limit - is what we hit)
        from app.security import limiter
        limiter.reset()
    r = anon.post("/auth/login", json={"email": email, "password": PASSWORD})  # even the right one now
    assert r.status_code == 429 and "locked" in r.json()["detail"]


def test_login_does_not_reveal_which_part_was_wrong(anon):
    email, _, _ = register(anon)
    unknown = anon.post("/auth/login", json={"email": f"nobody-{uid()}@example.com", "password": PASSWORD})
    wrong = anon.post("/auth/login", json={"email": email, "password": "wrong-password-1"})
    assert unknown.status_code == wrong.status_code == 401 and unknown.json() == wrong.json()


def test_auth_endpoints_are_rate_limited(anon):
    codes = [anon.post("/auth/login", json={"email": f"x{i}@example.com", "password": "nope-nope-1"}).status_code
             for i in range(settings.auth_rate_limit_per_minute + 3)]
    assert codes[:settings.auth_rate_limit_per_minute] == [401] * settings.auth_rate_limit_per_minute
    assert set(codes[settings.auth_rate_limit_per_minute:]) == {429}


def test_disabled_account_is_locked_out_immediately(anon, admin):
    from app.database import SessionLocal
    from app.models import AppUser
    email, cust, user = register(anon)
    with SessionLocal() as db:
        db.get(AppUser, user["user_id"]).is_active = False
        db.commit()
    assert cust.get("/auth/me").status_code == 401  # existing token stops working at once
    assert anon.post("/auth/login", json={"email": email, "password": PASSWORD}).status_code == 401


# ---------- injection and abuse ----------

def test_injection_attempts_are_inert(anon, admin):
    evil = "'; DROP TABLE customer; --"
    assert admin.get("/customers", params={"q": evil}).status_code == 200
    assert admin.get("/customers", params={"q": "%"}).headers["x-total-count"] == "0"  # % is not a wildcard
    assert anon.post("/auth/login", json={"email": evil, "password": evil}).status_code == 401
    r = admin.post("/customers", json={"name": evil, "email": f"{uid()}@x.in", "phone": "1234567", "id_proof": "PROOF-1"})
    assert r.status_code == 201 and r.json()["name"] == evil  # stored as text, never executed
    assert admin.get("/customers").status_code == 200  # table still there


def test_errors_do_not_leak_internals(admin):
    r = admin.get("/customers/abc")
    assert r.status_code == 422
    r = admin.post("/aircraft", json={"registration_no": "VT-NOPE", "operator_id": 99999999, "type_id": 99999999})
    assert r.status_code == 422 and "psycopg" not in r.text and "SELECT" not in r.text and "Traceback" not in r.text
