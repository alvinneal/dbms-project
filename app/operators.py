from datetime import date

from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy import func, or_, select

from . import schemas as s
from .auth import OperatorUser
from .deps import DB, get_or_404
from .models import Aircraft, AircraftType, Booking, Operator, Pilot

router = APIRouter(prefix="/operator", tags=["operator"])


@router.get("/me", response_model=s.OperatorOut)
def operator_profile(user: OperatorUser, db: DB):
    return get_or_404(db, Operator, user.operator_id)


@router.get("/aircraft", response_model=list[s.AircraftOut])
def operator_aircraft(user: OperatorUser, db: DB):
    return db.scalars(select(Aircraft).where(Aircraft.operator_id == user.operator_id)
                      .order_by(Aircraft.registration_no)).unique().all()


@router.post("/aircraft", response_model=s.AircraftOut, status_code=201)
def add_aircraft(body: s.OperatorAircraftIn, user: OperatorUser, db: DB):
    """Add an aircraft to the authenticated operator's fleet."""
    get_or_404(db, AircraftType, body.type_id)
    aircraft = Aircraft(registration_no=body.registration_no, operator_id=user.operator_id,
                        type_id=body.type_id)
    db.add(aircraft)
    db.commit()
    db.refresh(aircraft)
    return aircraft


@router.get("/maintenance", response_model=list[s.AircraftOut])
def maintenance_due(user: OperatorUser, db: DB):
    return db.scalars(
        select(Aircraft).join(Operator, Operator.operator_id == Aircraft.operator_id)
        .where(Aircraft.operator_id == user.operator_id)
        .where(or_(Aircraft.status == "Maintenance",
                   Aircraft.total_hours - Aircraft.last_service_hours >= Operator.service_interval_hrs * 0.9))
        .order_by(Aircraft.total_hours - Aircraft.last_service_hours, Aircraft.registration_no)
    ).unique().all()


@router.post("/aircraft/{aircraft_id}/service", response_model=s.AircraftOut)
def service_aircraft(aircraft_id: int, body: s.ServiceIn, user: OperatorUser, db: DB):
    aircraft = get_or_404(db, Aircraft, aircraft_id, lock=True)
    if aircraft.operator_id != user.operator_id:
        raise HTTPException(404, f"Aircraft {aircraft_id} not found")
    aircraft.last_service_hours = aircraft.total_hours
    aircraft.last_service_date = date.today()
    aircraft.maintenance_cost += body.cost
    aircraft.status = "Available"
    db.commit()
    return aircraft


@router.get("/pilots", response_model=list[s.PilotOut])
def operator_pilots(user: OperatorUser, db: DB):
    return db.scalars(select(Pilot).where(Pilot.operator_id == user.operator_id)
                      .order_by(Pilot.name)).unique().all()


@router.get("/flights", response_model=list[s.BookingOut])
def operator_flights(response: Response, user: OperatorUser, db: DB,
                     limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0)):
    query = select(Booking).join(Aircraft, Aircraft.aircraft_id == Booking.aircraft_id)\
        .where(Aircraft.operator_id == user.operator_id)
    response.headers["X-Total-Count"] = str(db.scalar(select(func.count()).select_from(query.subquery())))
    return db.scalars(query.order_by(Booking.departure_time, Booking.booking_id)
                      .limit(limit).offset(offset)).unique().all()
