import os
import bot as B


def advanced_amenu():
    return B.kb([
        ["👥 همکاران", "➕ افزودن همکار"],
        ["💰 شارژها", "📋 درخواست‌ها"],
        ["⚙️ قیمت‌ها", "📊 گزارش"],
        ["🤖 افزودن بات", "🤖 بات‌های متصل"],
        ["📣 اعلان خدمت"],
        ["⬅️ منوی اصلی"],
    ])


def platform_kb():
    return B.kb([["🤖 Telegram", "🤖 Rubika"], ["🤖 Bale", "🤖 Eitaa"], ["⬅️ بازگشت"]])


def partner_kb(lang="fa"):
    if lang == "en":
        return B.kb([["➕ Top up", "🏛 Government access issue"], ["🔎 Track code", "📋 History"], ["💰 Balance"], ["❌ Cancel"]])
    if lang == "ar":
        return B.kb([["➕ شحن الحساب", "🏛 حل مشكلة خدمات الحكومة"], ["🔎 رمز المتابعة", "📋 السجل"], ["💰 الرصيد"], ["❌ إلغاء"]])
    return B.kb([["➕ شارژ حساب", "🏛 حل مشکل سامانه دولت من"], ["🔎 پیگیری کد", "📋 سوابق"], ["💰 موجودی"], [B.CANCEL]])

B.amenu = advanced_amenu
B.partner_kb = partner_kb
_original_main = B.main
_original_router = B.router
_original_service_text = B.service_text


def main(uid):
    markup = _original_main(uid)
    try:
        lang = B.S.get(uid, {}).get("lang", "fa")
        screening = {"fa": "📝 آزمون غربالگری", "en": "📝 Screening test", "ar": "📝 اختبار الفحص"}[lang]
        follow = {"fa": "🎫 پیگیری", "en": "🎫 Follow-up", "ar": "🎫 متابعة"}[lang]
        old = {"fa": "📝 آزمون غربالگری و پیگیری", "en": "📝 Screening & follow-up", "ar": "📝 الفحص والمتابعة"}[lang]
        rows = []
        for row in markup.keyboard:
            row = list(row)
            if old in row:
                nr=[]
                for item in row:
                    nr.extend([screening, follow] if item == old else [item])
                rows.append(nr)
            else:
                rows.append(row)
        return B.kb(rows)
    except Exception:
        return markup

B.main = main


async def fixed_service_text(u, c):
    uid = u.effective_user.id
    st = B.S.setdefault(uid, {})
    t = (u.message.text or "").strip()
    # Fix the common Government flow bug: the final phone answer must come
    # from gov_phone, not from the birth-date text.
    if st.get("mode") == "gov_dob":
        import re
        if not re.fullmatch(r"1[34]\d{2}/(0[1-9]|1[0-2])/(0[1-9]|[12]\d|3[01])", t):
            return await u.message.reply_text(B.L(uid, "❌ تاریخ تولد را به شکل 1356/01/01 وارد کنید.", "❌ Enter the birth date as 1356/01/01.", "❌ أدخل تاريخ الميلاد بالشكل 1356/01/01."), reply_markup=B.cancel_kb(st.get("lang", "fa")))
        st["dob"] = t
        amount = int(B.db.setting("price_government", "500000") or 500000)
        owner = st.get("partner_id") or B.db.user("telegram", uid, u.effective_user.username, u.effective_user.full_name)
        rid, code = B.db.create_request(owner, "government", "telegram", amount)
        for k, v in st.get("gov_files", {}).items():
            if k in ("id", "sim") and v != "ندارد":
                B.db.answer(rid, k, file_id=v)
            else:
                B.db.answer(rid, k, answer=v)
        B.db.answer(rid, "phone", st.get("gov_phone", ""))
        B.db.answer(rid, "dob", st["dob"])
        if st.get("partner_id"):
            p=B.db.conn.execute("SELECT * FROM partners WHERE id=?",(st["partner_id"],)).fetchone()
            if not p or int(p["balance"]) < amount:
                return await u.message.reply_text(f"❌ اعتبار کافی نیست. هزینه {amount:,} تومان است.", reply_markup=partner_kb(st.get("lang","fa")))
            B.db.conn.execute("UPDATE requests SET status='submitted',payment_status='paid',payment_method='partner_balance' WHERE id=?",(rid,))
            B.db.conn.execute("UPDATE partners SET balance=balance-?,updated_at=? WHERE id=?",(amount,B.now(),p["id"]))
            B.db.conn.commit(); st["mode"] = None
            return await u.message.reply_text(f"✅ درخواست سامانه دولت من ثبت شد.\n🎫 {code}\n💰 کسر از اعتبار: {amount:,} تومان", reply_markup=partner_kb(st.get("lang","fa")))
        # Online gateway is removed. Keep manual card/receipt workflow.
        st.update({"rid":rid,"code":code,"mode":"payment"})
        return await B.invoice(u, amount, code)
    if st.get("mode") == "gov_phone":
        if not t.isdigit() or len(t) not in (10,11):
            return await u.message.reply_text(B.L(uid,"❌ شماره موبایل مشترک را صحیح وارد کنید.","❌ Enter a valid customer mobile number.","❌ أدخل رقم هاتف العميل بشكل صحيح."),reply_markup=B.cancel_kb(st.get("lang","fa")))
        st["gov_phone"] = t; st["mode"] = "gov_dob"
        return await u.message.reply_text(B.L(uid,"🎂 تاریخ تولد مشترک را به صورت 1356/01/01 وارد کنید.","🎂 Enter the customer's birth date as 1356/01/01.","🎂 أدخل تاريخ ميلاد العميل بالشكل 1356/01/01."),reply_markup=B.cancel_kb(st.get("lang","fa")))
    return await _original_service_text(u, c)

