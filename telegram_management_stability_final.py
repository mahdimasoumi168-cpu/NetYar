"""Final management/partner/working-hours stability layer.

Adds non-destructive management controls on top of the existing NetYar panels.
It deliberately uses unique callback names so legacy admin handlers keep working.
"""
import re
from datetime import datetime, time
from zoneinfo import ZoneInfo
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackQueryHandler, MessageHandler, ApplicationHandlerStop, filters
TZ=ZoneInfo("Asia/Tehran")
DEFAULT_OPEN="07:00"
DEFAULT_CLOSE="19:00"
def _digits(v): return str(v or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩","01234567890123456789"))
def _setting(B,key,default):
    try:return str(B.db.setting(key,default) or default)
    except Exception:return default
def _set(B,key,value):
    try:B.db.set_setting(key,str(value));return True
    except Exception:return False
def _valid_hhmm(v):return bool(re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d",str(v or "")))
def _is_open(B):
    op=_setting(B,"work_open",DEFAULT_OPEN);cl=_setting(B,"work_close",DEFAULT_CLOSE)
    try:
        o=time.fromisoformat(op);c=time.fromisoformat(cl);now=datetime.now(TZ).time()
        return o<=now<c if o<c else (now>=o or now<c)
    except Exception:return False
def _admin_menu_with_stability(B):
    base=B.amenu() if callable(getattr(B,"amenu",None)) else None;rows=[]
    source=getattr(base,"inline_keyboard",None) if base is not None else None
    if source: rows=[[b for b in row] for row in source]
    labels={getattr(b,"text","") for row in rows for b in row}
    if "🕐 ساعت کاری" not in labels: rows.append([InlineKeyboardButton("🕐 ساعت کاری",callback_data="mgmt:hours")])
    if "👤 تعریف همکار شب‌کار" not in labels: rows.append([InlineKeyboardButton("👤 تعریف همکار شب‌کار",callback_data="mgmt:night")])
    return InlineKeyboardMarkup(rows)
def _partner_markup(B,uid):
    try:
        import telegram_ui_policy_v2 as UI
        return UI.inline([["➕ شارژ حساب","🏛 حل مشکل سامانه دولت من"],["🪪 فیدای غیر حضوری","📱 خدمات سیم کارت"],["🖨 خدمات چاپ","🔎 پیگیری کد"],["🎫 درخواست‌های من","📋 سوابق"],["💰 موجودی","💬 ارتباط با مدیریت"],["🚪 خروج از پنل"]],B,uid)
    except Exception:
        return B.kb([["➕ شارژ حساب","🏛 حل مشکل سامانه دولت من"],["🪪 فیدای غیر حضوری","📱 خدمات سیم کارت"],["🖨 خدمات چاپ","🔎 پیگیری کد"],["🎫 درخواست‌های من","📋 سوابق"],["💰 موجودی","💬 ارتباط با مدیریت"],["🚪 خروج از پنل"]])
def install(app,B):
    if getattr(B,"_management_stability_final",False):return
    old_amenu=getattr(B,"amenu",None)
    if callable(old_amenu):
        def amenu():return _admin_menu_with_stability(B)
        B.amenu=amenu
    B.partner_kb=lambda lang="fa":_partner_markup(B,None)
    async def cb(update,context):
        q=update.callback_query
        if not q or not B.admin(q.from_user.id):return
        data=str(q.data or "")
        if not data.startswith("mgmt:"):return
        await q.answer();uid=q.from_user.id;st=B.S.setdefault(uid,{"admin":True});action=data.split(":",1)[1]
        if action=="hours":
            op=_setting(B,"work_open",DEFAULT_OPEN);cl=_setting(B,"work_close",DEFAULT_CLOSE)
            await q.message.reply_text(f"🕐 تنظیمات ساعت کاری\n\n🌅 شروع: {op}\n🌆 پایان: {cl}\n\nبرای تغییر، ابتدا روی گزینه موردنظر بزنید.",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🌅 تغییر شروع",callback_data="mgmt:setopen"),InlineKeyboardButton("🌆 تغییر پایان",callback_data="mgmt:setclose")],[InlineKeyboardButton("🔄 بازگردانی ۰۷ تا ۱۹",callback_data="mgmt:reset")],[InlineKeyboardButton("⬅️ پنل مدیریت",callback_data="mgmt:back")]]));raise ApplicationHandlerStop
        if action in {"setopen","setclose"}:st["mgmt_mode"]=action;await q.message.reply_text("🕐 زمان را با قالب HH:MM وارد کنید؛ مثال: 07:30");raise ApplicationHandlerStop
        if action=="reset":_set(B,"work_open",DEFAULT_OPEN);_set(B,"work_close",DEFAULT_CLOSE);await q.message.reply_text("✅ ساعت کاری به ۰۷:۰۰ تا ۱۹:۰۰ بازگردانی شد.",reply_markup=B.amenu());raise ApplicationHandlerStop
        if action=="night":
            rows=B.db.conn.execute("SELECT id,name,phone,active FROM partners ORDER BY id DESC LIMIT 80").fetchall();lines=["👤 تعریف همکار شب‌کار","","همکار موردنظر را انتخاب کنید یا شماره موبایل او را وارد کنید.",""]
            for r in rows:
                enabled=_setting(B,"night_worker:"+str(r["id"]),"0")=="1";lines.append(f"#{r['id']} | {r['name'] or '-'} | {r['phone']} | {'🌙 شب‌کار' if enabled else '⚪ عادی'}")
            await q.message.reply_text("\n".join(lines)[:3900],reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("➕ تعریف همکار شب‌کار",callback_data="mgmt:nightadd")],[InlineKeyboardButton("➖ حذف همکار شب‌کار",callback_data="mgmt:nightremove")],[InlineKeyboardButton("⬅️ پنل مدیریت",callback_data="mgmt:back")]]));raise ApplicationHandlerStop
        if action in {"nightadd","nightremove"}:st["mgmt_mode"]=action;await q.message.reply_text("📱 شماره موبایل همکار را وارد کنید:");raise ApplicationHandlerStop
        if action=="back":st["mgmt_mode"]=None;await q.message.reply_text("🛠 پنل مدیریت کامل",reply_markup=B.amenu());raise ApplicationHandlerStop
    async def text_handler(update,context):
        if not update.effective_user or not update.message or not B.admin(update.effective_user.id):return
        st=B.S.setdefault(update.effective_user.id,{});mode=st.get("mgmt_mode")
        if not mode:return
        t=_digits((update.message.text or "").strip())
        if t in {"لغو","انصراف","❌ انصراف"}:st["mgmt_mode"]=None;await update.message.reply_text("لغو شد.",reply_markup=B.amenu());raise ApplicationHandlerStop
        if mode in {"setopen","setclose"}:
            if not _valid_hhmm(t):await update.message.reply_text("❌ زمان نامعتبر است. قالب صحیح: HH:MM مثل 07:30");raise ApplicationHandlerStop
            _set(B,"work_open" if mode=="setopen" else "work_close",t);st["mgmt_mode"]=None;await update.message.reply_text("✅ ساعت کاری ذخیره شد.",reply_markup=B.amenu());raise ApplicationHandlerStop
        if mode in {"nightadd","nightremove"}:
            phone=re.sub(r"\D","",t)
            if phone.startswith("98"):phone="0"+phone[2:]
            if not re.fullmatch(r"09\d{9}",phone):await update.message.reply_text("❌ شماره موبایل صحیح نیست.");raise ApplicationHandlerStop
            partner=B.db.partner(phone)
            if not partner:await update.message.reply_text("❌ همکار فعال با این شماره پیدا نشد.");raise ApplicationHandlerStop
            val="1" if mode=="nightadd" else "0";_set(B,"night_worker:"+str(partner["id"]),val);st["mgmt_mode"]=None
            await update.message.reply_text(f"✅ {partner['name'] or phone} {'برای شیفت شب فعال شد.' if val=='1' else 'از شیفت شب خارج شد.'}",reply_markup=B.amenu());raise ApplicationHandlerStop
    app.add_handler(CallbackQueryHandler(cb,pattern=r"^mgmt:"),group=-40000)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,text_handler),group=-39999)
    B._management_stability_final=True
