"""Expanded Telegram admin controls + residence booklet identity flow.

This module is intentionally isolated from legacy handlers. It is installed by
telegram_runtime_clean and runs before the generic UI router.
"""
import logging
import re
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup
from telegram.ext import MessageHandler, CallbackQueryHandler, filters

log = logging.getLogger("netyar.telegram.admin_plus")


def _digits(v):
    return str(v or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))


def _kb(rows):
    return InlineKeyboardMarkup([[InlineKeyboardButton(str(label), callback_data=data) for label, data in row] for row in rows])


def _admin_menu():
    return _kb([
        [("👤 کاربران", "adm:users"), ("👥 همکاران", "adm:partners")],
        [("💰 شارژها", "adm:topups"), ("💳 پرداخت‌ها", "adm:payments")],
        [("📋 درخواست‌ها", "adm:requests"), ("⚙️ قیمت‌ها", "adm:prices")],
        [("➕ افزایش قیمت", "adm:priceup"), ("➖ کاهش قیمت", "adm:pricedown")],
        [("💵 افزایش شارژ", "adm:creditup"), ("💸 کاهش شارژ", "adm:creditdown")],
        [("✏️ تغییر متن‌ها", "adm:texts"), ("🟢 خدمات", "adm:services")],
        [("📊 گزارش کامل", "adm:report"), ("📣 اعلان همگانی", "adm:announce")],
        [("🤖 بات‌های متصل", "adm:bots"), ("🧾 لاگ مدیریت", "adm:logs")],
        [("⚙️ تنظیمات", "adm:settings"), ("⬅️ منوی اصلی", "adm:main")],
    ])


def _back():
    return _kb([[("⬅️ پنل مدیریت", "adm:menu")]])


async def _show(update, text, markup=None):
    q = update.callback_query
    if q:
        return await q.message.reply_text(text, reply_markup=markup)
    return await update.message.reply_text(text, reply_markup=markup)


