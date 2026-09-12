"""Central Telegram access/UI hardening.

The canonical UI layer owns the single persistent restart keyboard. This layer
only enforces access rules and keeps the management ticket entry visible.
"""
from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton

PARTNER_LABELS = {"👥 پنل همکاران", "🔵 👥 پنل همکاران", "پنل همکاران"}
RESTART_LABELS = {"🔄 شروع مجدد", "شروع مجدد"}


def _partner_for_uid(B, uid):
    st = B.S.get(uid, {})
    pid = st.get("partner_id")
    if pid:
        row = B.db.conn.execute("SELECT id FROM partners WHERE id=? AND active=1", (pid,)).fetchone()
        if row:
            return row
    try:
        row = B.db.conn.execute(
            "SELECT p.id FROM partners p JOIN partner_telegram_links l ON l.partner_id=p.id "
            "WHERE l.telegram_user_id=? AND p.active=1 LIMIT 1", (str(uid),)
        ).fetchone()
        if row:
            st["partner_id"] = row["id"]
            st["partner_active"] = 1
            return row
    except Exception:
        pass
    phone = str(st.get("phone") or "").strip()
    if phone:
        row = B.db.conn.execute("SELECT id FROM partners WHERE phone=? AND active=1 LIMIT 1", (phone,)).fetchone()
        if row:
            st["partner_id"] = row["id"]
            st["partner_active"] = 1
        return row
    return None


def partner_allowed(B, uid):
    return bool(_partner_for_uid(B, uid))


def _night_allowed(B, uid):
    try:
        from telegram_night_shift_v2 import allowed
        return bool(allowed(B, uid))
    except Exception:
        return bool(B.admin(uid)) or partner_allowed(B, uid)


def _restart_only_keyboard():
    return ReplyKeyboardMarkup([["🔄 شروع مجدد"]], resize_keyboard=True, one_time_keyboard=False, is_persistent=True)


def install(app, B):
    if getattr(B, "_access_hardening", False):
        return
    B.db.conn.execute(
        "CREATE TABLE IF NOT EXISTS night_workers(partner_id INTEGER PRIMARY KEY, enabled INTEGER NOT NULL DEFAULT 1, updated_at TEXT NOT NULL)"
    )
    B.db.conn.commit()

    # Do not wrap B.start here. telegram_ui_policy_v2 owns the single restart
    # keyboard and wrapping start in multiple layers caused duplicate messages.
    old_main = B.main
    B.main = lambda uid: old_main(uid)

    try:
        import telegram_admin_plus as A
        old_admin_menu = A._admin_menu
        def admin_menu():
            m = old_admin_menu()
            rows = [list(r) for r in m.inline_keyboard]
            if not any(any(getattr(b, "callback_data", "") == "tk:partners" for b in r) for r in rows):
                rows.insert(max(0, len(rows) - 1), [InlineKeyboardButton("🎫 تیکت‌ها و چت همکاران", callback_data="tk:partners")])
            return InlineKeyboardMarkup(rows)
        A._admin_menu = admin_menu
    except Exception:
        pass
    B._access_hardening = True
