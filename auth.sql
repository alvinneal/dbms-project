-- Login accounts. Kept apart from schema.sql so the original schema is untouched.
-- A customer/operator account belongs to one matching business row; an admin belongs to neither.
-- Loaded by scripts/setup_db.py (safe to run repeatedly).
CREATE TABLE IF NOT EXISTS app_user (
    user_id       SERIAL PRIMARY KEY,
    email         VARCHAR(100) NOT NULL,
    password_hash VARCHAR(300) NOT NULL,
    role          VARCHAR(10)  NOT NULL,
    customer_id   INT UNIQUE REFERENCES customer (customer_id) ON DELETE CASCADE,
    operator_id   INT UNIQUE REFERENCES operator (operator_id),
    is_active     BOOLEAN      NOT NULL DEFAULT TRUE,
    failed_logins INT          NOT NULL DEFAULT 0,
    locked_until  TIMESTAMP,
    -- bumped on password change so every older login token stops working
    token_version INT          NOT NULL DEFAULT 0,
    created_at    TIMESTAMP    NOT NULL DEFAULT now(),
    CONSTRAINT app_user_role_check CHECK (role IN ('admin', 'customer', 'operator')),
    CONSTRAINT app_user_identity_check CHECK (
        (role = 'admin' AND customer_id IS NULL AND operator_id IS NULL) OR
        (role = 'customer' AND customer_id IS NOT NULL AND operator_id IS NULL) OR
        (role = 'operator' AND customer_id IS NULL AND operator_id IS NOT NULL)
    )
);

-- Upgrade existing installations safely; settings and active customer/admin accounts remain intact.
ALTER TABLE app_user ADD COLUMN IF NOT EXISTS operator_id INT REFERENCES operator (operator_id);
ALTER TABLE app_user DROP CONSTRAINT IF EXISTS app_user_check;
ALTER TABLE app_user DROP CONSTRAINT IF EXISTS app_user_check1;
ALTER TABLE app_user DROP CONSTRAINT IF EXISTS app_user_role_check;
ALTER TABLE app_user DROP CONSTRAINT IF EXISTS app_user_identity_check;
ALTER TABLE app_user ADD CONSTRAINT app_user_role_check CHECK (role IN ('admin', 'customer', 'operator'));
ALTER TABLE app_user ADD CONSTRAINT app_user_identity_check CHECK (
    (role = 'admin' AND customer_id IS NULL AND operator_id IS NULL) OR
    (role = 'customer' AND customer_id IS NOT NULL AND operator_id IS NULL) OR
    (role = 'operator' AND customer_id IS NULL AND operator_id IS NOT NULL)
);
CREATE UNIQUE INDEX IF NOT EXISTS app_user_operator_id_key ON app_user (operator_id) WHERE operator_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS app_user_email_key ON app_user (lower(email));
