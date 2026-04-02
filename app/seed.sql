-- 1. Registries
INSERT INTO registry (name, country, accreditation_body, contact_email) VALUES
('Verra Registry', 'USA', 'ICAO', 'contact@verra.org'),
('Gold Standard', 'Switzerland', 'WWF', 'info@goldstandard.org'),
('American Carbon Registry', 'USA', 'Winrock International', 'acr@winrock.org');

-- 2. Companies
INSERT INTO company (name, registration_number, country, sector, status) VALUES
('GreenEarth Industries', 'GEI-001', 'India', 'MANUFACTURING', 'ACTIVE'),
('SolarWave Energy', 'SWE-002', 'India', 'ENERGY', 'ACTIVE'),
('EcoForest Ltd', 'EFL-003', 'Brazil', 'FORESTRY', 'ACTIVE'),
('CleanAir Corp', 'CAC-004', 'USA', 'TRANSPORT', 'ACTIVE'),
('BlueSky Aviation', 'BSA-005', 'UK', 'AVIATION', 'ACTIVE');

-- 3. Wallets (one per company)
INSERT INTO wallet (company_id, balance, currency)
SELECT company_id, 100000.0000, 'USD' FROM company WHERE registration_number = 'GEI-001';

INSERT INTO wallet (company_id, balance, currency)
SELECT company_id, 250000.0000, 'USD' FROM company WHERE registration_number = 'SWE-002';

INSERT INTO wallet (company_id, balance, currency)
SELECT company_id, 180000.0000, 'USD' FROM company WHERE registration_number = 'EFL-003';

INSERT INTO wallet (company_id, balance, currency)
SELECT company_id, 320000.0000, 'USD' FROM company WHERE registration_number = 'CAC-004';

INSERT INTO wallet (company_id, balance, currency)
SELECT company_id, 95000.0000, 'USD' FROM company WHERE registration_number = 'BSA-005';

-- 4. Projects
INSERT INTO project (registry_id, name, type, location, start_date, end_date, status)
SELECT registry_id, 'Amazon Reforestation Initiative', 'REFORESTATION', 
       'Para, Brazil', '2022-01-01', '2027-12-31', 'ACTIVE'
FROM registry WHERE name = 'Verra Registry';

INSERT INTO project (registry_id, name, type, location, start_date, end_date, status)
SELECT registry_id, 'Rajasthan Solar Farm', 'SOLAR',
       'Rajasthan, India', '2021-06-01', '2026-05-31', 'ACTIVE'
FROM registry WHERE name = 'Gold Standard';

INSERT INTO project (registry_id, name, type, location, start_date, end_date, status)
SELECT registry_id, 'Punjab Wind Energy Project', 'WIND',
       'Punjab, India', '2020-03-15', '2025-03-14', 'ACTIVE'
FROM registry WHERE name = 'American Carbon Registry';

INSERT INTO project (registry_id, name, type, location, start_date, end_date, status)
SELECT registry_id, 'Maharashtra Methane Capture', 'METHANE_CAPTURE',
       'Pune, India', '2023-01-01', '2028-12-31', 'ACTIVE'
FROM registry WHERE name = 'Verra Registry';

-- 5. Credit batches
INSERT INTO credit_batch (
    project_id, registry_id, owner_company_id,
    quantity, quantity_available, unit_price,
    certification_standard, vintage_year, expiry_date, status
)
SELECT 
    p.project_id, p.registry_id, c.company_id,
    5000, 5000, 12.5000,
    'VCS', '2023-01-01', '2028-12-31', 'AVAILABLE'
FROM project p, company c
WHERE p.name = 'Amazon Reforestation Initiative'
AND c.registration_number = 'EFL-003';

INSERT INTO credit_batch (
    project_id, registry_id, owner_company_id,
    quantity, quantity_available, unit_price,
    certification_standard, vintage_year, expiry_date, status
)
SELECT
    p.project_id, p.registry_id, c.company_id,
    3000, 3000, 15.0000,
    'Gold Standard', '2023-01-01', '2027-12-31', 'AVAILABLE'
FROM project p, company c
WHERE p.name = 'Rajasthan Solar Farm'
AND c.registration_number = 'SWE-002';

INSERT INTO credit_batch (
    project_id, registry_id, owner_company_id,
    quantity, quantity_available, unit_price,
    certification_standard, vintage_year, expiry_date, status
)
SELECT
    p.project_id, p.registry_id, c.company_id,
    2000, 2000, 10.0000,
    'ACR', '2022-01-01', '2026-12-31', 'AVAILABLE'
FROM project p, company c
WHERE p.name = 'Punjab Wind Energy Project'
AND c.registration_number = 'SWE-002';

INSERT INTO credit_batch (
    project_id, registry_id, owner_company_id,
    quantity, quantity_available, unit_price,
    certification_standard, vintage_year, expiry_date, status
)
SELECT
    p.project_id, p.registry_id, c.company_id,
    4000, 4000, 18.0000,
    'VCS', '2024-01-01', '2029-12-31', 'AVAILABLE'
FROM project p, company c
WHERE p.name = 'Maharashtra Methane Capture'
AND c.registration_number = 'GEI-001';

-- 6. Users (password is 'password123' -- we will hash this properly later)
INSERT INTO users (company_id, email, password, role)
SELECT company_id, 'admin@greenearth.com', 'password123', 'ADMIN'
FROM company WHERE registration_number = 'GEI-001';

INSERT INTO users (company_id, email, password, role)
SELECT company_id, 'user@solarwave.com', 'password123', 'USER'
FROM company WHERE registration_number = 'SWE-002';

INSERT INTO users (company_id, email, password, role)
SELECT company_id, 'user@ecoforest.com', 'password123', 'USER'
FROM company WHERE registration_number = 'EFL-003';

INSERT INTO users (company_id, email, password, role)
SELECT company_id, 'user@cleanair.com', 'password123', 'USER'
FROM company WHERE registration_number = 'CAC-004';

INSERT INTO users (company_id, email, password, role)
SELECT company_id, 'user@bluesky.com', 'password123', 'USER'
FROM company WHERE registration_number = 'BSA-005';