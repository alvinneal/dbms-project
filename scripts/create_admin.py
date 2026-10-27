"""Create (or reset the password of) a staff account.

    python scripts/create_admin.py you@example.com

The password is asked for on the terminal, so it never ends up in your shell history.
"""
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app import schemas as s  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import AppUser  # noqa: E402
from app.security import hash_password  # noqa: E402


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    email = s.LoginIn(email=sys.argv[1], password="x").email
    password = getpass.getpass("Password (10+ characters, letters and digits): ")
    if password != getpass.getpass("Again: "):
        sys.exit("Passwords differ")
    try:
        s._password_rules(password)
    except ValueError as e:
        sys.exit(f"Password {e}")

    with SessionLocal() as db:
        user = db.scalar(select(AppUser).where(AppUser.email == email))
        if user and user.role != "admin":
            sys.exit(f"{email} is a customer account; use a different email for staff")
        if user:
            user.password_hash = hash_password(password)
            user.token_version += 1  # signs out every existing login
            user.failed_logins, user.locked_until, user.is_active = 0, None, True
            print(f"password reset for {email}")
        else:
            db.add(AppUser(email=email, password_hash=hash_password(password), role="admin"))
            print(f"created staff account {email}")
        db.commit()


if __name__ == "__main__":
    main()
