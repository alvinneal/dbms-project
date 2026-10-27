from datetime import datetime
from typing import Annotated

from fastapi import Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .database import get_db
from .models import Booking

DB = Annotated[Session, Depends(get_db)]


def get_or_404(db: Session, model, id: int, lock: bool = False):
    # `of` locks just this table; Postgres refuses a bare FOR UPDATE with the outer joins of eager-loaded relationships
    obj = db.get(model, id, with_for_update={"of": model} if lock else None)
    if obj is None:
        raise HTTPException(404, f"{model.__name__} {id} not found")
    return obj


class Page:
    """?limit=&offset= query parameters, shared by every list endpoint."""

    def __init__(self, limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0)):
        self.limit, self.offset = limit, offset


def count_active_bookings(db: Session, **column_equals) -> int:
    """Pending/Confirmed bookings that have not landed yet, e.g. count_active_bookings(db, pilot_id=3)."""
    q = select(func.count()).select_from(Booking).where(
        Booking.status.in_(("Pending", "Confirmed")), Booking.arrival_time > datetime.now())
    for col, value in column_equals.items():
        q = q.where(getattr(Booking, col) == value)
    return db.scalar(q)
