"""Final cross-platform stability layer for Telegram and Rubika."""
from __future__ import annotations
import logging
log = logging.getLogger("netyar.cross_platform_stability_final")

def install():
    try:
        import bot as B
        def modern_amenu(*_args, **_kwargs):
            return B.kb([["👥 کاربران", "🤝 همکاران"],["📋 درخواست‌ها", "🎫 تیکت‌ها"],["🟢/🔴 خدمات ایرانی", "🟢/🔴 خدمات اتباع"],["💰 قیمت خدمات", "📝 تغییر متن‌ها"],["📎 مدارک و فایل‌ها", "👤 مدیران"],["🤖 پیام‌رسان‌ها", "📊 گزارش‌ها"],["⚙️ تنظیمات پایه", "📞 پشتیبانی"],["💬 ارتباط با همکار"],["⬅️ منوی اصلی"]])
        B.amenu = modern_amenu
        old_exit=getattr(B,"partner_exit_choice",None)
        if old_exit:
            async def stable_exit(update,context):
                uid=update.effective_user.id; st=B.S.setdefault(uid,{}); text=(getattr(update.message,"text","") or "").strip()
                if st.get("mode")!="partner_exit_choice": return await old_exit(update,context)
                if text in {"🔒 خروج دائمی","🔒 Permanent exit","🔒 خروج دائم"}:
                    status=st.get("status","foreign"); lang=st.get("lang","fa"); B.S[uid]={"status":status,"lang":lang}
                    if status=="iranian": kb=B.kb([["🎫 پیگیری","👥 پنل همکاران"],[B.CANCEL]]); msg={"fa":"🔒 خروج دائمی انجام شد.\n🇮🇷 به منوی ایرانی برگشتید.","en":"🔒 Permanent exit completed.\n🇮🇷 Back to the Iranian menu.","ar":"🔒 تم تسجيل الخروج الدائم.\n🇮🇷 عدت إلى قائمة الإيرانيين."}.get(lang)
                    else: kb=B.main(uid); msg={"fa":"🔒 خروج دائمی انجام شد.\n🪪 به منوی اتباع برگشتید.","en":"🔒 Permanent exit completed.\n🪪 Back to the foreign-resident menu.","ar":"🔒 تم تسجيل الخروج الدائم.\n🪪 عدت إلى قائمة المقيمين الأجانب."}.get(lang)
                    return await update.message.reply_text(msg,reply_markup=kb)
                return await old_exit(update,context)
            B.partner_exit_choice=stable_exit
        B._cross_platform_stability_final_telegram=True
    except Exception: log.exception("Telegram stability install failed")
    try:
        import rubika_v2 as R
        if getattr(R,"_cross_platform_stability_final_rubika",False): return
        old_handle=R.handle
        def admin_rows(): return [[("1","👥 مدیریت همکاران"),("2","💰 مدیریت شارژها")],[("3","📋 مدیریت درخواست‌ها"),("4","💳 مدیریت پرداخت‌ها")],[("5","🛠 مدیریت خدمات"),("6","📝 مدیریت متن‌ها")],[("7","💵 مدیریت قیمت‌ها"),("8","🤖 مدیریت بات‌ها")],[("9","📊 گزارش‌ها"),("10","👤 مدیریت مدیران")],[("11","🎫 مدیریت تیکت‌ها"),("12","⚙️ تنظیمات")],[("99","🔄 شروع مجدد"),("0","❌ انصراف")]]
        R.admin_rows=admin_rows
        def handle(uid,chat,x,update):
            uid=str(uid); st=R.STATE.setdefault(uid,{}); step=st.get("step"); x=str(x or "").strip()
            if step in {"partner_ticket_chat","admin_ticket_chat","admin_ticket_reply","ticket_admin_reply"}:
                if x in {"0","❌ انصراف","99","🔄 شروع مجدد","cancel","Cancel","إلغاء"}:
                    st["step"]="admin" if R.is_admin(uid) else "partner"; R.send(chat,"✅ گفت‌وگو بسته شد.",R.admin_rows() if R.is_admin(uid) else R.partner_rows()); return
                # Media updates have no text. Let the dedicated final Rubika
                # ticket router forward the actual media exactly once instead
                # of converting it into an empty/garbled text reply.
                if not x:
                    return old_handle(uid,chat,x,update)
            return old_handle(uid,chat,x,update)
        R.handle=handle; R._cross_platform_stability_final_rubika=True
    except Exception: log.exception("Rubika stability install failed")
