from flask import Blueprint, render_template, request, redirect, url_for, session
from app.db import get_db_connection

main = Blueprint('main', __name__)

#@main.route('/')
# def index():
#     return render_template('index.html')

# @main.route('/login', methods=['GET', 'POST'])
# def login():
#     error = None
#     if request.method == 'POST':
#         email = request.form['email']
#         password = request.form['password']
#         conn = get_db_connection()
#         cur = conn.cursor()
#         cur.execute("""
#             SELECT u.user_id, u.role, c.name, u.company_id
#             FROM users u
#             JOIN company c ON u.company_id = c.company_id
#             WHERE u.email = %s AND u.password = %s
#         """, (email, password))
#         user = cur.fetchone()
#         cur.close()
#         conn.close()
#         if user:
#             session['user_id'] = str(user[0])
#             session['role'] = user[1]
#             session['company_name'] = user[2]
#             session['company_id'] = str(user[3])
#             return redirect(url_for('main.dashboard'))
#         else:
#             error = 'Invalid email or password'
#     return render_template('login.html', error=error)

# @main.route('/logout')
# def logout():
#     session.clear()
#     return redirect(url_for('main.login'))

# @main.route('/dashboard')
# def dashboard():
#     if 'user_id' not in session:
#         return redirect(url_for('main.login'))
#     conn = get_db_connection()
#     cur = conn.cursor()
#     cur.execute("SELECT company_id, name, sector, status FROM company;")
#     companies = cur.fetchall()
#     cur.close()
#     conn.close()
#     return render_template('dashboard.html', companies=companies)

# @main.route('/portfolio')
# def portfolio():
#     if 'user_id' not in session:
#         return redirect(url_for('main.login'))
#     conn = get_db_connection()
#     cur = conn.cursor()

#     cur.execute("""
#         SELECT balance, currency FROM wallet
#         WHERE company_id = %s
#     """, (session['company_id'],))
#     wallet = cur.fetchone()

#     cur.execute("""
#         SELECT cb.batch_id, p.name, p.type, r.name,
#                cb.certification_standard, cb.vintage_year,
#                cb.quantity_available, cb.unit_price,
#                cb.expiry_date, cb.status
#         FROM credit_batch cb
#         JOIN project p ON cb.project_id = p.project_id
#         JOIN registry r ON cb.registry_id = r.registry_id
#         WHERE cb.owner_company_id = %s
#         AND cb.status NOT IN ('RETIRED', 'EXPIRED', 'SOLD_OUT')
#         ORDER BY cb.expiry_date ASC
#     """, (session['company_id'],))
#     credits = cur.fetchall()

#     cur.close()
#     conn.close()
#     return render_template('portfolio.html', wallet=wallet, credits=credits)

# @main.route('/transactions')
# def transactions():
#     if 'user_id' not in session:
#         return redirect(url_for('main.login'))
#     conn = get_db_connection()
#     cur = conn.cursor()

#     cur.execute("""
#         SELECT t.transaction_id, 
#                buyer.name AS buyer_name,
#                seller.name AS seller_name,
#                p.name AS project_name,
#                t.quantity, t.price_per_unit, t.total_amount,
#                t.transaction_type, t.status, t.timestamp
#         FROM transaction t
#         LEFT JOIN company buyer ON t.buyer_id = buyer.company_id
#         LEFT JOIN company seller ON t.seller_id = seller.company_id
#         JOIN credit_batch cb ON t.batch_id = cb.batch_id
#         JOIN project p ON cb.project_id = p.project_id
#         WHERE t.buyer_id = %s OR t.seller_id = %s
#         ORDER BY t.timestamp DESC
#     """, (session['company_id'], session['company_id']))
#     txns = cur.fetchall()

#     cur.close()
#     conn.close()
#     return render_template('transactions.html', txns=txns)

from app.services.transaction_service import process_buy_transaction

@main.route('/buy', methods=['GET', 'POST'])
def buy():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    conn = get_db_connection()
    cur = conn.cursor()

    error = None
    success = None

    # -------- HANDLE POST --------
    if request.method == 'POST':
        batch_id = request.form['batch_id']
        quantity = int(request.form['quantity'])

        result, message = process_buy_transaction(conn, session, batch_id, quantity)

        if result:
            success = message
        else:
            error = message

    # -------- ALWAYS FETCH BATCHES --------
    cur.execute("""
        SELECT cb.batch_id, c.name, p.name, p.type,
               cb.quantity_available, cb.unit_price,
               cb.certification_standard, cb.expiry_date
        FROM credit_batch cb
        JOIN company c ON cb.owner_company_id = c.company_id
        JOIN project p ON cb.project_id = p.project_id
        WHERE cb.status IN ('AVAILABLE', 'PARTIALLY_SOLD')
        AND cb.owner_company_id != %s
        ORDER BY cb.unit_price ASC
    """, (session['company_id'],))

    batches = cur.fetchall()

    cur.close()
    conn.close()

    return render_template('buy.html', batches=batches, error=error, success=success)

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
        new_price = request.form['unit_price']

        cur.execute("""
            UPDATE credit_batch
            SET unit_price = %s,
                status = 'AVAILABLE'
            WHERE batch_id = %s
            AND owner_company_id = %s
        """, (new_price, batch_id, session['company_id']))
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