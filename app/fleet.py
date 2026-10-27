from datetime import date, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text

from . import schemas as s
from .auth import require_admin
from .crud import refuse
from .deps import DB, count_active_bookings, get_or_404
from .models import Aircraft, Booking, Customer, Payment

# maintenance and the dashboard are staff only
router = APIRouter(dependencies=[Depends(require_admin)])


# ---------- rules for editing / deleting master data (used by the CRUD routers) ----------

def aircraft_before_update(db, aircraft: Aircraft, changes: dict):
    if aircraft.status == "Maintenance" and changes.get("status") == "Available":
        refuse("Use POST /aircraft/{id}/service to return an aircraft from maintenance")
    if ({"operator_id", "type_id"} & changes.keys()) and count_active_bookings(db, aircraft_id=aircraft.aircraft_id):
        refuse("The operator and type cannot change while the aircraft has upcoming bookings")


def aircraft_before_delete(db, aircraft: Aircraft, _):
    if count_active_bookings(db, aircraft_id=aircraft.aircraft_id):
        refuse("This aircraft has upcoming bookings; cancel them first")


def pilot_before_update(db, pilot, changes: dict):
    needs_free = {"operator_id", "category_rating"} & changes.keys() or changes.get("status") == "On leave"
    if needs_free and count_active_bookings(db, pilot_id=pilot.pilot_id):
        refuse("This pilot has upcoming bookings; they cannot change operator or rating or go on leave")


def pilot_before_delete(db, pilot, _):
    if count_active_bookings(db, pilot_id=pilot.pilot_id):
        refuse("This pilot has upcoming bookings")


# ---------- maintenance ----------

@router.post("/aircraft/{aircraft_id}/service", response_model=s.AircraftOut, tags=["maintenance"])
def service_aircraft(aircraft_id: int, body: s.ServiceIn, db: DB):
    """Record a service: reset the hours counter, add the cost, make it Available again."""
    aircraft = get_or_404(db, Aircraft, aircraft_id, lock=True)
    aircraft.last_service_hours = aircraft.total_hours
    aircraft.last_service_date = date.today()
    aircraft.maintenance_cost += body.cost
    aircraft.status = "Available"
    db.commit()
    return aircraft


@router.post("/maintenance/check", response_model=list[s.AircraftOut], tags=["maintenance"])
def maintenance_check(db: DB):
    """Ground every aircraft past its service interval; returns all aircraft now in Maintenance."""
    db.execute(text("CALL check_overdue_aircraft()"))
    db.commit()
    return db.scalars(select(Aircraft).where(Aircraft.status == "Maintenance").order_by(Aircraft.aircraft_id)).unique().all()


# ---------- dashboard ----------

@router.get("/stats", response_model=s.Stats, tags=["dashboard"])
def stats(db: DB):
    """Numbers for a dashboard landing page."""
    by_status = lambda col: dict(db.execute(select(col, func.count()).group_by(col)).all())
    collected = db.scalar(select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.status == "Paid"))
    # fare still unpaid on live bookings = fare minus what has been paid
    owed = db.scalar(select(func.coalesce(func.sum(Booking.total_fare), 0)).where(Booking.status == "Pending"))
    owed_paid = db.scalar(select(func.coalesce(func.sum(Payment.amount), 0))
                          .join(Booking, Booking.booking_id == Payment.booking_id)
                          .where(Booking.status == "Pending", Payment.status == "Paid"))
    due = db.scalar(text("""SELECT count(*) FROM aircraft a JOIN operator o USING (operator_id)
                             WHERE a.status = 'Available'
                               AND a.total_hours - a.last_service_hours > o.service_interval_hrs * 0.9"""))
    upcoming = db.scalar(select(func.count()).select_from(Booking)
                         .where(Booking.status.in_(("Pending", "Confirmed")), Booking.departure_time > datetime.now()))
    return {
        "bookings_by_status": by_status(Booking.status),
        "revenue_collected": collected,
        "outstanding_balance": owed - owed_paid,
        "aircraft_by_status": by_status(Aircraft.status),
        "aircraft_service_due": due,
        "upcoming_flights": upcoming,
        "customers": db.scalar(select(func.count()).select_from(Customer)),
    }
