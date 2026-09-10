"""Compatibility bridge between the Rubika flow and the unified core DB API."""

def install():
    import core
    db = core.db
    if getattr(db, "_netyar_rubika_core_compat", False):
        return

    def get_balance(owner):
        value = str(owner or "").strip()
        row = db.conn.execute(
            "SELECT balance FROM partners WHERE phone=? AND active=1", (value,)
        ).fetchone()
        return int(row["balance"]) if row else 0

    def create_topup(owner, amount, file_id=""):
        row = db.partner(owner)
        if not row:
            return None
        return db.add_topup(row["id"], int(amount), file_id)

    def get_request(code):
        row = db.conn.execute(
            "SELECT tracking_code AS code,status,amount,payment_status,payment_method,created_at,updated_at "
            "FROM requests WHERE tracking_code=?", (str(code or "").strip(),)
        ).fetchone()
        return dict(row) if row else None

    original_create_request = db.create_request

    def create_request_compat(user_id, service_key, platform, amount, file_id=""):
        result = original_create_request(user_id, service_key, platform, amount)
        if not file_id:
            return result
        request_id, code = result
        db.answer(request_id, "file", file_id=file_id)
        db.conn.commit()
        return code

    db.get_balance = get_balance
    db.create_topup = create_topup
    db.get_request = get_request
    db.create_request = create_request_compat
    db._netyar_rubika_core_compat = True
