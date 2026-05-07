def process_buy_transaction(conn, session, batch_id, quantity):
    cur = conn.cursor()

    # Fetch batch
    cur.execute("""
        SELECT cb.batch_id, cb.owner_company_id, cb.quantity_available,
               cb.unit_price, w.wallet_id, w.balance
        FROM credit_batch cb
        JOIN wallet w ON w.company_id = cb.owner_company_id
        WHERE cb.batch_id = %s
        AND cb.status IN ('AVAILABLE', 'PARTIALLY_SOLD')
        AND cb.quantity_available >= %s
    """, (batch_id, quantity))

    batch = cur.fetchone()

    if not batch:
        return None, 'Batch not available or insufficient quantity.'

    seller_company_id = str(batch[1])

    if seller_company_id == session['company_id']:
        return None, 'You cannot buy your own credits.'

    total = quantity * float(batch[3])

    # Buyer wallet
    cur.execute("""
        SELECT wallet_id, balance 
        FROM wallet 
        WHERE company_id = %s
    """, (session['company_id'],))

    buyer_wallet = cur.fetchone()

    if float(buyer_wallet[1]) < total:
        return None, 'Insufficient wallet balance.'

    try:
        # Create transaction
        cur.execute("""
            INSERT INTO "transaction" (
                buyer_id, seller_id, batch_id,
                wallet_debit_id, wallet_credit_id,
                quantity, price_per_unit, total_amount,
                transaction_type, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'BUY', 'COMPLETED')
            RETURNING transaction_id
        """, (
            session['company_id'], seller_company_id, batch_id,
            buyer_wallet[0], batch[4],
            quantity, batch[3], total
        ))

        txn_id = cur.fetchone()[0]

        # Update wallets
        cur.execute("""
            UPDATE wallet SET balance = balance - %s WHERE wallet_id = %s
        """, (total, buyer_wallet[0]))

        cur.execute("""
            UPDATE wallet SET balance = balance + %s WHERE wallet_id = %s
        """, (total, batch[4]))

        # Update batch
        new_qty = batch[2] - quantity
        new_status = 'SOLD_OUT' if new_qty == 0 else 'PARTIALLY_SOLD'

        cur.execute("""
            UPDATE credit_batch
            SET quantity_available = %s, owner_company_id = %s, status = %s
            WHERE batch_id = %s
        """, (new_qty, session['company_id'], new_status, batch_id))

        # Ownership history
        cur.execute("""
            INSERT INTO ownership_history (
                batch_id, from_company_id, to_company_id,
                transaction_id, quantity
            ) VALUES (%s, %s, %s, %s, %s)
        """, (
            batch_id, seller_company_id,
            session['company_id'], txn_id, quantity
        ))

        conn.commit()
        return True, f"Purchased {quantity} credits for ${total:.2f}"

    except Exception as e:
        conn.rollback()
        return None, str(e)