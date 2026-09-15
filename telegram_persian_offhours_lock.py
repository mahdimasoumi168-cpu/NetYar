"""Final Persian-only and strict working-hours gate.

Rules:
- The bot UI is Persian only; language selection is disabled.
- Outside configured working hours, Telegram interactions are rejected.
- The off-hours gate is deliberately fail-closed: malformed hours block access.
"""
from datetime import datetime, time
from zoneinfo import ZoneInfo
from telegram.ext import MessageHandler, CallbackQueryHandler, ApplicationHandlerStop, filters

TZ = ZoneInfo("Asia/Tehran")
DEFAULT_OPEN = "07:00"
DEFAULT_CLOSE = "19:00"


def _setting(B, key, default):
    try:
        return str(B.db.setting(key, default) or default)
    except Exception:
        return default


def _open_now(B):
    """Return True only when current Tehran time is inside a valid interval."""
    try:
        op = time.fromisoformat(_setting(B, "work_open", DEFAULT_OPEN))
        cl = time.fromisoformat(_setting(B, "work_close", DEFAULT_CLOSE))
        if op == cl:
            return False
        now = datetime.now(TZ).time()
        return op <= now < cl if op < cl else (now >= op or now < cl)
    except Exception:
        # Fail closed: a broken/missing schedule must never open the bot.
        return False


def install(app, B):
    if getattr(B, "_persian_offhours_lock_installed", False):
        return

    # Force the persisted in-memory language state to Persian whenever a user
    # interacts with the bot. Existing handlers therefore resolve Persian text.
    old_start = getattr(B, "start", None)
    if callable(old_start):
        async def persian_start(update, context):
            uid = update.effective_user.id
            st = B.S.setdefault(uid, {})
            st["lang"] = "fa"
            return await old_start(update, context)
        B.start = persian_start

    async def gate(update, context):
        user = getattr(update, "effective_user", None)
        if user:
            st = B.S.setdefault(user.id, {})
            st["lang"] = "fa"

        # Stale/old language buttons can never change the bot language.
        q = getattr(update, "callback_query", None)
        if q and str(q.data or "").startswith("lang:"):
            await q.answer("زبان ربات فقط فارسی است.", show_alert=False)
            await q.message.reply_text("🇮🇷 زبان ربات فارسی است و تغییر زبان فعال نیست.")
            raise ApplicationHandlerStop

        if _open_now(B):
            return

        if q:
            try:
                await q.answer("⏰ ربات در حال حاضر خارج از ساعت کاری است.", show_alert=True)
            except Exception:
                pass
            if q.message:
                await q.message.reply_text(
                    "⏰ ساعت کاری ربات به پایان رسیده است.\n"
                    "🕐 ساعت کاری: ۰۷:۰۰ تا ۱۹:۰۰\n\n"
                    "لطفاً در ساعت کاری دوباره مراجعه کنید."
                )
        elif getattr(update, "message", None):
            await update.message.reply_text(
                "⏰ ربات در حال حاضر خارج از ساعت کاری است.\n"
                "🕐 ساعت کاری: ۰۷:۰۰ تا ۱۹:۰۰\n\n"
                "لطفاً در ساعت کاری دوباره مراجعه کنید."
            )
        raise ApplicationHandlerStop

    # Very early groups make this the final access gate regardless of legacy
    # routing layers installed later in the project history.
    app.add_handler(MessageHandler(filters.ALL, gate), group=-100000)
    app.add_handler(CallbackQueryHandler(gate), group=-99999)
    B._persian_offhours_lock_installed = True
