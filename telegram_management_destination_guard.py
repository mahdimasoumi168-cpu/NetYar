"""Resolve the management destination automatically for partner chat."""
import os
import logging
from telegram.ext import MessageHandler, ApplicationHandlerStop, filters
log=logging.getLogger("netyar.telegram.management_destination_guard")

def _admin_ids(B):
    ids=[]
    for source in (getattr(B,"ADM",set()), os.getenv("ADMIN_IDS","").replace(";",",")):
        vals=source if isinstance(source,(set,list,tuple)) else str(source).split(",")
        for v in vals:
            s=str(v).strip()
            if s.lstrip("-").isdigit() and int(s)!=0: ids.append(int(s))
    out=[]
    for x in ids:
        if x not in out:out.append(x)
    return out

def _resolve(B,uid):
    st=B.S.setdefault(uid,{})
    admin=st.get("final_chat_admin") or st.get("management_chat_id")
    if str(admin).lstrip("-").isdigit():return int(admin)
    ids=_admin_ids(B)
    if ids:
        st["final_chat_admin"]=ids[0]
        st["management_chat_id"]=ids[0]
        return ids[0]
    return None

def install(app,B):
    if getattr(B,"_management_destination_guard",False):return True
    async def relay(update,context):
        msg=getattr(update,"effective_message",None);user=getattr(update,"effective_user",None)
        if not msg or not user or not getattr(msg,"text",None):return
        uid=user.id;st=B.S.setdefault(uid,{})
        if st.get("mode")!="final_partner_chat":return
        admin=_resolve(B,uid)
        if not admin:
            await msg.reply_text("❌ مقصد مدیریت هنوز در تنظیمات ربات تعریف نشده است.")
            raise ApplicationHandlerStop
        try:
            await context.bot.send_message(chat_id=admin,text=f"👥 همکار:\n{msg.text.strip()}")
            await msg.reply_text("✅ پیام برای مدیریت ارسال شد.",reply_markup=B.partner_kb())
        except Exception:
            log.exception("management relay failed")
            await msg.reply_text("❌ ارسال پیام به مدیریت انجام نشد؛ لطفاً دوباره تلاش کنید.",reply_markup=B.partner_kb())
        raise ApplicationHandlerStop
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,relay),group=-59997)
    B._management_destination_guard=True
    return True