B.service_text = fixed_service_text
async def fixed_topup(u,c):
    uid=u.effective_user.id
    st=B.S.setdefault(uid,{})
    if not st.get("partner_id"):
        return await u.message.reply_text("❌ ابتدا وارد پنل همکاران شوید.",reply_markup=B.main(uid))
    st["mode"]="topup_amount"
    return await u.message.reply_text("💰 مبلغ شارژ را به تومان وارد کنید:",reply_markup=B.cancel_kb(st.get("lang","fa")))

B.topup = fixed_topup



async def extra_text(u, c):
    uid = u.effective_user.id
    st = B.S.setdefault(uid, {})
    if st.get("partner_id"):
        try:
            B.db.set_setting(f"partner_chat_{st['partner_id']}", str(u.effective_chat.id))
        except Exception:
            pass
    t = (u.message.text or "").strip()
    lang = st.get("lang", "fa")

    actions = {
        "➕ Top up": "topup", "➕ شحن الحساب": "topup", "➕ شارژ حساب": "topup",
        "🏛 Government access issue": "gov", "🏛 حل مشکل خدمات الحكومة": "gov", "🏛 حل مشکل سامانه دولت من": "gov",
        "🔎 Track code": "track", "🔎 رمز المتابعة": "track", "🔎 پیگیری کد": "track",
        "📋 History": "history", "📋 السجل": "history", "📋 سوابق": "history",
        "💰 Balance": "balance", "💰 الرصيد": "balance", "💰 موجودی": "balance",
    }
    if st.get("partner_id") and t in actions:
        a=actions[t]
        if a=="topup": return await B.topup(u,c)
        if a=="track": return await B.ptrack(u,c)
        if a=="history": return await fixed_history(u,c)
        if a=="gov": return await B.gov(u,c)
        if a=="balance":
            p=B.db.conn.execute("SELECT balance FROM partners WHERE id=?",(st["partner_id"],)).fetchone()
            amount=f"{p['balance']:,}" if p else "0"
            return await u.message.reply_text({"fa":f"💰 موجودی کیف پول شما: {amount} تومان","en":f"💰 Your balance: {amount} toman","ar":f"💰 رصيدك: {amount} تومان"}[lang],reply_markup=partner_kb(lang))

    if t in (B.CANCEL,"❌ Cancel","❌ إلغاء","❌ لغو","لغو","انصراف","❌ انصراف"):
        st.pop("extra_step",None); st.pop("mode",None)
        return await u.message.reply_text("❌ عملیات لغو شد.", reply_markup=partner_kb(lang) if st.get("partner_id") else main(uid))
    if t == "⬅️ بازگشت":
        st.pop("extra_step",None); st.pop("mode",None); return await u.message.reply_text("🛠 پنل مدیریت", reply_markup=B.amenu()) if B.admin(uid) else await u.message.reply_text("منوی اصلی",reply_markup=main(uid))

    if st.get("mode") == "print_color":
        if t in ("⚫ سیاه و سفید","⚫ Black & White","⚫ أبيض وأسود"): st["color"]="bw"
        elif t in ("🌈 رنگی","🌈 Color","🌈 ملون"): st["color"]="color"
        else: return None
        st["mode"]="print_side"
        return await u.message.reply_text(B.L(uid,"📄 یک‌رو یا 🔄 پشت‌ورو؟","📄 Single-sided or 🔄 double-sided?","📄 وجه واحد أم 🔄 وجهان؟"),reply_markup=B.kb([[B.L(uid,"📄 یک‌رو","📄 Single-sided","📄 وجه واحد"),B.L(uid,"🔄 پشت‌ورو","🔄 Double-sided","🔄 وجهان")],[B.L(uid,B.CANCEL,"❌ Cancel","❌ إلغاء")]]))
    if st.get("mode") == "print_side":
        if t in ("📄 یک‌رو","📄 Single-sided","📄 وجه واحد"): st["side"]=1
        elif t in ("🔄 پشت‌ورو","🔄 Double-sided","🔄 وجهان"): st["side"]=2
        else: return None
        st["mode"]="print_copies"
        return await u.message.reply_text(B.L(uid,"🔢 تعداد نسخه موردنیاز از هر صفحه را وارد کنید.","🔢 Enter the number of copies per page.","🔢 أدخل عدد النسخ لكل صفحة."),reply_markup=B.cancel_kb(lang))
    if st.get("mode") == "print_copies":
        if not t.isdigit() or int(t)<1: return await u.message.reply_text(B.L(uid,"❌ تعداد را به صورت عدد مثبت وارد کنید.","❌ Enter a positive number.","❌ أدخل رقماً موجباً."),reply_markup=B.cancel_kb(lang))
        st["copies"]=int(t);st["mode"]="print"
        return await u.message.reply_text(B.L(uid,"📎 فایل‌ها را یکی‌یکی ارسال کنید؛ پایان با «تأیید».","📎 Send files/images one by one; choose Confirm when finished.","📎 أرسل الملفات أو الصور واحداً تلو الآخر، ثم اختر تأكيد عند الانتهاء."),reply_markup=B.kb([[B.L(uid,B.OK,"✅ Confirm","✅ تأكيد"),B.L(uid,B.CANCEL,"❌ Cancel","❌ إلغاء")]]))
    if st.get("mode") == "print" and t in ("✅ تأیید","✅ Confirm","✅ تأكيد"):
        old=t
        try: u.message.text=B.OK; return await _original_service_text(u,c)
        finally: u.message.text=old

    if not B.admin(uid): return None
    step=st.get("extra_step")
    if t=="➕ افزودن همکار":
        st["extra_step"]="partner"; return await u.message.reply_text("📱 شماره، 🔐 رمز و 👤 نام همکار را در سه بخش وارد کنید.\nمثال: شماره رمز نام",reply_markup=B.amenu())
    if step=="partner":
        a=t.split(maxsplit=2)
        if len(a)<3:return await u.message.reply_text("❌ قالب: شماره رمز نام",reply_markup=B.amenu())
        try:B.db.add_partner(a[0],a[1],a[2]);st["extra_step"]=None;return await u.message.reply_text("✅ همکار با موفقیت اضافه شد.",reply_markup=B.amenu())
        except Exception:return await u.message.reply_text("❌ ثبت همکار انجام نشد؛ احتمالاً شماره تکراری است.",reply_markup=B.amenu())
    if t=="🤖 افزودن بات":
        st["extra_step"]="bot_platform";return await u.message.reply_text("🤖 پیام‌رسان را انتخاب کنید:",reply_markup=platform_kb())
    if step=="bot_platform":
        aliases={"🤖 telegram":"telegram","🤖 rubika":"rubika","🤖 bale":"bale","🤖 eitaa":"eitaa","telegram":"telegram","rubika":"rubika","bale":"bale","eitaa":"eitaa","تلگرام":"telegram","روبیکا":"rubika","بله":"bale","ایتا":"eitaa"}
        p=aliases.get(t.lower().strip())
        if not p:return await u.message.reply_text("❌ یکی از Telegram / Rubika / Bale / Eitaa را انتخاب کنید.",reply_markup=platform_kb())
        st["bot_platform"]=p;st["extra_step"]="bot_token";return await u.message.reply_text("🔑 API Token بات را ارسال کنید.",reply_markup=B.amenu())
    if step=="bot_token":
        if not t:return await u.message.reply_text("❌ API Token خالی است.",reply_markup=B.amenu())
        st["bot_token"]=t;st["extra_step"]="bot_name";return await u.message.reply_text("🤖 نام بات را ارسال کنید.",reply_markup=B.amenu())
    if step=="bot_name":
        if not t:return await u.message.reply_text("❌ نام بات خالی است.",reply_markup=B.amenu())
        B.db.add_bot(st["bot_platform"],t,st["bot_token"]);st["extra_step"]=None;st.pop("bot_token",None);return await u.message.reply_text("✅ بات ثبت شد.",reply_markup=B.amenu())
    if t=="🤖 بات‌های متصل":
        rs=B.db.bots();txt="\n".join(f"#{r['id']} | {r['platform']} | {r['bot_name']} | {'فعال' if r['active'] else 'غیرفعال'}" for r in rs) or "هیچ باتی ثبت نشده است.";return await u.message.reply_text(txt,reply_markup=B.amenu())
    if t=="📣 اعلان خدمت":
        st["extra_step"]="done";return await u.message.reply_text("🎫 کد پیگیری خدمت انجام‌شده را ارسال کنید.",reply_markup=B.amenu())
    if step=="done":
        r=B.db.conn.execute("SELECT * FROM requests WHERE tracking_code=?",(t,)).fetchone()
        if not r:return await u.message.reply_text("❌ کد پیگیری پیدا نشد.",reply_markup=B.amenu())
        B.db.conn.execute("UPDATE requests SET status='completed',updated_at=? WHERE id=?",(B.now(),r["id"]));B.db.conn.commit();st["extra_step"]=None;return await u.message.reply_text(f"✅ خدمت {t} انجام‌شده ثبت شد و اعلان مربوطه ارسال شد.",reply_markup=B.amenu())
    return None


