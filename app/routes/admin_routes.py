from datetime import date

from flask import Blueprint, render_template, request, redirect, url_for, flash
from psycopg2.extras import RealDictCursor

from app.db import get_db_connection
from app.utils import admin_required

admin = Blueprint("admin", __name__, url_prefix="/admin")


@admin.route("/dashboard")
@admin_required
def dashboard():
    conn = get_db_connection()
    cur = conn.cursor()

    # Total active companies
    cur.execute("SELECT COUNT(*) FROM company WHERE status = 'ACTIVE';")
    active_companies = cur.fetchone()[0]

    # Total credits in circulation (available in market)
    cur.execute(
        """
        SELECT COALESCE(SUM(quantity_available), 0)
        FROM credit_batch
        WHERE status IN ('AVAILABLE', 'PARTIALLY_SOLD')
        """
    )
    credits_in_circulation = cur.fetchone()[0]

    # Total transaction volume (completed only)
    cur.execute(
        """
        SELECT COALESCE(SUM(total_amount), 0)
        FROM "transaction"
        WHERE status = 'COMPLETED'
        """
    )
    total_volume = cur.fetchone()[0]

    # Total credits retired
    cur.execute("SELECT COALESCE(SUM(quantity_retired), 0) FROM retirement_record;")
    credits_retired = cur.fetchone()[0]

    # Transactions today
    cur.execute(
        """
        SELECT COUNT(*)
        FROM "transaction"
        WHERE DATE(timestamp) = CURRENT_DATE
        """
    )
    txns_today = cur.fetchone()[0]

    cur.close()
    conn.close()

    stats = {
        "active_companies": active_companies,
        "credits_in_circulation": credits_in_circulation,
        "total_volume": total_volume,
        "credits_retired": credits_retired,
        "txns_today": txns_today,
        "today": date.today(),
    }

    return render_template("admin/dashboard.html", stats=stats)


@admin.route("/companies", methods=["GET", "POST"])
@admin_required
def companies():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    if request.method == "POST":
        company_id = request.form.get("company_id")
        action = (request.form.get("action") or "").strip().upper()

        try:
            if action in {"SUSPEND", "REACTIVATE"}:
                new_status = "SUSPENDED" if action == "SUSPEND" else "ACTIVE"
                cur.execute(
                    """
                    UPDATE company
                    SET status = %s
                    WHERE company_id = %s::uuid
                    """,
                    (new_status, company_id),
                )
                conn.commit()
                flash(f"Company status updated to {new_status}.", "success")
            elif action == "DISSOLVE":
                # Dissolve only if wallet balance is 0 and company holds 0 credits.
                cur.execute(
                    """
                    SELECT COALESCE(w.balance, 0) as balance
                    FROM wallet w
                    WHERE w.company_id = %s::uuid
                    """,
                    (company_id,),
                )
                balance = cur.fetchone()
                balance_val = float(balance['balance']) if balance else 0.0

                cur.execute(
                    """
                    SELECT COALESCE(SUM(quantity_available), 0) as total
                    FROM credit_batch
                    WHERE owner_company_id = %s::uuid
                      AND status NOT IN ('EXPIRED', 'RETIRED')
                    """,
                    (company_id,),
                )
                credits_held = int(cur.fetchone()['total'])

                if balance_val != 0.0 or credits_held != 0:
                    conn.rollback()
                    flash(
                        "Cannot dissolve: company must have 0 wallet balance and 0 credits held.",
                        "error",
                    )
                else:
                    cur.execute(
                        """
                        UPDATE company
                        SET status = 'DISSOLVED'
                        WHERE company_id = %s::uuid
                        """,
                        (company_id,),
                    )
                    conn.commit()
                    flash("Company dissolved successfully.", "success")
            else:
                conn.rollback()
                flash("Invalid action.", "error")
        except Exception:
            conn.rollback()
            flash("Failed to update company due to a database error.", "error")

    cur.execute(
        """
        SELECT c.company_id, c.name, c.sector, c.country, c.status,
               COALESCE(w.balance, 0) AS balance, COALESCE(w.currency, 'USD') AS currency
        FROM company c
        LEFT JOIN wallet w ON w.company_id = c.company_id
        ORDER BY c.created_at DESC
        """
    )
    companies_rows = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("admin/companies.html", companies=companies_rows)


