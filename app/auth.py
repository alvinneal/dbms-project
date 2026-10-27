from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy import select

from . import schemas as s
from .config import settings
from .deps import DB
from .models import AppUser, Customer, Operator
from .security import DUMMY_HASH, create_token, hash_password, limiter, read_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])

# tokenUrl is what the "Authorize" button in /docs logs in against
oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)


def unauthorized(message: str = "Not authenticated"):
    return HTTPException(401, message, headers={"WWW-Authenticate": "Bearer"})


# ---------- who is calling ----------

def current_user(db: DB, token: Annotated[str | None, Depends(oauth2)]) -> AppUser:
    claims = read_token(token) if token else None
    if not claims:
        raise unauthorized("Not authenticated or the login has expired")
    try:
        user = db.get(AppUser, int(claims["sub"]))
    except ValueError:
        user = None
    # looked up on every request, so disabling an account or changing a password takes effect at once
    if user is None or not user.is_active or user.token_version != claims["tv"]:
        raise unauthorized("Not authenticated or the login has expired")
    return user


def require_admin(user: Annotated[AppUser, Depends(current_user)]) -> AppUser:
    if not user.is_admin:
        raise HTTPException(403, "Staff access only")
    return user


def require_operator(user: Annotated[AppUser, Depends(current_user)]) -> AppUser:
    if user.role != "operator" or user.operator_id is None:
        raise HTTPException(403, "Operator access only")
    return user


User = Annotated[AppUser, Depends(current_user)]
Admin = Annotated[AppUser, Depends(require_admin)]
OperatorUser = Annotated[AppUser, Depends(require_operator)]


# ---------- abuse protection for the login endpoints ----------

def auth_rate_limit(request: Request):
    wait = limiter.check(f"auth:{request.client.host if request.client else '?'}", settings.auth_rate_limit_per_minute)
    if wait:
        raise HTTPException(429, f"Too many attempts, try again in {int(wait)} seconds",
                            headers={"Retry-After": str(int(wait))})


# ---------- endpoints ----------

def issue_token(user: AppUser) -> dict:
    return {"access_token": create_token(user.user_id, user.token_version),
            "expires_in": settings.access_token_minutes * 60, "user": user}


def authenticate(db, email: str, password: str) -> AppUser:
    user = db.scalar(select(AppUser).where(AppUser.email == email.lower()))
    now = datetime.now()

    if user and user.locked_until and user.locked_until > now:
        minutes = int((user.locked_until - now).total_seconds() // 60) + 1
        raise HTTPException(429, f"Too many wrong passwords, this account is locked for {minutes} more minute(s)")

    # always do one hash comparison, so timing does not reveal whether the email exists
    ok = verify_password(password, user.password_hash if user else DUMMY_HASH)
    if not (user and ok and user.is_active):
        if user:
            user.failed_logins += 1
            if user.failed_logins >= settings.max_failed_logins:
                user.failed_logins = 0
                user.locked_until = now + timedelta(minutes=settings.lockout_minutes)
            db.commit()
        # same message for unknown email, wrong password and disabled account
        raise unauthorized("Incorrect email or password")

    if user.failed_logins or user.locked_until:
        user.failed_logins, user.locked_until = 0, None
        db.commit()
    return user


@router.post("/register", response_model=s.TokenOut, status_code=201, dependencies=[Depends(auth_rate_limit)])
def register(body: s.RegisterIn, db: DB):
    """Sign up as a customer. Creates the customer record and the login, and logs you in."""
    # a duplicate email is a unique violation: reported as 409 by the error handler
    customer = Customer(name=body.name, email=body.email, phone=body.phone, id_proof=body.id_proof)
    db.add(customer)
    db.flush()
    user = AppUser(email=body.email, password_hash=hash_password(body.password), role="customer",
                   customer_id=customer.customer_id)
    db.add(user)
    db.commit()
    return issue_token(user)


@router.post("/operator/register", response_model=s.TokenOut, status_code=201,
             dependencies=[Depends(auth_rate_limit)])
def register_operator(body: s.OperatorRegisterIn, db: DB):
    """Create an operator company and its first operator login."""
    values = body.model_dump(exclude={"password"}, exclude_none=True)
    operator = Operator(**values)
    db.add(operator)
    db.flush()
    user = AppUser(email=body.email, password_hash=hash_password(body.password),
                   role="operator", operator_id=operator.operator_id)
    db.add(user)
    db.commit()
    return issue_token(user)


@router.post("/login", response_model=s.TokenOut, dependencies=[Depends(auth_rate_limit)])
def login(body: s.LoginIn, db: DB):
    """Email + password (JSON) -> bearer token. Send it as `Authorization: Bearer <token>`."""
    return issue_token(authenticate(db, body.email, body.password))


@router.post("/operator/login", response_model=s.TokenOut, dependencies=[Depends(auth_rate_limit)])
def operator_login(body: s.OperatorLoginIn, db: DB):
    """Operators sign in with their account email, password, and company license number."""
    user = authenticate(db, body.email, body.password)
    if user.role != "operator" or user.operator is None or user.operator.license_no != body.license_no:
        raise unauthorized("Incorrect email, password, or operator license number")
    return issue_token(user)


@router.post("/token", response_model=s.TokenOut, dependencies=[Depends(auth_rate_limit)], include_in_schema=True)
def login_form(db: DB, form: Annotated[OAuth2PasswordRequestForm, Depends()]):
    """Same as /auth/login but as a form post; this is what the Authorize button in /docs uses."""
    return issue_token(authenticate(db, form.username, form.password))


@router.get("/me", response_model=s.MeOut)
def me(user: User):
    return user


@router.patch("/me", response_model=s.MeOut)
def update_me(body: s.ProfileUpdate, user: User, db: DB):
    """A customer edits their own name, phone and ID proof (email and role cannot be changed here)."""
    if user.customer_id is None:
        raise HTTPException(409, "Staff accounts have no customer profile")
    customer = db.get(Customer, user.customer_id)
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(customer, k, v)
    db.commit()
    return user


@router.post("/change-password", response_model=s.TokenOut, dependencies=[Depends(auth_rate_limit)])
def change_password(body: s.ChangePasswordIn, user: User, db: DB):
    """Changes the password and signs out every other device; returns a fresh token for this one."""
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(403, "Current password is incorrect")
    if verify_password(body.new_password, user.password_hash):
        raise HTTPException(409, "The new password must differ from the current one")
    user.password_hash = hash_password(body.new_password)
    user.token_version += 1
    db.commit()
    return issue_token(user)
