"""Direct Telegram admin-to-partner communication.
The canonical admin menu owns the visible button; this module owns only the
callback and message conversation, so it never replaces admin keyboards.
"""
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationHandlerStop, MessageHandler, CallbackQueryHandler, filters
log=logging.getLogger("netyar.telegram.admin_partner_chat")
BUTTON="💬 ارتباط با همکار"

def _partners(B):
    return B.db.conn.execute("SELECT id,name,phone,active FROM partners ORDER BY active DESC,id DESC LIMIT 100").fetchall()

async def _show_partners(update,B):
    q=update.callback_query
    rows=_partners(B)
    if not rows:
        await q.message.reply_text("👥 هیچ همکاری در پنل ثبت نشده است.",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ پنل مدیریت",callback_data="adm:menu")]]))
        return
    buttons=[[InlineKeyboardButton(f"{'🟢' if p['active'] else '🔴'} {(p['name'] or 'بدون نام').strip()} | {(p['phone'] or '-').strip()}",callback_data=f"adminpartner:select:{int(p['id'])}")] for p in rows]
    buttons.append([InlineKeyboardButton("⬅️ پنل مدیریت",callback_data="adm:menu")])
    await q.message.reply_text("💬 ارتباط با همکار\n\nهمکار موردنظر را انتخاب کنید:",reply_markup=InlineKeyboardMarkup(buttons))

async def _select_partner(update,B,pid):
    q=update.callback_query; uid=q.from_user.id
    if not B.admin(uid):
        await q.message.reply_text("❌ دسترسی مدیریت ندارید."); return
    p=B.db.conn.execute("SELECT id,name,phone,active FROM partners WHERE id=?",(pid,)).fetchone()
    if not p:
        await q.message.reply_text("❌ همکار پیدا نشد."); return
    chat_value=B.db.setting(f"partner_chat_{pid}","").strip()
    if not chat_value and p["phone"]:
        chat_value=B.db.setting(f"partner_chat_{p['phone']}","").strip()
    if not chat_value:
        await q.message.reply_text("❌ ارتباط این همکار هنوز ثبت نشده است.\n\nاز همکار بخواهید یک‌بار وارد «پنل همکاران» شود تا ارتباط او ثبت شود.",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ پنل مدیریت",callback_data="adm:menu")]])); return
    try:int(chat_value)
    except Exception:
        await q.message.reply_text("❌ شناسه چت همکار نامعتبر است."); return
    st=B.S.setdefault(uid,{})
    st["mode"]="ticket_admin_reply"; st["ticket_partner_id"]=pid
    B.db.set_setting(f"partner_chat_{pid}",str(chat_value)); B.db.set_setting(f"ticket_admin_{pid}",str(uid))
    await q.message.reply_text(f"💬 ارتباط با همکار فعال شد.\n\n👤 همکار: {(p['name'] or 'بدون نام').strip()}\n📱 موبایل: {(p['phone'] or '-').strip()}\n\nحالا پیام خود را بفرستید.\n📝 متن، 🖼 عکس، 🎥 ویدیو، 🎤 ویس یا 📎 فایل قابل ارسال است.")

async def _callback(update,context,B):
    q=update.callback_query; data=str(q.data or "") if q else ""
    if not data.startswith("adminpartner:"): return
    await q.answer()
    if not B.admin(q.from_user.id):
        await q.message.reply_text("❌ دسترسی مدیریت ندارید."); raise ApplicationHandlerStop
    try:
        if data=="adminpartner:list": await _show_partners(update,B)
        elif data=="adminpartner:close": await q.message.reply_text("✅ بخش ارتباط با همکار بسته شد.",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ پنل مدیریت",callback_data="adm:menu")]]))
        elif data.startswith("adminpartner:select:"): await _select_partner(update,B,int(data.rsplit(":",1)[1]))
    except Exception:
        log.exception("admin partner chat callback failed")
        await q.message.reply_text("❌ انجام عملیات ارتباط با همکار ناموفق بود.")
    raise ApplicationHandlerStop

async def _reply_text(update,context,B):
    m=update.effective_message; u=update.effective_user
    if not m or not u or not B.admin(u.id): return
    st=B.S.setdefault(u.id,{})
    if st.get("mode")!="ticket_admin_reply": return
    text=(m.text or "").strip()
    if text in {"❌ انصراف","لغو","انصراف"}:
        st["mode"]=None; st.pop("ticket_partner_id",None)
        await m.reply_text("❌ گفت‌وگو بسته شد.",reply_markup=B.amenu())
        raise ApplicationHandlerStop
    pid=st.get("ticket_partner_id")
    try:
        chat_id=int(B.db.setting(f"partner_chat_{pid}","") or 0)
    except Exception:
        chat_id=0
    if not chat_id:
        await m.reply_text("❌ ارتباط با همکار پیدا نشد.",reply_markup=B.amenu())
        raise ApplicationHandlerStop
    await context.bot.send_message(chat_id=chat_id,text=f"👔 پیام مدیریت\n\n{text}",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ پاسخ پیام",callback_data=f"ticket:reply:{pid}")]]))
    B.db.set_setting(f"ticket_admin_{pid}",str(u.id))
    st["mode"]=None; st.pop("ticket_partner_id",None)
    await m.reply_text("✅ پیام برای همکار ارسال شد.",reply_markup=B.amenu())
    raise ApplicationHandlerStop

async def _entry(update,context,B):
    m=update.effective_message; u=update.effective_user
    if not m or not u or not B.admin(u.id) or (m.text or "").strip()!=BUTTON: return
    await m.reply_text("💬 برای شروع ارتباط، همکار موردنظر را انتخاب کنید:",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("👥 انتخاب همکار",callback_data="adminpartner:list")]]))
    raise ApplicationHandlerStop

def install(app,B):
    if getattr(B,"_admin_partner_chat_v2",False): return
    app.add_handler(CallbackQueryHandler(lambda u,c:_callback(u,c,B),pattern=r"^adminpartner:"),group=-110)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,lambda u,c:_reply_text(u,c,B)),group=-110)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,lambda u,c:_entry(u,c,B)),group=-109)
    try:
        import telegram_ticket_media as TM
        TM.install(app,B)
    except Exception:
        log.exception("ticket media owner unavailable")
    B._admin_partner_chat_v2=True
