import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy import text

from . import auth, bookings, errors, fleet
from . import schemas as s
from .auth import current_user
from .config import settings
from .crud import crud
from .deps import DB
from .models import Aircraft, AircraftType, Customer, Location, Operator, Pilot
from .security import limiter

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("app")

app = FastAPI(
    title="Charter Aircraft Rental",
    version="1.0.0",
    description=(
        "**Auth**: `POST /auth/register` or `/auth/login`, then send `Authorization: Bearer <access_token>` "
        "(click *Authorize* here). Roles: `customer` (own bookings, search, pay) and `admin` (staff: everything).\n\n"
        "**Errors** always look like `{\"detail\": \"...\"}`; invalid input (422) also carries "
        "`errors: [{field, message}]`. 401 = log in, 403 = not allowed, 404 = not found, 409 = business rule / conflict, "
        "429 = slow down.\n\n"
        "**Lists** take `limit`/`offset` and return the number of matches in the `X-Total-Count` header. "
        "`GET /meta` lists every dropdown value and rule the forms need."
    ),
    # the interactive docs are for development; in production they are not exposed
    docs_url=None if settings.production else "/docs",
    redoc_url=None if settings.production else "/redoc",
    openapi_url=None if settings.production else "/openapi.json",
)
errors.install(app)

# Bearer tokens travel in a header, not a cookie, so there are no credentials to protect from cross-site requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["X-Total-Count", "X-Request-ID", "Retry-After"],
    max_age=600,
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.host_list)

DOC_PATHS = ("/docs", "/redoc", "/openapi.json")


@app.middleware("http")
async def harden(request: Request, call_next):
    rid = uuid.uuid4().hex[:8]
    start = time.perf_counter()
    ip = request.client.host if request.client else "?"

    declared = request.headers.get("content-length", "0")
    if declared.isdigit() and int(declared) > settings.max_body_bytes:
        response = JSONResponse(status_code=413, content={"detail": "Request body too large"})
    elif request.method != "OPTIONS" and (wait := limiter.check(f"all:{ip}", settings.rate_limit_per_minute)):
        response = JSONResponse(status_code=429, content={"detail": "Too many requests, slow down"},
                                headers={"Retry-After": str(int(wait))})
    else:
        response = await call_next(request)

    response.headers["X-Request-ID"] = rid
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"  # responses hold personal data: never cached by browsers or proxies
    if request.url.path not in DOC_PATHS:  # the docs page needs to load its own scripts
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    if settings.production:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    # path only: query strings and bodies (emails, tokens) never reach the log
    log.info("%s %s %s %s %.0fms", rid, request.method, request.url.path, response.status_code,
             (time.perf_counter() - start) * 1000)
    return response


@app.get("/health", tags=["system"])
def health(db: DB):
    """Is the API up and the database reachable (with the routines and login table installed)?"""
    db.execute(text("SELECT 1"))
    routines = db.scalar(text("SELECT count(*) FROM pg_proc WHERE proname IN "
                              "('book_flight','complete_flight','check_overdue_aircraft','fn_distance_nm','fn_flight_hours')"))
    if routines != 5:
        return {"status": "degraded", "detail": "routines.sql has not been loaded into this database"}
    if not db.scalar(text("SELECT to_regclass('public.app_user') IS NOT NULL")):
        return {"status": "degraded", "detail": "auth.sql has not been loaded (run scripts/setup_db.py)"}
    return {"status": "ok"}


@app.get("/meta", tags=["system"])
def meta():
    """Every fixed list and rule a form needs, so the frontend never hard-codes them."""
    return {
        "categories": list(s.Category.__args__),
        "booking_statuses": list(s.BookingStatus.__args__),
        "aircraft_statuses": list(s.AircraftStatus.__args__),
        "pilot_statuses": list(s.PilotStatus.__args__),
        "payment_methods": list(s.PayMethod.__args__),
        "location_types": ["Airport", "Helipad"],
        "booking_rules": {"min_lead_minutes": settings.min_lead_minutes,
                          "max_advance_days": settings.max_advance_days, "max_passengers": 500},
        "password_rules": {"min_length": 10, "max_length": 128, "needs_letter_and_digit": True},
        "token_lifetime_seconds": settings.access_token_minutes * 60,
        "max_page_size": 500,
    }


app.include_router(auth.router)

# ---------- master tables: reading as noted, writing is always staff only ----------
# locations are public (a landing page can show destinations); the catalogue of aircraft types needs a login;
# the rest (operators, fleet, pilots, customers) is staff only.

app.include_router(crud("operators", Operator, s.OperatorIn, s.OperatorOut, filters={"city": str}))
app.include_router(crud("aircraft-types", AircraftType, s.AircraftTypeIn, s.AircraftTypeOut,
                        read=current_user, filters={"category": s.Category}))
app.include_router(crud("locations", Location, s.LocationIn, s.LocationOut,
                        read=None, filters={"city": str, "loc_type": str}))
app.include_router(crud("customers", Customer, s.CustomerIn, s.CustomerOut))
app.include_router(crud("aircraft", Aircraft, s.AircraftIn, s.AircraftOut,
                        filters={"status": s.AircraftStatus, "operator_id": int, "type_id": int},
                        before_update=fleet.aircraft_before_update, before_delete=fleet.aircraft_before_delete))
app.include_router(crud("pilots", Pilot, s.PilotIn, s.PilotOut,
                        filters={"status": s.PilotStatus, "operator_id": int, "category_rating": s.Category},
                        before_update=fleet.pilot_before_update, before_delete=fleet.pilot_before_delete))

app.include_router(bookings.router)
app.include_router(fleet.router)