async def _callback(update, context, B):
    q = update.callback_query
    data = q.data or ""
    if not data.startswith("adm:") or not B.admin(q.from_user.id):
        return
    await q.answer()
    uid = q.from_user.id
    st = B.S.setdefault(uid, {"admin": True})
    action = data.split(":", 1)[1]
    if action == "menu":
        st["admin_plus_mode"] = None
        return await _show(update, "🛠 پنل مدیریت کامل\n\nاز منوی زیر بخش موردنظر را انتخاب کنید:", _admin_menu())
    if action == "main":
        st["admin_plus_mode"] = None
        return await _show(update, "منوی اصلی", B.main(uid))
    if action == "users":
        rows = B.db.conn.execute("SELECT id,platform,full_name,username,created_at FROM users ORDER BY id DESC LIMIT 80").fetchall()
        body = "\n".join(f"#{r['id']} | {r['platform']} | {r['full_name'] or '-'} | @{r['username'] or '-'}" for r in rows) or "کاربری ثبت نشده است."
        return await _show(update, "👤 کاربران\n\n" + body[:3800], _back())
    if action == "partners":
        rows = B.db.conn.execute("SELECT id,name,phone,balance,active FROM partners ORDER BY id DESC LIMIT 80").fetchall()
        body = "\n".join(f"#{r['id']} | {r['name']} | {r['phone']} | 💰 {int(r['balance'] or 0):,} | {'فعال' if r['active'] else 'غیرفعال'}" for r in rows) or "همکاری ثبت نشده است."
        return await _show(update, "👥 همکاران\n\n" + body[:3800], _back())
    if action == "topups":
        rows = B.db.conn.execute("SELECT id,partner_id,amount,status,created_at FROM topups ORDER BY id DESC LIMIT 50").fetchall()
        lines=[]
        for r in rows:
            p=B.db.conn.execute("SELECT name FROM partners WHERE id=?",(r['partner_id'],)).fetchone()
            lines.append(f"#{r['id']} | {p['name'] if p else '-'} | {int(r['amount'] or 0):,} | {r['status']} | {r['created_at']}")
        return await _show(update, "💰 شارژها\n\n" + ("\n".join(lines) or "موردی نیست."), _back())
    if action == "payments":
        rows=B.db.conn.execute("SELECT tracking_code,service_key,amount,payment_status,payment_method,created_at FROM requests ORDER BY id DESC LIMIT 50").fetchall()
        body="\n".join(f"{r['tracking_code']} | {r['service_key']} | {int(r['amount'] or 0):,} | {r['payment_status']} | {r['payment_method'] or '-'}" for r in rows) or "پرداختی ثبت نشده است."
        return await _show(update, "💳 پرداخت‌های مشتری\n\n"+body[:3800], _back())
    if action == "requests":
        rows=B.db.conn.execute("SELECT id,tracking_code,service_key,status,amount,created_at FROM requests ORDER BY id DESC LIMIT 60").fetchall()
        body="\n".join(f"#{r['id']} | {r['tracking_code']} | {r['service_key']} | {r['status']} | {int(r['amount'] or 0):,}" for r in rows) or "درخواستی نیست."
        return await _show(update, "📋 درخواست‌ها\n\n"+body[:3800], _back())
    if action in {"prices","priceup","pricedown"}:
        amount=int(B.db.setting("price_government","500000") or 500000)
        if action == "prices":
            return await _show(update, f"⚙️ قیمت‌ها\n\n🏛 دولت من: {amount:,} تومان\n\nگزینه موردنظر را انتخاب کنید:", _kb([[("➕ افزایش", "adm:priceup"), ("➖ کاهش", "adm:pricedown")],[("✏️ تعیین مبلغ دقیق", "adm:priceset")],[("⬅️ پنل مدیریت", "adm:menu")]]))
        st["admin_plus_mode"] = "price_delta"
        st["admin_plus_action"] = "up" if action == "priceup" else "down"
        return await _show(update, ("➕ مبلغ افزایش" if action == "priceup" else "➖ مبلغ کاهش") + " را به تومان وارد کنید:", _back())
    if action == "priceset":
        st["admin_plus_mode"]="price_set"
        return await _show(update, "💰 قیمت جدید خدمت دولت من را به تومان وارد کنید:", _back())
    if action in {"creditup","creditdown"}:
        st["admin_plus_mode"]="credit_partner"
        st["admin_plus_action"]="up" if action=="creditup" else "down"
        return await _show(update, ("💵 افزایش شارژ" if action=="creditup" else "💸 کاهش شارژ") + "\n\nشماره موبایل همکار را وارد کنید:", _back())
    if action == "texts":
        return await _show(update, "✏️ تغییر متن‌ها\n\nمتن‌ها در تنظیمات ذخیره می‌شوند و برای استفاده در جریان‌های فعال در دسترس هستند:", _kb([
            [("👋 متن خوش‌آمدگویی", "adm:text:welcome"),("🏛 متن دولت من", "adm:text:government")],
            [("📨 متن اعلان مدیریت", "adm:text:admin_notice"),("❌ متن خطا", "adm:text:error")],
            [("⬅️ پنل مدیریت", "adm:menu")],
        ]))
    if action.startswith("text:"):
        key=action.split(":",1)[1]
        names={"welcome":"welcome_fa","government":"government_fa","admin_notice":"admin_notice_fa","error":"error_fa"}
        skey=names.get(key)
        if not skey:return
        st["admin_plus_mode"]="text"
        st["admin_plus_key"]=skey
        current=B.db.setting("text_"+skey, "")
        return await _show(update, f"✏️ متن جدید را ارسال کنید.\n\nمتن فعلی:\n{current or 'تعریف نشده'}", _back())
    if action == "services":
        rows=B.db.conn.execute("SELECT key,name,price,active FROM services ORDER BY id").fetchall()
        body="\n".join(f"{'🟢' if r['active'] else '🔴'} {r['name']} | {int(r['price'] or 0):,} تومان | {r['key']}" for r in rows) or "خدمتی تعریف نشده است."
        return await _show(update,"🟢 خدمات\n\n"+body[:3800],_back())
    if action == "report":
        users=B.db.conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        partners=B.db.conn.execute("SELECT COUNT(*) FROM partners").fetchone()[0]
        requests=B.db.conn.execute("SELECT COUNT(*) FROM requests").fetchone()[0]
        completed=B.db.conn.execute("SELECT COUNT(*) FROM requests WHERE status='completed'").fetchone()[0]
        revenue=B.db.conn.execute("SELECT COALESCE(SUM(amount),0) FROM requests WHERE payment_status='paid'").fetchone()[0]
        return await _show(update,f"📊 گزارش کامل\n\n👤 کاربران: {users}\n👥 همکاران: {partners}\n📋 درخواست‌ها: {requests}\n✅ انجام‌شده: {completed}\n💰 پرداخت‌شده: {int(revenue or 0):,} تومان",_back())
    if action == "announce":
        st["admin_plus_mode"]="announce"
        return await _show(update,"📣 متن اعلان همگانی را ارسال کنید:",_back())
    if action == "bots":
        try: rows=B.db.bots()
        except Exception: rows=[]
        body="\n".join(f"#{r['id']} | {r['platform']} | {r['bot_name']} | {'فعال' if r['active'] else 'خاموش'}" for r in rows) or "باتی ثبت نشده است."
        return await _show(update,"🤖 بات‌های متصل\n\n"+body,_back())
    if action == "logs":
        rows=B.db.conn.execute("SELECT platform,actor_id,action,target,details,created_at FROM audit_log ORDER BY id DESC LIMIT 50").fetchall()
        body="\n".join(f"{r['created_at']} | {r['action']} | {r['target']} | {str(r['details'])[:70]}" for r in rows) or "لاگی نیست."
        return await _show(update,"🧾 لاگ مدیریت\n\n"+body[:3800],_back())
    if action == "settings":
        rows=B.db.conn.execute("SELECT key,value FROM settings ORDER BY key").fetchall()
        body="\n".join(f"{r['key']} = {r['value']}" for r in rows) or "تنظیمی ثبت نشده است."
        return await _show(update,"⚙️ تنظیمات\n\n"+body[:3800],_back())


