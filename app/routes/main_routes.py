from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from decimal import Decimal, InvalidOperation
from app.db import get_db_connection
from app.services.transaction_service import process_buy_transaction

main = Blueprint('main', __name__)

# ---------------- HOME ----------------
@main.route('/')
def index():
    return render_template('index.html')


# ---------------- LOGIN ----------------
@main.route('/login', methods=['GET', 'POST'])
def login():
    error = None

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT u.user_id, u.role, c.name, u.company_id
            FROM users u
            JOIN company c ON u.company_id = c.company_id
            WHERE u.email = %s AND u.password = %s
        """, (email, password))

        user = cur.fetchone()
        cur.close()
        conn.close()

        if user:
            session['user_id'] = str(user[0])
            session['role'] = user[1]
            session['company_name'] = user[2]
            session['company_id'] = str(user[3])

            return redirect(url_for('main.dashboard'))
        else:
            error = 'Invalid email or password'

    return render_template('login.html', error=error)


# ---------------- LOGOUT ----------------
@main.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('main.login'))


# ---------------- DASHBOARD ----------------
@main.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT company_id, name, sector, status FROM company;")
    companies = cur.fetchall()

    cur.close()
    conn.close()

    return render_template('dashboard.html', companies=companies)


# ---------------- ADD COMPANY ----------------
@main.route('/add-company', methods=['GET', 'POST'])
def add_company():
    error = None
    success = None

    if request.method == 'POST':
        company_name = request.form['name'].strip()
        registration_number = request.form['registration_number'].strip()
        country = request.form['country'].strip()
        sector = request.form['sector'].strip()
        status = request.form['status'].strip().upper()

        admin_email = request.form['admin_email'].strip().lower()
        admin_password = request.form['admin_password'].strip()
        admin_role = request.form['admin_role'].strip().upper()
        currency = request.form['currency'].strip().upper() or 'USD'

        opening_balance_raw = request.form.get('opening_balance', '0').strip()
        try:
            # Allow values like 10000, 10000.50, or 10,000.50
            normalized_balance = (opening_balance_raw or '0').replace(',', '')
            opening_balance = Decimal(normalized_balance)
            if opening_balance < 0:
                raise InvalidOperation
        except (InvalidOperation, ValueError):
            opening_balance = None

        if not all([company_name, registration_number, country, admin_email, admin_password]):
            error = 'Please fill all required fields.'
        elif opening_balance is None:
            error = 'Opening balance must be a valid non-negative number.'
        elif status not in ('ACTIVE', 'SUSPENDED', 'DISSOLVED'):
            error = 'Invalid company status selected.'
        elif admin_role not in ('ADMIN', 'USER'):
            error = 'Invalid user role selected.'
        else:
            conn = get_db_connection()
            cur = conn.cursor()
            try:
                cur.execute("""
                    INSERT INTO company (name, registration_number, country, sector, status)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING company_id
                """, (company_name, registration_number, country, sector or None, status))
                new_company_id = cur.fetchone()[0]

                cur.execute("""
                    INSERT INTO wallet (company_id, balance, currency)
                    VALUES (%s, %s, %s)
                """, (new_company_id, opening_balance, currency))

                cur.execute("""
                    INSERT INTO users (company_id, email, password, role)
                    VALUES (%s, %s, %s, %s)
                """, (new_company_id, admin_email, admin_password, admin_role))

                conn.commit()
                success = 'Company, wallet, and login user created successfully.'
            except Exception:
                conn.rollback()
                error = 'Could not create company. Registration number or email may already exist.'
            finally:
                cur.close()
                conn.close()

    return render_template('add_company.html', error=error, success=success)


@main.route('/delete-account', methods=['POST'])
def delete_account():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    company_id = session.get('company_id')
    user_id = session.get('user_id')

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("SELECT name FROM company WHERE company_id = %s::uuid", (company_id,))
        company = cur.fetchone()
        if not company:
            session.clear()
            flash('Account not found. You have been logged out.', 'error')
            return redirect(url_for('main.login'))

        cur.execute(
            'SELECT COUNT(*) FROM "transaction" WHERE buyer_id = %s::uuid OR seller_id = %s::uuid',
            (company_id, company_id),
        )
        has_transactions = cur.fetchone()[0] > 0

        cur.execute("SELECT COUNT(*) FROM credit_batch WHERE owner_company_id = %s::uuid", (company_id,))
        has_batches = cur.fetchone()[0] > 0

        if has_transactions or has_batches:
            # Preserve referential integrity: convert delete request into account closure.
            cur.execute(
                "UPDATE company SET status = 'DISSOLVED' WHERE company_id = %s::uuid",
                (company_id,),
            )
            cur.execute("DELETE FROM users WHERE user_id = %s::uuid", (user_id,))
            conn.commit()
            session.clear()
            flash(
                'Account closed. Company data with historical transactions was archived as DISSOLVED.',
                'success',
            )
            return redirect(url_for('main.login'))

        # No historical links: perform full deletion of company account footprint.
        cur.execute("DELETE FROM users WHERE company_id = %s::uuid", (company_id,))
        cur.execute("DELETE FROM wallet WHERE company_id = %s::uuid", (company_id,))
        cur.execute("DELETE FROM company WHERE company_id = %s::uuid", (company_id,))
        conn.commit()
        session.clear()
        flash(f'Account for "{company[0]}" deleted successfully.', 'success')
        return redirect(url_for('main.login'))
    except Exception:
        conn.rollback()
        flash('Failed to process account deletion due to a database error.', 'error')
        return redirect(url_for('main.dashboard'))
    finally:
        cur.close()
        conn.close()

    return redirect(url_for('main.dashboard'))
# ---------------- PORTFOLIO ----------------
@main.route('/portfolio')
def portfolio():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT balance, currency
        FROM wallet
        WHERE company_id = %s::uuid
    """, (session['company_id'],))
    wallet = cur.fetchone()

    if not wallet:
        # Self-heal legacy/missing wallet rows so portfolio always has data.
        cur.execute("""
            INSERT INTO wallet (company_id, balance, currency)
            VALUES (%s::uuid, 0, 'USD')
            ON CONFLICT (company_id) DO NOTHING
        """, (session['company_id'],))
        conn.commit()
        cur.execute("""
            SELECT balance, currency
            FROM wallet
            WHERE company_id = %s::uuid
        """, (session['company_id'],))
        wallet = cur.fetchone()

    cur.execute("""
        SELECT cb.batch_id, p.name, p.type, r.name,
               cb.certification_standard, cb.vintage_year,
               cb.quantity_available, cb.unit_price,
               cb.expiry_date, cb.status
        FROM credit_batch cb
        JOIN project p ON cb.project_id = p.project_id
        JOIN registry r ON cb.registry_id = r.registry_id
        WHERE cb.owner_company_id = %s
        AND cb.status NOT IN ('RETIRED', 'EXPIRED', 'SOLD_OUT')
        ORDER BY cb.expiry_date ASC
    """, (session['company_id'],))
    credits = cur.fetchall()

    cur.close()
    conn.close()

    return render_template('portfolio.html', wallet=wallet, credits=credits)


