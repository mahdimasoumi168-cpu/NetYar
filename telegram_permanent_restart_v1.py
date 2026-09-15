"""Permanent Telegram restart button."""
from telegram import ReplyKeyboardMarkup
from telegram.ext import MessageHandler, filters, ApplicationHandlerStop
RESTART="🔄 شروع مجدد"

def _keyboard():
    return ReplyKeyboardMarkup([[RESTART]],resize_keyboard=True,one_time_keyboard=False,is_persistent=True)

def _clear_flow(st):
    keep={k:st[k] for k in ("partner_id","partner_active","partner_phone","partner_username","lang","status") if k in st}
    st.clear();st.update(keep);st["mode"]=None

def install(app,B):
    if getattr(B,"_permanent_restart_v1",False): return
    B.restart_keyboard=_keyboard
    old_start=B.start
    async def wrapped_start(update,context):
        result=await old_start(update,context)
        try: await update.effective_message.reply_text("🔄 دکمه شروع مجدد همیشه در دسترس است.",reply_markup=_keyboard())
        except Exception: pass
        return result
    B.start=wrapped_start
    async def restart(update,context):
        if not update.message:return
        if (update.message.text or "").strip() not in {RESTART,"شروع مجدد"}:return
        st=B.S.setdefault(update.effective_user.id,{})
        _clear_flow(st)
        try: await B.start(update,context)
        except Exception:
            try: await update.effective_message.reply_text("❌ شروع مجدد انجام نشد. دوباره تلاش کنید.",reply_markup=_keyboard())
            except Exception: pass
        raise ApplicationHandlerStop
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,restart),group=-2000001)
    B._permanent_restart_v1=True
