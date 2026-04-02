-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 1. Registry
CREATE TABLE IF NOT EXISTS registry (
    registry_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(200) NOT NULL UNIQUE,
    country         VARCHAR(100) NOT NULL,
    accreditation_body VARCHAR(200),
    contact_email   VARCHAR(150),
    created_at      TIMESTAMP DEFAULT NOW()
);

-- 2. Company
CREATE TABLE IF NOT EXISTS company (
    company_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                VARCHAR(200) NOT NULL,
    registration_number VARCHAR(100) NOT NULL UNIQUE,
    country             VARCHAR(100) NOT NULL,
    sector              VARCHAR(100),
    status              VARCHAR(20) DEFAULT 'ACTIVE'
                        CHECK (status IN ('ACTIVE', 'SUSPENDED', 'DISSOLVED')),
    created_at          TIMESTAMP DEFAULT NOW()
);

-- 3. Users (login)
CREATE TABLE IF NOT EXISTS users (
    user_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id  UUID NOT NULL REFERENCES company(company_id),
    email       VARCHAR(150) NOT NULL UNIQUE,
    password    VARCHAR(255) NOT NULL,
    role        VARCHAR(20) DEFAULT 'USER'
                CHECK (role IN ('ADMIN', 'USER')),
    created_at  TIMESTAMP DEFAULT NOW()
);

-- 4. Wallet
CREATE TABLE IF NOT EXISTS wallet (
    wallet_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id  UUID NOT NULL UNIQUE REFERENCES company(company_id),
    balance     NUMERIC(20, 4) DEFAULT 0 CHECK (balance >= 0),
    currency    VARCHAR(10) DEFAULT 'USD',
    updated_at  TIMESTAMP DEFAULT NOW()
);

-- 5. Project
CREATE TABLE IF NOT EXISTS project (
    project_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    registry_id UUID NOT NULL REFERENCES registry(registry_id),
    name        VARCHAR(300) NOT NULL,
    type        VARCHAR(100) CHECK (type IN (
                    'REFORESTATION','SOLAR','WIND',
                    'METHANE_CAPTURE','OCEAN',
                    'DIRECT_AIR_CAPTURE','OTHER')),
    location    VARCHAR(200),
    start_date  DATE,
    end_date    DATE,
    status      VARCHAR(20) DEFAULT 'ACTIVE'
                CHECK (status IN ('ACTIVE','COMPLETED','SUSPENDED')),
    created_at  TIMESTAMP DEFAULT NOW()
);

-- 6. Credit batch
CREATE TABLE IF NOT EXISTS credit_batch (
    batch_id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id              UUID NOT NULL REFERENCES project(project_id),
    registry_id             UUID NOT NULL REFERENCES registry(registry_id),
    owner_company_id        UUID NOT NULL REFERENCES company(company_id),
    quantity                INTEGER NOT NULL CHECK (quantity > 0),
    quantity_available      INTEGER NOT NULL CHECK (quantity_available >= 0),
    unit_price              NUMERIC(14, 4),
    certification_standard  VARCHAR(100),
    vintage_year            DATE NOT NULL,
    expiry_date             DATE,
    status                  VARCHAR(20) DEFAULT 'AVAILABLE'
                            CHECK (status IN (
                                'AVAILABLE','PARTIALLY_SOLD',
                                'SOLD_OUT','EXPIRED','RETIRED')),
    created_at              TIMESTAMP DEFAULT NOW(),
    CONSTRAINT qty_available_lte_total 
        CHECK (quantity_available <= quantity)
);

-- 7. Transaction
CREATE TABLE IF NOT EXISTS transaction (
    transaction_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    buyer_id         UUID REFERENCES company(company_id),
    seller_id        UUID REFERENCES company(company_id),
    batch_id         UUID NOT NULL REFERENCES credit_batch(batch_id),
    wallet_debit_id  UUID REFERENCES wallet(wallet_id),
    wallet_credit_id UUID REFERENCES wallet(wallet_id),
    quantity         INTEGER NOT NULL CHECK (quantity > 0),
    price_per_unit   NUMERIC(14, 4),
    total_amount     NUMERIC(20, 4),
    transaction_type VARCHAR(20) NOT NULL
                     CHECK (transaction_type IN (
                        'BUY','SELL','TRANSFER',
                        'ISSUANCE','RETIREMENT')),
    status           VARCHAR(20) DEFAULT 'PENDING'
                     CHECK (status IN (
                        'PENDING','COMPLETED','FAILED','REVERSED')),
    timestamp        TIMESTAMP DEFAULT NOW(),
    notes            TEXT,
    CONSTRAINT no_self_trade CHECK (buyer_id <> seller_id)
);

-- 8. Ownership history
CREATE TABLE IF NOT EXISTS ownership_history (
    history_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id         UUID NOT NULL REFERENCES credit_batch(batch_id),
    from_company_id  UUID REFERENCES company(company_id),
    to_company_id    UUID REFERENCES company(company_id),
    transaction_id   UUID NOT NULL REFERENCES transaction(transaction_id),
    quantity         INTEGER NOT NULL CHECK (quantity > 0),
    transferred_at   TIMESTAMP DEFAULT NOW()
);

-- 9. Retirement record
CREATE TABLE IF NOT EXISTS retirement_record (
    retirement_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id         UUID NOT NULL REFERENCES credit_batch(batch_id),
    company_id       UUID NOT NULL REFERENCES company(company_id),
    transaction_id   UUID NOT NULL REFERENCES transaction(transaction_id),
    quantity_retired INTEGER NOT NULL CHECK (quantity_retired > 0),
    retirement_reason VARCHAR(200),
    retired_at       TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_txn_buyer     ON transaction(buyer_id);
CREATE INDEX IF NOT EXISTS idx_txn_seller    ON transaction(seller_id);
CREATE INDEX IF NOT EXISTS idx_txn_batch     ON transaction(batch_id);
CREATE INDEX IF NOT EXISTS idx_txn_time      ON transaction(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_batch_owner   ON credit_batch(owner_company_id);
CREATE INDEX IF NOT EXISTS idx_batch_status  ON credit_batch(status);
CREATE INDEX IF NOT EXISTS idx_history_batch ON ownership_history(batch_id);
CREATE INDEX IF NOT EXISTS idx_retirement_co ON retirement_record(company_id);