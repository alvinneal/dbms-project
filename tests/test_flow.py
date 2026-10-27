# End-to-end run against a real database loaded with schema.sql + routines.sql
# (set DATABASE_URL, ideally to a throwaway database such as charter_test).
# Creates its own rows with unique names, so it can rerun.
import uuid
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.database import engine
from app.main import app
from tests.conftest import bearer, login, make_admin

c = TestClient(app)


@pytest.fixture(autouse=True)
def as_staff():
    c.headers.update(bearer(login(c, make_admin())))


def post(url, body=None, status=201):
    r = c.post(url, json=body)
    assert r.status_code == status, r.text
    return r.json()


def make_fleet(service_interval=1):
    u = uuid.uuid4().hex[:6].upper()  # fresh names per call so tests never collide
    op = post("/operators", {"name": "Op", "license_no": f"L{u}", "email": f"{u}@op.in",
                             "phone": "1234567", "city": "Mumbai", "service_interval_hrs": service_interval})
    jet = post("/aircraft-types", {"model": "Jet", "category": "Jet", "seats": 6, "range_nm": 2000,
                                   "cruise_speed_kts": 400, "hourly_rate": "100000"})
    bom = post("/locations", {"name": "Mumbai", "city": "Mumbai", "code": f"B{u}", "loc_type": "Airport",
                              "latitude": "19.0896", "longitude": "72.8656"})
    del_ = post("/locations", {"name": "Delhi", "city": "Delhi", "code": f"D{u}", "loc_type": "Airport",
                               "latitude": "28.5562", "longitude": "77.1000"})
    cust = post("/customers", {"name": "Cust", "email": f"{u}@c.in", "phone": "1234567", "id_proof": "XPROOF1"})
    ac = post("/aircraft", {"registration_no": f"VT-{u}", "operator_id": op["operator_id"], "type_id": jet["type_id"]})
    pilot = post("/pilots", {"operator_id": op["operator_id"], "name": "P", "license_no": f"P{u}",
                             "category_rating": "Jet"})
    return u, op, jet, bom, del_, cust, ac, pilot


def test_health():
    assert c.get("/health").json() == {"status": "ok"}


