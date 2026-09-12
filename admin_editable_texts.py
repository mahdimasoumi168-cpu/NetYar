"""Admin editor for bot option labels and user-facing texts."""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, MessageHandler, filters

OPTION_KEYS={
    "ir_gov":"🏛 حل مشکل ورود اتباع دولت من",
    "ir_track":"🎫 پیگیری",
    "ir_wallet":"💰 کیف پول من",
    "contact":"📞 تماس با ما",
    "complaint":"📝 ثبت شکایت",
    "partner":"🔵 👥 پنل همکاران",
}
TEXT_KEYS={
    "welcome":"👋 متن خوش‌آمدگویی",
    "iranian":"🇮🇷 متن منوی ایرانی",
    "complaint_prompt":"📝 متن درخواست شکایت",
    "complaint_ok":"✅ متن موفقیت شکایت",
    "contact":"📞 متن تماس با ما",
}


def _kb(rows):
    return InlineKeyboardMarkup([[InlineKeyboardButton(t,callback_data=d) for t,d in row] for row in rows])

def _get(B,key,default):
    try:return B.db.setting("ui_text_"+key,default) or default
    except Exception:return default

def install(app,B):
    if getattr(B,"_editable_texts_installed",False):return
    import telegram_admin_plus as A
    old_menu=A._admin_menu
    def admin_menu_extended():
        base=old_menu().inline_keyboard
        rows=[[InlineKeyboardButton(x.text,callback_data=x.callback_data) for x in row] for row in base]
        rows.insert(-1,[InlineKeyboardButton("✏️ متن گزینه‌ها",callback_data="adm:ui_options"),InlineKeyboardButton("🤖 متن‌های ربات",callback_data="adm:ui_texts")])
        return InlineKeyboardMarkup(rows)
    A._admin_menu=admin_menu_extended

    async def cb(update,context):
        q=update.callback_query
        if not B.admin(q.from_user.id):return
        await q.answer();uid=q.from_user.id;st=B.S.setdefault(uid,{})
        action=q.data
        if action=="adm:ui_options":
            return await q.message.reply_text("✏️ ویرایش متن گزینه‌های ربات\n\nگزینه‌ای را انتخاب کنید:",reply_markup=_kb([[ (v,"adm:editopt:"+k) for k,v in list(OPTION_KEYS.items())[:2] ],[(v,"adm:editopt:"+k) for k,v in list(OPTION_KEYS.items())[2:4]],[(v,"adm:editopt:"+k) for k,v in list(OPTION_KEYS.items())[4:]],[("⬅️ پنل مدیریت","adm:menu")]]))
        if action=="adm:ui_texts":
            return await q.message.reply_text("🤖 ویرایش متن‌های ربات\n\nمتن موردنظر را انتخاب کنید:",reply_markup=_kb([[(v,"adm:edittext:"+k) for k,v in list(TEXT_KEYS.items())[:2]],[(v,"adm:edittext:"+k) for k,v in list(TEXT_KEYS.items())[2:4]],[(v,"adm:edittext:"+k) for k,v in list(TEXT_KEYS.items())[4:]],[("⬅️ پنل مدیریت","adm:menu")]]))
        if action.startswith("adm:editopt:"):
            key=action.split(":",2)[2];st.update({"editable_mode":"option","editable_key":key})
            return await q.message.reply_text(f"✏️ متن جدید برای گزینه «{OPTION_KEYS.get(key,key)}» را ارسال کنید:\n\nمتن فعلی:\n{_get(B,key,OPTION_KEYS.get(key,key))}",reply_markup=_kb([[("⬅️ پنل مدیریت","adm:menu")]]))
        if action.startswith("adm:edittext:"):
            key=action.split(":",2)[2];st.update({"editable_mode":"text","editable_key":key})
            defaults={"welcome":"سلام 👋\nبه کمک یار مهاجر خوش آمدید.","iranian":"🇮🇷 منوی مشترکین ایرانی","complaint_prompt":"📝 لطفاً متن شکایت خود را ارسال کنید.","complaint_ok":"✅ شکایت شما برای مدیریت ارسال شد.","contact":"📞 تماس با ما"}
            return await q.message.reply_text(f"✏️ متن جدید را ارسال کنید:\n\nمتن فعلی:\n{_get(B,key,defaults.get(key,key))}",reply_markup=_kb([[("⬅️ پنل مدیریت","adm:menu")]]))

    async def text(update,context):
        uid=update.effective_user.id
        if not B.admin(uid):return
        st=B.S.setdefault(uid,{})
        if st.get("editable_mode") not in {"option","text"}:return
        value=(update.message.text or "").strip()
        if not value:return
        key=st.get("editable_key")
        B.db.set_setting("ui_text_"+key,value)
        st["editable_mode"]=None;st["editable_key"]=None
        return await update.message.reply_text("✅ متن با موفقیت ذخیره شد.\n\nاز این پس در بخش‌های متصل به این تنظیم استفاده می‌شود.",reply_markup=admin_menu_extended())

    app.add_handler(CallbackQueryHandler(cb,pattern=r"^adm:(ui_options|ui_texts|editopt:|edittext:)"),group=-30)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,text),group=-30)
    B._editable_texts_installed=True
