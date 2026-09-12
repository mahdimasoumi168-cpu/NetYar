"""Rubika Iranian subscriber menu and complaint forwarding."""
import os
import logging
log=logging.getLogger("netyar.rubika.iranian")
CONTACT_USERNAME=os.getenv("CONTACT_USERNAME","").strip().lstrip("@")


def install(rb):
    if getattr(rb,"_iranian_complaints_installed",False): return
    old_handle=rb.handle
    old_main=getattr(rb,"main_rows",None)

    def iranian_rows(uid):
        lang=rb.STATE.get(str(uid),{}).get("lang","fa")
        if lang=="en":
            return [[("1","🏛 Government access issue")],[ ("2","🎫 Tracking"),("3","💰 My wallet")],[ ("4","📞 Contact us"),("5","📝 Complaint")],[ ("6","👥 Partner panel")],[ ("0",rb.CANCEL)]]
        if lang=="ar":
            return [[("1","🏛 مشكلة دخول الحكومة")],[ ("2","🎫 متابعة"),("3","💰 محفظتي")],[ ("4","📞 اتصل بنا"),("5","📝 شكوى")],[ ("6","👥 لوحة الشركاء")],[ ("0","❌ إلغاء")]]
        return [[("1","🏛 حل مشکل ورود اتباع دولت من")],[ ("2","🎫 پیگیری"),("3","💰 کیف پول من")],[ ("4","📞 تماس با ما"),("5","📝 ثبت شکایت")],[ ("6","🔵 👥 پنل همکاران")],[ ("0",rb.CANCEL)]]

    def main_rows(uid):
        st=rb.STATE.get(str(uid),{})
        return iranian_rows(uid) if st.get("status")=="iranian" or st.get("step")=="iranian_menu" else (old_main(uid) if old_main else [])
    rb.main_rows=main_rows

    def handle(uid,chat,x,u):
        uid=str(uid);x=str(x or "").strip();st=rb.STATE.setdefault(uid,{})
        step=st.get("step","")
        if step=="citizenship" and x in {"2","🇮🇷 ایرانی هستم","🇮🇷 Iranian","🇮🇷 إيراني"}:
            st.update({"status":"iranian","step":"iranian_menu"})
            return rb.send(chat,"🇮🇷 منوی مشترکین ایرانی\n\nخدمات عادی برای مشترکین ایرانی غیرفعال است.",iranian_rows(uid))
        if st.get("status")=="iranian" and step in {"iranian_menu","menu"}:
            if x in {"1","🏛 حل مشکل ورود اتباع دولت من"}:
                st["step"]="menu"
                return old_handle(uid,chat,"🏛 حل مشکل ورود اتباع دولت من",u)
            if x in {"2","🎫 پیگیری","🎫 Tracking","🎫 متابعة"}:
                st["step"]="track";return rb.send(chat,rb.T(uid,"track"),[[('0',rb.CANCEL)]])
            if x in {"3","💰 کیف پول من","💰 My wallet","💰 محفظتي"}:
                st["step"]="menu";return old_handle(uid,chat,"💰 کیف پول من",u)
            if x in {"4","📞 تماس با ما","📞 Contact us","📞 اتصل بنا"}:
                text="📞 تماس با ما\n"
                if CONTACT_USERNAME:text+=f"\nآیدی پشتیبانی: @{CONTACT_USERNAME}"
                else:text+="\nآیدی پشتیبانی در تنظیمات ربات ثبت نشده است."
                return rb.send(chat,text,[[('0','⬅️ بازگشت')]])
            if x in {"5","📝 ثبت شکایت","📝 Complaint","📝 شكوى"}:
                st["step"]="iranian_complaint"
                return rb.send(chat,"📝 متن شکایت یا انتقاد خود را ارسال کنید:",[[('0',rb.CANCEL)]])
            if x in {"6","🔵 👥 پنل همکاران","👥 پنل همکاران","👥 Partner panel"}:
                st["step"]="menu";return old_handle(uid,chat,"👥 پنل همکاران",u)
            if x in {"0",rb.CANCEL,"❌ انصراف"}:
                st["step"]="iranian_menu";return rb.send(chat,"🇮🇷 منوی مشترکین ایرانی:",iranian_rows(uid))
        if st.get("status")=="iranian" and step=="iranian_complaint":
            if x in {"0",rb.CANCEL,"❌ انصراف"}:
                st["step"]="iranian_menu";return rb.send(chat,"عملیات لغو شد.",iranian_rows(uid))
            try:
                import bot as telegram_bot
                admins=list(getattr(telegram_bot,"ADM",[]) or [])
                app=getattr(__import__("server"),"telegram_app",None)
                sender=(u.get("message") or u.get("new_message") or u or {}).get("sender") or {}
                name=sender.get("name") or sender.get("first_name") or "-"
                msg=(f"📝 شکایت/انتقاد جدید از روبیکا\n\n👤 نام: {name}\n🔹 شناسه روبیکا: {uid}\n\n💬 متن شکایت:\n{x}")
                if app:
                    import asyncio
                    for aid in admins:
                        try: asyncio.create_task(app.bot.send_message(chat_id=int(aid),text=msg))
                        except Exception: log.exception("Rubika complaint notification failed")
            except Exception: log.exception("Rubika complaint forwarding failed")
            st["step"]="iranian_menu"
            return rb.send(chat,"✅ شکایت شما برای مدیریت ارسال شد.",iranian_rows(uid))
        if st.get("status")=="iranian" and x=="⬅️ بازگشت":
            st["step"]="iranian_menu";return rb.send(chat,"🇮🇷 منوی مشترکین ایرانی:",iranian_rows(uid))
        return old_handle(uid,chat,x,u)

    rb.handle=handle;rb.iranian_rows=iranian_rows;rb._iranian_complaints_installed=True
