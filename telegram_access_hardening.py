"""Central access/UI hardening for Telegram.

Rules:
- Only registered active partners see the partner-panel entry.
- Admins are never blocked by business hours.
- Selected night-shift partners are allowed outside normal hours.
- Start/restart remains usable for admins/night partners while closed.
- Admin panel exposes the existing two-way ticket chat.
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
            return row
    except Exception:
        pass
    phone = str(st.get("phone") or "").strip()
    if phone:
        return B.db.conn.execute("SELECT id FROM partners WHERE phone=? AND active=1 LIMIT 1", (phone,)).fetchone()
    return None


def partner_allowed(B, uid):
    return bool(_partner_for_uid(B, uid))


def _night_allowed(B, uid):
    try:
        from telegram_night_shift_v2 import allowed
        return bool(allowed(B, uid))
    except Exception:
        return bool(B.admin(uid)) or partner_allowed(B, uid)


def _filter_markup(markup, allow_partner):
    if not markup or not hasattr(markup, "keyboard"):
        return markup
    rows = []
    for row in markup.keyboard:
        nr = []
        for button in row:
            text = getattr(button, "text", "")
            if text in PARTNER_LABELS and not allow_partner:
                continue
            nr.append(button)
        if nr:
            rows.append(nr)
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, one_time_keyboard=False, is_persistent=True)


def _with_partner_and_restart(markup, allow_partner):
    if not isinstance(markup, ReplyKeyboardMarkup):
        return markup
    rows = [list(r) for r in markup.keyboard]
    # Remove stale/duplicate partner entries first.
    cleaned = []
    for row in rows:
        nr = [b for b in row if getattr(b, "text", "") not in PARTNER_LABELS]
        if nr:
            cleaned.append(nr)
    if allow_partner:
        # Put the partner panel immediately before the restart row.
        idx = next((i for i, r in enumerate(cleaned) if any(getattr(b, "text", "") in RESTART_LABELS for b in r)), len(cleaned))
        cleaned.insert(idx, ["👥 پنل همکاران"])
    return ReplyKeyboardMarkup(cleaned, resize_keyboard=True, one_time_keyboard=False, is_persistent=True)


def install(app, B):
    if getattr(B, "_access_hardening", False):
        return

    # Ensure the common night-worker table exists even after a clean DB bootstrap.
    B.db.conn.execute(
        "CREATE TABLE IF NOT EXISTS night_workers(partner_id INTEGER PRIMARY KEY, enabled INTEGER NOT NULL DEFAULT 1, updated_at TEXT NOT NULL)"
    )
    B.db.conn.commit()

    old_main = B.main
    def main(uid):
        allow = partner_allowed(B, uid)
        return _with_partner_and_restart(old_main(uid), allow)
    B.main = main

    old_start = B.start
    async def start(update, context):
        result = await old_start(update, context)
        uid = update.effective_user.id
        allow = partner_allowed(B, uid)
        # The canonical start handler sends language buttons. Add the persistent
        # navigation keyboard without exposing the partner panel to unregistered users.
        try:
            await update.effective_message.reply_text(
                "🔄 شروع مجدد آماده است." + ("\n👥 پنل همکاران برای حساب شما فعال است." if allow else ""),
                reply_markup=_with_partner_and_restart(None, allow) if False else ReplyKeyboardMarkup(
                    [["👥 پنل همکاران"], ["🔄 شروع مجدد"]] if allow else [["🔄 شروع مجدد"]],
                    resize_keyboard=True, one_time_keyboard=False, is_persistent=True,
                ),
            )
        except Exception:
            pass
        return result
    B.start = start

    # Add ticket access to the current admin menu without replacing the existing menu.
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
