"""Partner panel v33 navigation and admin add-partner entry."""
import logging
import re
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationHandlerStop
log = logging.getLogger("netyar.telegram.partner_navigation_v33")
PARTNER_LABELS={"👥 پنل همکاران","🔵 👥 پنل همکاران","👥 Partner panel","👥 لوحة الشركاء"}
CANCEL_LABELS={"❌ انصراف","❌ Cancel","❌ إلغاء","انصراف","Cancel","إلغاء"}
ADD_PARTNER_LABELS={"➕ افزودن همکار","➕ افزودن همکار جدید"}
def _fresh_login(B,uid):
    old=dict(B.S.get(uid,{}) or {}); keep={k:old[k] for k in ("lang","status","citizenship") if old.get(k) is not None}; keep.update(partner_logged_out=True,partner_active=False,mode="p_phone",step="partner_phone"); B.S[uid]=keep; return keep
def _clear_service_keep_auth(B,uid):
    st=B.S.setdefault(uid,{}); keep={k:st[k] for k in ("lang","status","citizenship","partner","partner_phone","partner_id","partner_active","partner_logged_out") if st.get(k) is not None}; keep.update(mode="partner",step="partner"); B.S[uid]=keep; return keep
def _add_partner_markup(B,uid,markup):
    if not B.admin(uid) or markup is None or not hasattr(markup,"inline_keyboard"): return markup
    rows=[list(r) for r in markup.inline_keyboard]
    if not any(any(str(getattr(b,"text","")) in ADD_PARTNER_LABELS for b in r) for r in rows): rows.insert(max(0,len(rows)-1),[InlineKeyboardButton("➕ افزودن همکار",callback_data="ui2:add_partner_panel")])
    return InlineKeyboardMarkup(rows)
def _digits(value): return str(value or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩","01234567890123456789"))
def install(app,B):
    if getattr(B,"_partner_navigation_v33",False): return True
    import telegram_ui_policy_v2 as UI
    old_dispatch=UI._dispatch; old_partner_kb=B.partner_kb
    def partner_kb(lang="fa"):
        try: uid=int(UI._uid())
        except Exception: uid=getattr(UI,"_ui_current_uid",None) or 0
        return _add_partner_markup(B,uid,old_partner_kb(lang))
    B.partner_kb=partner_kb
    async def dispatch(update,context,bot,label):
        label=str(label or "").strip(); q=getattr(update,"callback_query",None); uid=int(q.from_user.id if q else update.effective_user.id); st=bot.S.setdefault(uid,{})
        if label in PARTNER_LABELS:
            st=_fresh_login(bot,uid)
            if q:
                await q.answer(); await q.message.reply_text("👥 ورود به پنل همکاران\n\n📱 لطفاً شماره موبایل اختصاصی همکار را وارد کنید:",reply_markup=bot.cancel_kb(st.get("lang","fa"))); raise ApplicationHandlerStop
        if label in CANCEL_LABELS and st.get("partner_active") and not st.get("partner_logged_out"):
            _clear_service_keep_auth(bot,uid)
            if q:
                await q.answer(); await q.message.reply_text("↩️ به پنل همکاران برگشتید.",reply_markup=bot.partner_kb(st.get("lang","fa"))); raise ApplicationHandlerStop
        if label in ADD_PARTNER_LABELS and bot.admin(uid):
            st.update(admin_plus_mode="power_add_name",power_partner={},mode="admin_add_partner")
            if q:
                await q.answer(); await q.message.reply_text("➕ افزودن همکار جدید\n\n👤 نام و نام خانوادگی یا نام مجموعه همکار را وارد کنید:",reply_markup=bot.cancel_kb(st.get("lang","fa"))); raise ApplicationHandlerStop
        return await old_dispatch(update,context,bot,label)
    UI._dispatch=dispatch
    async def add_partner_text(update,context):
        user=getattr(update,"effective_user",None); msg=getattr(update,"effective_message",None)
        if not user or not msg or not B.admin(user.id): return
        st=B.S.setdefault(user.id,{}); mode=st.get("admin_plus_mode"); text=str(getattr(msg,"text","") or "").strip()
        if mode not in {"power_add_name","power_add_phone","power_add_password"}: return
        if mode=="power_add_name":
            if len(text)<2: await msg.reply_text("❌ نام معتبر وارد کنید.",reply_markup=B.cancel_kb(st.get("lang","fa")))
            else: st["power_partner"]["name"]=text; st["admin_plus_mode"]="power_add_phone"; await msg.reply_text("📱 شماره موبایل اختصاصی همکار را وارد کنید:",reply_markup=B.cancel_kb(st.get("lang","fa")))
            raise ApplicationHandlerStop
        if mode=="power_add_phone":
            phone=re.sub(r"\D","",_digits(text)); phone="0"+phone[2:] if phone.startswith("98") else phone
            if not re.fullmatch(r"09\d{9}",phone): await msg.reply_text("❌ شماره موبایل معتبر نیست. مثال: 09123456789",reply_markup=B.cancel_kb(st.get("lang","fa")))
            elif B.db.conn.execute("SELECT 1 FROM partners WHERE phone=? LIMIT 1",(phone,)).fetchone(): await msg.reply_text("❌ این شماره قبلاً به‌عنوان همکار ثبت شده است.",reply_markup=B.cancel_kb(st.get("lang","fa")))
            else: st["power_partner"]["phone"]=phone; st["admin_plus_mode"]="power_add_password"; await msg.reply_text("🔐 رمز ورود همکار را وارد کنید (حداقل ۴ کاراکتر):",reply_markup=B.cancel_kb(st.get("lang","fa")))
            raise ApplicationHandlerStop
        if len(text)<4: await msg.reply_text("❌ رمز باید حداقل ۴ کاراکتر باشد.",reply_markup=B.cancel_kb(st.get("lang","fa"))); raise ApplicationHandlerStop
        from core import hash_password
        p=st.get("power_partner") or {}
        B.db.conn.execute("INSERT INTO partners(phone,password_hash,name,active,balance,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",(p["phone"],hash_password(text),p["name"],1,0,B.now(),B.now())); B.db.conn.commit()
        row=B.db.conn.execute("SELECT id FROM partners WHERE phone=? LIMIT 1",(p["phone"],)).fetchone(); st.pop("admin_plus_mode",None); st.pop("power_partner",None); st["mode"]="partner"; st["step"]="partner"
        await msg.reply_text(f"✅ همکار جدید با موفقیت اضافه شد.\n\n👤 {p['name']}\n📱 {p['phone']}\n🆔 شناسه: {row['id'] if row else '-'}\n💰 موجودی اولیه: 0 تومان",reply_markup=B.partner_kb(st.get("lang","fa"))); raise ApplicationHandlerStop
    from telegram.ext import MessageHandler,filters
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,add_partner_text),group=-100000)
    B._partner_navigation_v33=True; log.info("Partner navigation v33 installed"); return True
