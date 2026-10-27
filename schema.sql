CREATE TABLE operator (
    operator_id          SERIAL PRIMARY KEY,
    name                 VARCHAR(100) NOT NULL,
    license_no           VARCHAR(30)  NOT NULL UNIQUE,
    email                VARCHAR(100) NOT NULL UNIQUE,
    phone                VARCHAR(15)  NOT NULL,
    city                 VARCHAR(50)  NOT NULL,
    service_interval_hrs INT          NOT NULL DEFAULT 100 CHECK (service_interval_hrs > 0)
);

CREATE TABLE aircraft_type (
    type_id          SERIAL PRIMARY KEY,
    model            VARCHAR(50)   NOT NULL,
    category         VARCHAR(20)   NOT NULL CHECK (category IN ('Helicopter', 'Jet', 'Turboprop')),
    seats            INT           NOT NULL CHECK (seats > 0),
    range_nm         INT           NOT NULL CHECK (range_nm > 0),
    cruise_speed_kts INT           NOT NULL CHECK (cruise_speed_kts > 0),
    hourly_rate      NUMERIC(10,2) NOT NULL CHECK (hourly_rate > 0)
);

CREATE TABLE location (
    location_id SERIAL PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    city        VARCHAR(50)  NOT NULL,
    code        VARCHAR(10)  NOT NULL UNIQUE,
    loc_type    VARCHAR(10)  NOT NULL CHECK (loc_type IN ('Airport', 'Helipad')),
    latitude    NUMERIC(9,6) NOT NULL CHECK (latitude BETWEEN -90 AND 90),
    longitude   NUMERIC(9,6) NOT NULL CHECK (longitude BETWEEN -180 AND 180)
);

CREATE TABLE customer (
    customer_id SERIAL PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    email       VARCHAR(100) NOT NULL UNIQUE,
    phone       VARCHAR(15)  NOT NULL,
    id_proof    VARCHAR(30)  NOT NULL,
    created_on  DATE         NOT NULL DEFAULT CURRENT_DATE
);

CREATE TABLE aircraft (
    aircraft_id        SERIAL PRIMARY KEY,
    registration_no    VARCHAR(15)   NOT NULL UNIQUE,
    operator_id        INT           NOT NULL REFERENCES operator (operator_id),
    type_id            INT           NOT NULL REFERENCES aircraft_type (type_id),
    status             VARCHAR(15)   NOT NULL DEFAULT 'Available' CHECK (status IN ('Available', 'Maintenance')),
    total_hours        NUMERIC(8,1)  NOT NULL DEFAULT 0 CHECK (total_hours >= 0),
    last_service_hours NUMERIC(8,1)  NOT NULL DEFAULT 0,
    last_service_date  DATE,
    maintenance_cost   NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (maintenance_cost >= 0),
    CHECK (last_service_hours <= total_hours)
);

CREATE TABLE pilot (
    pilot_id         SERIAL PRIMARY KEY,
    operator_id      INT          NOT NULL REFERENCES operator (operator_id),
    name             VARCHAR(100) NOT NULL,
    license_no       VARCHAR(30)  NOT NULL UNIQUE,
    category_rating  VARCHAR(20)  NOT NULL CHECK (category_rating IN ('Helicopter', 'Jet', 'Turboprop')),
    experience_hours NUMERIC(8,1) NOT NULL DEFAULT 0 CHECK (experience_hours >= 0),
    status           VARCHAR(15)  NOT NULL DEFAULT 'Active' CHECK (status IN ('Active', 'On leave'))
);

CREATE TABLE booking (
    booking_id     SERIAL PRIMARY KEY,
    customer_id    INT           NOT NULL REFERENCES customer (customer_id),
    aircraft_id    INT           NOT NULL REFERENCES aircraft (aircraft_id),
    pilot_id       INT           NOT NULL REFERENCES pilot (pilot_id),
    origin_id      INT           NOT NULL REFERENCES location (location_id),
    dest_id        INT           NOT NULL REFERENCES location (location_id),
    departure_time TIMESTAMP     NOT NULL,
    arrival_time   TIMESTAMP     NOT NULL,
    passengers     INT           NOT NULL CHECK (passengers > 0),
    status         VARCHAR(15)   NOT NULL DEFAULT 'Pending' CHECK (status IN ('Pending', 'Confirmed', 'Completed', 'Cancelled')),
    total_fare     NUMERIC(12,2) NOT NULL CHECK (total_fare >= 0),
    CHECK (dest_id <> origin_id),
    CHECK (arrival_time > departure_time)
);

CREATE TABLE payment (
    payment_id SERIAL PRIMARY KEY,
    booking_id INT           NOT NULL REFERENCES booking (booking_id),
    amount     NUMERIC(12,2) NOT NULL CHECK (amount > 0),
    method     VARCHAR(20)   NOT NULL CHECK (method IN ('Card', 'UPI', 'Bank transfer')),
    paid_on    DATE          NOT NULL DEFAULT CURRENT_DATE,
    status     VARCHAR(15)   NOT NULL DEFAULT 'Paid' CHECK (status IN ('Paid', 'Refunded'))
);