def test_booking_flow():
    u, op, jet, bom, del_, cust, ac, pilot = make_fleet()
    assert ac["status"] == "Available" and cust["created_on"]  # DB defaults came back
    assert ac["operator_name"] == "Op" and ac["type_model"] == "Jet" and ac["seats"] == 6

    dep = (datetime.now() + timedelta(days=30)).replace(microsecond=0).isoformat()
    route = {"origin_id": bom["location_id"], "dest_id": del_["location_id"]}

    hits = c.get("/search", params={**route, "departure_time": dep, "passengers": 4}).json()
    hit = next(h for h in hits if h["aircraft_id"] == ac["aircraft_id"])
    q = c.get("/quote", params={"aircraft_id": ac["aircraft_id"], **route, "departure_time": dep}).json()
    assert q["fare"] == hit["fare"] and q["flight_hours"] == hit["flight_hours"]

    book = {"customer_id": cust["customer_id"], "aircraft_id": ac["aircraft_id"], **route,
            "departure_time": dep, "passengers": 4}
    b = post("/bookings", book)
    assert b["status"] == "Pending" and b["pilot_id"] == pilot["pilot_id"]
    assert b["customer_name"] == "Cust" and b["origin_code"] == f"B{u}" and b["balance_due"] == b["total_fare"]
    fare = b["total_fare"]

    # the aircraft is no longer offered at that time
    hits = c.get("/search", params={**route, "departure_time": dep, "passengers": 4}).json()
    assert ac["aircraft_id"] not in [h["aircraft_id"] for h in hits]

    # business rules come back as 409 with a readable message
    overlap = post("/bookings", book, status=409)["detail"]  # the only pilot is busy, and so is the aircraft
    assert "No free" in overlap or "already booked" in overlap
    assert "seats" in post("/bookings", {**book, "passengers": 9}, status=409)["detail"]
    post("/bookings", {**book, "dest_id": bom["location_id"]}, status=422)  # same place
    post("/bookings", {**book, "customer_id": 99999999}, status=404)
    # patching things that have upcoming bookings is refused
    r = c.patch(f"/pilots/{pilot['pilot_id']}", json={"status": "On leave"})
    assert r.status_code == 409, r.text
    assert c.delete(f"/aircraft/{ac['aircraft_id']}").status_code == 409

    bid = b["booking_id"]
    post(f"/bookings/{bid}/payments", {"amount": f"{fare + 1:.2f}", "method": "UPI"}, status=409)  # overpay
    p = post(f"/bookings/{bid}/payments", {"amount": "1.00", "method": "Card"})
    assert p["status"] == "Paid"
    now = c.get(f"/bookings/{bid}").json()
    assert now["status"] == "Pending" and now["amount_paid"] == 1.0
    post(f"/bookings/{bid}/payments", {"amount": f"{fare - 1:.2f}", "method": "UPI"})
    done = c.get(f"/bookings/{bid}").json()
    assert done["status"] == "Confirmed" and done["balance_due"] == 0
    post(f"/bookings/{bid}/payments", {"amount": "1.00", "method": "UPI"}, status=409)  # already confirmed

    post(f"/bookings/{bid}/complete", status=409)  # not landed yet
    with engine.begin() as conn:  # pretend the flight happened
        conn.execute(text("UPDATE booking SET departure_time = departure_time - INTERVAL '60 days', "
                          "arrival_time = arrival_time - INTERVAL '60 days' WHERE booking_id = :b"), {"b": bid})
    assert post(f"/bookings/{bid}/complete", status=200)["status"] == "Completed"
    post(f"/bookings/{bid}/complete", status=409)  # only once
    post(f"/bookings/{bid}/cancel", status=409)

    # ~1.7 flight hours > 1 hour service interval, so it got grounded
    ac = c.get(f"/aircraft/{ac['aircraft_id']}").json()
    assert ac["status"] == "Maintenance" and float(ac["total_hours"]) > 1 and ac["service_due_in_hours"] < 0
    assert "maintenance" in post("/bookings", book, status=409)["detail"]
    r = c.patch(f"/aircraft/{ac['aircraft_id']}", json={"status": "Available"})
    assert r.status_code == 409  # must go through /service
    ac = post(f"/aircraft/{ac['aircraft_id']}/service", {"cost": "5000"}, status=200)
    assert ac["status"] == "Available" and ac["last_service_hours"] == ac["total_hours"]

    # cancel refunds payments
    b2 = post("/bookings", {**book, "passengers": 2})
    post(f"/bookings/{b2['booking_id']}/payments", {"amount": "10.00", "method": "Card"})
    cancelled = post(f"/bookings/{b2['booking_id']}/cancel", status=200)
    assert cancelled["status"] == "Cancelled" and cancelled["balance_due"] == 0
    assert c.get(f"/bookings/{b2['booking_id']}/payments").json()[0]["status"] == "Refunded"

    # referenced rows can't be deleted
    r = c.delete(f"/operators/{op['operator_id']}")
    assert r.status_code == 409 and "cannot be deleted" in r.json()["detail"]


def test_lists_filters_and_duplicates():
    u, op, *_ = make_fleet()
    r = c.get("/operators", params={"q": u, "limit": 5})
    assert r.status_code == 200 and int(r.headers["X-Total-Count"]) >= 1
    assert c.get("/aircraft", params={"status": "Available", "operator_id": op["operator_id"]}).json()
    assert c.get("/aircraft", params={"status": "Broken"}).status_code == 422
    dup = c.post("/customers", json={"name": "Dup", "email": f"{u}@c.in".upper(), "phone": "1234567", "id_proof": "XPROOF1"})
    assert dup.status_code == 409 and "already exists" in dup.json()["detail"]
    assert c.get("/customers/99999999").status_code == 404
    assert c.post("/aircraft", json={"registration_no": "VT-NOPE", "operator_id": 99999999, "type_id": 1}).status_code == 422
    assert c.get("/stats").json()["bookings_by_status"] is not None