async def fixed_history(u,c):
    uid=u.effective_user.id;st=B.S.get(uid,{})
    if not st.get("partner_id"):
        return await u.message.reply_text(B.L(uid,"ابتدا وارد پنل همکاران شوید.","Please log in first.","يرجى تسجيل الدخول أولاً."),reply_markup=main(uid))
    rows=B.db.conn.execute("SELECT tracking_code,service_key,status,amount FROM requests WHERE user_id=? ORDER BY id DESC LIMIT 20",(st["partner_id"],)).fetchall()
    text="\n".join(f"{r['tracking_code']} | {r['service_key']} | {r['status']} | {int(r['amount']):,}" for r in rows) or "سابقه‌ای نیست."
    return await u.message.reply_text(text,reply_markup=partner_kb(st.get("lang","fa")))


async def split_router(u,c):
    t=(u.message.text or "").strip();uid=u.effective_user.id;st=B.S.get(uid,{})
    lang=st.get("lang","fa")
    screening={"fa":"📝 آزمون غربالگری","en":"📝 Screening test","ar":"📝 اختبار الفحص"}[lang]
    follow={"fa":"🎫 پیگیری","en":"🎫 Follow-up","ar":"🎫 متابعة"}[lang]
    track={"fa":"🎫 کد رهگیری تمدید کارت‌ها","en":"🎫 Track request","ar":"🎫 متابعة الطلب"}[lang]
    result=await extra_text(u,c)
    if result is not None:return result
    if t==screening:
        return await u.message.reply_text(B.L(uid,"⏳ آزمون غربالگری فعلاً غیرفعال است.","⏳ Screening test is currently unavailable.","⏳ اختبار الفحص غير متاح حالياً."),reply_markup=main(uid))
    if t==follow:
        old=u.message.text
        try:u.message.text=track;return await _original_router(u,c)
        finally:u.message.text=old
    return await _original_router(u,c)

B.router=split_router


def build():
    return B.build()

if __name__=="__main__":
    build().run_polling(allowed_updates=None)
