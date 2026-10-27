-- Login accounts. Kept apart from schema.sql so the original schema is untouched.
-- A 'customer' account belongs to exactly one customer row; an 'admin' (staff) account to none.
-- Loaded by scripts/setup_db.py (safe to run repeatedly).
CREATE TABLE IF NOT EXISTS app_user (
    user_id       SERIAL PRIMARY KEY,
    email         VARCHAR(100) NOT NULL,
    password_hash VARCHAR(300) NOT NULL,
    role          VARCHAR(10)  NOT NULL CHECK (role IN ('admin', 'customer')),
    customer_id   INT UNIQUE REFERENCES customer (customer_id) ON DELETE CASCADE,
    is_active     BOOLEAN      NOT NULL DEFAULT TRUE,
    failed_logins INT          NOT NULL DEFAULT 0,
    locked_until  TIMESTAMP,
    -- bumped on password change so every older login token stops working
    token_version INT          NOT NULL DEFAULT 0,
    created_at    TIMESTAMP    NOT NULL DEFAULT now(),
    CHECK ((role = 'customer') = (customer_id IS NOT NULL))
);

CREATE UNIQUE INDEX IF NOT EXISTS app_user_email_key ON app_user (lower(email));
