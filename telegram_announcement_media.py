"""Canonical Telegram broadcast owner.
When the admin chooses «📣 اعلان همگانی», the next message of any supported
Telegram type is copied to every registered Telegram user.
"""
import logging
from telegram.ext import MessageHandler, filters, ApplicationHandlerStop
log=logging.getLogger("netyar.telegram.announcement")

async def _broadcast(update,context,B):
    msg=update.effective_message
    uid=update.effective_user.id if update.effective_user else None
    if not msg or not uid or not B.admin(uid): return
    st=B.S.setdefault(uid,{})
    if st.get("admin_plus_mode")!="announce": return
    rows=B.db.conn.execute("SELECT external_id FROM users WHERE platform='telegram' AND external_id IS NOT NULL").fetchall()
    ok=fail=0
    for row in rows:
        try:
            await context.bot.copy_message(chat_id=int(row["external_id"]),from_chat_id=msg.chat_id,message_id=msg.message_id)
            ok+=1
        except Exception:
            fail+=1
            log.exception("broadcast failed for %s",row["external_id"])
    st["admin_plus_mode"]=None
    await msg.reply_text(f"📣 اعلان همگانی ارسال شد.\n\n✅ موفق: {ok}\n❌ ناموفق: {fail}",reply_markup=B.amenu() if hasattr(B,"amenu") else None)
    raise ApplicationHandlerStop

def install(app,B):
    if getattr(B,"_announcement_media_installed_v2",False): return
    app.add_handler(MessageHandler(filters.ALL,_broadcast),group=-21)
    B._announcement_media_installed_v2=True
    log.info("Canonical all-media broadcast support installed")
