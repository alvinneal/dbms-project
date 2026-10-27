from datetime import date, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.exceptions import RequestValidationError
from sqlalchemy import func, select, text, update
from sqlalchemy.orm import Session

from . import schemas as s
from .auth import Admin, User, current_user
from .deps import DB, Page, get_or_404
from .models import AppUser, Aircraft, Booking, Customer, Location, Payment

# every route here needs a login; customers are further limited to their own bookings
router = APIRouter(dependencies=[Depends(current_user)])


def own_booking(db: Session, booking_id: int, user: AppUser, lock: bool = False) -> Booking:
    """The booking, or 404 if it is someone else's (a customer cannot tell it exists)."""
    booking = get_or_404(db, Booking, booking_id, lock=lock)
    if not user.is_admin and booking.customer_id != user.customer_id:
        raise HTTPException(404, f"Booking {booking_id} not found")
    return booking


def departure_param(departure_time: datetime) -> datetime:
    """Query-string version of the BookingIn departure rules."""
    try:
        return s.check_departure(departure_time)
    except ValueError as e:  # same 422 shape as any other bad input
        raise RequestValidationError([{"loc": ("query", "departure_time"), "msg": str(e), "type": "value_error"}])


Departure = Annotated[datetime, Depends(departure_param)]


def check_route(db: Session, origin_id: int, dest_id: int):
    if origin_id == dest_id:
        raise RequestValidationError([{"loc": ("query", "dest_id"), "msg": "must differ from origin_id",
                                       "type": "value_error"}])
    get_or_404(db, Location, origin_id)
    get_or_404(db, Location, dest_id)


# ---------- search & quote ----------

SEARCH_SQL = text("""
WITH c AS (
    SELECT a.aircraft_id, a.registration_no, a.operator_id, t.model, t.category, t.seats, t.hourly_rate,
           fn_distance_nm(:o, :d) AS distance_nm,
           fn_flight_hours(a.aircraft_id, :o, :d) AS hours
      FROM aircraft a JOIN aircraft_type t ON t.type_id = a.type_id
     WHERE a.status = 'Available' AND t.seats >= :pax AND t.range_nm >= fn_distance_nm(:o, :d)
)
SELECT c.aircraft_id, c.registration_no, c.model, c.category, c.seats, c.distance_nm,
       c.hours AS flight_hours,
       CAST(:dep AS timestamp) + c.hours * INTERVAL '1 hour' AS arrival_time,
       ROUND(c.hours * c.hourly_rate, 2) AS fare
  FROM c
 WHERE NOT EXISTS (SELECT 1 FROM booking b
                    WHERE b.aircraft_id = c.aircraft_id AND b.status <> 'Cancelled'
                      AND b.departure_time < CAST(:dep AS timestamp) + c.hours * INTERVAL '1 hour'
                      AND b.arrival_time > CAST(:dep AS timestamp))
   AND EXISTS (SELECT 1 FROM pilot p
                WHERE p.operator_id = c.operator_id AND p.category_rating = c.category AND p.status = 'Active'
                  AND NOT EXISTS (SELECT 1 FROM booking b
                                   WHERE b.pilot_id = p.pilot_id AND b.status <> 'Cancelled'
                                     AND b.departure_time < CAST(:dep AS timestamp) + c.hours * INTERVAL '1 hour'
                                     AND b.arrival_time > CAST(:dep AS timestamp)))
 ORDER BY fare
""")


@router.get("/search", response_model=list[s.SearchHit], tags=["bookings"])
def search(origin_id: Annotated[int, Query(gt=0)], dest_id: Annotated[int, Query(gt=0)],
           departure_time: Departure, passengers: Annotated[int, Query(gt=0, le=500)], db: DB):
    """Aircraft that can fly this route at this time: in range, enough seats, free, with a free pilot. Cheapest first."""
    check_route(db, origin_id, dest_id)
    rows = db.execute(SEARCH_SQL, {"o": origin_id, "d": dest_id, "dep": departure_time, "pax": passengers})
    return [dict(r._mapping) for r in rows]


@router.get("/quote", response_model=s.Quote, tags=["bookings"])
def quote(aircraft_id: Annotated[int, Query(gt=0)], origin_id: Annotated[int, Query(gt=0)],
          dest_id: Annotated[int, Query(gt=0)], departure_time: Departure, db: DB):
    """Distance, flight time, arrival and fare for one aircraft on a route, without booking it."""
    aircraft = get_or_404(db, Aircraft, aircraft_id)
    check_route(db, origin_id, dest_id)
    distance, hours = db.execute(
        text("SELECT fn_distance_nm(:o, :d), fn_flight_hours(:a, :o, :d)"),
        {"o": origin_id, "d": dest_id, "a": aircraft_id}).one()
    if distance > aircraft.aircraft_type.range_nm:
        raise HTTPException(409, f"Route is longer than the aircraft range of {aircraft.aircraft_type.range_nm} nm")
    return {"aircraft_id": aircraft_id, "distance_nm": distance, "flight_hours": hours,
            "departure_time": departure_time, "arrival_time": departure_time + timedelta(hours=float(hours)),
            "fare": round(hours * aircraft.aircraft_type.hourly_rate, 2)}


# ---------- bookings ----------

