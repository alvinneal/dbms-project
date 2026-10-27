# Maps the existing tables in schema.sql. Tables, functions and triggers are
# created by schema.sql / routines.sql, not by SQLAlchemy.
# The relationships and properties below are read-only conveniences so a
# response can carry names/codes/balances instead of bare ids.
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import FetchedValue, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base

ZERO = Decimal("0.00")
# column has a DEFAULT in schema.sql: leave it out of INSERTs and read back what the database chose
DB_DEFAULT = dict(server_default=FetchedValue())


class Operator(Base):
    __tablename__ = "operator"
    operator_id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    license_no: Mapped[str]
    email: Mapped[str]
    phone: Mapped[str]
    city: Mapped[str]
    service_interval_hrs: Mapped[int] = mapped_column(**DB_DEFAULT)


class AircraftType(Base):
    __tablename__ = "aircraft_type"
    type_id: Mapped[int] = mapped_column(primary_key=True)
    model: Mapped[str]
    category: Mapped[str]
    seats: Mapped[int]
    range_nm: Mapped[int]
    cruise_speed_kts: Mapped[int]
    hourly_rate: Mapped[Decimal]


class Location(Base):
    __tablename__ = "location"
    location_id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    city: Mapped[str]
    code: Mapped[str]
    loc_type: Mapped[str]
    latitude: Mapped[Decimal]
    longitude: Mapped[Decimal]


class Customer(Base):
    __tablename__ = "customer"
    customer_id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    email: Mapped[str]
    phone: Mapped[str]
    id_proof: Mapped[str]
    created_on: Mapped[date] = mapped_column(**DB_DEFAULT)


class Aircraft(Base):
    __tablename__ = "aircraft"
    aircraft_id: Mapped[int] = mapped_column(primary_key=True)
    registration_no: Mapped[str]
    operator_id: Mapped[int] = mapped_column(ForeignKey("operator.operator_id"))
    type_id: Mapped[int] = mapped_column(ForeignKey("aircraft_type.type_id"))
    status: Mapped[str] = mapped_column(**DB_DEFAULT)
    total_hours: Mapped[Decimal] = mapped_column(**DB_DEFAULT)
    last_service_hours: Mapped[Decimal] = mapped_column(**DB_DEFAULT)
    last_service_date: Mapped[date | None]
    maintenance_cost: Mapped[Decimal] = mapped_column(**DB_DEFAULT)

    operator: Mapped[Operator] = relationship(lazy="joined", viewonly=True)
    aircraft_type: Mapped[AircraftType] = relationship(lazy="joined", viewonly=True)

    @property
    def operator_name(self) -> str:
        return self.operator.name

    @property
    def type_model(self) -> str:
        return self.aircraft_type.model

    @property
    def category(self) -> str:
        return self.aircraft_type.category

    @property
    def seats(self) -> int:
        return self.aircraft_type.seats

    @property
    def hours_since_service(self) -> Decimal:
        return self.total_hours - self.last_service_hours

    @property
    def service_due_in_hours(self) -> Decimal:
        return self.operator.service_interval_hrs - self.hours_since_service


class Pilot(Base):
    __tablename__ = "pilot"
    pilot_id: Mapped[int] = mapped_column(primary_key=True)
    operator_id: Mapped[int] = mapped_column(ForeignKey("operator.operator_id"))
    name: Mapped[str]
    license_no: Mapped[str]
    category_rating: Mapped[str]
    experience_hours: Mapped[Decimal] = mapped_column(**DB_DEFAULT)
    status: Mapped[str] = mapped_column(**DB_DEFAULT)

    operator: Mapped[Operator] = relationship(lazy="joined", viewonly=True)

    @property
    def operator_name(self) -> str:
        return self.operator.name


class Booking(Base):
    __tablename__ = "booking"
    booking_id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customer.customer_id"))
    aircraft_id: Mapped[int] = mapped_column(ForeignKey("aircraft.aircraft_id"))
    pilot_id: Mapped[int] = mapped_column(ForeignKey("pilot.pilot_id"))
    origin_id: Mapped[int] = mapped_column(ForeignKey("location.location_id"))
    dest_id: Mapped[int] = mapped_column(ForeignKey("location.location_id"))
    departure_time: Mapped[datetime]
    arrival_time: Mapped[datetime]
    passengers: Mapped[int]
    status: Mapped[str]
    total_fare: Mapped[Decimal]

    customer: Mapped[Customer] = relationship(lazy="joined", viewonly=True)
    aircraft: Mapped[Aircraft] = relationship(lazy="joined", viewonly=True)
    pilot: Mapped[Pilot] = relationship(lazy="joined", viewonly=True)
    origin: Mapped[Location] = relationship(foreign_keys=[origin_id], lazy="joined", viewonly=True)
    destination: Mapped[Location] = relationship(foreign_keys=[dest_id], lazy="joined", viewonly=True)
    payments: Mapped[list["Payment"]] = relationship(lazy="selectin", viewonly=True)

    @property
    def customer_name(self) -> str:
        return self.customer.name

    @property
    def registration_no(self) -> str:
        return self.aircraft.registration_no

    @property
    def aircraft_model(self) -> str:
        return self.aircraft.type_model

    @property
    def pilot_name(self) -> str:
        return self.pilot.name

    @property
    def origin_code(self) -> str:
        return self.origin.code

    @property
    def dest_code(self) -> str:
        return self.destination.code

    @property
    def amount_paid(self) -> Decimal:
        return sum((p.amount for p in self.payments if p.status == "Paid"), ZERO)

    @property
    def balance_due(self) -> Decimal:
        if self.status == "Cancelled":
            return ZERO
        return max(self.total_fare - self.amount_paid, ZERO)


class AppUser(Base):
    """A login (see auth.sql). Role 'customer' owns one customer row; 'admin' is staff."""
    __tablename__ = "app_user"
    user_id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str]
    password_hash: Mapped[str]
    role: Mapped[str]
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customer.customer_id"))
    is_active: Mapped[bool] = mapped_column(**DB_DEFAULT)
    failed_logins: Mapped[int] = mapped_column(**DB_DEFAULT)
    locked_until: Mapped[datetime | None]
    token_version: Mapped[int] = mapped_column(**DB_DEFAULT)
    created_at: Mapped[datetime] = mapped_column(**DB_DEFAULT)

    customer: Mapped[Customer | None] = relationship(lazy="joined", viewonly=True)

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


class Payment(Base):
    __tablename__ = "payment"
    payment_id: Mapped[int] = mapped_column(primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("booking.booking_id"))
    amount: Mapped[Decimal]
    method: Mapped[str]
    paid_on: Mapped[date] = mapped_column(**DB_DEFAULT)
    status: Mapped[str] = mapped_column(**DB_DEFAULT)