@admin.route("/transactions")
@admin_required
def all_transactions():
    txn_type = (request.args.get("type") or "").strip().upper()
    status = (request.args.get("status") or "").strip().upper()
    start_date = (request.args.get("start") or "").strip()
    end_date = (request.args.get("end") or "").strip()

    where = []
    params = []

    if txn_type:
        where.append("t.transaction_type = %s")
        params.append(txn_type)
    if status:
        where.append("t.status = %s")
        params.append(status)
    if start_date:
        where.append("DATE(t.timestamp) >= %s")
        params.append(start_date)
    if end_date:
        where.append("DATE(t.timestamp) <= %s")
        params.append(end_date)

    where_sql = ""
    if where:
        where_sql = "WHERE " + " AND ".join(where)

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute(
        f"""
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
        {where_sql}
        ORDER BY t.timestamp DESC
        """,
        tuple(params),
    )
    transactions = cur.fetchall()

    cur.close()
    conn.close()

    filters = {
        "type": txn_type,
        "status": status,
        "start": start_date,
        "end": end_date,
    }
    return render_template("admin/transactions.html", transactions=transactions, filters=filters)


@admin.route("/batches", methods=["GET", "POST"])
@admin_required
def batches():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    if request.method == "POST":
        batch_id = request.form.get("batch_id")
        action = (request.form.get("action") or "").strip().upper()
        try:
            if action == "MARK_EXPIRED":
                cur.execute(
                    """
                    UPDATE credit_batch
                    SET status = 'EXPIRED'
                    WHERE batch_id = %s::uuid
                      AND status NOT IN ('RETIRED')
                    """,
                    (batch_id,),
                )
                conn.commit()
                flash("Batch marked as EXPIRED.", "success")
            else:
                conn.rollback()
                flash("Invalid action.", "error")
        except Exception:
            conn.rollback()
            flash("Failed to update batch due to a database error.", "error")

    cur.execute(
        """
        SELECT cb.batch_id, p.name AS project_name, p.type AS project_type,
               r.name AS registry_name, c.name AS owner_name,
               cb.quantity_available, cb.unit_price, cb.expiry_date, cb.status
        FROM credit_batch cb
        JOIN project p ON cb.project_id = p.project_id
        JOIN registry r ON cb.registry_id = r.registry_id
        JOIN company c ON cb.owner_company_id = c.company_id
        ORDER BY cb.created_at DESC
        """
    )
    batches = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("admin/batches.html", batches=batches)


@admin.route("/issue", methods=["GET", "POST"])
@admin_required
def issue_credits():
    conn = get_db_connection()
    cur = conn.cursor()

    error = None
    success = None

    if request.method == "POST":
        project_id = request.form.get("project_id")
        registry_id = request.form.get("registry_id")
        owner_company_id = request.form.get("owner_company_id")
        quantity_raw = (request.form.get("quantity") or "").strip()
        price_raw = (request.form.get("unit_price") or "").strip()
        certification_standard = (request.form.get("certification_standard") or "").strip()
        vintage_year = request.form.get("vintage_year")
        expiry_date = request.form.get("expiry_date") or None

        try:
            quantity = int(quantity_raw)
            unit_price = float(price_raw)
            if quantity <= 0 or unit_price < 0:
                raise ValueError
        except (TypeError, ValueError):
            error = "Quantity must be > 0 and unit price must be a valid non-negative number."
        else:
            try:
                # Create new batch
                cur.execute(
                    """
                    INSERT INTO credit_batch (
                        project_id, registry_id, owner_company_id,
                        quantity, quantity_available, unit_price,
                        certification_standard, vintage_year, expiry_date, status
                    )
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, 'AVAILABLE')
                    RETURNING batch_id
                    """,
                    (
                        project_id,
                        registry_id,
                        owner_company_id,
                        quantity,
                        quantity,
                        unit_price,
                        certification_standard or None,
                        vintage_year,
                        expiry_date,
                    ),
                )
                batch_id = cur.fetchone()[0]

                # Record issuance as a system transaction.
                cur.execute(
                    """
                    INSERT INTO "transaction" (
                        buyer_id, seller_id, batch_id,
                        wallet_debit_id, wallet_credit_id,
                        quantity, price_per_unit, total_amount,
                        transaction_type, status, notes
                    )
                    VALUES (NULL, NULL, %s, NULL, NULL, %s, %s, 0, 'ISSUANCE', 'COMPLETED', 'Issued by admin')
                    RETURNING transaction_id
                    """,
                    (batch_id, quantity, unit_price),
                )
                txn_id = cur.fetchone()[0]

                cur.execute(
                    """
                    INSERT INTO ownership_history (
                        batch_id, from_company_id, to_company_id,
                        transaction_id, quantity
                    )
                    VALUES (%s, NULL, %s::uuid, %s, %s)
                    """,
                    (batch_id, owner_company_id, txn_id, quantity),
                )

                conn.commit()
                success = "New credit batch issued successfully."
            except Exception:
                conn.rollback()
                error = "Failed to issue credits due to a database error."

    # Dropdown data for the issue form
    cur.execute("SELECT project_id, name FROM project ORDER BY name;")
    projects = cur.fetchall()
    cur.execute("SELECT registry_id, name FROM registry ORDER BY name;")
    registries = cur.fetchall()
    cur.execute("SELECT company_id, name FROM company WHERE status != 'DISSOLVED' ORDER BY name;")
    companies = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "admin/issue.html",
        projects=projects,
        registries=registries,
        companies=companies,
        error=error,
        success=success,
    )


