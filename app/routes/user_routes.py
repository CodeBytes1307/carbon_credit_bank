from decimal import Decimal, InvalidOperation

from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from psycopg2.extras import RealDictCursor

from app.db import get_db_connection
from app.services.transaction_service import process_buy_transaction
from app.utils import login_required, user_required

user = Blueprint("user", __name__)


@user.route("/dashboard")
@login_required
@user_required
def dashboard():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("SELECT company_id, name, sector, country, status FROM company;")
    companies = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("user/dashboard.html", companies=companies)


@user.route("/portfolio")
@login_required
@user_required
def portfolio():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Validate company exists
    cur.execute(
        "SELECT company_id FROM company WHERE company_id = %s::uuid",
        (session["company_id"],),
    )
    if not cur.fetchone():
        cur.close()
        conn.close()
        session.clear()
        return redirect(url_for("auth.login"))

    cur.execute(
        """
        SELECT balance, currency
        FROM wallet
        WHERE company_id = %s::uuid
        """,
        (session["company_id"],),
    )
    wallet = cur.fetchone()

    if not wallet:
        try:
            cur.execute(
                """
                INSERT INTO wallet (company_id, balance, currency)
                VALUES (%s::uuid, 0, 'USD')
                ON CONFLICT (company_id) DO NOTHING
                """,
                (session["company_id"],),
            )
            conn.commit()
            cur.execute(
                """
                SELECT balance, currency
                FROM wallet
                WHERE company_id = %s::uuid
                """,
                (session["company_id"],),
            )
            wallet = cur.fetchone()
        except Exception:
            conn.rollback()
            wallet = {"balance": 0, "currency": "USD"}

    cur.execute(
        """
        SELECT cb.batch_id, p.name as project_name, p.type, r.name as registry_name,
               cb.certification_standard, cb.vintage_year,
               cb.quantity_available, cb.unit_price,
               cb.expiry_date, cb.status, cb.quantity
        FROM credit_batch cb
        JOIN project p ON cb.project_id = p.project_id
        JOIN registry r ON cb.registry_id = r.registry_id
        WHERE cb.owner_company_id = %s
          AND cb.status NOT IN ('RETIRED', 'EXPIRED', 'SOLD_OUT')
        ORDER BY cb.expiry_date ASC
        """,
        (session["company_id"],),
    )
    batches = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("user/portfolio.html", wallet=wallet, batches=batches)


@user.route("/transactions")
@login_required
@user_required
def transactions():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute(
        """
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
        """,
        (session["company_id"], session["company_id"]),
    )
    transactions = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("user/transactions.html", transactions=transactions)


@user.route("/buy", methods=["GET", "POST"])
@login_required
@user_required
def buy():
    error = None
    success = None

    conn = get_db_connection()

    if request.method == "POST":
        batch_id = request.form["batch_id"]
        try:
            quantity = int(request.form["quantity"])
            if quantity <= 0:
                raise ValueError
        except (TypeError, ValueError):
            error = "Please enter a valid quantity greater than 0."
        else:
            ok, message = process_buy_transaction(conn, session, batch_id, quantity)
            if ok:
                success = message
            else:
                error = message

    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        """
        SELECT cb.batch_id, c.name as owner_name, p.name as project_name, p.type,
               cb.quantity_available, cb.unit_price,
               cb.certification_standard, cb.expiry_date, 'USD' as currency
        FROM credit_batch cb
        JOIN company c ON cb.owner_company_id = c.company_id
        JOIN project p ON cb.project_id = p.project_id
        WHERE cb.owner_company_id != %s
          AND cb.status IN ('AVAILABLE', 'PARTIALLY_SOLD')
        ORDER BY cb.unit_price ASC
        """,
        (session["company_id"],),
    )
    batches = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("user/buy.html", batches=batches, error=error, success=success)


@user.route("/sell", methods=["GET", "POST"])
@login_required
@user_required
def sell():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    error = None
    success = None

    if request.method == "POST":
        batch_id = request.form["batch_id"]
        try:
            new_price = float(request.form["unit_price"])
            if new_price <= 0:
                raise ValueError
        except (TypeError, ValueError):
            error = "Please enter a valid sale price greater than 0."
        else:
            cur.execute(
                """
                UPDATE credit_batch
                SET unit_price = %s,
                    status = 'AVAILABLE'
                WHERE batch_id = %s
                  AND owner_company_id = %s
                  AND status NOT IN ('RETIRED', 'EXPIRED', 'SOLD_OUT')
                """,
                (new_price, batch_id, session["company_id"]),
            )

            if cur.rowcount == 0:
                conn.rollback()
                error = "Batch not found or cannot be listed."
            else:
                conn.commit()
                success = "Credit batch listed for sale successfully."

    cur.execute(
        """
        SELECT cb.batch_id, p.name as project_name, p.type,
               cb.quantity_available, cb.unit_price,
               cb.certification_standard, cb.status
        FROM credit_batch cb
        JOIN project p ON cb.project_id = p.project_id
        WHERE cb.owner_company_id = %s
          AND cb.status NOT IN ('RETIRED', 'EXPIRED', 'SOLD_OUT')
        """,
        (session["company_id"],),
    )
    owned_batches = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("user/sell.html", owned_batches=owned_batches, error=error, success=success)