@router.get("/bookings", response_model=list[s.BookingOut], tags=["bookings"])
def list_bookings(response: Response, db: DB, user: User, page: Annotated[Page, Depends()],
                  customer_id: int | None = None, aircraft_id: int | None = None, pilot_id: int | None = None,
                  status: s.BookingStatus | None = None,
                  departs_from: Annotated[date | None, Query(description="departure on or after")] = None,
                  departs_to: Annotated[date | None, Query(description="departure on or before")] = None):
    """Soonest departure first. Total matches in the X-Total-Count header. Customers see only their own."""
    if not user.is_admin:
        if customer_id not in (None, user.customer_id):
            raise HTTPException(403, "You can only list your own bookings")
        customer_id = user.customer_id
    q = select(Booking)
    for col, value in (("customer_id", customer_id), ("aircraft_id", aircraft_id),
                       ("pilot_id", pilot_id), ("status", status)):
        if value is not None:
            q = q.where(getattr(Booking, col) == value)
    if departs_from:
        q = q.where(Booking.departure_time >= departs_from)
    if departs_to:
        q = q.where(Booking.departure_time < departs_to + timedelta(days=1))
    response.headers["X-Total-Count"] = str(db.scalar(select(func.count()).select_from(q.subquery())))
    q = q.order_by(Booking.departure_time, Booking.booking_id).limit(page.limit).offset(page.offset)
    return db.scalars(q).unique().all()


@router.get("/bookings/{booking_id}", response_model=s.BookingOut, tags=["bookings"])
def get_booking(booking_id: int, db: DB, user: User):
    return own_booking(db, booking_id, user)


@router.post("/bookings", response_model=s.BookingOut, status_code=201, tags=["bookings"])
def create_booking(body: s.BookingIn, db: DB, user: User):
    """Range, fare, arrival and pilot are worked out by the book_flight procedure. Starts as Pending until fully paid.

    Customers book for themselves (omit customer_id); staff must pass the customer_id.
    """
    if user.is_admin:
        if body.customer_id is None:
            raise RequestValidationError([{"loc": ("body", "customer_id"), "msg": "is required for staff",
                                           "type": "missing"}])
        customer_id = body.customer_id
    elif body.customer_id not in (None, user.customer_id):
        raise HTTPException(403, "You can only book for yourself")
    else:
        customer_id = user.customer_id
    get_or_404(db, Customer, customer_id)
    aircraft = get_or_404(db, Aircraft, body.aircraft_id)
    check_route(db, body.origin_id, body.dest_id)
    # clear messages up front; the procedure and its trigger enforce the same rules for real
    if aircraft.status != "Available":
        raise HTTPException(409, f"Aircraft {aircraft.registration_no} is in maintenance")
    if body.passengers > aircraft.seats:
        raise HTTPException(409, f"Passengers ({body.passengers}) exceed the aircraft seats ({aircraft.seats})")

    # The overlap check in the trigger can't see uncommitted bookings, so two
    # requests at once could double-book. Serialize booking creation.
    # shortcut: one global lock, fine for a small operator; lock per aircraft/pilot if it gets busy.
    db.execute(text("SELECT pg_advisory_xact_lock(1)"))
    booking_id = db.execute(
        text("CALL book_flight(:c, :a, :o, :d, CAST(:dep AS timestamp), :pax, NULL)"),
        {"c": customer_id, "a": body.aircraft_id, "o": body.origin_id, "d": body.dest_id,
         "dep": body.departure_time, "pax": body.passengers},
    ).scalar_one()
    db.commit()
    return db.get(Booking, booking_id)


@router.post("/bookings/{booking_id}/cancel", response_model=s.BookingOut, tags=["bookings"])
def cancel_booking(booking_id: int, db: DB, user: User):
    """Cancel before departure; every payment on it is marked Refunded."""
    booking = own_booking(db, booking_id, user, lock=True)
    if booking.status not in ("Pending", "Confirmed"):
        raise HTTPException(409, f"A {booking.status} booking cannot be cancelled")
    if booking.departure_time <= datetime.now():
        raise HTTPException(409, "The flight has already departed")
    booking.status = "Cancelled"
    db.execute(update(Payment).where(Payment.booking_id == booking_id, Payment.status == "Paid")
               .values(status="Refunded"))
    db.commit()
    return booking


@router.post("/bookings/{booking_id}/complete", response_model=s.BookingOut, tags=["bookings"])
def complete_booking(booking_id: int, db: DB, _: Admin):
    """Staff only. Mark the flight flown, add hours to aircraft and pilot, then ground anything overdue for service."""
    # lock first so two calls at once can't add the hours twice
    booking = get_or_404(db, Booking, booking_id, lock=True)
    if booking.status != "Confirmed":
        raise HTTPException(409, f"Only a Confirmed booking can be completed (this one is {booking.status})")
    if booking.arrival_time > datetime.now():
        raise HTTPException(409, "The flight has not landed yet")
    db.execute(text("CALL complete_flight(:b)"), {"b": booking_id})
    db.execute(text("CALL check_overdue_aircraft()"))
    db.commit()
    return booking


# ---------- payments ----------

@router.get("/bookings/{booking_id}/payments", response_model=list[s.PaymentOut], tags=["payments"])
def list_payments(booking_id: int, db: DB, user: User):
    own_booking(db, booking_id, user)
    return db.scalars(select(Payment).where(Payment.booking_id == booking_id).order_by(Payment.payment_id)).all()


@router.post("/bookings/{booking_id}/payments", response_model=s.PaymentOut, status_code=201, tags=["payments"])
def pay(booking_id: int, body: s.PaymentIn, db: DB, user: User):
    """Part payments are fine. Overpayment is rejected; a fully paid booking is confirmed by the payment trigger."""
    # lock so two payments at once can't both slip under the fare
    booking = own_booking(db, booking_id, user, lock=True)
    if booking.status != "Pending":
        raise HTTPException(409, f"A {booking.status} booking cannot take payments")
    if booking.departure_time <= datetime.now():
        raise HTTPException(409, "The flight has already departed")
    if body.amount > booking.balance_due:
        raise HTTPException(409, f"Payment exceeds the balance due ({booking.balance_due})")
    payment = Payment(booking_id=booking_id, **body.model_dump())
    db.add(payment)
    db.commit()
    return payment
