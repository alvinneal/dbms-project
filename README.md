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
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Open **http://localhost:8000/docs**, click **Authorize**, log in with the staff email and
password, and try everything. `/health` should say `ok`.
`setup_db.py --reset` wipes and rebuilds the database (destructive).

**Demo data**: `--seed` loads a small set (2 operators, 4 aircraft, 2 customers, no bookings).
`--seed-large` loads `seed_large.sql` instead (25 operators, 80 aircraft, 117 pilots, 150 customers,
600 bookings, 824 payments), which is better for trying lists, filters, paging and `/stats`.
Pick one: both use the same ids, and seeding only happens into an empty database
(use `--reset` for a clean start). The seeded customers have no login; sign up with
`POST /auth/register` to get a customer account, or use the staff account to see everything.

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
1. `POST /auth/register` `{name, email, phone, id_proof, password}` (customers) or
   `POST /auth/login` `{email, password}` -> `{access_token, expires_in, user}`.
2. Send `Authorization: Bearer <access_token>` on every other call. Keep the token in
   memory (or sessionStorage); there are no cookies, so no CSRF to worry about.
3. A `401` means log in again (expired, signed out, account disabled). `GET /auth/me` returns
   the current user and role, so the UI knows whether to show customer or staff screens.
4. Staff accounts are created with `scripts/create_admin.py`; nobody can register as staff.

**Who can do what**

| | logged out | customer | staff (admin) |
|---|---|---|---|
| `/locations` read, `/meta`, `/health` | yes | yes | yes |
| `/aircraft-types` read, `/search`, `/quote` | | yes | yes |
| book, pay, cancel, list bookings | | **own only** | all |
| `/customers`, `/operators`, `/aircraft`, `/pilots` | | | yes |
| complete a flight, maintenance, `/stats`, any create/edit/delete of master data | | | yes |

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
* `GET /meta` returns every dropdown list and rule (categories, statuses, payment
  methods, booking lead time, password rules) so the UI never hard-codes them.
* `GET /quote` prices one aircraft, `GET /search` finds all that can fly a route.

## Security

* **Passwords**: scrypt (salted, memory-hard), 10+ characters with a letter and a digit.
  Login says only "Incorrect email or password" and takes the same time for unknown emails.
* **Tokens**: signed JWT (HS256, algorithm pinned), 60 minutes. The user is re-checked on every
  request, so disabling an account or changing a password signs out old tokens immediately.
* **Brute force**: 5 wrong passwords lock the account for 15 minutes; login/register are limited to
  10 requests per minute per IP; everything else to 300 per minute.
* **Access control**: roles on every route, customers confined to their own data, mass assignment
  impossible (unknown JSON fields are rejected, so nobody can send `role` or `status`).
* **Injection**: all queries are parameterised; text search escapes `%` and `_`.
* **Hardening**: strict CORS (only your origins, only needed methods/headers), Host header allow-list,
  64 KB request limit, `nosniff`, no-framing, `no-store`, CSP, HSTS in production, no stack traces
  or SQL in errors, request ids, and logs that never contain passwords, tokens or query strings.
* **Production**: set `ENVIRONMENT=production` (hides `/docs`, requires `SECRET_KEY`), a real
  `ALLOWED_HOSTS` and `CORS_ORIGINS`, and serve it behind HTTPS (a reverse proxy such as nginx/Caddy).
  The rate limiter keeps its counters in memory, so behind a proxy make sure the real client IP is
  forwarded (`uvicorn --proxy-headers`), and move to Redis if you run several workers.
* Not included: email verification / password reset, refresh tokens, and a real payment gateway
  (`POST /payments` just records a payment).

## Business rules worth knowing

* Departure must be `MIN_LEAD_MINUTES` (30) to `MAX_ADVANCE_DAYS` (365) from now.
* Emails are lower-cased, codes/registrations/licences upper-cased, whitespace trimmed.
* An aircraft in Maintenance returns to service only via `POST /aircraft/{id}/service`.
* Aircraft/pilots with upcoming bookings can't be deleted, change operator/type/rating,
  or (pilots) go on leave.
* Payments: part payments allowed, overpayment refused, fully paid -> Confirmed
  (by trigger). Cancelling refunds every payment.
