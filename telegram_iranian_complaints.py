"""Canonical Iranian subscriber UX, complaints, contact and editable labels."""
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import MessageHandler, CallbackQueryHandler, ApplicationHandlerStop, filters

log = logging.getLogger("netyar.telegram.iranian")
CONTACT_USERNAME = "Good_ok_2000"

OPTION_DEFAULTS = {
    "ir_gov": "🏛 حل مشکل ورود اتباع دولت من",
    "ir_track": "🎫 پیگیری",
    "ir_wallet": "💰 کیف پول من",
    "contact": "📞 تماس با ما",
    "complaint": "📝 ثبت شکایت",
    "partner": "🔵 👥 پنل همکاران",
}
TEXT_DEFAULTS = {
    "iranian": "🇮🇷 منوی مشترکین ایرانی\n\nگزینه موردنظر را انتخاب کنید:",
    "complaint_prompt": "📝 ثبت شکایت\n\nمتن شکایت یا انتقاد خود را ارسال کنید.",
    "complaint_ok": "✅ شکایت شما برای مدیریت ارسال شد.",
}

def _get(B, key, default):
    try:
        return B.db.setting("ui_text_" + key, default) or default
    except Exception:
        return default

def _enabled(B, key):
    try:
        return str(B.db.setting("ir_enabled_" + key, "1")).strip().lower() not in {"0", "false", "off", "no"}
    except Exception:
        return True

def _menu(B):
    rows=[]
    for key in ("ir_gov","ir_track","ir_wallet","contact","complaint","partner"):
        if not _enabled(B,key):
            continue
        label=_get(B,key,OPTION_DEFAULTS[key])
        if key=="ir_gov": rows.append([InlineKeyboardButton(label,callback_data="ir:gov")])
        elif key in {"ir_track","ir_wallet"}:
            if key=="ir_track": rows.append([InlineKeyboardButton(label,callback_data="ir:track")])
            else:
                if rows and len(rows[-1])==1: rows[-1].append(InlineKeyboardButton(label,callback_data="ir:wallet"))
                else: rows.append([InlineKeyboardButton(label,callback_data="ir:wallet")])
        elif key=="contact":
            if rows and len(rows[-1])==1: rows[-1].append(InlineKeyboardButton(label,url=f"https://t.me/{CONTACT_USERNAME}"))
            else: rows.append([InlineKeyboardButton(label,url=f"https://t.me/{CONTACT_USERNAME}")])
        elif key=="complaint":
            if rows and len(rows[-1])==1: rows[-1].append(InlineKeyboardButton(label,callback_data="ir:complaint"))
            else: rows.append([InlineKeyboardButton(label,callback_data="ir:complaint")])
        elif key=="partner": rows.append([InlineKeyboardButton(label,callback_data="ir:partner")])
    rows.append([InlineKeyboardButton("🔄 شروع مجدد",callback_data="ir:restart")])
    return InlineKeyboardMarkup(rows)

def install(app, B):
    if getattr(B,"_iranian_complaints_installed",False): return
    old_status=B.statuscb

    async def status(update,context):
        q=update.callback_query
        if q.data!="st:iranian": return await old_status(update,context)
        await q.answer()
        st=B.S.setdefault(q.from_user.id,{})
        st.update({"status":"iranian"});st.pop("mode",None)
        await q.message.reply_text(_get(B,"iranian",TEXT_DEFAULTS["iranian"]),reply_markup=_menu(B))
        # Critical: bot.py has a legacy st: callback registered in B.build().
        # Stop propagation so the old "services unavailable" message cannot fire.
        raise ApplicationHandlerStop

    async def cb(update,context):
        q=update.callback_query;a=q.data or ""
        if not a.startswith("ir:"): return
        await q.answer();st=B.S.setdefault(q.from_user.id,{})
        act=a.split(":",1)[1]
        if act=="gov":
            if not _enabled(B,"ir_gov"): return await q.message.reply_text("⛔ این گزینه فعلاً غیرفعال است.",reply_markup=_menu(B))
            st["mode"]="gov_doc_type"
            return await q.message.reply_text("🪪 نوع مدرک مشترک را انتخاب کنید:",reply_markup=B.kb([["🪪 کارت آمایش","🛂 گذرنامه"],["📗 دفترچه اقامت"],[B.CANCEL]]))
        if act=="track":
            if not _enabled(B,"ir_track"): return await q.message.reply_text("⛔ این گزینه فعلاً غیرفعال است.",reply_markup=_menu(B))
            st["mode"]="track";return await q.message.reply_text("🎫 کد پیگیری را وارد کنید:",reply_markup=B.cancel_kb(st.get("lang","fa")))
        if act=="wallet":
            if not _enabled(B,"ir_wallet"): return await q.message.reply_text("⛔ این گزینه فعلاً غیرفعال است.",reply_markup=_menu(B))
            try:return await B.customer_wallet(update,context)
            except Exception:return await q.message.reply_text("💰 کیف پول من\n\nموجودی کیف پول شما در دسترس است.",reply_markup=_menu(B))
        if act=="partner":
            if not _enabled(B,"partner"): return await q.message.reply_text("⛔ این گزینه فعلاً غیرفعال است.",reply_markup=_menu(B))
            st["mode"]="p_phone";return await q.message.reply_text("📱 شماره همراه همکار را وارد کنید:",reply_markup=B.cancel_kb(st.get("lang","fa")))
        if act=="complaint":
            if not _enabled(B,"complaint"): return await q.message.reply_text("⛔ این گزینه فعلاً غیرفعال است.",reply_markup=_menu(B))
            st["mode"]="iranian_complaint";return await q.message.reply_text(_get(B,"complaint_prompt",TEXT_DEFAULTS["complaint_prompt"]))
        if act=="restart":
            st.clear();st["lang"]="fa";return await B.start(update,context)
        raise ApplicationHandlerStop

    async def complaint_text(update,context):
        uid=update.effective_user.id;st=B.S.setdefault(uid,{})
        if st.get("mode")!="iranian_complaint": return
        t=(update.message.text or "").strip();u=update.effective_user
        if not t:return await update.message.reply_text("❌ متن شکایت خالی است.")
        username=f"@{u.username}" if u.username else "ندارد"
        msg=("📝 شکایت/انتقاد جدید\n\n" f"👤 نام: {u.full_name or '-'}\n" f"🔹 آیدی عددی: {u.id}\n" f"🔹 یوزرنیم: {username}\n\n" f"💬 متن شکایت:\n{t}")
        try:await B.notify_admins(context.application,msg)
        except Exception:log.exception("complaint notification failed")
        st["mode"]=None
        return await update.message.reply_text(_get(B,"complaint_ok",TEXT_DEFAULTS["complaint_ok"]),reply_markup=_menu(B))

    app.add_handler(CallbackQueryHandler(status,pattern=r"^st:iranian$"),group=-100)
    app.add_handler(CallbackQueryHandler(cb,pattern=r"^ir:"),group=-99)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,complaint_text),group=-100)
    B._iranian_complaints_installed=True
