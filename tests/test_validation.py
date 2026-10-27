# Input validation only: no database needed, requests are rejected before any query runs.
# Login is replaced by a stand-in staff user so the checks behind it can be reached.
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app import schemas as s
from app.auth import current_user
from app.main import app
from app.models import AppUser

c = TestClient(app)


@pytest.fixture(autouse=True)
def pretend_staff():
    app.dependency_overrides[current_user] = lambda: AppUser(user_id=0, email="x@x", role="admin")
    yield
    app.dependency_overrides.clear()


def future(**kw):
    return (datetime.now() + timedelta(**kw)).replace(microsecond=0).isoformat()


def errors_of(r):
    assert r.status_code == 422, r.text
    body = r.json()
    assert isinstance(body["detail"], str)
    return {e["field"]: e["message"] for e in body["errors"]}


GOOD_CUSTOMER = {"name": "Asha  Rao", "email": "Asha@Example.COM", "phone": "+91 90000 11111", "id_proof": "pass-1234"}


def test_normalisation():
    m = s.CustomerIn(**GOOD_CUSTOMER)
    assert m.name == "Asha Rao" and m.email == "asha@example.com" and m.id_proof == "PASS-1234"
    assert s.LocationIn(name="x", city="y", code=" bom ", loc_type="Airport", latitude=1, longitude=1).code == "BOM"
    assert s.AircraftIn(registration_no="vt-abc", operator_id=1, type_id=1).registration_no == "VT-ABC"


@pytest.mark.parametrize("field,value", [
    ("email", "not-an-email"), ("phone", "12"), ("phone", "call me maybe"),
    ("name", "   "), ("name", "x" * 101), ("id_proof", "!!"),
])
def test_customer_rejects(field, value):
    r = c.post("/customers", json={**GOOD_CUSTOMER, field: value})
    assert field in errors_of(r)


def test_unknown_and_missing_fields():
    r = c.post("/customers", json={**GOOD_CUSTOMER, "is_admin": True})
    assert "is_admin" in errors_of(r)
    assert set(errors_of(c.post("/customers", json={}))) == {"name", "email", "phone", "id_proof"}


def test_master_data_ranges():
    loc = {"name": "n", "city": "c", "code": "BOM", "loc_type": "Airport", "latitude": 91, "longitude": 181}
    assert set(errors_of(c.post("/locations", json=loc))) == {"latitude", "longitude"}
    typ = {"model": "m", "category": "Rocket", "seats": 0, "range_nm": -1, "cruise_speed_kts": 0, "hourly_rate": "0"}
    assert set(errors_of(c.post("/aircraft-types", json=typ))) == {"category", "seats", "range_nm", "cruise_speed_kts", "hourly_rate"}
    ac = {"registration_no": "bad reg!", "operator_id": 0, "type_id": 1}
    assert set(errors_of(c.post("/aircraft", json=ac))) == {"registration_no", "operator_id"}


def test_patch_is_validated_too():
    assert "email" in errors_of(c.patch("/customers/1", json={"email": "nope"}))
    assert "seats" in errors_of(c.patch("/aircraft-types/1", json={"seats": -3}))
    assert "customer_id" in errors_of(c.patch("/customers/1", json={"customer_id": 9}))  # ids are not editable


def test_booking_rules():
    base = {"customer_id": 1, "aircraft_id": 1, "origin_id": 1, "dest_id": 2, "passengers": 2}
    assert "departure_time" in errors_of(c.post("/bookings", json={**base, "departure_time": future(minutes=-5)}))
    assert "departure_time" in errors_of(c.post("/bookings", json={**base, "departure_time": future(minutes=2)}))
    assert "departure_time" in errors_of(c.post("/bookings", json={**base, "departure_time": future(days=900)}))
    assert "passengers" in errors_of(c.post("/bookings", json={**base, "departure_time": future(days=3), "passengers": 0}))
    assert "dest_id" in errors_of(c.post("/bookings", json={**base, "dest_id": 1, "departure_time": future(days=3)}))


def test_timezone_aware_departure_is_accepted():
    dt = datetime.now(timezone.utc) + timedelta(days=3)
    assert s.check_departure(dt).tzinfo is None


def test_payment_rules():
    assert "amount" in errors_of(c.post("/bookings/1/payments", json={"amount": "0", "method": "UPI"}))
    assert "amount" in errors_of(c.post("/bookings/1/payments", json={"amount": "10.999", "method": "UPI"}))
    assert "method" in errors_of(c.post("/bookings/1/payments", json={"amount": "10", "method": "Cash"}))


def test_query_param_rules():
    assert "limit" in errors_of(c.get("/customers", params={"limit": 0}))
    assert "limit" in errors_of(c.get("/customers", params={"limit": 100000}))
    assert "status" in errors_of(c.get("/bookings", params={"status": "Flying"}))
    assert "passengers" in errors_of(c.get("/search", params={"origin_id": 1, "dest_id": 2, "passengers": 0,
                                                              "departure_time": future(days=2)}))
    assert "departure_time" in errors_of(c.get("/search", params={"origin_id": 1, "dest_id": 2, "passengers": 1,
                                                                  "departure_time": future(days=-2)}))


def test_account_input_rules():
    ok = {"name": "Asha", "email": "asha@example.com", "phone": "+91 90000 11111", "id_proof": "PASS-1234",
          "password": "Correct-horse-9"}
    for weak in ("short1", "alllettersnodigits", "1234567890123", "asha@example.com"):
        assert "password" in errors_of(c.post("/auth/register", json={**ok, "password": weak})), weak
    assert "role" in errors_of(c.post("/auth/register", json={**ok, "role": "admin"}))  # cannot self-promote
    assert "new_password" in errors_of(c.post("/auth/change-password",
                                              json={"current_password": "x", "new_password": "weak"}))


def test_cors_preflight_for_a_frontend():
    r = c.options("/customers", headers={"Origin": "http://localhost:5173",
                                         "Access-Control-Request-Method": "POST",
                                         "Access-Control-Request-Headers": "content-type,authorization"})
    assert r.status_code == 200 and r.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert c.options("/customers", headers={"Origin": "http://evil.example",
                                            "Access-Control-Request-Method": "POST"}).status_code == 400


def test_security_headers_and_meta():
    r = c.get("/meta")
    assert r.status_code == 200 and "Jet" in r.json()["categories"]
    assert r.headers["x-content-type-options"] == "nosniff" and r.headers["x-frame-options"] == "DENY"
    assert r.headers["cache-control"] == "no-store" and "default-src 'none'" in r.headers["content-security-policy"]


def test_hostile_requests_are_refused():
    assert c.post("/customers", content=b"x" * 70_000, headers={"content-type": "application/json"}).status_code == 413
    assert c.get("/meta", headers={"host": "evil.example"}).status_code == 400  # host-header attack
    assert c.post("/customers", content=b"{not json", headers={"content-type": "application/json"}).status_code == 422
