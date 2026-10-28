# Charter Aircraft Rental API

FastAPI + SQLAlchemy on top of the PostgreSQL schema in `schema.sql` / `routines.sql`
(plus `auth.sql` for login accounts). The database owns the hard rules (constraints,
`book_flight`, `complete_flight`, `check_overdue_aircraft`, the booking and payment
triggers); the API authenticates, validates, adds friendly pre-checks, and returns clean JSON.

## Run it

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env            # fill in DATABASE_URL and SECRET_KEY, then SAVE the file

.\venv\Scripts\python.exe scripts\setup_db.py --seed        # safe to rerun; adds what is missing
.\venv\Scripts\python.exe scripts\create_admin.py you@example.com   # staff login (asks for a password)
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8001
```

The API loads `.env` from the repository root when it starts. Restart the API after changing
`DATABASE_URL` so the SQLAlchemy engine connects to the new database.

Open **http://localhost:8001/docs**, click **Authorize**, log in with the staff email and
password, and try everything. `/health` should say `ok`.
`setup_db.py --reset` wipes and rebuilds the database (destructive).

The demo operator account is created by `setup_db.py --seed`:

- Email: `ops@skyway.example`
- Password: `SkywayDemo2026`
- Operator license: `OP-1001`

Use all three values in the operator sign-in form. This account is for local demo data only.

Operators can add aircraft to their own fleet with `POST /operator/aircraft`
(`registration_no`, `type_id`). They can view their aircraft, pilots, maintenance queue,
and flights; they can also record service for their own aircraft. Customers create bookings
for themselves, and staff can create bookings for customers. Operators cannot create bookings.

## Test it

```powershell
.\venv\Scripts\python.exe -m pytest tests\test_validation.py     # no database needed

# the rest creates rows: point it at a throwaway database
$env:DATABASE_URL = "postgresql+psycopg2://postgres:PASSWORD@localhost:5432/charter_test"
.\venv\Scripts\python.exe scripts\setup_db.py
.\venv\Scripts\python.exe -m pytest
```

## For the frontend

**Login**
1. Customers use `POST /auth/register` with `{name, email, phone, id_proof, password}` or
   `POST /auth/login` with `{email, password}`. Operators use `/auth/operator/register` or
   `/auth/operator/login`; operator login also requires `license_no`. Both return
   `{access_token, expires_in, user}`.
2. Send `Authorization: Bearer <access_token>` on protected calls. The frontend stores the
   token in `sessionStorage`; the API does not use cookies.
3. `GET /auth/me` returns the current role (`customer`, `operator`, or `admin`). A `401`
   means the token is missing or no longer valid.
4. Admin accounts are created with `scripts/create_admin.py`. Customers and operators can
   register through the API.

**Who can do what**

| Capability | logged out | customer | operator | staff (admin) |
|---|---|---|---|---|
| `/locations` read, `/meta`, `/health` | yes | yes | yes | yes |
| `/aircraft-types` read, `/search`, `/quote` | | yes | yes | yes |
| Create bookings | | for self | | for a customer |
| List bookings | | own only | own fleet only | all |
| Read, pay, or cancel a booking | | own only | | all |
| `/operator/me`, `/operator/aircraft`, `/operator/pilots`, `/operator/maintenance`, `/operator/flights` | | | own operator data | |
| Add aircraft with `POST /operator/aircraft`; record service with `/operator/aircraft/{id}/service` | | | own fleet | |
| `/customers`, `/operators`, `/aircraft`, `/pilots` master data | | | | yes |
| Complete a flight, run maintenance check, `/stats`, edit/delete master data | | | | yes |

Customers get a `404` (not `403`) for someone else's booking, so ids cannot be probed.

**Responses**
* **Errors** always `{"detail": "message"}`; bad input (422) adds
  `"errors": [{"field": "email", "message": "..."}]` to mark form fields.
  `401` log in, `403` not allowed, `404` not found, `409` business rule or conflict
  (double booking, wrong state, duplicate, still referenced), `422` invalid input,
  `429` too many requests (see `Retry-After`), `503` database down.
* **Lists** take `limit` (<=500) and `offset`; matches are in the `X-Total-Count` header.
  Master tables also take `q` (text search) and field filters; `/bookings` takes
  `customer_id`, `aircraft_id`, `pilot_id`, `status`, `departs_from`, `departs_to`.
* **Numbers** (money, hours) are JSON numbers. **Times** are naive local time
  (`2026-11-05T10:00:00`); an offset (`...Z`) is converted to server local time.
* **Bookings** include names/codes and `amount_paid` / `balance_due`; aircraft include
  operator, model, seats and `service_due_in_hours`.
* `GET /meta` returns fixed dropdown values and rules (categories, statuses, payment
  methods, booking lead time, password rules). Locations and aircraft types are listed by
  `/locations` and `/aircraft-types`.
* `GET /quote` prices one aircraft, `GET /search` finds all that can fly a route.

## Security

* **Passwords**: scrypt (salted, memory-hard), 10+ characters with a letter and a digit.
  Login says only "Incorrect email or password" and takes the same time for unknown emails.
* **Tokens**: signed JWT (HS256, algorithm pinned), 60 minutes by default. The user is re-checked on every
  request, so disabling an account or changing a password signs out old tokens immediately.
* **Brute force**: by default, 5 wrong passwords lock the account for 15 minutes; login/register are limited to
  10 requests per minute per IP; everything else to 300 per minute. These values can be configured in `.env`.
* **Access control**: roles on every route, customers confined to their own data, and operator
  actions scoped to their own fleet. Request schemas reject unknown fields, including attempts to
  supply an operator ID when adding an aircraft.
* **Injection**: all queries are parameterised; text search escapes `%` and `_`.
* **Hardening**: strict CORS (only your origins, only needed methods/headers), Host header allow-list,
  64 KB request limit, `nosniff`, no-framing, `no-store`, CSP, HSTS in production, no stack traces
  or SQL in errors, request ids, and logs that never contain passwords, tokens or query strings.
* **Production**: set `ENVIRONMENT=production` (hides `/docs`, requires `SECRET_KEY`), a real
  `ALLOWED_HOSTS` and `CORS_ORIGINS`, and serve it behind HTTPS (a reverse proxy such as nginx/Caddy).
  The rate limiter keeps its counters in memory, so behind a proxy make sure the real client IP is
  forwarded (`uvicorn --proxy-headers`), and move to Redis if you run several workers.
* Not included: email verification / password reset, refresh tokens, and a real payment gateway
  (`POST /bookings/{id}/payments` records a payment in the database).

## Business rules worth knowing

* Departure must be between `MIN_LEAD_MINUTES` (30 by default) and `MAX_ADVANCE_DAYS` (365 by default) from now.
* Emails are lower-cased, codes/registrations/licences upper-cased, whitespace trimmed.
* An aircraft in Maintenance returns to service only through the service endpoint:
  staff use `POST /aircraft/{id}/service`, and operators use
  `POST /operator/aircraft/{id}/service` for their own aircraft.
* Aircraft/pilots with upcoming bookings can't be deleted, change operator/type/rating,
  or (pilots) go on leave.
* Payments: part payments allowed, overpayment refused, fully paid -> Confirmed
  (by trigger). Cancelling refunds every payment.