async def _text(update, context, B):
    uid=update.effective_user.id
    if not B.admin(uid): return
    st=B.S.setdefault(uid,{"admin":True})
    mode=st.get("admin_plus_mode")
    t=(update.message.text or "").strip()
    if not mode:return
    if t in {"❌ انصراف","⬅️ پنل مدیریت","لغو","انصراف"}:
        st["admin_plus_mode"]=None
        return await update.message.reply_text("لغو شد.",reply_markup=_admin_menu())
    if mode=="price_delta":
        n=int(_digits(t)) if _digits(t).isdigit() else 0
        if n<=0:return await update.message.reply_text("❌ مبلغ معتبر وارد کنید.")
        old=int(B.db.setting("price_government","500000") or 500000)
        new=old+n if st.get("admin_plus_action")=="up" else max(0,old-n)
        B.db.set_setting("price_government",new)
        st["admin_plus_mode"]=None
        return await update.message.reply_text(f"✅ قیمت دولت من از {old:,} به {new:,} تومان تغییر کرد.",reply_markup=_admin_menu())
    if mode=="price_set":
        n=int(_digits(t)) if _digits(t).isdigit() else 0
        if n<=0:return await update.message.reply_text("❌ مبلغ معتبر وارد کنید.")
        B.db.set_setting("price_government",n);st["admin_plus_mode"]=None
        return await update.message.reply_text(f"✅ قیمت جدید: {n:,} تومان",reply_markup=_admin_menu())
    if mode=="credit_partner":
        phone=re.sub(r"\D", "", _digits(t))
        if phone.startswith("98"):phone="0"+phone[2:]
        p=B.db.partner(phone)
        if not p:return await update.message.reply_text("❌ همکار پیدا نشد. شماره را صحیح وارد کنید.",reply_markup=_back())
        st["admin_credit_partner"]=p["id"];st["admin_plus_mode"]="credit_amount"
        return await update.message.reply_text(f"👤 {p['name']}\n💳 موجودی فعلی: {int(p['balance'] or 0):,} تومان\n\nمبلغ را وارد کنید:",reply_markup=_back())
    if mode=="credit_amount":
        n=int(_digits(t)) if _digits(t).isdigit() else 0
        if n<=0:return await update.message.reply_text("❌ مبلغ معتبر وارد کنید.")
        pid=st.get("admin_credit_partner");p=B.db.conn.execute("SELECT name,balance FROM partners WHERE id=?",(pid,)).fetchone()
        if not p:return await update.message.reply_text("❌ همکار پیدا نشد.",reply_markup=_admin_menu())
        old=int(p["balance"] or 0); up=st.get("admin_plus_action")=="up"; new=old+n if up else old-n
        if new<0:return await update.message.reply_text("❌ کاهش شارژ بیشتر از موجودی مجاز نیست.",reply_markup=_back())
        B.db.conn.execute("UPDATE partners SET balance=?,updated_at=? WHERE id=?",(new,B.now(),pid));B.db.conn.commit()
        try:B.db.audit("telegram",uid,"balance_adjust","partners",f"partner={pid};old={old};new={new};delta={n if up else -n}")
        except Exception:pass
        st["admin_plus_mode"]=None
        return await update.message.reply_text(f"✅ موجودی {p['name']} به {new:,} تومان رسید.",reply_markup=_admin_menu())
    if mode=="text":
        key=st.get("admin_plus_key")
        if key:
            B.db.set_setting("text_"+key,t)
        st["admin_plus_mode"]=None
        return await update.message.reply_text("✅ متن ذخیره شد.",reply_markup=_admin_menu())
    if mode=="announce":
        rows=B.db.conn.execute("SELECT external_id FROM users WHERE platform='telegram'").fetchall();ok=fail=0
        for r in rows:
            try: await context.bot.send_message(chat_id=int(r["external_id"]),text=t);ok+=1
            except Exception:fail+=1
        st["admin_plus_mode"]=None
        return await update.message.reply_text(f"📣 اعلان ارسال شد.\n✅ موفق: {ok}\n❌ ناموفق: {fail}",reply_markup=_admin_menu())