# ---------------- TRANSACTIONS ----------------
@main.route('/transactions')
def transactions():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT t.transaction_id, 
               buyer.name AS buyer_name,
               seller.name AS seller_name,
               p.name AS project_name,
               t.quantity, t.price_per_unit, t.total_amount,
               t.transaction_type, t.status, t.timestamp
        FROM "transaction" t
        LEFT JOIN company buyer ON t.buyer_id = buyer.company_id
        LEFT JOIN company seller ON t.seller_id = seller.company_id
        JOIN credit_batch cb ON t.batch_id = cb.batch_id
        JOIN project p ON cb.project_id = p.project_id
        WHERE t.buyer_id = %s OR t.seller_id = %s
        ORDER BY t.timestamp DESC
    """, (session['company_id'], session['company_id']))

    txns = cur.fetchall()

    cur.close()
    conn.close()

    return render_template('transactions.html', txns=txns)
# ---------------- BUY ----------------
@main.route('/buy', methods=['GET', 'POST'])
def buy():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    error = None
    success = None

    conn = get_db_connection()

    if request.method == 'POST':
        batch_id = request.form['batch_id']
        try:
            quantity = int(request.form['quantity'])
            if quantity <= 0:
                raise ValueError
        except (TypeError, ValueError):
            error = 'Please enter a valid quantity greater than 0.'
        else:
            ok, message = process_buy_transaction(conn, session, batch_id, quantity)
            if ok:
                success = message
            else:
                error = message

    # Fetch available batches
    cur = conn.cursor()
    cur.execute("""
        SELECT cb.batch_id, c.name, p.name, p.type,
               cb.quantity_available, cb.unit_price,
               cb.certification_standard, cb.expiry_date
        FROM credit_batch cb
        JOIN company c ON cb.owner_company_id = c.company_id
        JOIN project p ON cb.project_id = p.project_id
        WHERE cb.owner_company_id != %s
        AND cb.status IN ('AVAILABLE', 'PARTIALLY_SOLD')
        ORDER BY cb.unit_price ASC
    """, (session['company_id'],))

    batches = cur.fetchall()

    cur.close()
    conn.close()

    return render_template('buy.html', batches=batches, error=error, success=success)


# ---------------- SELL ----------------
@main.route('/sell', methods=['GET', 'POST'])
def sell():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    conn = get_db_connection()
    cur = conn.cursor()
    error = None
    success = None

    if request.method == 'POST':
        batch_id = request.form['batch_id']
        try:
            new_price = float(request.form['unit_price'])
            if new_price <= 0:
                raise ValueError
        except (TypeError, ValueError):
            error = 'Please enter a valid sale price greater than 0.'
        else:
            cur.execute("""
                UPDATE credit_batch
                SET unit_price = %s,
                    status = 'AVAILABLE'
                WHERE batch_id = %s
                AND owner_company_id = %s
                AND status NOT IN ('RETIRED', 'EXPIRED', 'SOLD_OUT')
            """, (new_price, batch_id, session['company_id']))

            if cur.rowcount == 0:
                conn.rollback()
                error = 'Batch not found or cannot be listed.'
            else:
                conn.commit()
                success = 'Credit batch listed for sale successfully.'

    cur.execute("""
        SELECT cb.batch_id, p.name, p.type,
               cb.quantity_available, cb.unit_price,
               cb.certification_standard, cb.status
        FROM credit_batch cb
        JOIN project p ON cb.project_id = p.project_id
        WHERE cb.owner_company_id = %s
        AND cb.status NOT IN ('RETIRED', 'EXPIRED', 'SOLD_OUT')
    """, (session['company_id'],))
    my_batches = cur.fetchall()

    cur.close()
    conn.close()
    return render_template('sell.html', my_batches=my_batches, error=error, success=success)