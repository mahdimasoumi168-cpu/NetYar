"""Telegram broadcast media support for the canonical admin announcement flow."""
import logging
from telegram.ext import MessageHandler, filters

log = logging.getLogger("netyar.telegram.announcement_media")


async def _photo(update, context, B):
    msg = update.effective_message
    uid = update.effective_user.id if update.effective_user else None
    if not msg or not uid or not B.admin(uid):
        return
    st = B.S.setdefault(uid, {"admin": True})
    if st.get("admin_plus_mode") != "announce":
        return

    photo = msg.photo[-1] if msg.photo else None
    if not photo:
        return await msg.reply_text("❌ تصویر دریافت نشد. دوباره ارسال کنید.")

    caption = (msg.caption or "").strip()
    rows = B.db.conn.execute(
        "SELECT external_id FROM users WHERE platform='telegram' AND external_id IS NOT NULL"
    ).fetchall()
    ok = fail = 0
    for row in rows:
        try:
            await context.bot.send_photo(
                chat_id=int(row["external_id"]),
                photo=photo.file_id,
                caption=caption or None,
            )
            ok += 1
        except Exception:
            fail += 1
            log.exception("announcement photo failed for %s", row["external_id"])

    st["admin_plus_mode"] = None
    return await msg.reply_text(
        f"📣 اعلان تصویری ارسال شد.\n\n✅ موفق: {ok}\n❌ ناموفق: {fail}",
        reply_markup=B.amenu() if hasattr(B, "amenu") else None,
    )


def install(app, B):
    if getattr(B, "_announcement_media_installed", False):
        return
    app.add_handler(MessageHandler(filters.PHOTO, lambda u, c: _photo(u, c, B)), group=-21)
    B._announcement_media_installed = True
    log.info("Telegram announcement photo support installed")

    # Canonical final repair is loaded from an already-installed feature hook,
    # so it runs in the real Telegram runtime without adding another giant
    # layer stack to entrypoint.py.
    try:
        import telegram_final_runtime_repair_v1 as repair
        repair.install(app, B)
        log.info("FINAL RUNTIME REPAIR v1 installed")
    except Exception:
        log.exception("FINAL RUNTIME REPAIR v1 unavailable")
