-- ============================================================
-- FUNCTIONS (2)
-- ============================================================

-- 1. Distance between two locations in nautical miles (haversine formula)
CREATE OR REPLACE FUNCTION fn_distance_nm(p_origin INT, p_dest INT)
RETURNS NUMERIC AS $$
DECLARE
    lat1 DOUBLE PRECISION;
    lon1 DOUBLE PRECISION;
    lat2 DOUBLE PRECISION;
    lon2 DOUBLE PRECISION;
    a    DOUBLE PRECISION;
BEGIN
    SELECT radians(latitude), radians(longitude) INTO lat1, lon1
      FROM location WHERE location_id = p_origin;
    SELECT radians(latitude), radians(longitude) INTO lat2, lon2
      FROM location WHERE location_id = p_dest;

    a := sin((lat2 - lat1) / 2) ^ 2
       + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ^ 2;

    RETURN ROUND((3440.065 * 2 * asin(sqrt(a)))::NUMERIC, 1);
END;
$$ LANGUAGE plpgsql;


-- 2. Flight time in hours = distance in nautical miles / cruise speed in knots
CREATE OR REPLACE FUNCTION fn_flight_hours(p_aircraft INT, p_origin INT, p_dest INT)
RETURNS NUMERIC AS $$
DECLARE
    v_speed INT;
BEGIN
    SELECT t.cruise_speed_kts INTO v_speed
      FROM aircraft a JOIN aircraft_type t ON a.type_id = t.type_id
     WHERE a.aircraft_id = p_aircraft;

    RETURN ROUND(fn_distance_nm(p_origin, p_dest) / v_speed, 2);
END;
$$ LANGUAGE plpgsql;


-- ============================================================
-- PROCEDURES (3)
-- ============================================================

-- 1. Book a flight.
--    Checks the route is within range, works out flight time, arrival and fare,
--    picks a free pilot, and inserts the booking (Trigger 1 then validates it).
--    Call with NULL as the last argument; the new booking id comes back in it.
CREATE OR REPLACE PROCEDURE book_flight(
    p_customer INT, p_aircraft INT, p_origin INT, p_dest INT,
    p_departure TIMESTAMP, p_passengers INT, INOUT p_booking_id INT)
LANGUAGE plpgsql AS $$
DECLARE
    v_operator INT;
    v_category VARCHAR;
    v_range    INT;
    v_rate     NUMERIC;
    v_hours    NUMERIC;
    v_arrival  TIMESTAMP;
    v_pilot    INT;
BEGIN
    -- the aircraft
    SELECT a.operator_id, t.category, t.range_nm, t.hourly_rate
      INTO v_operator, v_category, v_range, v_rate
      FROM aircraft a JOIN aircraft_type t ON a.type_id = t.type_id
     WHERE a.aircraft_id = p_aircraft;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Aircraft % does not exist', p_aircraft;
    END IF;

    -- the route
    IF fn_distance_nm(p_origin, p_dest) > v_range THEN
        RAISE EXCEPTION 'Route is longer than the aircraft range of % nm', v_range;
    END IF;

    v_hours   := fn_flight_hours(p_aircraft, p_origin, p_dest);
    v_arrival := p_departure + v_hours * INTERVAL '1 hour';

    -- a free pilot of the same operator with the right rating
    SELECT p.pilot_id INTO v_pilot
      FROM pilot p
     WHERE p.operator_id = v_operator
       AND p.category_rating = v_category
       AND p.status = 'Active'
       AND NOT EXISTS (SELECT 1 FROM booking b
                        WHERE b.pilot_id = p.pilot_id
                          AND b.status <> 'Cancelled'
                          AND b.departure_time < v_arrival
                          AND b.arrival_time   > p_departure)
     ORDER BY p.experience_hours DESC
     LIMIT 1;

    IF v_pilot IS NULL THEN
        RAISE EXCEPTION 'No free % pilot available for that time', v_category;
    END IF;

    -- the booking (fare = flight hours x hourly rate)
    INSERT INTO booking (customer_id, aircraft_id, pilot_id, origin_id, dest_id,
                         departure_time, arrival_time, passengers, status, total_fare)
    VALUES (p_customer, p_aircraft, v_pilot, p_origin, p_dest,
            p_departure, v_arrival, p_passengers, 'Pending', ROUND(v_hours * v_rate, 2))
    RETURNING booking_id INTO p_booking_id;

    RAISE NOTICE 'Booking % created, pilot %', p_booking_id, v_pilot;
END;
$$;


-- 2. Complete a flight: mark it Completed and add the flown hours
--    to the aircraft and to the pilot.
CREATE OR REPLACE PROCEDURE complete_flight(p_booking INT)
LANGUAGE plpgsql AS $$
DECLARE
    v_aircraft INT;
    v_pilot    INT;
    v_status   VARCHAR;
    v_hours    NUMERIC;
