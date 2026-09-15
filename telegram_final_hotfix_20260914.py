"""Deterministic Telegram hotfix layer.

Protect active phone-input states from being swallowed by generic routers and
keep the Irancell partner-service price synchronized to 980,000 toman.
"""
import re
from telegram.ext import MessageHandler, filters, ApplicationHandlerStop

PHONE_MODES = {
    "govv2_phone": ("gov_phone", "govv2_dob", "🎂 تاریخ تولد مشترک را وارد کنید:"),
    "gov_phone": ("gov_phone", "govv2_dob", "🎂 تاریخ تولد مشترک را وارد کنید:"),
    "government_phone": ("gov_phone", "govv2_dob", "🎂 تاریخ تولد مشترک را وارد کنید:"),
    "gov_phone_input": ("gov_phone", "govv2_dob", "🎂 تاریخ تولد مشترک را وارد کنید:"),
    "irancell_partner_phone": ("irancell_phone", "irancell_partner_document", "📸 حالا عکس مدرک شناسایی مشترک را ارسال کنید:\n\nمدرک باید واضح و خوانا باشد."),
}

PRICE = 980_000

def _digits(v):
    return str(v or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "0123456789"))

def _phone(v):
    s = re.sub(r"[^0-9]", "", _digits(v))
    if s.startswith("98"):
        s = "0" + s[2:]
    elif s.startswith("0098"):
        s = "0" + s[4:]
    return s if re.fullmatch(r"09\d{9}", s) else None

def _sync_price(B):
    try:
        B.db.conn.execute("UPDATE services SET price=?, active=1 WHERE key=?", (PRICE, "irancell_sim_issue"))
        B.db.conn.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", ("price_irancell_sim", str(PRICE)))
        B.db.conn.commit()
    except Exception:
        try: B.db.conn.rollback()
        except Exception: pass

def install(app, B):
    if getattr(B, "_final_hotfix_20260914", False):
        return
    _sync_price(B)

    async def handler(update, context):
        msg = update.effective_message
        user = update.effective_user
        if not msg or not user or not msg.text:
            return
        uid = user.id
        st = B.S.setdefault(uid, {})
        mode = str(st.get("mode") or "")
        if mode not in PHONE_MODES:
            return
        p = _phone(msg.text)
        if not p:
            if mode.startswith("gov"):
                await msg.reply_text("❌ شماره موبایل صحیح نیست.\n\n📱 لطفاً شماره ۱۱ رقمی را با ۰۹ وارد کنید:", reply_markup=B.cancel_kb(st.get("lang", "fa")))
            else:
                await msg.reply_text("❌ شماره موبایل صحیح نیست.\n\n📱 لطفاً شماره ۱۱ رقمی ایرانسل را با ۰۹ وارد کنید:", reply_markup=B.cancel_kb(st.get("lang", "fa")))
            raise ApplicationHandlerStop
        key, next_mode, prompt = PHONE_MODES[mode]
        if mode.startswith("gov"):
            st["gov_phone"] = p
        else:
            st.setdefault("irancell", {})["phone"] = p
        st["mode"] = next_mode
        await msg.reply_text(prompt, reply_markup=B.cancel_kb(st.get("lang", "fa")))
        raise ApplicationHandlerStop
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handler), group=-10000000)
    B._final_hotfix_20260914 = True