@user.route("/retire", methods=["GET", "POST"])
@login_required
@user_required
def retire():
    """
    Retire credits owned by the logged-in user's company.
    This removes credits from circulation and records a retirement record.
    """

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    error = None
    success = None

    allowed_reasons = {"COMPLIANCE", "VOLUNTARY", "OFFSET"}

    if request.method == "POST":
        batch_id = request.form.get("batch_id")
        reason = (request.form.get("reason") or "").strip().upper()
        qty_raw = (request.form.get("quantity") or "").strip()

        try:
            quantity = int(qty_raw)
            if quantity <= 0:
                raise ValueError
        except (TypeError, ValueError):
            error = "Please enter a valid retirement quantity greater than 0."

        if error is None and reason not in allowed_reasons:
            error = "Invalid retirement reason."

        if error is None:
            try:
                # Verify batch belongs to current company and has enough available.
                cur.execute(
                    """
                    SELECT batch_id, quantity_available, status
                    FROM credit_batch
                    WHERE batch_id = %s
                      AND owner_company_id = %s::uuid
                      AND status NOT IN ('EXPIRED', 'SOLD_OUT')
                    """,
                    (batch_id, session["company_id"]),
                )
                batch = cur.fetchone()

                if not batch:
                    raise ValueError("Batch not found for your company.")

                available = int(batch['quantity_available'])
                if quantity > available:
                    raise ValueError("Retirement quantity exceeds available credits.")

                # Create a transaction record of type RETIREMENT.
                cur.execute(
                    """
                    INSERT INTO "transaction" (
                        buyer_id, seller_id, batch_id,
                        wallet_debit_id, wallet_credit_id,
                        quantity, price_per_unit, total_amount,
                        transaction_type, status, notes
                    )
                    VALUES (NULL, NULL, %s, NULL, NULL, %s, 0, 0, 'RETIREMENT', 'COMPLETED', %s)
                    RETURNING transaction_id
                    """,
                    (batch_id, quantity, reason),
                )
                txn_id = cur.fetchone()[0]

                # Record retirement details.
                cur.execute(
                    """
                    INSERT INTO retirement_record (
                        batch_id, company_id, transaction_id,
                        quantity_retired, retirement_reason
                    )
                    VALUES (%s, %s::uuid, %s, %s, %s)
                    """,
                    (batch_id, session["company_id"], txn_id, quantity, reason),
                )

                # Update batch quantity/status.
                new_available = available - quantity
                new_status = "RETIRED" if new_available == 0 else "PARTIALLY_SOLD"

                cur.execute(
                    """
                    UPDATE credit_batch
                    SET quantity_available = %s,
                        status = %s
                    WHERE batch_id = %s
                      AND owner_company_id = %s::uuid
                    """,
                    (new_available, new_status, batch_id, session["company_id"]),
                )

                # Ownership history: company -> NULL (retired).
                cur.execute(
                    """
                    INSERT INTO ownership_history (
                        batch_id, from_company_id, to_company_id,
                        transaction_id, quantity
                    )
                    VALUES (%s, %s::uuid, NULL, %s, %s)
                    """,
                    (batch_id, session["company_id"], txn_id, quantity),
                )

                conn.commit()
                success = f"Retired {quantity} credits successfully."
            except Exception as e:
                conn.rollback()
                error = str(e)

    # Fetch batches user can retire.
    cur.execute(
        """
        SELECT cb.batch_id, p.name as project_name, cb.quantity_available, cb.status, cb.expiry_date
        FROM credit_batch cb
        JOIN project p ON cb.project_id = p.project_id
        WHERE cb.owner_company_id = %s::uuid
          AND cb.status NOT IN ('RETIRED', 'EXPIRED', 'SOLD_OUT')
          AND cb.quantity_available > 0
        ORDER BY cb.expiry_date ASC NULLS LAST
        """,
        (session["company_id"],),
    )
    owned_batches = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "user/retire.html",
        owned_batches=owned_batches,
        error=error,
        success=success,
        allowed_reasons=sorted(allowed_reasons),
    )

