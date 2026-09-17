"""Final Telegram admin button/entry repair.

The management button is visible and actionable only for configured admins.
"""
import os
import re
from telegram.ext import MessageHandler, filters, ApplicationHandlerStop

LABEL = "🛠 پنل مدیریت بات"
LABELS = {LABEL, "🛠 پنل مدیریت", "پنل مدیریت بات", "پنل مدیریت"}


def _configured_admin(uid):
    sid = str(uid)
    raw = []
    for key in ("ADMIN_IDS", "ADMIN_ID_1", "ADMIN_ID_2", "TELEGRAM_ADMIN_IDS"):
        raw.append(os.getenv(key, ""))
    ids = set()
    for value in raw:
        ids.update(x.strip() for x in re.split(r"[;,\s]+", value) if x.strip())
    return sid in ids


def _is_admin(B, uid):
    # Environment IDs are authoritative; B.admin is retained as a secondary
    # compatibility check for existing database/admin state.
    if _configured_admin(uid):
        return True
    try:
        return bool(B.admin(uid))
    except Exception:
        return False


def install(app, B):
    if getattr(B, "_admin_button_final_v2", False):
        return

    old_main = getattr(B, "main", None)
    if callable(old_main):
        def main(uid):
            kb = old_main(uid)
            try:
                if not _is_admin(B, uid):
                    return kb
                rows = [list(r) for r in kb.keyboard]
                # Remove any accidental management button from non-admin or
                # duplicate rendering paths, then add exactly one for admins.
                rows = [
                    [x for x in row if str(x) not in LABELS]
                    for row in rows
                ]
                rows = [row for row in rows if row]
                rows.insert(max(0, len(rows) - 2), [LABEL])
                from telegram import ReplyKeyboardMarkup
                return ReplyKeyboardMarkup(rows, resize_keyboard=True)
            except Exception:
                return kb
        B.main = main

    async def handler(update, context):
        m = update.effective_message
        u = update.effective_user
        if not m or not u:
            return
        if (m.text or "").strip() not in LABELS:
            return
        if not _is_admin(B, u.id):
            # Never expose or open the management panel for ordinary users.
            raise ApplicationHandlerStop
        try:
            import telegram_admin_plus as A
            menu = A._admin_menu()
        except Exception:
            menu = None
        await m.reply_text(
            "🛠 پنل مدیریت کامل\n\nاز منوی زیر بخش موردنظر را انتخاب کنید:",
            reply_markup=menu,
        )
        raise ApplicationHandlerStop

    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handler),
        group=-30000,
    )
    B._admin_button_final_v2 = True
