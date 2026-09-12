"""Admin editor for bot option labels and user-facing texts."""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, MessageHandler, filters

OPTION_KEYS={"ir_gov":"🏛 حل مشکل ورود اتباع دولت من","ir_track":"🎫 پیگیری","ir_wallet":"💰 کیف پول من","contact":"📞 تماس با ما","complaint":"📝 ثبت شکایت","partner":"🔵 👥 پنل همکاران"}
TEXT_KEYS={"welcome":"👋 متن خوش‌آمدگویی","iranian":"🇮🇷 متن منوی ایرانی","complaint_prompt":"📝 متن درخواست شکایت","complaint_ok":"✅ متن موفقیت شکایت","contact":"📞 متن تماس با ما"}

def _kb(rows): return InlineKeyboardMarkup([[InlineKeyboardButton(t,callback_data=d) for t,d in row] for row in rows])
def _get(B,key,default):
    try:return B.db.setting("ui_text_"+key,default) or default
    except Exception:return default

def install(app,B):
    if getattr(B,"_editable_texts_installed",False): return
    import telegram_admin_plus as A
    old=A._admin_menu
    def menu():
        rows=[[ (b.text,b.callback_data) for b in row] for row in old().inline_keyboard]
        rows.insert(-1,[("✏️ متن گزینه‌ها","adm:ui_options"),("🤖 متن‌های ربات","adm:ui_texts")])
        return _kb(rows)
    async def cb(update,context):
        q=update.callback_query
        if not B.admin(q.from_user.id): return
        await q.answer();st=B.S.setdefault(q.from_user.id,{}) ;a=q.data
        if a=="adm:ui_options":
            return await q.message.reply_text("✏️ ویرایش متن گزینه‌ها",reply_markup=_kb([[(v,"adm:editopt:"+k)] for k,v in OPTION_KEYS.items()]+[[('⬅️ پنل مدیریت','adm:menu')]]))
        if a=="adm:ui_texts":
            return await q.message.reply_text("🤖 ویرایش متن‌های ربات",reply_markup=_kb([[(v,"adm:edittext:"+k)] for k,v in TEXT_KEYS.items()]+[[('⬅️ پنل مدیریت','adm:menu')]]))
        if a.startswith("adm:editopt:") or a.startswith("adm:edittext:"):
            mode="option" if a.startswith("adm:editopt:") else "text";key=a.split(":",2)[2]
            st.update({"editable_mode":mode,"editable_key":key})
            default=(OPTION_KEYS if mode=="option" else TEXT_KEYS).get(key,key)
            return await q.message.reply_text(f"✏️ متن جدید را ارسال کنید:\n\nمتن فعلی:\n{_get(B,key,default)}")
    async def text(update,context):
        st=B.S.setdefault(update.effective_user.id,{})
        if not B.admin(update.effective_user.id) or not st.get("editable_mode"): return
        v=(update.message.text or "").strip()
        if not v:return
        B.db.set_setting("ui_text_"+st["editable_key"],v);st.pop("editable_mode",None);st.pop("editable_key",None)
        return await update.message.reply_text("✅ متن با موفقیت ذخیره شد.",reply_markup=menu())
    app.add_handler(CallbackQueryHandler(cb,pattern=r"^adm:(ui_options|ui_texts|editopt:|edittext:)"),group=-30)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,text),group=-30)
    B._editable_texts_installed=True
