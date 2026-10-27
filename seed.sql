-- Demo data for trying the API from /docs or a frontend. Loaded by scripts/setup_db.py --seed.
INSERT INTO operator (name, license_no, email, phone, city, service_interval_hrs) VALUES
    ('SkyWay Charters',  'OP-1001', 'ops@skyway.example',  '+91 98200 11111', 'Mumbai', 100),
    ('Himalayan Air',    'OP-1002', 'ops@himair.example',  '+91 98110 22222', 'Delhi',  150);

INSERT INTO aircraft_type (model, category, seats, range_nm, cruise_speed_kts, hourly_rate) VALUES
    ('Cessna Citation CJ3', 'Jet',        7, 1900, 415, 95000.00),
    ('Bell 407',            'Helicopter', 6,  330, 133, 60000.00),
    ('Beechcraft King Air', 'Turboprop',  8, 1500, 290, 70000.00);

INSERT INTO location (name, city, code, loc_type, latitude, longitude) VALUES
    ('Chhatrapati Shivaji Intl',   'Mumbai',    'BOM', 'Airport', 19.088686,  72.867919),
    ('Indira Gandhi Intl',         'Delhi',     'DEL', 'Airport', 28.556160,  77.099999),
    ('Kempegowda Intl',            'Bengaluru', 'BLR', 'Airport', 13.198900,  77.705000),
    ('Juhu Aerodrome',             'Mumbai',    'JUHU','Helipad', 19.098000,  72.826000),
    ('Pune Airport',               'Pune',      'PNQ', 'Airport', 18.582100,  73.919700);

INSERT INTO customer (name, email, phone, id_proof) VALUES
    ('Asha Rao',    'asha@example.com',  '+91 90000 11111', 'PASS-A1234567'),
    ('Rohan Mehta', 'rohan@example.com', '+91 90000 22222', 'PASS-B7654321');

INSERT INTO aircraft (registration_no, operator_id, type_id, total_hours, last_service_hours) VALUES
    ('VT-SKY', 1, 1, 420.0, 380.0),
    ('VT-HLI', 1, 2, 210.5, 200.0),
    ('VT-KGA', 2, 3, 640.0, 600.0),
    ('VT-JET', 2, 1,  95.0,  95.0);

INSERT INTO pilot (operator_id, name, license_no, category_rating, experience_hours) VALUES
    (1, 'Capt. Vikram Singh', 'ATPL-5001', 'Jet',        4200.0),
    (1, 'Capt. Neha Kapoor',  'CPL-5002',  'Helicopter', 2600.0),
    (2, 'Capt. Arjun Nair',   'ATPL-5003', 'Turboprop',  3900.0),
    (2, 'Capt. Isha Verma',   'ATPL-5004', 'Jet',        3100.0);
