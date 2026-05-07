# Carbon Credit Bank

A DBMS mini-project that simulates a carbon credit trading platform where companies can:
- create and manage organizational accounts,
- maintain wallet balances,
- buy and sell credit batches,
- track transaction history and portfolio holdings.

The application is built with Flask + PostgreSQL and follows a server-rendered MVC-style structure with SQL-driven business logic.

---

## Features

- Company login with session-based authentication
- Company directory dashboard
- Portfolio view (wallet + owned credit batches)
- Buy credits workflow with transactional wallet and ownership updates
- Sell credits workflow by listing owned batches
- Transaction history (buyer/seller scoped)
- Add company (pre-login flow) with automatic wallet + initial user creation
- Self-service account deletion:
  - full delete when there is no linked history,
  - archival (`DISSOLVED`) when historical data must be preserved

---

## Tech Stack

- **Backend:** Flask 3
- **Database:** PostgreSQL
- **DB Driver:** psycopg2-binary
- **Templating:** Jinja2
- **Config:** python-dotenv
- **Frontend:** HTML/CSS (server-rendered templates)

---

## Project Structure

```text
carbon_credit_bank/
├── run.py
├── requirements.txt
├── app/
│   ├── __init__.py
│   ├── db.py
│   ├── schema.sql
│   ├── seed.sql
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── main_routes.py
│   │   └── transaction_routes.py
│   ├── services/
│   │   └── transaction_service.py
│   ├── models/
│   │   └── queries.py
│   ├── templates/
│   │   ├── base.html
│   │   ├── index.html
│   │   ├── login.html
│   │   ├── dashboard.html
│   │   ├── portfolio.html
│   │   ├── buy.html
│   │   ├── sell.html
│   │   ├── transactions.html
│   │   └── add_company.html
│   └── static/
│       └── css/
│           └── style.css
```

---

## Database Schema Overview

Main entities:

- `registry` - verification/registry organizations
- `company` - participating companies
- `users` - login users mapped to a company
- `wallet` - one wallet per company
- `project` - carbon projects
- `credit_batch` - tradable carbon credit inventory
- `transaction` - buy/sell ledger
- `ownership_history` - batch transfer trace
- `retirement_record` - retired credits

Important constraints:
- UUID primary keys (`gen_random_uuid()`)
- one-wallet-per-company (`wallet.company_id` unique)
- status/type checks (company, project, credit_batch, transaction)
- quantity and balance non-negative checks

---

## Prerequisites

- Python 3.10+ (3.11 recommended)
- PostgreSQL 13+
- `pip` and virtual environment tools

---

## Local Setup

### 1) Clone and enter project

```bash
git clone <your-repo-url>
cd carbon_credit_bank
```

### 2) Create and activate virtualenv

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3) Install dependencies

```bash
pip install -r requirements.txt
```

### 4) Create PostgreSQL database

```sql
CREATE DATABASE carbon_credit_bank;
```

### 5) Configure environment variables

Create a `.env` file in project root:

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=carbon_credit_bank
DB_USER=your_postgres_user
DB_PASSWORD=your_postgres_password
```

### 6) Apply schema and seed data

```bash
psql -h localhost -U your_postgres_user -d carbon_credit_bank -f app/schema.sql
psql -h localhost -U your_postgres_user -d carbon_credit_bank -f app/seed.sql
```

### 7) Run the app

```bash
python run.py
```

App runs on: `http://127.0.0.1:5001`

---

## Seed Login Credentials

From `app/seed.sql`:

- `admin@greenearth.com` / `password123`
- `user@solarwave.com` / `password123`
- `user@ecoforest.com` / `password123`
- `user@cleanair.com` / `password123`
- `user@bluesky.com` / `password123`

> Note: passwords are currently stored in plain text for academic/demo purposes.

---

## Routes and Functional Flow

### Public routes

- `GET /` - landing page
- `GET|POST /login` - login
- `GET|POST /add-company` - create company + wallet + initial user (pre-login feature)

### Authenticated routes

- `GET /dashboard` - company directory + delete account action
- `GET /portfolio` - current company wallet and held credits
- `GET|POST /buy` - buy from available external batches
- `GET|POST /sell` - list own batches for sale/update price
- `GET /transactions` - company-scoped transaction history
- `GET /logout` - clear session
- `POST /delete-account` - self-delete/self-close account

---

## Business Rules Implemented

### Buy transaction (`process_buy_transaction`)

- batch must be available and have sufficient quantity
- buyer cannot buy own credits
- buyer wallet must have sufficient balance
- single DB transaction updates:
  - `transaction` record
  - buyer and seller wallet balances
  - batch quantity/status/ownership
  - ownership history

### Add Company

On success, creates:
- one `company` row
- one `wallet` row
- one initial `users` row

Also validates:
- required fields
- status/role values
- non-negative opening balance (supports commas, e.g. `10,000.50`)

### Delete Account

- if company has historical trading links, account is archived:
  - company marked `DISSOLVED`
  - active user removed
- if no linked trade history, company footprint is deleted:
  - users + wallet + company

---

## Viewing Live Database Data

Connect with `psql`:

```bash
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME"
```

Useful queries:

```sql
\dt

SELECT name, registration_number, status, created_at
FROM company
ORDER BY created_at DESC;

SELECT c.name, w.balance, w.currency
FROM wallet w
JOIN company c ON c.company_id = w.company_id
ORDER BY c.created_at DESC;

SELECT transaction_id, buyer_id, seller_id, quantity, total_amount, status, timestamp
FROM "transaction"
ORDER BY timestamp DESC;
```

---

## Testing Checklist (Manual)

1. Login with seeded account.
2. Open dashboard, portfolio, buy, sell, transactions.
3. Create a new company using `/add-company`.
4. Login with newly created account.
5. Verify opening wallet balance in portfolio.
6. Buy credits from another company.
7. Verify:
   - buyer wallet decreases,
   - seller wallet increases,
   - transaction appears in history,
   - ownership and quantity updates.
8. Use delete account and verify expected behavior for:
   - account with no history (full delete),
   - account with history (archived as `DISSOLVED`).

---

## Common Issues and Fixes

### `ModuleNotFoundError: No module named 'flask'`
- Activate venv and install dependencies:
  - `source venv/bin/activate`
  - `pip install -r requirements.txt`

### DB connection error (`psycopg2.OperationalError`)
- verify `.env` values
- ensure PostgreSQL server is running
- ensure database exists and user has privileges

### Portfolio shows zero/missing wallet
- wallet auto-heal is implemented in `/portfolio`, but verify:
  - company exists,
  - wallet row exists for company,
  - correct login company is being used

### SQL keyword conflict on `transaction`
- the app uses quoted references (`"transaction"`) in query paths where required.

---

## Security and Production Notes

This project is intended for educational/demo use. Before production:

- hash passwords (`werkzeug.security` or `bcrypt`)
- replace hardcoded Flask secret key with environment variable
- add CSRF protection on forms (`Flask-WTF`)
- enforce stricter authorization and audit logging
- add migration tooling (Alembic)
- add automated tests and CI checks

---

## Future Enhancements

- role-based admin panel
- advanced filtering/search on transactions and companies
- retirement workflow UI
- analytics dashboard (wallet trends, trading volume)
- API layer (REST) for external integrations

---

## License

Use your preferred license (MIT/Apache-2.0/etc.) before publishing publicly.