async def _gov_start(update, context, B):
    q=update.callback_query
    if not q or not B.admin(q.from_user.id) and False: pass
    uid=q.from_user.id
    old=dict(B.S.get(uid,{}))
    B.S[uid]={"mode":"gov_doc_type","lang":old.get("lang","fa"),"gov_files":{},"partner_id":old.get("partner_id")}
    await q.answer()
    return await q.message.reply_text("🪪 نوع مدرک مشترک را انتخاب کنید:",reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("🪪 کارت آمایش",callback_data="govtype:card"),InlineKeyboardButton("🛂 گذرنامه",callback_data="govtype:passport")],
        [InlineKeyboardButton("📗 دفترچه اقامت",callback_data="govtype:residence")],
        [InlineKeyboardButton("❌ انصراف",callback_data="adm:menu")],
    ]))

async def _govtype(update, context, B):
    q=update.callback_query; data=q.data or ""; uid=q.from_user.id
    if not data.startswith("govtype:"):return
    await q.answer(); st=B.S.setdefault(uid,{})
    typ=data.split(":",1)[1]; st["gov_doc_type"]="residence_booklet" if typ=="residence" else typ
    st["mode"]="gov_phone"
    return await q.message.reply_text("📱 شماره موبایل مشترک را وارد کنید:",reply_markup=ReplyKeyboardMarkup([["❌ انصراف"]],resize_keyboard=True))

async def _gov_residence_text(update, context, B):
    uid=update.effective_user.id;st=B.S.setdefault(uid,{})
    if st.get("mode") not in {"gov_phone","gov_booklet_number"}:return
    t=(update.message.text or "").strip(); d=_digits(t)
    if st.get("mode")=="gov_phone":
        phone=re.sub(r"\D", "", d)
        if phone.startswith("98"):phone="0"+phone[2:]
        if not re.fullmatch(r"09\d{9}",phone):return await update.message.reply_text("❌ شماره موبایل باید ۱۱ رقم و با ۰۹ شروع شود.")
        st["gov_phone"]=phone;st["mode"]="gov_dob"
        return await update.message.reply_text("🎂 تاریخ تولد مشترک را وارد کنید:")
    if st.get("mode")=="gov_booklet_number":
        if len(t)<3:return await update.message.reply_text("❌ شماره دفترچه اقامت را صحیح وارد کنید.")
        st["gov_booklet_number"]=t;st["mode"]="gov_photo"
        return await update.message.reply_text("📸 تصویر دفترچه اقامت را ارسال کنید:")


def install(app,B):
    B.amenu=_admin_menu
    app.add_handler(CallbackQueryHandler(lambda u,c:_callback(u,c,B),pattern=r"^(adm:|govtype:)"),group=-3)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,lambda u,c:_text(u,c,B),),group=-3)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,lambda u,c:_gov_residence_text(u,c,B)),group=-4)