BEGIN
    SELECT aircraft_id, pilot_id, status,
           ROUND((EXTRACT(EPOCH FROM (arrival_time - departure_time)) / 3600)::NUMERIC, 1)
      INTO v_aircraft, v_pilot, v_status, v_hours
      FROM booking WHERE booking_id = p_booking;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Booking % does not exist', p_booking;
    END IF;
    IF v_status <> 'Confirmed' THEN
        RAISE EXCEPTION 'Only a Confirmed booking can be completed (this one is %)', v_status;
    END IF;

    UPDATE booking  SET status = 'Completed' WHERE booking_id = p_booking;
    UPDATE aircraft SET total_hours = total_hours + v_hours WHERE aircraft_id = v_aircraft;
    UPDATE pilot    SET experience_hours = experience_hours + v_hours WHERE pilot_id = v_pilot;

    RAISE NOTICE 'Booking % completed, % hours added', p_booking, v_hours;
END;
$$;


-- 3. Maintenance check (CURSOR): go through every aircraft that is past its
--    operator's service interval and set it to Maintenance.
CREATE OR REPLACE PROCEDURE check_overdue_aircraft()
LANGUAGE plpgsql AS $$
DECLARE
    cur CURSOR FOR
        SELECT a.aircraft_id, a.registration_no,
               a.total_hours - a.last_service_hours AS hours_since_service,
               o.service_interval_hrs
          FROM aircraft a JOIN operator o ON a.operator_id = o.operator_id
         WHERE a.status = 'Available'
           AND a.total_hours - a.last_service_hours > o.service_interval_hrs;
    rec     RECORD;
    v_count INT := 0;
BEGIN
    OPEN cur;
    LOOP
        FETCH cur INTO rec;
        EXIT WHEN NOT FOUND;

        UPDATE aircraft SET status = 'Maintenance' WHERE aircraft_id = rec.aircraft_id;
        RAISE NOTICE 'Grounded %: % hours since service (limit %)',
                     rec.registration_no, rec.hours_since_service, rec.service_interval_hrs;
        v_count := v_count + 1;
    END LOOP;
    CLOSE cur;

    RAISE NOTICE '% aircraft grounded', v_count;
END;
$$;


-- ============================================================
-- TRIGGERS (2)
-- ============================================================

-- Trigger 1: before a booking is inserted, check the rules a CHECK constraint cannot.
CREATE OR REPLACE FUNCTION booking_validate() RETURNS TRIGGER AS $$
DECLARE
    v_status      VARCHAR;
    v_seats       INT;
    v_category    VARCHAR;
    v_aircraft_op INT;
    v_rating      VARCHAR;
    v_pilot_op    INT;
BEGIN
    SELECT a.status, t.seats, t.category, a.operator_id
      INTO v_status, v_seats, v_category, v_aircraft_op
      FROM aircraft a JOIN aircraft_type t ON a.type_id = t.type_id
     WHERE a.aircraft_id = NEW.aircraft_id;

    SELECT category_rating, operator_id INTO v_rating, v_pilot_op
      FROM pilot WHERE pilot_id = NEW.pilot_id;

    IF v_status = 'Maintenance' THEN
        RAISE EXCEPTION 'Aircraft % is in maintenance', NEW.aircraft_id;
    END IF;
    IF NEW.passengers > v_seats THEN
        RAISE EXCEPTION 'Passengers (%) exceed the aircraft seats (%)', NEW.passengers, v_seats;
    END IF;
    IF v_rating <> v_category THEN
        RAISE EXCEPTION 'Pilot rating (%) does not match the aircraft category (%)', v_rating, v_category;
    END IF;
    IF v_pilot_op <> v_aircraft_op THEN
        RAISE EXCEPTION 'Pilot and aircraft belong to different operators';
    END IF;
    IF EXISTS (SELECT 1 FROM booking b
                WHERE (b.aircraft_id = NEW.aircraft_id OR b.pilot_id = NEW.pilot_id)
                  AND b.status <> 'Cancelled'
                  AND b.departure_time < NEW.arrival_time
                  AND b.arrival_time   > NEW.departure_time) THEN
        RAISE EXCEPTION 'The aircraft or the pilot is already booked in that time range';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_booking_validate
BEFORE INSERT ON booking
FOR EACH ROW EXECUTE FUNCTION booking_validate();


-- Trigger 2: after a payment, reject overpayment, and confirm the booking
-- once the fare is fully paid.
CREATE OR REPLACE FUNCTION payment_confirm() RETURNS TRIGGER AS $$
DECLARE
    v_fare NUMERIC;
    v_paid NUMERIC;
BEGIN
    SELECT total_fare INTO v_fare FROM booking WHERE booking_id = NEW.booking_id;

    SELECT SUM(amount) INTO v_paid
      FROM payment WHERE booking_id = NEW.booking_id AND status = 'Paid';

    IF v_paid > v_fare THEN
        RAISE EXCEPTION 'Payment exceeds the fare (paid %, fare %)', v_paid, v_fare;
    END IF;

    IF v_paid = v_fare THEN
        UPDATE booking SET status = 'Confirmed'
         WHERE booking_id = NEW.booking_id AND status = 'Pending';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_payment_confirm
AFTER INSERT ON payment
FOR EACH ROW EXECUTE FUNCTION payment_confirm();
