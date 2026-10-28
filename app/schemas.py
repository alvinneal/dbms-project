# Request bodies (*In) are strict and normalise their input (trim, upper/lower case).
# Responses (*Out) are deliberately plain: they must be able to describe any row
# already in the database, so they carry no validation.
# Optional fields left out of a request fall back to the column DEFAULT in the database.
import re
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import (AfterValidator, BaseModel, ConfigDict, EmailStr, Field,
                      PlainSerializer, StringConstraints, field_validator)

from .config import settings

Category = Literal["Helicopter", "Jet", "Turboprop"]
BookingStatus = Literal["Pending", "Confirmed", "Completed", "Cancelled"]
AircraftStatus = Literal["Available", "Maintenance"]
PilotStatus = Literal["Active", "On leave"]
PayMethod = Literal["Card", "UPI", "Bank transfer"]


# ---------- reusable input types ----------

def _upper(v: str) -> str:
    return v.upper()


def _lower(v: str) -> str:
    return v.lower()


def _matches(pattern: str, message: str):
    rx = re.compile(pattern)

    def check(v: str) -> str:
        if not rx.fullmatch(v):
            raise ValueError(message)
        return v
    return AfterValidator(check)


def _text(max_length: int, min_length: int = 1):
    return StringConstraints(strip_whitespace=True, min_length=min_length, max_length=max_length)


def _collapse_spaces(v: str) -> str:
    return re.sub(r"\s+", " ", v)


Name = Annotated[str, _text(100), AfterValidator(_collapse_spaces)]
City = Annotated[str, _text(50), AfterValidator(_collapse_spaces)]
Email = Annotated[EmailStr, _text(100), AfterValidator(_lower)]
Phone = Annotated[str, _text(15, 7), _matches(r"\+?[0-9][0-9 \-]{5,13}[0-9]",
                                              "must be 7-15 digits, optionally starting with + (spaces/dashes allowed)")]
LicenseNo = Annotated[str, _text(30, 3), AfterValidator(_upper),
                      _matches(r"[A-Z0-9][A-Z0-9\-/]{2,29}", "may only contain letters, digits, - and /")]
Registration = Annotated[str, _text(15, 2), AfterValidator(_upper),
                         _matches(r"[A-Z0-9]+(-[A-Z0-9]+)*", "must look like VT-ABC (letters, digits, single dashes)")]
LocationCode = Annotated[str, _text(10, 2), AfterValidator(_upper),
                         _matches(r"[A-Z0-9]{2,10}", "may only contain letters and digits")]
IdProof = Annotated[str, _text(30, 4), AfterValidator(_upper),
                    _matches(r"[A-Z0-9][A-Z0-9 \-/]{3,29}", "may only contain letters, digits, spaces, - and /")]
Money = Annotated[Decimal, Field(max_digits=12, decimal_places=2)]
# Numbers in responses are JSON numbers (1250.5), not strings, so a frontend can use them directly.
Num = Annotated[Decimal, PlainSerializer(float, return_type=float, when_used="json")]


def _password_rules(v: str) -> str:
    if not (10 <= len(v) <= 128):
        raise ValueError("must be 10-128 characters")
    if not (any(ch.isalpha() for ch in v) and any(ch.isdigit() for ch in v)):
        raise ValueError("must contain at least one letter and one digit")
    return v


Password = Annotated[str, AfterValidator(_password_rules)]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Strict(BaseModel):
    """Request bodies: unknown fields are an error, so a typo is not silently ignored."""
    model_config = ConfigDict(extra="forbid")


# ---------- departure time rules, shared by /bookings, /search and /quote ----------

def normalise_departure(dt: datetime) -> datetime:
    """The database stores naive local timestamps; an aware one is converted to server local time."""
    if dt.tzinfo is not None:
        dt = dt.astimezone().replace(tzinfo=None)
    return dt


def check_departure(dt: datetime) -> datetime:
    dt = normalise_departure(dt)
    now = datetime.now()
    if dt < now + timedelta(minutes=settings.min_lead_minutes):
        raise ValueError(f"must be at least {settings.min_lead_minutes} minutes from now")
    if dt > now + timedelta(days=settings.max_advance_days):
        raise ValueError(f"cannot be more than {settings.max_advance_days} days ahead")
    return dt


# ---------- operators ----------

class OperatorIn(Strict):
    name: Name
    license_no: LicenseNo
    email: Email
    phone: Phone
    city: City
    service_interval_hrs: int | None = Field(None, gt=0, le=5000)


class OperatorOut(ORM):
    operator_id: int
    name: str
    license_no: str
    email: str
    phone: str
    city: str
    service_interval_hrs: int


# ---------- aircraft types ----------

class AircraftTypeIn(Strict):
    model: Annotated[str, _text(50)]
    category: Category
    seats: int = Field(gt=0, le=500)
    range_nm: int = Field(gt=0, le=20000)
    cruise_speed_kts: int = Field(gt=0, le=2000)
    hourly_rate: Decimal = Field(gt=0, max_digits=10, decimal_places=2)


class AircraftTypeOut(ORM):
    type_id: int
    model: str
    category: str
    seats: int
    range_nm: int
    cruise_speed_kts: int
    hourly_rate: Num


# ---------- locations ----------

class LocationIn(Strict):
    name: Name
    city: City
    code: LocationCode
    loc_type: Literal["Airport", "Helipad"]
    latitude: Decimal = Field(ge=-90, le=90, max_digits=9, decimal_places=6)
    longitude: Decimal = Field(ge=-180, le=180, max_digits=9, decimal_places=6)