@admin.route("/reports")
@admin_required
def reports():
    conn = get_db_connection()
    cur = conn.cursor()

    # Credits traded per company (as buyer or seller) by quantity
    cur.execute(
        """
        SELECT c.name, COALESCE(SUM(t.quantity), 0) AS total_qty
        FROM company c
        LEFT JOIN "transaction" t
          ON (t.buyer_id = c.company_id OR t.seller_id = c.company_id)
         AND t.status = 'COMPLETED'
         AND t.transaction_type IN ('BUY', 'SELL', 'TRANSFER')
        GROUP BY c.name
        ORDER BY total_qty DESC
        """
    )
    traded_per_company = cur.fetchall()

    # Average price per project type
    cur.execute(
        """
        SELECT p.type, COALESCE(AVG(cb.unit_price), 0) AS avg_price
        FROM project p
        JOIN credit_batch cb ON cb.project_id = p.project_id
        GROUP BY p.type
        ORDER BY p.type
        """
    )
    avg_price_by_type = cur.fetchall()

    # Most active traders (count of completed trades)
    cur.execute(
        """
        SELECT c.name, COUNT(t.transaction_id) AS txn_count
        FROM company c
        LEFT JOIN "transaction" t
          ON (t.buyer_id = c.company_id OR t.seller_id = c.company_id)
         AND t.status = 'COMPLETED'
        GROUP BY c.name
        ORDER BY txn_count DESC
        """
    )
    most_active = cur.fetchall()

    # Credits expiring within 30 days
    cur.execute(
        """
        SELECT cb.batch_id, c.name, p.name, cb.quantity_available, cb.expiry_date, cb.status
        FROM credit_batch cb
        JOIN company c ON cb.owner_company_id = c.company_id
        JOIN project p ON cb.project_id = p.project_id
        WHERE cb.expiry_date IS NOT NULL
          AND cb.expiry_date < (CURRENT_DATE + INTERVAL '30 days')
          AND cb.status IN ('AVAILABLE', 'PARTIALLY_SOLD')
        ORDER BY cb.expiry_date ASC
        """
    )
    expiring_soon = cur.fetchall()

    # Credits retired per company with reason breakdown
    cur.execute(
        """
        SELECT c.name, rr.retirement_reason, COALESCE(SUM(rr.quantity_retired), 0) AS qty
        FROM retirement_record rr
        JOIN company c ON rr.company_id = c.company_id
        GROUP BY c.name, rr.retirement_reason
        ORDER BY c.name, rr.retirement_reason
        """
    )
    retired_breakdown = cur.fetchall()

    cur.close()
    conn.close()

    data = {
        "traded_per_company": traded_per_company,
        "avg_price_by_type": avg_price_by_type,
        "most_active": most_active,
        "expiring_soon": expiring_soon,
        "retired_breakdown": retired_breakdown,
    }
    return render_template("admin/reports.html", data=data)