class LocationOut(ORM):
    location_id: int
    name: str
    city: str
    code: str
    loc_type: str
    latitude: Num
    longitude: Num


# ---------- customers ----------

class CustomerIn(Strict):
    name: Name
    email: Email
    phone: Phone
    id_proof: IdProof


class CustomerOut(ORM):
    customer_id: int
    name: str
    email: str
    phone: str
    id_proof: str
    created_on: date


# ---------- aircraft ----------

class AircraftIn(Strict):
    registration_no: Registration
    operator_id: int = Field(gt=0)
    type_id: int = Field(gt=0)
    status: AircraftStatus | None = None


class OperatorAircraftIn(Strict):
    registration_no: Registration
    type_id: int = Field(gt=0)


class AircraftOut(ORM):
    aircraft_id: int
    registration_no: str
    operator_id: int
    operator_name: str
    type_id: int
    type_model: str
    category: str
    seats: int
    status: str
    total_hours: Num
    last_service_hours: Num
    last_service_date: date | None
    maintenance_cost: Num
    hours_since_service: Num
    service_due_in_hours: Num  # negative once overdue


class ServiceIn(Strict):
    cost: Decimal = Field(ge=0, max_digits=12, decimal_places=2)


# ---------- pilots ----------

class PilotIn(Strict):
    operator_id: int = Field(gt=0)
    name: Name
    license_no: LicenseNo
    category_rating: Category
    experience_hours: Decimal | None = Field(None, ge=0, max_digits=8, decimal_places=1)
    status: PilotStatus | None = None


class PilotOut(ORM):
    pilot_id: int
    operator_id: int
    operator_name: str
    name: str
    license_no: str
    category_rating: str
    experience_hours: Num
    status: str


# ---------- bookings ----------

class BookingIn(Strict):
    # customers book for themselves (leave it out); staff must say who the booking is for
    customer_id: int | None = Field(None, gt=0)
    aircraft_id: int = Field(gt=0)
    origin_id: int = Field(gt=0)
    dest_id: int = Field(gt=0)
    departure_time: datetime
    passengers: int = Field(gt=0, le=500)

    @field_validator("departure_time")
    @classmethod
    def _departure(cls, v):
        return check_departure(v)

    @field_validator("dest_id")
    @classmethod
    def _different_places(cls, v, info):
        if v == info.data.get("origin_id"):
            raise ValueError("must differ from origin_id")
        return v


class BookingOut(ORM):
    booking_id: int
    customer_id: int
    customer_name: str
    aircraft_id: int
    registration_no: str
    aircraft_model: str
    pilot_id: int
    pilot_name: str
    origin_id: int
    origin_code: str
    dest_id: int
    dest_code: str
    departure_time: datetime
    arrival_time: datetime
    passengers: int
    status: str
    total_fare: Num
    amount_paid: Num
    balance_due: Num


# ---------- payments ----------

class PaymentIn(Strict):
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    method: PayMethod


class PaymentOut(ORM):
    payment_id: int
    booking_id: int
    amount: Num
    method: str
    paid_on: date
    status: str


# ---------- accounts ----------

class RegisterIn(Strict):
    """A new customer: creates the customer record and a login for it."""
    name: Name
    email: Email
    phone: Phone
    id_proof: IdProof
    password: Password

    @field_validator("password")
    @classmethod
    def _not_the_email(cls, v, info):
        if v.lower() == str(info.data.get("email", "")).lower():
            raise ValueError("must not be your email address")
        return v


class OperatorRegisterIn(Strict):
    """Create an operator company profile and its initial login."""
    name: Name
    license_no: LicenseNo
    email: Email
    phone: Phone
    city: City
    service_interval_hrs: int | None = Field(None, gt=0, le=5000)
    password: Password

    @field_validator("password")
    @classmethod
    def _not_the_email(cls, v, info):
        if v.lower() == str(info.data.get("email", "")).lower():
            raise ValueError("must not be your email address")
        return v


class LoginIn(Strict):
    email: Annotated[str, _text(100), AfterValidator(_lower)]
    password: Annotated[str, Field(min_length=1, max_length=128)]


class OperatorLoginIn(LoginIn):
    license_no: LicenseNo




class ChangePasswordIn(Strict):
    current_password: Annotated[str, Field(min_length=1, max_length=128)]
    new_password: Password


class ProfileUpdate(Strict):
    """What a customer may change about themselves."""
    name: Name | None = None
    phone: Phone | None = None
    id_proof: IdProof | None = None


class MeOut(ORM):
    user_id: int
    email: str
    role: str
    customer: CustomerOut | None
    operator: OperatorOut | None


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    user: MeOut


# ---------- search / quote / stats ----------

class SearchHit(BaseModel):
    aircraft_id: int
    registration_no: str
    model: str
    category: str
    seats: int
    distance_nm: Num
    flight_hours: Num
    arrival_time: datetime
    fare: Num


class Quote(BaseModel):
    aircraft_id: int
    distance_nm: Num
    flight_hours: Num
    departure_time: datetime
    arrival_time: datetime
    fare: Num


class Stats(BaseModel):
    bookings_by_status: dict[str, int]
    revenue_collected: Num
    outstanding_balance: Num
    aircraft_by_status: dict[str, int]
    aircraft_service_due: int
    upcoming_flights: int
    customers: int
